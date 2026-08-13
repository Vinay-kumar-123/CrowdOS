"""Tests for temporal recognition stabilization."""
import pytest
from recognition.pipeline.temporal import TemporalRecognitionStabilizer, TrackRecognitionState
from recognition.results.schema import RecognitionStatus


def test_temporal_state_stabilizes_after_confirmation_frames():
    """After TEMPORAL_CONFIRMATION_FRAMES consecutive MATCHED observations, identity should stabilize."""
    state = TrackRecognitionState(confirmation_frames=3)

    for _ in range(3):
        state.update("person_001", RecognitionStatus.MATCHED)

    assert state.is_stable is True
    assert state.stable_identity_id == "person_001"


def test_temporal_no_face_does_not_overwrite_stable_identity():
    """CTO Rule: NO_FACE must never overwrite an already established stable identity."""
    state = TrackRecognitionState(confirmation_frames=2)

    # Establish stable identity
    for _ in range(2):
        state.update("person_001", RecognitionStatus.MATCHED)
    assert state.is_stable is True

    # Next frame: no face detected
    eff_id, eff_status = state.update("UNKNOWN", RecognitionStatus.NO_FACE)
    assert eff_id == "person_001"  # Still preserves established identity
    assert eff_status == RecognitionStatus.MATCHED


def test_temporal_quality_rejected_does_not_overwrite_stable():
    """CTO Rule: QUALITY_REJECTED must never overwrite stable identity."""
    state = TrackRecognitionState(confirmation_frames=2)

    for _ in range(2):
        state.update("person_002", RecognitionStatus.MATCHED)
    assert state.is_stable is True

    eff_id, eff_status = state.update("UNKNOWN", RecognitionStatus.QUALITY_REJECTED)
    assert eff_id == "person_002"


def test_temporal_unknown_returns_unknown_when_not_stable():
    state = TrackRecognitionState(confirmation_frames=3)
    eff_id, eff_status = state.update("UNKNOWN", RecognitionStatus.UNKNOWN)
    assert eff_id == "UNKNOWN"
    assert state.is_stable is False


def test_temporal_reset_clears_state():
    state = TrackRecognitionState(confirmation_frames=2)
    for _ in range(2):
        state.update("person_001", RecognitionStatus.MATCHED)
    assert state.is_stable is True

    state.reset()
    assert state.is_stable is False
    assert state.stable_identity_id is None


def test_temporal_stabilizer_camera_track_isolation():
    """CTO Rule: Track 1 on Camera A must not share state with Track 1 on Camera B."""
    stabilizer = TemporalRecognitionStabilizer(confirmation_frames=2)

    # Stabilize cam_A track 1 as person_001
    for _ in range(2):
        stabilizer.update("cam_A", "1", "person_001", RecognitionStatus.MATCHED)

    assert stabilizer.is_stable("cam_A", "1") is True
    assert stabilizer.is_stable("cam_B", "1") is False  # cam_B track 1 is independent


def test_temporal_stabilizer_cleanup_removes_state():
    stabilizer = TemporalRecognitionStabilizer(confirmation_frames=2)

    for _ in range(2):
        stabilizer.update("cam_C", "5", "person_003", RecognitionStatus.MATCHED)
    assert stabilizer.is_stable("cam_C", "5") is True

    stabilizer.cleanup_track("cam_C", "5")
    assert stabilizer.is_stable("cam_C", "5") is False


def test_temporal_incomplete_observations_do_not_stabilize():
    """Only TEMPORAL_CONFIRMATION_FRAMES consecutive MATCHED observations stabilize."""
    state = TrackRecognitionState(confirmation_frames=4)

    # Only 2 MATCHED observations out of required 4
    state.update("person_001", RecognitionStatus.MATCHED)
    state.update("person_001", RecognitionStatus.MATCHED)

    assert state.is_stable is False
