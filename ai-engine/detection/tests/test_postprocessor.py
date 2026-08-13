"""
Test: Postprocessor — person-class filtering, confidence thresholding, non-person exclusion.
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.processors.postprocessor import Postprocessor
from detection.results.schema import DetectionItem


class MockBoxes:
    def __init__(self, classes, confidences, xyxy):
        self.cls = np.array(classes, dtype=np.float32)
        self.conf = np.array(confidences, dtype=np.float32)
        self.xyxy = np.array(xyxy, dtype=np.float32)


class MockResult:
    def __init__(self, classes, confidences, xyxy):
        self.boxes = MockBoxes(classes, confidences, xyxy)


@pytest.fixture
def postprocessor():
    return Postprocessor(confidence_threshold=0.45, person_class_id=0, max_detections=300)


def make_raw(classes, confidences, xyxy):
    return [MockResult(classes, confidences, xyxy)]


def test_person_class_detected(postprocessor):
    """Postprocessor should return DetectionItem for Person class (ID 0) above threshold."""
    raw = make_raw([0], [0.90], [[50, 60, 200, 400]])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert len(results) == 1
    assert results[0].class_id == 0
    assert results[0].class_name == "person"


def test_non_person_class_excluded(postprocessor):
    """Car (class 2), bicycle (class 1) must be excluded — only Person (0) allowed."""
    raw = make_raw([2, 1, 0], [0.90, 0.92, 0.88], [
        [10, 20, 100, 200],
        [120, 130, 300, 400],
        [50, 60, 200, 400],
    ])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert len(results) == 1
    assert results[0].class_id == 0


def test_confidence_filtering(postprocessor):
    """Detections below confidence threshold must be excluded."""
    raw = make_raw([0, 0], [0.20, 0.90], [
        [10, 20, 100, 200],
        [150, 160, 300, 400],
    ])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert len(results) == 1
    assert results[0].confidence >= 0.45


def test_empty_raw_results(postprocessor):
    """Empty raw results should return empty list."""
    results = postprocessor.process_results([], original_shape=(640, 480))
    assert results == []


def test_detection_id_unique(postprocessor):
    """Each DetectionItem must have a unique detection_id."""
    raw = make_raw([0, 0], [0.88, 0.92], [
        [10, 20, 100, 200],
        [200, 210, 400, 500],
    ])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert len(results) == 2
    ids = [r.detection_id for r in results]
    assert ids[0] != ids[1]


def test_detection_center_calculation(postprocessor):
    """Center coordinates must be midpoint of bounding box."""
    raw = make_raw([0], [0.90], [[100, 200, 300, 400]])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert len(results) == 1
    cx, cy = results[0].center
    assert abs(cx - 200.0) < 1.0  # center_x = (100+300)/2
    assert abs(cy - 300.0) < 1.0  # center_y = (200+400)/2


def test_detection_width_height(postprocessor):
    """Width and Height must be computed correctly from bounding box."""
    raw = make_raw([0], [0.90], [[100, 200, 300, 400]])
    results = postprocessor.process_results(raw, original_shape=(640, 480))
    assert abs(results[0].width - 200.0) < 1.0
    assert abs(results[0].height - 200.0) < 1.0


def test_max_detections_limit(postprocessor):
    """Max detection limit must be respected."""
    # 5 person detections with tiny max_detections=2
    pp = Postprocessor(confidence_threshold=0.45, person_class_id=0, max_detections=2)
    classes = [0] * 5
    confs = [0.9] * 5
    boxes = [[i*10, i*10, i*10+100, i*10+200] for i in range(5)]
    raw = make_raw(classes, confs, boxes)
    results = pp.process_results(raw, original_shape=(640, 480))
    assert len(results) == 2
