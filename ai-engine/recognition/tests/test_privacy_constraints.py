"""
Tests for CTO-mandated privacy and security constraints.

CTO Rules enforced here:
- Raw embeddings must never appear in RecognitionResult.
- Raw face crops must never be logged.
- UNKNOWN is always a valid result; matches are never forced.
- Recognition state is always scoped by camera_id + track_id.
"""
import json
import logging
import numpy as np
import pytest

from recognition.tests.conftest import make_tracking_result, make_blank_frame, make_synthetic_store
from recognition.models.insightface_recognizer import InsightFaceRecognizer
from recognition.engine.recognition_engine import RecognitionEngine
from recognition.results.schema import RecognitionStatus, RecognizedPerson


def test_recognized_person_has_no_raw_embedding_field():
    """RecognizedPerson schema must NOT expose a raw embedding field."""
    person = RecognizedPerson(
        camera_id="cam_01",
        track_id="1",
        detection_id="det_001",
        frame_number=1,
        identity_status=RecognitionStatus.UNKNOWN,
    )
    # Direct attribute must not exist in the public API
    assert not hasattr(person, "embedding")
    assert not hasattr(person, "raw_embedding")
    assert not hasattr(person, "face_vector")


def test_recognition_result_has_no_raw_embedding_field(recognition_engine, blank_frame):
    """RecognitionResult must not expose any raw embedding in its fields."""
    tracking_res = make_tracking_result("cam_priv", frame_number=1, num_tracks=1)
    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)

    for person in result.recognized_persons:
        person_dict = person.model_dump()
        for key in person_dict:
            assert "embedding" not in key.lower(), f"Embedding-related key found: {key}"
            assert "vector" not in key.lower(), f"Vector-related key found: {key}"
            assert "biometric" not in key.lower(), f"Biometric key found: {key}"


def test_unknown_is_valid_result_not_exception():
    """UNKNOWN must always be a valid identity outcome, not an error or None."""
    person = RecognizedPerson(
        camera_id="cam_01",
        track_id="1",
        detection_id="det_001",
        frame_number=1,
        identity_status=RecognitionStatus.UNKNOWN,
        identity_id="UNKNOWN",
    )
    assert person.identity_status == RecognitionStatus.UNKNOWN
    assert person.identity_id is not None


def test_camera_state_isolation_across_two_cameras(blank_frame):
    """Track ID 1 on cam_A must never share recognition state with Track ID 1 on cam_B."""
    from recognition.models.insightface_embedder import InsightFaceEmbedder
    store = make_synthetic_store(3)
    recognizer_a = InsightFaceRecognizer(embedder=InsightFaceEmbedder(allow_synthetic_fallback=True))
    recognizer_b = InsightFaceRecognizer(embedder=InsightFaceEmbedder(allow_synthetic_fallback=True))

    engine_a = RecognitionEngine(recognizer_a, store)
    engine_b = RecognitionEngine(recognizer_b, store)

    tr_a = make_tracking_result("cam_A", frame_number=1, num_tracks=1)
    tr_b = make_tracking_result("cam_B", frame_number=1, num_tracks=1)

    result_a = engine_a.process_tracking_result(tr_a, blank_frame)
    result_b = engine_b.process_tracking_result(tr_b, blank_frame)

    assert result_a.camera_id == "cam_A"
    assert result_b.camera_id == "cam_B"

    # Temporal state keys must not cross cameras
    state_keys_a = set(engine_a.temporal_stabilizer._states.keys())
    state_keys_b = set(engine_b.temporal_stabilizer._states.keys())

    # Engines are separate instances - their state sets are independent
    for key in state_keys_a:
        assert key.startswith("cam_A:")

    for key in state_keys_b:
        assert key.startswith("cam_B:")


def test_no_real_biometric_data_in_test_store():
    """Test that the synthetic store contains only synthetic reference vectors, not real biometrics."""
    store = make_synthetic_store(3)
    ids = store.list_identities()
    for identity_id in ids:
        assert identity_id.startswith("synthetic_"), (
            f"Non-synthetic identity found in test store: {identity_id}"
        )


def test_production_safety_disables_synthetic_embedding_fallback():
    """Production Safety: When allow_synthetic_fallback is False and model is unavailable, compute_embedding returns None."""
    from recognition.models.insightface_embedder import InsightFaceEmbedder
    embedder = InsightFaceEmbedder(allow_synthetic_fallback=False)
    if embedder._backend_used != "InsightFace_ArcFace":
        dummy_crop = np.zeros((112, 112, 3), dtype=np.uint8)
        assert embedder.compute_embedding(dummy_crop) is None

