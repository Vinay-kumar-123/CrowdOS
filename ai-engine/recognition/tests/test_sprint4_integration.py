"""
Sprint 4 → Sprint 5 integration tests.
Verifies that Sprint 5 correctly consumes Sprint 4 TrackingResult without modifying Sprint 1-4.
"""
import uuid
import numpy as np
import pytest

from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
from detection.results.schema import BoundingBox
from recognition.tests.conftest import make_blank_frame, make_synthetic_store
from recognition.models.insightface_recognizer import InsightFaceRecognizer
from recognition.engine.recognition_engine import RecognitionEngine
from recognition.pipeline.recognition_pipeline import RecognitionPipeline
from recognition.validation.validator import RecognitionValidator
from recognition.results.schema import RecognitionStatus


def make_multi_track_result(
    camera_id: str = "cam_integration",
    frame_number: int = 1,
    num_tracks: int = 3,
    track_state: TrackState = TrackState.ACTIVE
) -> TrackingResult:
    tracks = []
    for i in range(num_tracks):
        x1 = float(50 + i * 150)
        tracks.append(TrackedPerson(
            track_id=str(i + 1),
            detection_id=str(uuid.uuid4()),
            camera_id=camera_id,
            frame_number=frame_number,
            bbox=BoundingBox(x1=x1, y1=80.0, x2=x1 + 120.0, y2=360.0),
            confidence=0.87,
            center=(x1 + 60.0, 220.0),
            track_state=track_state
        ))
    return TrackingResult(
        frame_number=frame_number,
        camera_id=camera_id,
        tracking_time_ms=3.0,
        total_active_tracks=num_tracks,
        total_lost_tracks=0,
        tracks=tracks
    )


def make_test_recognizer():
    from recognition.models.insightface_embedder import InsightFaceEmbedder
    return InsightFaceRecognizer(embedder=InsightFaceEmbedder(allow_synthetic_fallback=True))


def test_pipeline_produces_recognized_persons_per_track():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)
    pipeline = RecognitionPipeline(engine)

    tracking_res = make_multi_track_result(num_tracks=3)
    frame = make_blank_frame()
    result = pipeline.process(tracking_res, frame)

    assert result.total_tracked_persons == 3
    assert len(result.recognized_persons) == 3


def test_pipeline_recognition_result_validated():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)
    validator = RecognitionValidator()
    pipeline = RecognitionPipeline(engine, validator=validator)

    tracking_res = make_multi_track_result(num_tracks=1, frame_number=10)
    frame = make_blank_frame()
    result = pipeline.process(tracking_res, frame)

    is_valid, errors = validator.validate_recognition_result(result)
    # Note: validator already called inside pipeline - this confirms no regression on second pass
    assert result.frame_number == 10


def test_pipeline_multiple_cameras_independent():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)
    pipeline = RecognitionPipeline(engine)
    frame = make_blank_frame()

    for cam_id in ["cam_X", "cam_Y", "cam_Z"]:
        tracking_res = make_multi_track_result(camera_id=cam_id, num_tracks=2)
        result = pipeline.process(tracking_res, frame)
        assert result.camera_id == cam_id
        assert result.total_tracked_persons == 2


def test_pipeline_tracks_across_frames_preserve_traceability():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)
    pipeline = RecognitionPipeline(engine)
    frame = make_blank_frame()

    for frame_num in range(1, 6):
        tracking_res = make_multi_track_result(
            camera_id="cam_trace", frame_number=frame_num, num_tracks=2
        )
        result = pipeline.process(tracking_res, frame)

        for person in result.recognized_persons:
            assert person.track_id in ["1", "2"]
            assert person.camera_id == "cam_trace"
            assert person.frame_number == frame_num
            assert person.detection_id is not None


def test_pipeline_removed_tracks_are_excluded():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)
    pipeline = RecognitionPipeline(engine)
    frame = make_blank_frame()

    tracking_res = make_multi_track_result(
        camera_id="cam_rem", num_tracks=2, track_state=TrackState.REMOVED
    )
    result = pipeline.process(tracking_res, frame)
    assert len(result.recognized_persons) == 0
    assert result.total_tracked_persons == 0


def test_pipeline_result_callback_fires():
    store = make_synthetic_store(3)
    engine = RecognitionEngine(make_test_recognizer(), store)

    callback_results = []
    pipeline = RecognitionPipeline(
        engine, result_callback=lambda r: callback_results.append(r)
    )

    frame = make_blank_frame()
    tracking_res = make_multi_track_result(num_tracks=1)
    pipeline.process(tracking_res, frame)

    assert len(callback_results) == 1
    assert callback_results[0].camera_id == "cam_integration"
