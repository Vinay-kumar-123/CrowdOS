"""
BaseDetector — Abstract detector interface for CrowdOS AI Detection Engine.

All concrete detector implementations (YOLO, RT-DETR, Grounding DINO, PeopleNet)
must subclass BaseDetector and implement its contract.

DetectionEngine depends ONLY on this interface — never on a concrete model library.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np


class BaseDetector(ABC):
    """
    Abstract base class for all person detector backends.
    New detection models are plugged in by subclassing this interface.
    """

    @abstractmethod
    def load(self, model_path: str, device: str) -> bool:
        """
        Load model weights onto the specified device.
        Returns True on success, False on failure.
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """
        Free model weights and release device memory.
        """
        ...

    @abstractmethod
    def predict(self, frame: np.ndarray, conf: float, iou: float) -> Any:
        """
        Run inference on a preprocessed frame.
        Returns raw model output (model-specific). Postprocessor handles parsing.
        """
        ...

    @abstractmethod
    def warmup(self, img_size: int, iterations: int) -> bool:
        """
        Run dummy inference to prime GPU CUDA JIT compilation caches.
        """
        ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Returns True if model weights are currently resident in memory."""
        ...

    @property
    @abstractmethod
    def device(self) -> str:
        """Returns the active device string: 'cuda', 'mps', or 'cpu'."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns human-readable model identifier string."""
        ...

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Returns a dict of model metadata for observability."""
        ...
