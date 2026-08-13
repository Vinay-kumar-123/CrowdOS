"""Tests for RecognitionEngine — no-face, error handling, metrics."""
import uuid
import numpy as np
import pytest

from recognition.tests.conftest import (
    make_tracking_result, make_blank_frame, make_synthetic_store
)
from recognition.models.insightface_recognizer import InsightFaceRecognizer
from recognition.engine.recognition_engine import RecognitionEngine
from recognition.results.schema import RecognitionStatus
from tracking.results.schema import TrackState


def test_recognition_engine_processes_tracking_result(recognition_engine, blank_frame):
    tracking_res = make_tracking_result("cam_engine", frame_number=1, num_tracks=1)
    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)

    assert result.camera_id == "cam_engine"
    assert result.frame_number == 1
    assert result.total_tracked_persons == 1
    assert len(result.recognized_persons) == 1


def test_recognition_engine_empty_tracking_result(recognition_engine, blank_frame):
    tracking_res = make_tracking_result("cam_engine", frame_number=1, num_tracks=0)
    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)
    assert result.total_tracked_persons == 0
    assert result.recognized_persons == []


def test_recognition_engine_no_face_on_blank_frame(recognition_engine, blank_frame):
    """Blank frame should yield NO_FACE or QUALITY_REJECTED — never forced match."""
    tracking_res = make_tracking_result("cam_noface", frame_number=1, num_tracks=1)
    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)

    for person in result.recognized_persons:
        assert person.identity_status in (
            RecognitionStatus.NO_FACE,
            RecognitionStatus.QUALITY_REJECTED,
            RecognitionStatus.UNKNOWN,
            RecognitionStatus.ERROR
        )
        # Must never force a match on blank frame
        assert person.identity_status != RecognitionStatus.MATCHED


def test_recognition_engine_skips_removed_tracks(recognition_engine, blank_frame):
    tracking_res = make_tracking_result("cam_removed", frame_number=1, num_tracks=1,
                                        track_state=TrackState.REMOVED)
    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)
    assert len(result.recognized_persons) == 0


def test_recognition_engine_statistics(recognition_engine, blank_frame):
    tracking_res = make_tracking_result("cam_stats", frame_number=1, num_tracks=1)
    recognition_engine.process_tracking_result(tracking_res, blank_frame)
    stats = recognition_engine.get_statistics()
    assert "metrics" in stats
    assert stats["metrics"]["total_frames_processed"] == 1


def test_recognition_engine_preserves_traceability_chain(recognition_engine, blank_frame):
    """CTO Rule: detection_id -> track_id -> face_id -> identity_id must be preserved."""
    tracking_res = make_tracking_result("cam_chain", frame_number=5, num_tracks=1)
    original_detection_id = tracking_res.tracks[0].detection_id
    original_track_id = tracking_res.tracks[0].track_id

    result = recognition_engine.process_tracking_result(tracking_res, blank_frame)

    person = result.recognized_persons[0]
    assert person.track_id == original_track_id
    assert person.detection_id == original_detection_id
    assert person.camera_id == "cam_chain"
    assert person.frame_number == 5
