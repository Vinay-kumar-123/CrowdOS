"""
Test: DetectionPipeline — end-to-end pipeline execution from synthetic frame to FrameDetectionResult.
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.pipeline.detection_pipeline import DetectionPipeline
from detection.results.schema import FrameDetectionResult


@pytest.fixture
def pipeline():
    pl = DetectionPipeline()
    pl.initialize()
    return pl


def test_pipeline_process_frame_returns_result(pipeline):
    """Pipeline must return FrameDetectionResult from a raw synthetic frame."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pipeline.process_frame(frame=frame, camera_id="cam_001", frame_number=0)
    assert isinstance(result, FrameDetectionResult)


def test_pipeline_result_callback_called():
    """Result callback must be invoked after each frame is processed."""
    callback_results = []

    def on_result(result):
        callback_results.append(result)

    pl = DetectionPipeline(result_callback=on_result)
    pl.initialize()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    pl.process_frame(frame=frame, camera_id="cam_002", frame_number=1)
    assert len(callback_results) == 1
    assert isinstance(callback_results[0], FrameDetectionResult)


def test_pipeline_camera_id_preserved(pipeline):
    """Pipeline result must preserve the camera_id from input."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pipeline.process_frame(frame=frame, camera_id="exit_gate_7", frame_number=10)
    assert result.camera_id == "exit_gate_7"


def test_pipeline_frame_number_preserved(pipeline):
    """Pipeline result must preserve frame_number from input."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pipeline.process_frame(frame=frame, camera_id="cam_003", frame_number=99)
    assert result.frame_number == 99


def test_pipeline_sequential_frames(pipeline):
    """Pipeline must process multiple sequential frames without error."""
    for i in range(5):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = pipeline.process_frame(frame=frame, camera_id="main_gate", frame_number=i)
        assert isinstance(result, FrameDetectionResult)
        assert result.frame_number == i


def test_pipeline_provides_camera_callback(pipeline):
    """get_camera_callback must return a callable."""
    cb = pipeline.get_camera_callback()
    assert callable(cb)


def test_pipeline_get_camera_callback_works(pipeline):
    """Camera callback must return FrameDetectionResult when invoked with a frame."""
    cb = pipeline.get_camera_callback()

    class FakeFrameItem:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_number = 7

    result = cb("cam_gate_A", FakeFrameItem())
    assert isinstance(result, FrameDetectionResult)
    assert result.camera_id == "cam_gate_A"
