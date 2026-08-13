"""Tests for face quality assessment module."""
import numpy as np
import pytest
import cv2
from recognition.utils.quality import assess_face_quality
from recognition.results.schema import FaceQualityStatus


def make_sharp_face(size: int = 80) -> np.ndarray:
    """Generate a sharp, high-contrast synthetic face crop."""
    img = np.random.randint(100, 200, (size, size, 3), dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (size - 10, size - 10), (255, 255, 255), 2)
    return img


def make_blurry_face(size: int = 80) -> np.ndarray:
    """Generate a heavily blurred face crop."""
    img = make_sharp_face(size)
    return cv2.GaussianBlur(img, (31, 31), 10)


def test_quality_good_face():
    face = make_sharp_face(100)
    result = assess_face_quality(face, detection_confidence=0.90)
    assert result.face_width == 100
    assert result.blur_score > 0.0


def test_quality_too_small_face():
    face = np.ones((20, 20, 3), dtype=np.uint8) * 150
    result = assess_face_quality(face, detection_confidence=0.90, min_size=32)
    assert result.status == FaceQualityStatus.QUALITY_TOO_SMALL
    assert result.is_usable is False


def test_quality_low_confidence():
    face = make_sharp_face(80)
    result = assess_face_quality(face, detection_confidence=0.10, min_confidence=0.50)
    assert result.status == FaceQualityStatus.QUALITY_LOW_CONFIDENCE
    assert result.is_usable is False


def test_quality_blurry_face():
    face = make_blurry_face(80)
    result = assess_face_quality(face, detection_confidence=0.90, blur_thresh=100.0)
    assert result.status == FaceQualityStatus.QUALITY_BLURRY
    assert result.is_usable is False


def test_quality_none_image_returns_poor():
    result = assess_face_quality(None, detection_confidence=0.90)
    assert result.status == FaceQualityStatus.QUALITY_POOR
    assert result.is_usable is False


def test_quality_empty_array_returns_poor():
    result = assess_face_quality(np.array([]), detection_confidence=0.90)
    assert result.status == FaceQualityStatus.QUALITY_POOR
    assert result.is_usable is False


def test_quality_score_in_range():
    face = make_sharp_face(100)
    result = assess_face_quality(face, detection_confidence=0.90)
    assert 0.0 <= result.score <= 1.0
