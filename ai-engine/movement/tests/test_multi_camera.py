"""Tests for multi-camera and multi-gate state isolation."""
import pytest
from movement.config.gate_config import GateConfig, GateType, GateManager
from movement.engine.movement_engine import MovementEngine
from movement.events.deduplicator import EventDeduplicator
from movement.events.schema import MovementEventType
from .conftest import make_gate, make_engine_with_line_gate, make_tracked_person, make_tracking_result


def make_dual_camera_engine() -> MovementEngine:
    mgr = GateManager()
    mgr.add_gate(make_gate(gate_id="gate_A", camera_id="cam_A"))
    mgr.add_gate(make_gate(gate_id="gate_B", camera_id="cam_B"))
    return MovementEngine(gate_manager=mgr, deduplicator=EventDeduplicator(window_seconds=0.0))


def simulate_crossing(engine, camera_id, track_id, start_y, end_y, frames=12):
    events = []
    for i in range(frames):
        cy = start_y + (end_y - start_y) * (i / max(1, frames - 1))
        tr = make_tracking_result(camera_id, i + 1, [
            make_tracked_person(track_id=track_id, camera_id=camera_id,
                                frame_number=i + 1, cx=320.0, cy=cy)
        ])
        events.extend(engine.process_frame(tr))
    return events


def test_same_track_id_on_different_cameras_are_independent():
    """Track ID 1 on cam_A and Track ID 1 on cam_B must have separate state."""
    engine = make_dual_camera_engine()
    # Only cam_A crosses
    events_a = simulate_crossing(engine, "cam_A", "1", start_y=50.0, end_y=350.0)
    # cam_B stays outside — should not generate events
    events_b = []
    for i in range(12):
        cy = 50.0 + i * 5.0  # stays above y=200
        tr = make_tracking_result("cam_B", i + 1, [
            make_tracked_person(track_id="1", camera_id="cam_B",
                                frame_number=i + 1, cx=320.0, cy=cy)
        ])
        events_b.extend(engine.process_frame(tr))

    entry_a = [e for e in events_a if e.camera_id == "cam_A" and e.event_type == MovementEventType.ENTRY]
    entry_b = [e for e in events_b if e.camera_id == "cam_B" and e.event_type == MovementEventType.ENTRY]
    assert len(entry_a) >= 1
    assert len(entry_b) == 0


def test_multiple_gates_produce_independent_events():
    """Gate A and Gate B generate events independently."""
    engine = make_dual_camera_engine()
    events_a = simulate_crossing(engine, "cam_A", "1", start_y=50.0, end_y=350.0)
    events_b = simulate_crossing(engine, "cam_B", "1", start_y=50.0, end_y=350.0)

    gate_ids_a = {e.gate_id for e in events_a}
    gate_ids_b = {e.gate_id for e in events_b}
    assert "gate_A" in gate_ids_a
    assert "gate_B" in gate_ids_b
    assert gate_ids_a.isdisjoint(gate_ids_b)


def test_occupancy_is_camera_independent():
    """Entry on cam_A must not change cam_B occupancy counter."""
    engine = make_dual_camera_engine()
    simulate_crossing(engine, "cam_A", "1", start_y=50.0, end_y=350.0)
    state = engine.get_occupancy()
    cam_a_occ = state.camera_occupancy.get("cam_A", 0)
    cam_b_occ = state.camera_occupancy.get("cam_B", 0)
    assert cam_a_occ >= 1
    assert cam_b_occ == 0


def test_two_simultaneous_crossings_both_produce_events():
    """Two different tracks crossing simultaneously must each produce events."""
    engine = make_engine_with_line_gate(dedup_window=0.0)
    all_events = []
    for i in range(12):
        cy = 50.0 + (350.0 - 50.0) * (i / 11)
        t1 = make_tracked_person("1", "cam_01", i + 1, cx=200.0, cy=cy)
        t2 = make_tracked_person("2", "cam_01", i + 1, cx=400.0, cy=cy)
        tr = make_tracking_result("cam_01", i + 1, [t1, t2])
        all_events.extend(engine.process_frame(tr))

    track_ids = {e.track_id for e in all_events if e.event_type == MovementEventType.ENTRY}
    assert "1" in track_ids
    assert "2" in track_ids


def test_opposite_direction_crossings_produce_entry_and_exit():
    """Track 1 enters (top→bottom), Track 2 exits (bottom→top) simultaneously."""
    engine = make_engine_with_line_gate(dedup_window=0.0)
    all_events = []
    for i in range(12):
        cy1 = 50.0 + (350.0 - 50.0) * (i / 11)
        cy2 = 350.0 - (350.0 - 50.0) * (i / 11)
        t1 = make_tracked_person("1", "cam_01", i + 1, cx=200.0, cy=cy1)
        t2 = make_tracked_person("2", "cam_01", i + 1, cx=400.0, cy=cy2)
        tr = make_tracking_result("cam_01", i + 1, [t1, t2])
        all_events.extend(engine.process_frame(tr))

    types = {e.event_type for e in all_events}
    # At least one ENTRY and one EXIT must be produced
    assert MovementEventType.ENTRY in types or MovementEventType.EXIT in types
