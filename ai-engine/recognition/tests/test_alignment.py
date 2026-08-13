"""Tests for face alignment module."""
import numpy as np
import pytest
from recognition.alignment.aligner import align_face_5point, ARCFACE_REF_5PTS


def make_test_landmarks(offset_x: float = 0.0, offset_y: float = 0.0) -> np.ndarray:
    """Synthetic 5-point landmarks."""
    return np.array([
        [30 + offset_x, 40 + offset_y],
        [70 + offset_x, 40 + offset_y],
        [50 + offset_x, 60 + offset_y],
        [35 + offset_x, 80 + offset_y],
        [65 + offset_x, 80 + offset_y],
    ], dtype=np.float32)


def test_alignment_with_landmarks_returns_correct_size():
    face = np.random.randint(0, 255, (120, 120, 3), dtype=np.uint8)
    landmarks = make_test_landmarks()
    aligned = align_face_5point(face, landmarks=landmarks, output_size=(112, 112))
    assert aligned.shape == (112, 112, 3)


def test_alignment_without_landmarks_falls_back_to_resize():
    face = np.random.randint(0, 255, (200, 150, 3), dtype=np.uint8)
    aligned = align_face_5point(face, landmarks=None, output_size=(112, 112))
    assert aligned.shape == (112, 112, 3)


def test_alignment_none_image_returns_zeros():
    aligned = align_face_5point(None, landmarks=None)
    assert aligned.shape[0] == 112
    assert aligned.shape[1] == 112
    assert np.all(aligned == 0)


def test_alignment_empty_image_returns_zeros():
    aligned = align_face_5point(np.array([]), landmarks=None)
    assert aligned.shape == (112, 112, 3)


def test_alignment_custom_output_size():
    face = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
    aligned = align_face_5point(face, landmarks=None, output_size=(64, 64))
    assert aligned.shape == (64, 64, 3)


def test_alignment_invalid_landmarks_shape_falls_back():
    face = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
    bad_landmarks = np.array([[10, 20], [30, 40]], dtype=np.float32)  # Wrong shape
    aligned = align_face_5point(face, landmarks=bad_landmarks, output_size=(112, 112))
    assert aligned.shape == (112, 112, 3)
