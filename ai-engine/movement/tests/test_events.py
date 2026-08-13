"""Tests for MovementEvent schema validation and EventDeduplicator."""
import time
import pytest
from detection.results.schema import BoundingBox
from movement.events.schema import (
    MovementEvent, EntryEvent, ExitEvent, MovementEventType, EventSource
)
from movement.events.deduplicator import EventDeduplicator
from movement.events.validator import MovementEventValidator


def make_entry_event(
    camera_id="cam_01", gate_id="gate_main", track_id="1",
    detection_id="det_001", identity_id="UNKNOWN"
) -> EntryEvent:
    return EntryEvent(
        camera_id=camera_id,
        gate_id=gate_id,
        entry_gate_id=gate_id,
        track_id=track_id,
        detection_id=detection_id,
        identity_id=identity_id,
        identity_status="UNKNOWN",
        direction="ENTRY",
        confidence=0.95,
        event_source=EventSource.TRACK_CROSSING
    )


def make_exit_event(
    camera_id="cam_01", gate_id="gate_main", track_id="1",
    detection_id="det_002", identity_id="UNKNOWN"
) -> ExitEvent:
    return ExitEvent(
        camera_id=camera_id,
        gate_id=gate_id,
        exit_gate_id=gate_id,
        track_id=track_id,
        detection_id=detection_id,
        identity_id=identity_id,
        identity_status="UNKNOWN",
        direction="EXIT",
        confidence=0.95,
        event_source=EventSource.TRACK_CROSSING
    )


# ─────────────────── Schema Tests ───────────────────

def test_entry_event_has_correct_type():
    ev = make_entry_event()
    assert ev.event_type == MovementEventType.ENTRY


def test_exit_event_has_correct_type():
    ev = make_exit_event()
    assert ev.event_type == MovementEventType.EXIT


def test_entry_event_preserves_traceability():
    ev = make_entry_event(
        camera_id="cam_01", gate_id="gate_A",
        track_id="42", detection_id="det_XYZ", identity_id="Person_A"
    )
    assert ev.camera_id == "cam_01"
    assert ev.gate_id == "gate_A"
    assert ev.track_id == "42"
    assert ev.detection_id == "det_XYZ"
    assert ev.identity_id == "Person_A"


def test_exit_event_can_have_dwell_time():
    ev = make_exit_event()
    ev.dwell_time = 123.5
    assert ev.dwell_time == 123.5


def test_movement_event_to_dict_contains_required_fields():
    ev = make_entry_event()
    d = ev.to_dict()
    for field in ["event_id", "event_type", "camera_id", "gate_id", "track_id",
                  "detection_id", "identity_id", "identity_status", "timestamp",
                  "direction", "confidence", "event_source"]:
        assert field in d, f"Missing field: {field}"


def test_movement_event_has_no_raw_embedding():
    ev = make_entry_event()
    d = ev.to_dict()
    assert "embedding" not in d
    assert "face_crop" not in d
    assert "biometric_vector" not in d


# ─────────────────── Deduplicator Tests ───────────────────

def test_deduplicator_first_event_is_not_duplicate():
    dedup = EventDeduplicator(window_seconds=5.0)
    assert not dedup.is_duplicate("cam_01", "gate_main", "1", "ENTRY")


def test_deduplicator_second_event_within_window_is_duplicate():
    dedup = EventDeduplicator(window_seconds=5.0)
    t0 = time.time()
    dedup.record_event("cam_01", "gate_main", "1", "ENTRY", current_time=t0)
    assert dedup.is_duplicate("cam_01", "gate_main", "1", "ENTRY", current_time=t0 + 1.0)


def test_deduplicator_event_after_window_is_not_duplicate():
    dedup = EventDeduplicator(window_seconds=2.0)
    t0 = time.time()
    dedup.record_event("cam_01", "gate_main", "1", "ENTRY", current_time=t0)
    assert not dedup.is_duplicate("cam_01", "gate_main", "1", "ENTRY", current_time=t0 + 3.0)


def test_deduplicator_entry_and_exit_are_independent():
    dedup = EventDeduplicator(window_seconds=5.0)
    t0 = time.time()
    dedup.record_event("cam_01", "gate_main", "1", "ENTRY", current_time=t0)
    # EXIT for same track is NOT a duplicate
    assert not dedup.is_duplicate("cam_01", "gate_main", "1", "EXIT", current_time=t0 + 1.0)


def test_deduplicator_different_cameras_are_independent():
    dedup = EventDeduplicator(window_seconds=5.0)
    t0 = time.time()
    dedup.record_event("cam_01", "gate_main", "1", "ENTRY", current_time=t0)
    assert not dedup.is_duplicate("cam_02", "gate_main", "1", "ENTRY", current_time=t0 + 1.0)


def test_deduplicator_identity_key_also_deduplicates():
    dedup = EventDeduplicator(window_seconds=5.0)
    t0 = time.time()
    dedup.record_event("cam_01", "gate_main", "1", "ENTRY",
                       identity_id="Person_A", current_time=t0)
    # Different track_id but same identity_id within window → duplicate
    assert dedup.is_duplicate("cam_01", "gate_main", "2", "ENTRY",
                              identity_id="Person_A", current_time=t0 + 0.5)


# ─────────────────── Validator Tests ───────────────────

def test_validator_accepts_valid_entry_event():
    v = MovementEventValidator()
    ev = make_entry_event()
    ok, errs = v.validate_event(ev)
    assert ok
    assert errs == []


def test_validator_rejects_empty_camera_id():
    v = MovementEventValidator()
    ev = make_entry_event()
    ev.camera_id = ""
    ok, errs = v.validate_event(ev)
    assert not ok
    assert any("camera_id" in e for e in errs)


def test_validator_rejects_invalid_confidence():
    v = MovementEventValidator()
    ev = make_entry_event()
    ev.confidence = 1.5
    ok, errs = v.validate_event(ev)
    assert not ok


def test_validator_rejects_invalid_bbox():
    v = MovementEventValidator()
    ev = make_entry_event()
    ev.bounding_box = BoundingBox(x1=300.0, y1=100.0, x2=100.0, y2=200.0)
    ok, errs = v.validate_event(ev)
    assert not ok
