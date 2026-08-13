import os
try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np
from typing import Tuple, Optional, Any
from camera.capture.base import BaseCameraCapture, CameraMetadata
from camera.utils.logger import camera_logger


class FileCameraCapture(BaseCameraCapture):
    """
    Local MP4/AVI Video File Capture implementation supporting seamless looping.
    """
    def __init__(self, metadata: CameraMetadata, loop: bool = True):
        super().__init__(metadata)
        self.file_path = metadata.camera_source
        self.loop = loop
        self.cap: Optional[Any] = None

    def connect(self) -> bool:
        if cv2 is None:
            camera_logger.error("OpenCV (cv2) is not installed.", extra={"camera_id": self.metadata.camera_id})
            self.is_connected_flag = False
            return False

        try:
            if not os.path.exists(self.file_path):
                camera_logger.error(
                    f"Video file not found at path: {self.file_path}",
                    extra={"camera_id": self.metadata.camera_id}
                )
                self.is_connected_flag = False
                return False

            camera_logger.info(
                f"Opening video file stream: {self.file_path}...",
                extra={"camera_id": self.metadata.camera_id}
            )
            self.cap = cv2.VideoCapture(self.file_path)
            if not self.cap.isOpened():
                camera_logger.error(
                    f"Failed to open video file: {self.file_path}",
                    extra={"camera_id": self.metadata.camera_id}
                )
                self.is_connected_flag = False
                return False

            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if w > 0 and h > 0:
                self.metadata.resolution = (w, h)
            self.metadata.fps = fps

            self.is_connected_flag = True
            camera_logger.info(
                f"Video File stream connected: {self.metadata.resolution} @ {self.metadata.fps} FPS",
                extra={"camera_id": self.metadata.camera_id}
            )
            return True
        except Exception as e:
            camera_logger.error(
                f"Video file connection error: {e}",
                extra={"camera_id": self.metadata.camera_id}
            )
            self.is_connected_flag = False
            return False

    def disconnect(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_connected_flag = False
        camera_logger.info(
            "Video file stream disconnected.",
            extra={"camera_id": self.metadata.camera_id}
        )

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_connected_flag or not self.cap:
            return False, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            if self.loop:
                # Seek back to first frame for seamless looping
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    return True, frame
            self.is_connected_flag = False
            return False, None

        return True, frame
