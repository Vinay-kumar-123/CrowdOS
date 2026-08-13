import os
try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np
from typing import Tuple, Optional, Any
from camera.capture.base import BaseCameraCapture, CameraMetadata
from camera.utils.logger import camera_logger


class RTSPCameraCapture(BaseCameraCapture):
    """
    RTSP / IP Camera Video Capture implementation with TCP transport optimizations.
    """
    def __init__(self, metadata: CameraMetadata):
        super().__init__(metadata)
        self.rtsp_url = metadata.camera_source
        self.cap: Optional[Any] = None

    def connect(self) -> bool:
        if cv2 is None:
            camera_logger.error("OpenCV (cv2) is not installed.", extra={"camera_id": self.metadata.camera_id})
            self.is_connected_flag = False
            return False

        try:
            camera_logger.info(
                f"Connecting to RTSP stream: {self.rtsp_url}...",
                extra={"camera_id": self.metadata.camera_id}
            )

            # Enforce TCP transport for RTSP stability
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                camera_logger.error(
                    f"Failed to open RTSP stream: {self.rtsp_url}",
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
                f"RTSP Camera connected successfully: {self.metadata.resolution} @ {self.metadata.fps} FPS",
                extra={"camera_id": self.metadata.camera_id}
            )
            return True
        except Exception as e:
            camera_logger.error(
                f"RTSP Stream connection error: {e}",
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
            "RTSP Stream disconnected.",
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
