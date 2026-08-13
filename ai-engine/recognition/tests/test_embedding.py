"""Tests for embedding normalization and validation utilities."""
import numpy as np
import pytest
from recognition.embedding.normalizer import l2_normalize, validate_embedding


def test_l2_normalize_produces_unit_vector():
    raw = np.array([3.0, 4.0, 0.0], dtype=np.float32)
    result = l2_normalize(raw)
    assert result is not None
    assert abs(np.linalg.norm(result) - 1.0) < 1e-5


def test_l2_normalize_already_normalized():
    raw = np.ones(512, dtype=np.float32) / np.sqrt(512)
    result = l2_normalize(raw)
    assert result is not None
    assert abs(np.linalg.norm(result) - 1.0) < 1e-5


def test_l2_normalize_returns_none_on_zero_vector():
    raw = np.zeros(512, dtype=np.float32)
    result = l2_normalize(raw)
    assert result is None


def test_l2_normalize_returns_none_on_nan():
    raw = np.full(512, float('nan'), dtype=np.float32)
    result = l2_normalize(raw)
    assert result is None


def test_l2_normalize_returns_none_on_inf():
    raw = np.full(512, float('inf'), dtype=np.float32)
    result = l2_normalize(raw)
    assert result is None


def test_l2_normalize_returns_none_on_none():
    result = l2_normalize(None)
    assert result is None


def test_validate_embedding_correct():
    vec = np.ones(512, dtype=np.float32) / np.sqrt(512)
    ok, err = validate_embedding(vec, expected_dim=512)
    assert ok is True
    assert err == ""


def test_validate_embedding_dimension_mismatch():
    vec = np.ones(256, dtype=np.float32) / np.sqrt(256)
    ok, err = validate_embedding(vec, expected_dim=512)
    assert ok is False
    assert "Dimension mismatch" in err


def test_validate_embedding_nan_rejected():
    vec = np.full(512, float('nan'), dtype=np.float32)
    ok, err = validate_embedding(vec, expected_dim=512)
    assert ok is False
    assert "NaN" in err


def test_validate_embedding_zero_rejected():
    vec = np.zeros(512, dtype=np.float32)
    ok, err = validate_embedding(vec, expected_dim=512)
    assert ok is False
