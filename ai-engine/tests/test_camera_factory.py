from camera.capture.base import CameraMetadata
from camera.capture.factory import CameraFactory
from camera.capture.usb import USBCameraCapture
from camera.capture.rtsp import RTSPCameraCapture
from camera.capture.file import FileCameraCapture


def test_camera_factory_instantiation():
    usb_meta = CameraMetadata("c1", "USB Cam", "usb", "0")
    rtsp_meta = CameraMetadata("c2", "RTSP Cam", "rtsp", "rtsp://localhost:8554/live")
    file_meta = CameraMetadata("c3", "File Cam", "file", "sample.mp4")

    usb_cam = CameraFactory.create_camera(usb_meta)
    rtsp_cam = CameraFactory.create_camera(rtsp_meta)
    file_cam = CameraFactory.create_camera(file_meta)

    assert isinstance(usb_cam, USBCameraCapture)
    assert isinstance(rtsp_cam, RTSPCameraCapture)
    assert isinstance(file_cam, FileCameraCapture)
