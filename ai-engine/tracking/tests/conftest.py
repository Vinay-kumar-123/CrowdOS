import uuid
import pytest
from typing import List
from detection.results.schema import FrameDetectionResult, DetectionItem, BoundingBox
from tracking.results.schema import TrackState


@pytest.fixture
def sample_detection_item():
    return DetectionItem(
        detection_id=str(uuid.uuid4()),
        class_id=0,
        class_name="person",
        confidence=0.85,
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=300.0),
        center=(150.0, 200.0),
        width=100.0,
        height=200.0
    )


@pytest.fixture
def sample_frame_detection_result(sample_detection_item):
    return FrameDetectionResult(
        frame_number=1,
        camera_id="cam_01",
        inference_time_ms=10.5,
        total_persons_detected=1,
        detections=[sample_detection_item],
        device_used="cpu",
        resolution=(1920, 1080)
    )


def make_detection_result(
    frame_number: int,
    camera_id: str,
    boxes_with_conf: List[tuple]
) -> FrameDetectionResult:
    """
    Helper to construct FrameDetectionResult from list of (x1, y1, x2, y2, confidence).
    """
    items = []
    for x1, y1, x2, y2, conf in boxes_with_conf:
        w = x2 - x1
        h = y2 - y1
        item = DetectionItem(
            detection_id=str(uuid.uuid4()),
            class_id=0,
            class_name="person",
            confidence=conf,
            bbox=BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2)),
            center=(float(x1 + w / 2.0), float(y1 + h / 2.0)),
            width=float(w),
            height=float(h)
        )
        items.append(item)

    return FrameDetectionResult(
        frame_number=frame_number,
        camera_id=camera_id,
        inference_time_ms=8.0,
        total_persons_detected=len(items),
        detections=items,
        device_used="cpu",
        resolution=(1920, 1080)
    )
