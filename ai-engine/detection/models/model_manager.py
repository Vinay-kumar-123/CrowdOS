import os
import time
import threading
import numpy as np
from typing import Optional, Dict, Any
from detection.config.settings import detection_settings
from detection.utils.device import detect_device, get_device_info
from detection.utils.logger import detection_logger


class ModelManager:
    """
    Singleton ModelManager providing lifecycle controls for Ultralytics YOLO11 models.
    Handles GPU/CPU device resolution, lazy loading, warmup, reloading, and thread-safe caching.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model = None
        self.model_path = detection_settings.MODEL_PATH
        self.model_name = detection_settings.MODEL_NAME
        self.device = detect_device()
        self.is_loaded = False
        self.load_time_seconds = 0.0
        self.version = "YOLO11-v1.0"
        self._model_lock = threading.Lock()
        self._initialized = True

    def load_model(self, model_path: Optional[str] = None, device: Optional[str] = None) -> bool:
        """
        Load YOLO model onto target hardware device. Fallback gracefully to CPU on GPU error.
        """
        with self._model_lock:
            if self.is_loaded and not model_path:
                return True

            path = model_path or self.model_path
            target_device = device or self.device

            detection_logger.info(
                f"Loading YOLO model '{path}' onto device '{target_device}'...",
                extra={"model_name": self.model_name}
            )

            start_time = time.time()
            try:
                # Attempt importing Ultralytics
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(path)
                    if target_device != "cpu":
                        try:
                            self.model.to(target_device)
                        except Exception as dev_err:
                            detection_logger.warning(
                                f"Failed loading onto {target_device}, falling back to CPU: {dev_err}",
                                extra={"model_name": self.model_name}
                            )
                            target_device = "cpu"
                            self.model.to("cpu")

                except ImportError:
                    detection_logger.warning(
                        "Ultralytics library not found. Instantiating Fallback Model Stub.",
                        extra={"model_name": self.model_name}
                    )
                    self.model = MockYOLOModel()

                self.device = target_device
                self.model_path = path
                self.load_time_seconds = round(time.time() - start_time, 3)
                self.is_loaded = True

                detection_logger.info(
                    f"Model loaded successfully in {self.load_time_seconds}s on '{self.device}'.",
                    extra={"model_name": self.model_name}
                )

                self.warmup_model()
                return True

            except Exception as e:
                detection_logger.error(
                    f"Failed to load model '{path}': {e}",
                    extra={"model_name": self.model_name}
                )
                self.is_loaded = False
                self.model = None
                return False

    def warmup_model(self, iterations: int = None) -> bool:
        """
        Runs dummy inference passes to warmup GPU CUDA context and memory caches.
        """
        if not self.is_loaded or self.model is None:
            return False

        num_iters = iterations or detection_settings.WARMUP_ITERATIONS
        detection_logger.info(f"Warming up model ({num_iters} iterations)...", extra={"model_name": self.model_name})

        dummy_frame = np.zeros((detection_settings.IMG_SIZE, detection_settings.IMG_SIZE, 3), dtype=np.uint8)
        try:
            for _ in range(num_iters):
                if hasattr(self.model, "predict"):
                    self.model.predict(dummy_frame, verbose=False)
                elif hasattr(self.model, "__call__"):
                    self.model(dummy_frame)
            detection_logger.info("Model warmup complete.", extra={"model_name": self.model_name})
            return True
        except Exception as e:
            detection_logger.warning(f"Model warmup encountered warning: {e}", extra={"model_name": self.model_name})
            return False

    def _unload_unsafe(self) -> None:
        """
        Internal unload — MUST be called while already holding self._model_lock.
        Releases model memory and clears GPU VRAM cache.
        """
        if self.model is not None:
            del self.model
            self.model = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    detection_logger.info(
                        "GPU VRAM cache cleared after model unload.",
                        extra={"model_name": self.model_name}
                    )
            except ImportError:
                pass
        self.is_loaded = False

    def unload_model(self) -> None:
        """
        Thread-safe model unload. Releases weights and frees GPU VRAM.
        """
        with self._model_lock:
            self._unload_unsafe()
        detection_logger.info("Model unloaded successfully.", extra={"model_name": self.model_name})

    def reload_model(self, model_path: Optional[str] = None) -> bool:
        """
        Hot-reload the model without process restart.
        Uses a single lock acquisition to unload, then calls load_model()
        separately — avoiding the re-entrant deadlock of the previous design.
        """
        detection_logger.info(
            f"Reloading model (path={model_path or self.model_path})...",
            extra={"model_name": self.model_name}
        )
        # Unload under lock, then release before load acquires it again
        with self._model_lock:
            self._unload_unsafe()
        # load_model acquires _model_lock independently — no deadlock
        return self.load_model(model_path)

    def health_check(self) -> bool:
        return self.is_loaded and self.model is not None

    def get_model_info(self) -> Dict[str, Any]:
        device_info = get_device_info()
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "version": self.version,
            "is_loaded": self.is_loaded,
            "device": self.device,
            "load_time_seconds": self.load_time_seconds,
            "hardware": device_info,
        }


class MockYOLOModel:
    """
    Fallback Mock Model used when Ultralytics or GPU weights are unavailable in testing environments.
    """
    def predict(self, source, verbose=False, conf=0.25, iou=0.45):
        return [MockYOLOResults()]

    def __call__(self, source):
        return self.predict(source)


class MockYOLOResults:
    def __init__(self):
        # Mock 1 synthetic person detection
        self.boxes = MockYOLOBoxes()


class MockYOLOBoxes:
    def __init__(self):
        self.cls = np.array([0.0])  # Class 0 = Person
        self.conf = np.array([0.88])
        self.xyxy = np.array([[100.0, 150.0, 300.0, 500.0]])
