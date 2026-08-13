"""
YOLODetector — Ultralytics YOLO11 concrete implementation of BaseDetector.

This is the ONLY file in the codebase that may import from 'ultralytics'.
DetectionEngine never imports ultralytics directly.
"""
import time
import threading
import numpy as np
from typing import Any, Dict, Optional

from detection.models.base_detector import BaseDetector
from detection.utils.logger import detection_logger


class YOLODetector(BaseDetector):
    """
    Ultralytics YOLO11 detector. Implements the BaseDetector interface.
    Supports YOLO11n / YOLO11s / YOLO11m / YOLO11l / YOLO11x and custom .pt weights.
    """

    def __init__(self, model_path: str, target_device: str = "cpu"):
        self._model = None
        self._model_path = model_path
        self._device = target_device
        self._is_loaded = False
        self._model_name = model_path.split("/")[-1].split("\\")[-1]
        self._load_time_seconds = 0.0
        self._lock = threading.Lock()

    # ─── BaseDetector Properties ─────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_name(self) -> str:
        return self._model_name

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def load(self, model_path: str, device: str) -> bool:
        """Load YOLO weights with GPU fallback to CPU."""
        with self._lock:
            start_time = time.time()
            try:
                try:
                    from ultralytics import YOLO
                    self._model = YOLO(model_path)
                    if device != "cpu":
                        try:
                            self._model.to(device)
                            self._device = device
                        except Exception as dev_err:
                            detection_logger.warning(
                                f"[YOLODetector] GPU device '{device}' unavailable, falling back to CPU: {dev_err}",
                                extra={"model_name": self._model_name},
                            )
                            self._model.to("cpu")
                            self._device = "cpu"
                    else:
                        self._device = "cpu"
                except ImportError:
                    detection_logger.warning(
                        "[YOLODetector] Ultralytics not installed — loading MockYOLOModel stub.",
                        extra={"model_name": self._model_name},
                    )
                    self._model = _MockYOLOModel()
                    self._device = device

                self._model_path = model_path
                self._model_name = model_path.split("/")[-1].split("\\")[-1]
                self._load_time_seconds = round(time.time() - start_time, 3)
                self._is_loaded = True

                detection_logger.info(
                    f"[YOLODetector] Model '{self._model_name}' loaded in {self._load_time_seconds}s on '{self._device}'.",
                    extra={"model_name": self._model_name},
                )
                return True

            except Exception as e:
                detection_logger.error(
                    f"[YOLODetector] Failed to load model '{model_path}': {e}",
                    extra={"model_name": self._model_name},
                )
                self._model = None
                self._is_loaded = False
                return False

    def unload(self) -> None:
        """Release model weights and free GPU VRAM."""
        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        detection_logger.info(
                            "[YOLODetector] GPU VRAM cache cleared.",
                            extra={"model_name": self._model_name},
                        )
                except ImportError:
                    pass
            self._is_loaded = False
            detection_logger.info(
                f"[YOLODetector] Model '{self._model_name}' unloaded.",
                extra={"model_name": self._model_name},
            )

    def predict(self, frame: np.ndarray, conf: float, iou: float) -> Any:
        """Run YOLO inference on a preprocessed frame."""
        if not self._is_loaded or self._model is None:
            return []
        if hasattr(self._model, "predict"):
            return self._model.predict(frame, verbose=False, conf=conf, iou=iou)
        elif hasattr(self._model, "__call__"):
            return self._model(frame)
        return []

    def warmup(self, img_size: int = 640, iterations: int = 3) -> bool:
        """Prime GPU CUDA kernel caches with dummy inference passes."""
        if not self._is_loaded or self._model is None:
            return False
        dummy = np.zeros((img_size, img_size, 3), dtype=np.uint8)
        try:
            for _ in range(iterations):
                self.predict(dummy, conf=0.25, iou=0.45)
            detection_logger.info(
                f"[YOLODetector] Warmup complete ({iterations} iterations).",
                extra={"model_name": self._model_name},
            )
            return True
        except Exception as e:
            detection_logger.warning(
                f"[YOLODetector] Warmup warning: {e}",
                extra={"model_name": self._model_name},
            )
            return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self._model_name,
            "model_path": self._model_path,
            "detector_type": "YOLODetector",
            "device": self._device,
            "is_loaded": self._is_loaded,
            "load_time_seconds": self._load_time_seconds,
        }


# ─── Internal Mock (test / no-weights environments) ─────────────────────────

class _MockYOLOModel:
    """Fallback stub returned when Ultralytics is unavailable or weights missing."""

    def predict(self, source, verbose=False, conf=0.25, iou=0.45):
        return [_MockYOLOResults()]

    def __call__(self, source):
        return self.predict(source)

    def to(self, device):
        return self


class _MockYOLOResults:
    def __init__(self):
        self.boxes = _MockYOLOBoxes()


class _MockYOLOBoxes:
    def __init__(self):
        self.cls = np.array([0.0])
        self.conf = np.array([0.88])
        self.xyxy = np.array([[100.0, 150.0, 300.0, 500.0]])
