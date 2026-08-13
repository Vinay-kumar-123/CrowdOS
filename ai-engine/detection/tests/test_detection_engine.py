"""
Test: DetectionEngine — inference execution, timing, and result schema validation.
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.engine.detection_engine import DetectionEngine
from detection.results.schema import FrameDetectionResult


@pytest.fixture
def engine():
    eng = DetectionEngine()
    eng.initialize()
    return eng


def test_engine_initializes_successfully(engine):
    """Engine must initialize and load model without errors."""
    assert engine.model_manager.is_loaded is True


def test_detect_persons_returns_result(engine):
    """detect_persons must return a FrameDetectionResult object."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    assert isinstance(result, FrameDetectionResult)


def test_detect_persons_contains_camera_id(engine):
    """FrameDetectionResult must preserve the camera_id provided."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="gate_01", frame_number=5)
    assert result.camera_id == "gate_01"


def test_detect_persons_frame_number(engine):
    """FrameDetectionResult must preserve the frame_number provided."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=42)
    assert result.frame_number == 42


def test_detect_persons_inference_time_positive(engine):
    """Inference time must be a positive float."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    assert result.inference_time_ms > 0.0


def test_detect_persons_device_populated(engine):
    """FrameDetectionResult must populate device_used field."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    assert result.device_used in ("cuda", "cpu", "mps")


def test_detect_persons_resolution(engine):
    """FrameDetectionResult must record correct frame resolution."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    assert result.resolution == (1280, 720)


def test_detect_persons_only_person_class(engine):
    """All returned detections must exclusively have class_id=0 (person)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    for det in result.detections:
        assert det.class_id == 0
        assert det.class_name == "person"


def test_engine_metrics_after_inference(engine):
    """Engine metrics must update correctly after one inference pass."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    engine.detect_persons(frame=frame, camera_id="test_cam", frame_number=1)
    metrics = engine.get_engine_metrics()
    assert metrics["total_frames_processed"] >= 1
    assert metrics["average_inference_time_ms"] > 0.0
    assert metrics["average_fps"] > 0.0


def test_detect_persons_invalid_frame(engine):
    """Engine must handle unusual frame shapes gracefully."""
    # 1-pixel frame, edge case
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    result = engine.detect_persons(frame=frame, camera_id="edge_cam", frame_number=1)
    assert isinstance(result, FrameDetectionResult)
