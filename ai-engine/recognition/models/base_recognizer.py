from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
from recognition.models.base_store import BaseIdentityStore
from recognition.results.schema import RecognizedPerson


class BaseFaceRecognizer(ABC):
    """
    Abstract Base Interface for Face Recognizer implementations.
    Orchestrates detection, quality assessment, alignment, embedding generation, and matching.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize model resources.
        """
        pass

    @abstractmethod
    def recognize_face_in_track(
        self,
        frame: np.ndarray,
        person_bbox: List[float],
        camera_id: str,
        track_id: str,
        detection_id: str,
        identity_store: BaseIdentityStore,
        frame_number: int = 0
    ) -> RecognizedPerson:
        """
        Perform face detection, quality check, alignment, embedding extraction, and identity matching
        for a tracked person crop in a video frame.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Reset internal state.
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """
        Clean up model resources.
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Return recognizer algorithm details and hardware execution mode.
        """
        pass
