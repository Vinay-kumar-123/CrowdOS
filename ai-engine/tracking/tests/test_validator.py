import pytest
from detection.results.schema import BoundingBox
from tracking.pipeline.validator import TrackValidator
from tracking.results.schema import TrackedPerson, TrackingResult, TrackState


def test_validator_valid_tracked_person():
    validator = TrackValidator()
    person = TrackedPerson(
        track_id="1",
        detection_id="det_123",
        camera_id="cam_val",
        frame_number=1,
        bbox=BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=100.0),
        confidence=0.85,
        center=(30.0, 55.0),
        track_state=TrackState.ACTIVE
    )
    is_valid, err = validator.validate_tracked_person(person)
    assert is_valid is True
    assert err == ""


def test_validator_invalid_bbox_and_confidence():
    validator = TrackValidator()

    # Invalid negative bounding box width (x1 >= x2)
    bad_person1 = TrackedPerson(
        track_id="1",
        detection_id="det_123",
        camera_id="cam_val",
        frame_number=1,
        bbox=BoundingBox(x1=50.0, y1=10.0, x2=10.0, y2=100.0),
        confidence=0.85,
        center=(30.0, 55.0),
        track_state=TrackState.ACTIVE
    )
    is_valid, err = validator.validate_tracked_person(bad_person1)
    assert is_valid is False
    assert "Invalid bounding box" in err


def test_validator_duplicate_track_ids_and_frame_order():
    validator = TrackValidator()
    p1 = TrackedPerson(
        track_id="1", detection_id="d1", camera_id="c1", frame_number=1,
        bbox=BoundingBox(x1=10.0, y1=10.0, x2=20.0, y2=30.0), confidence=0.8,
        center=(15.0, 20.0), track_state=TrackState.ACTIVE
    )
    p2 = TrackedPerson(
        track_id="1", detection_id="d2", camera_id="c1", frame_number=1,
        bbox=BoundingBox(x1=40.0, y1=40.0, x2=60.0, y2=80.0), confidence=0.8,
        center=(50.0, 60.0), track_state=TrackState.ACTIVE
    )
    result = TrackingResult(
        frame_number=1, camera_id="c1", tracking_time_ms=2.0,
        total_active_tracks=2, total_lost_tracks=0, tracks=[p1, p2]
    )
    is_valid, errors = validator.validate_tracking_result(result)
    assert is_valid is False
    assert any("Duplicate track_id" in err for err in errors)
