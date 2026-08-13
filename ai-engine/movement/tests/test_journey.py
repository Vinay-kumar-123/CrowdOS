"""Tests for JourneyTracker — lifecycle, multi-visit, orphan exit, dwell time."""
import time
import pytest
from datetime import datetime, timezone
from movement.state.journey import JourneyTracker, JourneyStatus


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_start_journey_creates_active_journey():
    jt = JourneyTracker()
    j = jt.start_journey("cam_01", "1", "gate_main", identity_id="UNKNOWN")
    assert j is not None
    assert j.status == JourneyStatus.ACTIVE
    assert jt.get_active_journeys_count() == 1


def test_complete_journey_calculates_dwell_time():
    jt = JourneyTracker()
    t1 = "2026-01-01T10:00:00+00:00"
    t2 = "2026-01-01T10:05:00+00:00"
    jt.start_journey("cam_01", "1", "gate_main", identity_id="UNKNOWN", timestamp=t1)
    completed = jt.complete_journey("cam_01", "1", "gate_main", identity_id="UNKNOWN", timestamp=t2)
    assert completed is not None
    assert completed.dwell_time == 300.0
    assert completed.status == JourneyStatus.COMPLETED
    assert jt.get_active_journeys_count() == 0


def test_multiple_visits_create_separate_journeys():
    """Two separate visit sessions must produce distinct journey_ids."""
    jt = JourneyTracker()
    t1 = "2026-01-01T10:00:00+00:00"
    t2 = "2026-01-01T10:05:00+00:00"
    t3 = "2026-01-01T11:00:00+00:00"
    t4 = "2026-01-01T11:10:00+00:00"

    jt.start_journey("cam_01", "1", "gate_main", identity_id="Person_A", timestamp=t1)
    j1 = jt.complete_journey("cam_01", "1", "gate_main", identity_id="Person_A", timestamp=t2)

    jt.start_journey("cam_01", "1", "gate_main", identity_id="Person_A", timestamp=t3)
    j2 = jt.complete_journey("cam_01", "1", "gate_main", identity_id="Person_A", timestamp=t4)

    assert j1 is not None and j2 is not None
    assert j1.journey_id != j2.journey_id
    assert j1.dwell_time == 300.0
    assert j2.dwell_time == 600.0
    assert len(jt.list_completed_journeys()) == 2


def test_duplicate_entry_does_not_create_second_journey():
    """Second ENTRY for same identity while active journey exists must NOT create new journey."""
    jt = JourneyTracker()
    j1 = jt.start_journey("cam_01", "1", "gate_main", identity_id="Person_A")
    j2 = jt.start_journey("cam_01", "1", "gate_main", identity_id="Person_A")
    # Must return same journey, not create a second
    assert j1.journey_id == j2.journey_id
    assert jt.get_active_journeys_count() == 1


def test_exit_without_active_journey_returns_none():
    """EXIT without an active journey must return None (no fabricated journey)."""
    jt = JourneyTracker()
    result = jt.complete_journey("cam_01", "1", "gate_main", identity_id="UNKNOWN")
    assert result is None
    assert jt.get_active_journeys_count() == 0


def test_unknown_identity_journey_is_camera_track_scoped():
    """UNKNOWN identity journeys must be scoped by camera_id:track_id."""
    jt = JourneyTracker()
    jt.start_journey("cam_A", "17", "gate_main", identity_id="UNKNOWN")
    jt.start_journey("cam_B", "17", "gate_main", identity_id="UNKNOWN")
    # Two separate unknown journeys — distinct keys
    assert jt.get_active_journeys_count() == 2


def test_known_identity_journey_spans_across_camera_keys():
    """Known identity_id correlates the journey across cameras/tracks."""
    jt = JourneyTracker()
    jt.start_journey("cam_A", "1", "gate_main", identity_id="Person_A")
    # Second start for same identity → same key → no new journey
    j2 = jt.start_journey("cam_B", "99", "gate_main", identity_id="Person_A")
    assert jt.get_active_journeys_count() == 1


def test_recognition_noise_does_not_duplicate_journey():
    """Identity noise (Person_A → UNKNOWN → Person_A) must not create multiple active journeys."""
    jt = JourneyTracker()
    jt.start_journey("cam_01", "1", "gate_main", identity_id="Person_A")
    # Noise frame: UNKNOWN comes in — separate key, should create separate unknown journey
    jt.start_journey("cam_01", "1", "gate_main", identity_id="UNKNOWN")
    # Person_A key still only 1
    j = jt.get_active_journey("cam_01", "1", identity_id="Person_A")
    assert j is not None
    assert j.status == JourneyStatus.ACTIVE


def test_completed_journey_preserved_in_history():
    jt = JourneyTracker()
    jt.start_journey("cam_01", "1", "gate_main")
    jt.complete_journey("cam_01", "1", "gate_main")
    completed = jt.list_completed_journeys()
    assert len(completed) == 1
    assert completed[0].status == JourneyStatus.COMPLETED


def test_journey_dwell_time_non_negative():
    jt = JourneyTracker()
    # T_exit same as T_entry → dwell = 0
    t = "2026-01-01T10:00:00+00:00"
    jt.start_journey("cam_01", "1", "gate_main", timestamp=t)
    completed = jt.complete_journey("cam_01", "1", "gate_main", timestamp=t)
    assert completed is not None
    assert completed.dwell_time >= 0.0
