"""Tests for RecognitionValidator schema integrity and frame-ordering."""
import pytest
from datetime import datetime, timezone
from recognition.validation.validator import RecognitionValidator
from recognition.results.schema import (
    RecognitionResult, RecognizedPerson, RecognitionStatus, FaceQualityStatus
)
from detection.results.schema import BoundingBox


def make_valid_person(
    camera_id="cam_01", track_id="1", detection_id="det_001", frame_number=1
) -> RecognizedPerson:
    return RecognizedPerson(
        camera_id=camera_id,
        track_id=track_id,
        detection_id=detection_id,
        frame_number=frame_number,
        identity_id="UNKNOWN",
        identity_status=RecognitionStatus.UNKNOWN,
        face_confidence=0.85,
        face_quality_score=0.75,
        similarity_score=0.0
    )


def make_valid_result(camera_id="cam_01", frame_number=1) -> RecognitionResult:
    return RecognitionResult(
        frame_number=frame_number,
        camera_id=camera_id,
        total_tracked_persons=1,
        total_faces_detected=1,
        total_faces_matched=0,
        total_faces_unknown=1,
        recognition_time_ms=5.0,
        recognized_persons=[make_valid_person(camera_id=camera_id, frame_number=frame_number)],
        recognizer_name="TestRecognizer",
        recognizer_version="5.0.0"
    )


def test_validator_accepts_valid_result():
    validator = RecognitionValidator()
    result = make_valid_result()
    ok, errors = validator.validate_recognition_result(result)
    assert ok is True
    assert errors == []


def test_validator_detects_negative_frame_number():
    validator = RecognitionValidator()
    result = make_valid_result(frame_number=-1)
    result.recognized_persons[0].frame_number = -1
    ok, errors = validator.validate_recognition_result(result)
    assert ok is False


def test_validator_detects_frame_regression():
    validator = RecognitionValidator()
    validator.validate_recognition_result(make_valid_result("cam_r", 10))
    ok, errors = validator.validate_recognition_result(make_valid_result("cam_r", 5))
    assert ok is False
    assert any("regression" in e for e in errors)


def test_validator_accepts_sequential_frames():
    validator = RecognitionValidator()
    for i in range(1, 11):
        ok, errors = validator.validate_recognition_result(make_valid_result("cam_seq", i))
        assert ok is True


def test_validator_detects_invalid_bbox():
    validator = RecognitionValidator()
    person = make_valid_person()
    person.face_bbox = BoundingBox(x1=200.0, y1=100.0, x2=100.0, y2=200.0)  # x1 > x2
    result = make_valid_result()
    result.recognized_persons = [person]
    ok, errors = validator.validate_recognition_result(result)
    assert ok is False


def test_validator_detects_confidence_out_of_bounds():
    validator = RecognitionValidator()
    person = make_valid_person()
    person.face_confidence = 1.5  # Out of bounds
    result = make_valid_result()
    result.recognized_persons = [person]
    ok, errors = validator.validate_recognition_result(result)
    assert ok is False


def test_validator_camera_isolation():
    """Frame regression on cam_A must not affect cam_B validation."""
    validator = RecognitionValidator()
    validator.validate_recognition_result(make_valid_result("cam_A", 10))
    # Regression on cam_A
    ok_a, _ = validator.validate_recognition_result(make_valid_result("cam_A", 5))
    # cam_B at any frame is independent
    ok_b, _ = validator.validate_recognition_result(make_valid_result("cam_B", 1))
    assert ok_a is False
    assert ok_b is True
