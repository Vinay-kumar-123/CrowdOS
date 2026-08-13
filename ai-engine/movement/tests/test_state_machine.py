"""Tests for MovementState state machine and trajectory buffering."""
import pytest
from movement.state.movement_state import MovementState, TrackMovementState


def make_state() -> TrackMovementState:
    return TrackMovementState(
        camera_id="cam_01",
        gate_id="gate_main",
        track_id="1",
        trajectory_window=5,
        max_lost_frames=5
    )


def test_initial_state_is_unknown():
    s = make_state()
    assert s.current_state == MovementState.UNKNOWN


def test_update_position_appends_trajectory():
    s = make_state()
    s.update_position((100.0, 100.0), frame_number=1)
    s.update_position((100.0, 150.0), frame_number=2)
    assert len(s.get_trajectory_list()) == 2


def test_trajectory_window_bounded():
    s = make_state()
    for i in range(10):
        s.update_position((100.0, float(i * 10)), frame_number=i + 1)
    assert len(s.get_trajectory_list()) <= 5


def test_transition_changes_state():
    s = make_state()
    s.transition_to(MovementState.OUTSIDE)
    assert s.current_state == MovementState.OUTSIDE
    assert s.previous_state == MovementState.UNKNOWN


def test_mark_lost_does_not_expire_early():
    s = make_state()
    s.transition_to(MovementState.INSIDE)
    s.mark_lost()
    assert s.current_state == MovementState.LOST
    assert not s.is_expired()


def test_mark_lost_expires_after_max_frames():
    s = make_state()
    s.transition_to(MovementState.INSIDE)
    for _ in range(6):
        s.mark_lost()
    assert s.is_expired()


def test_track_recovery_from_lost_restores_inside():
    s = make_state()
    s.transition_to(MovementState.INSIDE)
    s.mark_lost()
    assert s.current_state == MovementState.LOST
    # Recovery — update position again
    s.update_position((320.0, 250.0), frame_number=10)
    # After update_position, recovery from LOST sets previous state (INSIDE)
    assert s.current_state == MovementState.INSIDE
    assert s.frames_lost == 0


def test_identity_update_preserves_established_identity():
    s = make_state()
    s.update_position((100.0, 100.0), frame_number=1, identity_id="Person_A")
    # UNKNOWN frame should NOT overwrite established Person_A
    s.update_position((100.0, 110.0), frame_number=2, identity_id="UNKNOWN")
    assert s.associated_identity_id == "Person_A"


def test_identity_update_with_new_known_identity():
    s = make_state()
    s.update_position((100.0, 100.0), frame_number=1, identity_id="UNKNOWN")
    s.update_position((100.0, 110.0), frame_number=2, identity_id="Person_B")
    assert s.associated_identity_id == "Person_B"
