"""Tests for CosineMatcher identity matching logic."""
import numpy as np
import pytest
from recognition.models.cosine_matcher import CosineMatcher
from recognition.models.in_memory_store import InMemoryIdentityStore
from recognition.results.schema import RecognitionStatus


def make_unit_vec(dim: int = 512, seed: int = 1) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_matcher_known_identity_returns_matched():
    store = InMemoryIdentityStore()
    ref_vec = make_unit_vec(seed=10)
    store.add_identity("person_001", ref_vec)

    matcher = CosineMatcher(match_threshold=0.50, low_confidence_threshold=0.30)
    # Query with same vector → similarity = 1.0
    result = matcher.match_embedding(ref_vec.copy(), store)
    assert result.status == RecognitionStatus.MATCHED
    assert result.identity_id == "person_001"
    assert result.similarity_score > 0.99


def test_matcher_orthogonal_vector_returns_unknown():
    store = InMemoryIdentityStore()
    ref = np.zeros(512, dtype=np.float32)
    ref[0] = 1.0
    store.add_identity("person_001", ref)

    query = np.zeros(512, dtype=np.float32)
    query[1] = 1.0  # Orthogonal to ref → similarity = 0.0

    matcher = CosineMatcher(match_threshold=0.60, low_confidence_threshold=0.40)
    result = matcher.match_embedding(query, store)
    assert result.status == RecognitionStatus.UNKNOWN
    assert result.identity_id == "UNKNOWN"


def test_matcher_low_confidence_range():
    store = InMemoryIdentityStore()
    ref = make_unit_vec(seed=20)
    store.add_identity("person_002", ref)

    # Slightly perturbed vector for lower similarity
    noise = np.random.RandomState(99).randn(512).astype(np.float32) * 0.5
    query = ref + noise
    query = query / np.linalg.norm(query)

    matcher = CosineMatcher(match_threshold=0.99, low_confidence_threshold=0.40)
    result = matcher.match_embedding(query, store)
    # similarity < 0.99 but may be > 0.40 → LOW_CONFIDENCE or UNKNOWN
    assert result.status in (RecognitionStatus.LOW_CONFIDENCE, RecognitionStatus.UNKNOWN)


def test_matcher_empty_store_returns_unknown():
    store = InMemoryIdentityStore()
    matcher = CosineMatcher()
    result = matcher.match_embedding(make_unit_vec(), store)
    assert result.status == RecognitionStatus.UNKNOWN
    assert result.identity_id == "UNKNOWN"


def test_matcher_none_embedding_returns_unknown():
    store = InMemoryIdentityStore()
    store.add_identity("person_001", make_unit_vec(seed=5))
    matcher = CosineMatcher()
    result = matcher.match_embedding(None, store)
    assert result.status == RecognitionStatus.UNKNOWN


def test_matcher_threshold_used_is_preserved():
    store = InMemoryIdentityStore()
    store.add_identity("p1", make_unit_vec(seed=1))
    matcher = CosineMatcher(match_threshold=0.75, low_confidence_threshold=0.50)
    result = matcher.match_embedding(make_unit_vec(seed=1), store)
    assert result.threshold_used == 0.75


def test_unknown_is_always_valid_result():
    """CTO Rule: UNKNOWN must always be a valid result. Never force a match."""
    store = InMemoryIdentityStore()
    # Near-zero similarity scenario
    ref = np.zeros(512, dtype=np.float32)
    ref[0] = 1.0
    store.add_identity("p1", ref)

    query = np.zeros(512, dtype=np.float32)
    query[-1] = 1.0  # Opposite direction

    matcher = CosineMatcher(match_threshold=0.60)
    result = matcher.match_embedding(query, store)
    # Must not be MATCHED; UNKNOWN is valid
    assert result.status != RecognitionStatus.MATCHED
