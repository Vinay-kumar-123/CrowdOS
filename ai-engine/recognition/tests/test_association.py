"""Tests for TrackFaceAssociator geometric face-to-track association."""
import pytest
from recognition.association.track_face_associator import (
    TrackFaceAssociator, is_face_within_person_box, compute_iou
)
from recognition.models.base_detector import FaceDetectionItem


def make_face_item(x1, y1, x2, y2, confidence=0.90):
    return FaceDetectionItem(
        face_id="face_test_001",
        bbox=[x1, y1, x2, y2],
        confidence=confidence,
        landmarks=None,
        crop=None
    )


def test_iou_overlapping_boxes():
    iou = compute_iou([0, 0, 100, 100], [50, 50, 150, 150])
    assert 0.0 < iou < 1.0


def test_iou_identical_boxes():
    iou = compute_iou([10, 10, 110, 110], [10, 10, 110, 110])
    assert abs(iou - 1.0) < 1e-5


def test_iou_non_overlapping_boxes():
    iou = compute_iou([0, 0, 50, 50], [100, 100, 200, 200])
    assert iou == 0.0


def test_face_within_person_box_contained():
    # Face clearly inside person box
    person = [100.0, 50.0, 300.0, 400.0]
    face = [130.0, 80.0, 250.0, 200.0]
    assert is_face_within_person_box(face, person) is True


def test_face_outside_person_box_rejected():
    person = [100.0, 50.0, 200.0, 350.0]
    face = [400.0, 400.0, 500.0, 500.0]  # Far outside
    assert is_face_within_person_box(face, person) is False


def test_associator_returns_best_face_within_track():
    associator = TrackFaceAssociator()
    person_bbox = [100.0, 50.0, 300.0, 400.0]

    face_inside = make_face_item(120, 80, 280, 220, confidence=0.92)
    face_outside = make_face_item(500, 500, 600, 600, confidence=0.98)

    result = associator.associate(
        person_bbox=person_bbox,
        face_detections=[face_inside, face_outside],
        camera_id="cam_01",
        track_id="1",
        detection_id="det_001"
    )
    assert result is not None
    assert result.face_id == face_inside.face_id


def test_associator_rejects_non_overlapping_face():
    associator = TrackFaceAssociator()
    person_bbox = [100.0, 50.0, 200.0, 350.0]
    face_outside = make_face_item(500, 500, 600, 600, confidence=0.95)

    result = associator.associate(
        person_bbox=person_bbox,
        face_detections=[face_outside],
        camera_id="cam_01",
        track_id="1",
        detection_id="det_001"
    )
    assert result is None


def test_associator_empty_faces_returns_none():
    associator = TrackFaceAssociator()
    result = associator.associate(
        person_bbox=[100.0, 50.0, 200.0, 350.0],
        face_detections=[],
        camera_id="cam_01",
        track_id="1",
        detection_id="det_001"
    )
    assert result is None


def test_associator_multiple_faces_returns_highest_confidence():
    associator = TrackFaceAssociator()
    person_bbox = [50.0, 50.0, 400.0, 450.0]

    face_low = make_face_item(80, 80, 200, 200, confidence=0.60)
    face_high = make_face_item(100, 100, 220, 220, confidence=0.95)

    result = associator.associate(
        person_bbox=person_bbox,
        face_detections=[face_low, face_high],
        camera_id="cam_01",
        track_id="2",
        detection_id="det_002"
    )
    assert result is not None
    assert result.confidence == 0.95
