from camera.capture.base import BaseCameraCapture, CameraMetadata
from camera.capture.usb import USBCameraCapture
from camera.capture.rtsp import RTSPCameraCapture
from camera.capture.file import FileCameraCapture
from camera.utils.logger import camera_logger


class CameraFactory:
    """
    Factory Pattern class for instantiating camera capture instances based on camera_type.
    """
    @staticmethod
    def create_camera(metadata: CameraMetadata) -> BaseCameraCapture:
        cam_type = metadata.camera_type.lower()
        if cam_type == "usb":
            return USBCameraCapture(metadata)
        elif cam_type in ["rtsp", "ip"]:
            return RTSPCameraCapture(metadata)
        elif cam_type in ["video", "file", "mp4"]:
            return FileCameraCapture(metadata)
        elif cam_type == "drone":
            # Future Drone camera stream abstraction (RTSP/WebRTC fallback)
            camera_logger.info("Initializing Drone camera stream handler (fallback to RTSP)...", extra={"camera_id": metadata.camera_id})
            return RTSPCameraCapture(metadata)
        else:
            raise ValueError(f"Unsupported camera type: {metadata.camera_type}")
