try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np
from typing import Tuple, Optional
from camera.capture.base import BaseCameraCapture, CameraMetadata
from camera.utils.logger import camera_logger


class USBCameraCapture(BaseCameraCapture):
    """
    USB WebCam Video Capture implementation using OpenCV VideoCapture.
    """
    def __init__(self, metadata: CameraMetadata):
        super().__init__(metadata)
        self.device_index = int(metadata.camera_source) if str(metadata.camera_source).isdigit() else 0
        self.cap: Optional[Any] = None

    def connect(self) -> bool:
        if cv2 is None:
            camera_logger.error("OpenCV (cv2) is not installed.", extra={"camera_id": self.metadata.camera_id})
            self.is_connected_flag = False
            return False

        try:
            camera_logger.info(
                f"Connecting to USB camera device index {self.device_index}...",
                extra={"camera_id": self.metadata.camera_id}
            )
            self.cap = cv2.VideoCapture(self.device_index)
            if not self.cap.isOpened():
                camera_logger.error(
                    f"Failed to open USB camera index {self.device_index}",
                    extra={"camera_id": self.metadata.camera_id}
                )
                self.is_connected_flag = False
                return False

            # Query actual resolution & FPS
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if w > 0 and h > 0:
                self.metadata.resolution = (w, h)
            self.metadata.fps = fps

            self.is_connected_flag = True
            camera_logger.info(
                f"USB Camera connected successfully: {self.metadata.resolution} @ {self.metadata.fps} FPS",
                extra={"camera_id": self.metadata.camera_id}
            )
            return True
        except Exception as e:
            camera_logger.error(
                f"USB Camera connection error: {e}",
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
            "USB Camera disconnected cleanly.",
            extra={"camera_id": self.metadata.camera_id}
        )

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_connected_flag or not self.cap:
            return False, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.is_connected_flag = False
            return False, None

        return True, frame
