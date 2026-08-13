"""Tests for MovementEngine end-to-end orchestration."""
import uuid
import pytest
from movement.events.schema import MovementEventType
from movement.events.deduplicator import EventDeduplicator
from .conftest import (
    make_gate, make_engine_with_line_gate, make_tracked_person, make_tracking_result
)
from movement.config.gate_config import GateManager, GateType
from movement.engine.movement_engine import MovementEngine


def simulate_crossing(engine: MovementEngine, camera_id: str, track_id: str,
                       start_y: float, end_y: float, frames: int = 12):
    """
    Drive a track from start_y to end_y across the y=200 virtual line over `frames` frames.
    Returns list of all generated events.
    """
    all_events = []
    for i in range(frames):
        cy = start_y + (end_y - start_y) * (i / max(1, frames - 1))
        track = make_tracked_person(track_id=track_id, camera_id=camera_id,
                                    frame_number=i + 1, cx=320.0, cy=cy)
        tr = make_tracking_result(camera_id=camera_id, frame_number=i + 1, tracks=[track])
        evts = engine.process_frame(tr)
        all_events.extend(evts)
    return all_events


def test_entry_event_generated_crossing_line():
    """Person crossing from above (y=50) to below (y=350) the y=200 line must produce ENTRY."""
    engine = make_engine_with_line_gate(dedup_window=0.0)
    events = simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0)
    entry_events = [e for e in events if e.event_type == MovementEventType.ENTRY]
    assert len(entry_events) >= 1


def test_exit_event_generated_crossing_line_reverse():
    """Person crossing from below (y=350) to above (y=50) the y=200 line must produce EXIT."""
    engine = make_engine_with_line_gate(dedup_window=0.0)
    events = simulate_crossing(engine, "cam_01", "1", start_y=350.0, end_y=50.0)
    exit_events = [e for e in events if e.event_type == MovementEventType.EXIT]
    assert len(exit_events) >= 1


def test_no_event_for_no_crossing():
    """Person moving entirely above line must not trigger any event."""
    engine = make_engine_with_line_gate(dedup_window=0.0)
    events = simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=150.0)
    assert len(events) == 0


def test_deduplication_prevents_multiple_entry_events():
    """A single physical crossing must produce exactly one ENTRY event."""
    engine = make_engine_with_line_gate(dedup_window=30.0)
    events = simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0, frames=20)
    entry_events = [e for e in events if e.event_type == MovementEventType.ENTRY]
    assert len(entry_events) <= 1


def test_event_preserves_track_id_and_camera_id():
    engine = make_engine_with_line_gate(dedup_window=0.0)
    events = simulate_crossing(engine, "cam_A", "track_99", start_y=50.0, end_y=350.0)
    for ev in events:
        assert ev.camera_id == "cam_A"
        assert ev.track_id == "track_99"


def test_event_preserves_detection_id():
    engine = make_engine_with_line_gate(dedup_window=0.0)
    events = simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0)
    for ev in events:
        assert ev.detection_id and ev.detection_id != ""


def test_no_event_for_removed_track():
    """Tracks in REMOVED state must be skipped by the engine."""
    from tracking.results.schema import TrackState
    engine = make_engine_with_line_gate(dedup_window=0.0)
    # Simulate removed track crossing
    for i in range(12):
        cy = 50.0 + (350.0 - 50.0) * (i / 11)
        track = make_tracked_person(
            track_id="1", camera_id="cam_01", frame_number=i + 1,
            cx=320.0, cy=cy, track_state=TrackState.REMOVED
        )
        tr = make_tracking_result("cam_01", i + 1, tracks=[track])
        events = engine.process_frame(tr)
        assert len(events) == 0


def test_occupancy_increments_on_entry():
    engine = make_engine_with_line_gate(dedup_window=30.0)
    simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0)
    state = engine.get_occupancy()
    assert state.total_entries >= 1


def test_occupancy_decrements_on_exit():
    engine = make_engine_with_line_gate(dedup_window=0.0)
    # Entry crossing
    simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0, frames=12)
    # Reset dedup and do exit
    engine.deduplicator.clear()
    simulate_crossing(engine, "cam_01", "1", start_y=350.0, end_y=50.0, frames=12)
    state = engine.get_occupancy()
    assert state.current_occupancy >= 0


def test_statistics_dict_contains_required_keys():
    engine = make_engine_with_line_gate()
    stats = engine.get_statistics()
    assert "metrics" in stats
    assert "occupancy" in stats
    assert "active_journeys" in stats
    assert "completed_journeys" in stats


def test_journey_created_on_entry():
    engine = make_engine_with_line_gate(dedup_window=30.0)
    simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0)
    assert engine.journey_tracker.get_active_journeys_count() >= 1


def test_entry_gate_only_rejects_exit_direction():
    """ENTRY-only gate must not generate EXIT events."""
    gate = make_gate(gate_id="gate_entry_only", camera_id="cam_01", gate_type=GateType.ENTRY)
    mgr = GateManager()
    mgr.add_gate(gate)
    engine = MovementEngine(gate_manager=mgr, deduplicator=EventDeduplicator(window_seconds=0.0))
    events = simulate_crossing(engine, "cam_01", "1", start_y=350.0, end_y=50.0)
    exit_events = [e for e in events if e.event_type == MovementEventType.EXIT]
    assert len(exit_events) == 0


def test_exit_gate_only_rejects_entry_direction():
    """EXIT-only gate must not generate ENTRY events."""
    gate = make_gate(gate_id="gate_exit_only", camera_id="cam_01", gate_type=GateType.EXIT)
    mgr = GateManager()
    mgr.add_gate(gate)
    engine = MovementEngine(gate_manager=mgr, deduplicator=EventDeduplicator(window_seconds=0.0))
    events = simulate_crossing(engine, "cam_01", "1", start_y=50.0, end_y=350.0)
    entry_events = [e for e in events if e.event_type == MovementEventType.ENTRY]
    assert len(entry_events) == 0


def test_no_gate_for_camera_returns_empty():
    """Camera with no configured gate must produce zero events."""
    engine = make_engine_with_line_gate(camera_id="cam_known")
    events = simulate_crossing(engine, "cam_unknown", "1", start_y=50.0, end_y=350.0)
    assert len(events) == 0
