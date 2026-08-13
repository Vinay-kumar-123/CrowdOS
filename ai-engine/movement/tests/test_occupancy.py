"""Tests for OccupancyTracker — multi-level occupancy, non-negative bounds."""
import pytest
from movement.state.occupancy import OccupancyTracker


def test_entry_increments_occupancy():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_main")
    state = ot.get_state()
    assert state.current_occupancy == 1
    assert state.total_entries == 1
    assert state.gate_occupancy.get("gate_main", 0) == 1
    assert state.camera_occupancy.get("cam_01", 0) == 1


def test_exit_decrements_occupancy():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_main")
    ot.record_exit("cam_01", "gate_main")
    state = ot.get_state()
    assert state.current_occupancy == 0
    assert state.total_exits == 1


def test_exit_without_prior_entry_does_not_go_negative():
    """Exit without active occupancy must clamp to 0 (non-negative)."""
    ot = OccupancyTracker()
    ot.record_exit("cam_01", "gate_main")
    state = ot.get_state()
    assert state.current_occupancy == 0


def test_multiple_entries_multiple_exits():
    ot = OccupancyTracker()
    for _ in range(5):
        ot.record_entry("cam_01", "gate_main")
    for _ in range(3):
        ot.record_exit("cam_01", "gate_main")
    state = ot.get_state()
    assert state.current_occupancy == 2


def test_gate_occupancy_tracked_separately():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_A")
    ot.record_entry("cam_01", "gate_B")
    ot.record_exit("cam_01", "gate_A")
    state = ot.get_state()
    assert state.gate_occupancy.get("gate_A", 0) == 0
    assert state.gate_occupancy.get("gate_B", 0) == 1


def test_camera_occupancy_tracked_separately():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_main")
    ot.record_entry("cam_02", "gate_main")
    state = ot.get_state()
    assert state.camera_occupancy.get("cam_01", 0) == 1
    assert state.camera_occupancy.get("cam_02", 0) == 1


def test_venue_occupancy_is_entries_minus_exits():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_A")
    ot.record_entry("cam_01", "gate_B")
    ot.record_exit("cam_01", "gate_A")
    state = ot.get_state()
    assert state.current_occupancy == max(0, state.total_entries - state.total_exits)


def test_reset_clears_occupancy():
    ot = OccupancyTracker()
    ot.record_entry("cam_01", "gate_main")
    ot.reset()
    state = ot.get_state()
    assert state.current_occupancy == 0
    assert state.total_entries == 0
