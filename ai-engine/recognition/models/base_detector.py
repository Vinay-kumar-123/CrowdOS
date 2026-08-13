from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


class FaceDetectionItem:
    """
    Standardized face detection payload item returned by BaseFaceDetector.
    """
    def __init__(
        self,
        face_id: str,
        bbox: List[float],  # [x1, y1, x2, y2]
        confidence: float,
        landmarks: Optional[np.ndarray] = None,  # 5-point landmarks (5x2)
        crop: Optional[np.ndarray] = None
    ):
        self.face_id = face_id
        self.bbox = bbox
        self.confidence = float(confidence)
        self.landmarks = landmarks
        self.crop = crop


class BaseFaceDetector(ABC):
    """
    Abstract Base Interface for all Face Detectors.
    Every face detector (InsightFaceDetector, OpenCVFaceDetector, etc.) must inherit from BaseFaceDetector.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize detector models and runtime resources.
        """
        pass

    @abstractmethod
    def detect_faces(
        self,
        image: np.ndarray,
        person_bbox: Optional[List[float]] = None
    ) -> List[FaceDetectionItem]:
        """
        Detect face bounding boxes and landmarks within an image or person bounding box region.
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Return metadata info describing detector algorithm and configuration.
        """
        pass
