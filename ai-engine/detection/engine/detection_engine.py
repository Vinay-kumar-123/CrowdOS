"""
DetectionEngine — Core inference orchestrator for CrowdOS Sprint 3.

Depends ONLY on BaseDetector (abstract interface).
No direct YOLO / Ultralytics imports here.
Supports:
  - Input frame validation (Task 4)
  - Thread-safe cumulative metrics via threading.Lock (Task 7)
  - BaseDetector dependency injection (Task 6)
  - ResultValidator post-inference sanitization (Task 8)
  - Enterprise observability metadata in FrameDetectionResult (Task 9)
"""
import time
import threading
import numpy as np
from typing import Dict, Any, Optional, Type

from detection.models.base_detector import BaseDetector
from detection.models.yolo_detector import YOLODetector
from detection.models.model_manager import ModelManager
from detection.processors.preprocessor import Preprocessor
from detection.processors.postprocessor import Postprocessor
from detection.processors.result_validator import ResultValidator
from detection.results.schema import FrameDetectionResult, INFERENCE_ENGINE_VERSION
from detection.config.settings import detection_settings
from detection.utils.logger import detection_logger

PIPELINE_VERSION = "3.1.0"


class FrameValidationError(Exception):
    """Raised when an input frame fails pre-inference validation checks."""
    pass


class DetectionEngine:
    """
    Central DetectionEngine — orchestrates frame validation, inference dispatch,
    postprocessing, validation, and metric collection.

    Depends on BaseDetector interface — YOLO, RT-DETR, PeopleNet are all pluggable.
    Thread-safe for concurrent multi-camera inference scenarios.
    """

    def __init__(
        self,
        detector: Optional[BaseDetector] = None,
        model_manager: Optional[ModelManager] = None,
    ):
        # Dependency injection: accept any BaseDetector implementation
        # Fall back to YOLODetector if not supplied
        if detector is not None:
            self._detector: BaseDetector = detector
            self._use_detector_api = True
        else:
            # Legacy path: use ModelManager (retains backward compatibility)
            self.model_manager = model_manager or ModelManager()
            self._use_detector_api = False

        self.preprocessor = Preprocessor()
        self.postprocessor = Postprocessor()
        self.validator = ResultValidator()

        # Thread-safe cumulative metrics (Task 7)
        self._metrics_lock = threading.Lock()
        self._total_frames_processed: int = 0
        self._total_inference_time_ms: float = 0.0
        self._last_inference_time_ms: float = 0.0

    # ─── Backward-compatible public properties ────────────────────────────────

    @property
    def total_frames_processed(self) -> int:
        with self._metrics_lock:
            return self._total_frames_processed

    @property
    def total_inference_time_ms(self) -> float:
        with self._metrics_lock:
            return self._total_inference_time_ms

    @property
    def last_inference_time_ms(self) -> float:
        with self._metrics_lock:
            return self._last_inference_time_ms

    # ─── Initialization ───────────────────────────────────────────────────────

    def initialize(self, model_path: str = None) -> bool:
        """Load model onto target device. Works for both detector API and ModelManager paths."""
        if self._use_detector_api:
            if not self._detector.is_loaded:
                path = model_path or detection_settings.MODEL_PATH
                device = detection_settings.DEVICE
                ok = self._detector.load(path, device)
                if ok:
                    self._detector.warmup(
                        img_size=detection_settings.IMG_SIZE,
                        iterations=detection_settings.WARMUP_ITERATIONS,
                    )
                return ok
            return True
        else:
            if not self.model_manager.is_loaded:
                return self.model_manager.load_model(model_path)
            return True

    # ─── Frame Validation (Task 4) ────────────────────────────────────────────

    @staticmethod
    def validate_frame(frame: np.ndarray) -> None:
        """
        Validate input frame before inference.
        Raises FrameValidationError with a descriptive message on any failure.
        Never crashes silently.
        """
        if frame is None:
            raise FrameValidationError("Frame is None — cannot run inference on null input.")

        if not isinstance(frame, np.ndarray):
            raise FrameValidationError(
                f"Frame must be a numpy.ndarray, got {type(frame).__name__}."
            )

        if frame.size == 0:
            raise FrameValidationError("Frame has zero elements (empty array).")

        if frame.ndim != 3:
            raise FrameValidationError(
                f"Frame must be 3-dimensional (H, W, C), got {frame.ndim}D array."
            )

        h, w, c = frame.shape
        if h == 0 or w == 0:
            raise FrameValidationError(f"Frame has zero spatial dimension: {w}x{h}.")

        if c != 3:
            raise FrameValidationError(
                f"Frame must have 3 channels (BGR/RGB), got {c} channel(s)."
            )

        if frame.dtype not in (np.uint8, np.float32, np.float64):
            raise FrameValidationError(
                f"Unsupported frame dtype '{frame.dtype}'. Expected uint8, float32, or float64."
            )

    # ─── Main Inference Method ────────────────────────────────────────────────

    def detect_persons(
        self,
        frame: np.ndarray,
        camera_id: str = "default_cam",
        frame_number: int = 0,
    ) -> FrameDetectionResult:
        """
        Validate frame, run inference via BaseDetector, postprocess, validate detections.
        Returns a fully-populated FrameDetectionResult.
        Never raises — returns empty result on validation or inference failure.
        """
        # ── 1. Input Validation ──────────────────────────────────────────────
        try:
            self.validate_frame(frame)
        except FrameValidationError as e:
            detection_logger.error(
                f"[DetectionEngine] Frame validation failed for camera '{camera_id}': {e}",
                extra={"camera_id": camera_id},
            )
            return self._empty_result(camera_id, frame_number, error=str(e))

        orig_h, orig_w = frame.shape[:2]

        # ── 2. Ensure model is loaded ────────────────────────────────────────
        if not self._is_model_loaded():
            self.initialize()

        start_time = time.time()

        detection_logger.info(
            f"[DetectionEngine] Inference started on camera '{camera_id}' frame {frame_number}",
            extra={"camera_id": camera_id},
        )

        # ── 3. Preprocess ────────────────────────────────────────────────────
        prep_data = self.preprocessor.preprocess(frame)

        # ── 4. Inference via BaseDetector or ModelManager ────────────────────
        try:
            raw_results = self._run_inference(prep_data["processed_image"])
        except Exception as e:
            detection_logger.error(
                f"[DetectionEngine] Inference error on camera '{camera_id}': {e}",
                extra={"camera_id": camera_id},
            )
            raw_results = []

        # ── 5. Postprocess — filter person class only ────────────────────────
        detections = self.postprocessor.process_results(
            raw_results=raw_results,
            original_shape=(orig_w, orig_h),
        )

        # ── 6. Validate detection geometry (Task 8) ──────────────────────────
        detections = self.validator.validate(
            detections=detections,
            frame_resolution=(orig_w, orig_h),
        )

        inference_time_ms = (time.time() - start_time) * 1000.0

        # ── 7. Thread-safe metrics update (Task 7) ───────────────────────────
        with self._metrics_lock:
            self._last_inference_time_ms = inference_time_ms
            self._total_inference_time_ms += inference_time_ms
            self._total_frames_processed += 1

        detection_logger.info(
            f"[DetectionEngine] {len(detections)} persons detected on '{camera_id}' "
            f"in {inference_time_ms:.2f}ms",
            extra={
                "camera_id": camera_id,
                "inference_time_ms": round(inference_time_ms, 2),
                "detections_count": len(detections),
            },
        )

        return FrameDetectionResult(
            frame_number=frame_number,
            camera_id=camera_id,
            inference_time_ms=inference_time_ms,
            total_persons_detected=len(detections),
            detections=detections,
            device_used=self._active_device(),
            resolution=(orig_w, orig_h),
            model_name=self._active_model_name(),
            pipeline_version=PIPELINE_VERSION,
            inference_engine_version=INFERENCE_ENGINE_VERSION,
        )

    # ─── Metrics ──────────────────────────────────────────────────────────────

    def get_engine_metrics(self) -> Dict[str, Any]:
        with self._metrics_lock:
            frames = self._total_frames_processed
            total_ms = self._total_inference_time_ms
            last_ms = self._last_inference_time_ms

        avg_infer = round(total_ms / frames, 2) if frames > 0 else 0.0
        avg_fps = round(1000.0 / avg_infer, 2) if avg_infer > 0 else 0.0

        return {
            "total_frames_processed": frames,
            "last_inference_time_ms": round(last_ms, 2),
            "average_inference_time_ms": avg_infer,
            "average_fps": avg_fps,
            "device": self._active_device(),
            "model_name": self._active_model_name(),
            "pipeline_version": PIPELINE_VERSION,
            "inference_engine_version": INFERENCE_ENGINE_VERSION,
        }

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _is_model_loaded(self) -> bool:
        if self._use_detector_api:
            return self._detector.is_loaded
        return self.model_manager.is_loaded

    def _run_inference(self, processed_image: np.ndarray):
        """Dispatch inference to BaseDetector or legacy ModelManager path."""
        if self._use_detector_api:
            return self._detector.predict(
                processed_image,
                conf=detection_settings.CONFIDENCE_THRESHOLD,
                iou=detection_settings.IOU_THRESHOLD,
            )
        # Legacy ModelManager path (backward compatible)
        model = self.model_manager.model
        if hasattr(model, "predict"):
            return model.predict(
                processed_image,
                verbose=False,
                conf=detection_settings.CONFIDENCE_THRESHOLD,
                iou=detection_settings.IOU_THRESHOLD,
            )
        elif hasattr(model, "__call__"):
            return model(processed_image)
        return []

    def _active_device(self) -> str:
        if self._use_detector_api:
            return self._detector.device
        return self.model_manager.device

    def _active_model_name(self) -> str:
        if self._use_detector_api:
            return self._detector.model_name
        return self.model_manager.model_name

    def _empty_result(
        self, camera_id: str, frame_number: int, error: str = ""
    ) -> FrameDetectionResult:
        """Returns a safe empty FrameDetectionResult for failed frames."""
        return FrameDetectionResult(
            frame_number=frame_number,
            camera_id=camera_id,
            inference_time_ms=0.0,
            total_persons_detected=0,
            detections=[],
            device_used=self._active_device() if self._is_model_loaded() else "unknown",
            resolution=(0, 0),
            model_name=self._active_model_name() if self._is_model_loaded() else "unknown",
            pipeline_version=PIPELINE_VERSION,
            inference_engine_version=INFERENCE_ENGINE_VERSION,
        )
