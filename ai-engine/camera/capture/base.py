from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import numpy as np


class CameraMetadata:
    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        camera_type: str,
        camera_source: str,
        fps: float = 30.0,
        resolution: Tuple[int, int] = (1920, 1080),
    ):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.camera_type = camera_type
        self.camera_source = camera_source
        self.fps = fps
        self.resolution = resolution
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "camera_type": self.camera_type,
            "camera_source": self.camera_source,
            "fps": self.fps,
            "resolution": self.resolution,
            "created_at": self.created_at,
        }


class BaseCameraCapture(ABC):
    """
    Abstract Base Class for all camera stream capture implementations.
    """
    def __init__(self, metadata: CameraMetadata):
        self.metadata = metadata
        self.is_connected_flag = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish physical/network stream connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close physical/network stream connection cleanly."""
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a single video frame. Returns (success, frame_matrix)."""
        pass

    def is_connected(self) -> bool:
        return self.is_connected_flag

    def get_metadata(self) -> CameraMetadata:
        return self.metadata
