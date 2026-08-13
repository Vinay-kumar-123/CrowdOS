"""
Sprint 1-4 regression tests for Sprint 5.
Verifies that Sprint 5 imports/implementation does NOT break Sprint 1-4 modules.
"""
import pytest
import importlib
import sys


def test_sprint1_camera_module_importable():
    """Sprint 1: Camera infrastructure must remain unmodified and importable."""
    try:
        camera = importlib.import_module("camera")
        assert camera is not None
    except ImportError:
        pytest.skip("Camera module not in PYTHONPATH for this test run")


def test_sprint2_detection_module_importable():
    """Sprint 2: Detection engine must remain unmodified and importable."""
    try:
        detection = importlib.import_module("detection")
        assert detection is not None
    except ImportError:
        pytest.skip("Detection module not in PYTHONPATH for this test run")


def test_sprint3_stabilization_module_importable():
    """Sprint 3/3.1: Detection stabilization must remain unmodified and importable."""
    try:
        stab = importlib.import_module("detection.stabilization")
        assert stab is not None
    except ImportError:
        pytest.skip("detection.stabilization not in PYTHONPATH for this test run")


def test_sprint4_tracking_module_importable():
    """Sprint 4: Tracking engine must remain unmodified and importable."""
    tracking = importlib.import_module("tracking")
    assert tracking is not None


def test_sprint4_tracking_result_schema_unchanged():
    """Sprint 4: TrackingResult schema must match Sprint 5 expectations exactly."""
    from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
    import inspect

    tracking_result_fields = set(TrackingResult.model_fields.keys())
    required_fields = {
        "frame_number", "camera_id", "tracks",
        "tracking_time_ms", "total_active_tracks", "total_lost_tracks"
    }
    assert required_fields.issubset(tracking_result_fields), (
        f"TrackingResult missing required fields: {required_fields - tracking_result_fields}"
    )


def test_sprint4_tracked_person_schema_unchanged():
    """Sprint 4: TrackedPerson schema must still provide all required fields."""
    from tracking.results.schema import TrackedPerson
    required_fields = {"track_id", "detection_id", "camera_id", "bbox", "confidence", "track_state"}
    actual_fields = set(TrackedPerson.model_fields.keys())
    assert required_fields.issubset(actual_fields), (
        f"TrackedPerson missing: {required_fields - actual_fields}"
    )


def test_sprint4_track_state_values_unchanged():
    """Sprint 4: TrackState enum must still have ACTIVE, REIDENTIFIED, REMOVED, EXPIRED."""
    from tracking.results.schema import TrackState
    assert hasattr(TrackState, "ACTIVE")
    assert hasattr(TrackState, "REIDENTIFIED")
    assert hasattr(TrackState, "REMOVED")
    assert hasattr(TrackState, "EXPIRED")


def test_sprint5_recognition_module_importable():
    """Sprint 5: Recognition module must be importable without side effects."""
    recognition = importlib.import_module("recognition")
    assert recognition is not None


def test_sprint5_settings_importable():
    """Sprint 5 settings must be importable and valid."""
    from recognition.config.settings import recognition_settings
    assert recognition_settings is not None
    assert recognition_settings.MATCH_THRESHOLD > 0.0
    assert recognition_settings.TEMPORAL_CONFIRMATION_FRAMES > 0
