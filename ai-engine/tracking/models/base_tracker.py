from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np
from detection.results.schema import FrameDetectionResult
from tracking.results.schema import TrackingResult


class BaseTracker(ABC):
    """
    Abstract Base Interface for all Multi-Object Trackers.
    Every concrete tracker (ByteTrack, DeepSORT, BoTSORT, OC-SORT, StrongSORT)
    must inherit from BaseTracker.

    DetectionEngine and TrackingEngine depend ONLY on BaseTracker, making
    the core architecture completely algorithm-agnostic.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the tracker state and resources.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def update(
        self,
        detection_result: FrameDetectionResult,
        frame: Optional[np.ndarray] = None
    ) -> TrackingResult:
        """
        Ingest frame detection results and perform multi-object tracking.
        Returns a frame TrackingResult payload with updated tracklets.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Reset all active and lost tracks maintained by this tracker instance.
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """
        Clean up resources and release internal memory.
        """
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retrieve operational performance metrics and track counts.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a self-diagnostic health check of tracker readiness.
        """
        pass
