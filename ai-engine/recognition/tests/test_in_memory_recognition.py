"""Tests for InMemoryIdentityStore with in-memory recognition pipeline (fast path, no InsightFace models needed)."""
import numpy as np
import pytest

from recognition.models.in_memory_store import InMemoryIdentityStore
from recognition.models.cosine_matcher import CosineMatcher
from recognition.results.schema import RecognitionStatus


def make_unit_vec(seed: int = 1, dim: int = 512) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_match_same_vector_returns_matched():
    """Identical query and reference vectors should always match at threshold 0.50."""
    store = InMemoryIdentityStore()
    ref = make_unit_vec(seed=7)
    store.add_identity("person_007", ref)

    matcher = CosineMatcher(match_threshold=0.50)
    result = matcher.match_embedding(ref.copy(), store)

    assert result.status == RecognitionStatus.MATCHED
    assert result.identity_id == "person_007"
    assert result.similarity_score > 0.99


def test_match_opposite_vector_returns_unknown():
    """Vectors in opposite directions should not match."""
    store = InMemoryIdentityStore()
    ref = make_unit_vec(seed=1)
    store.add_identity("person_001", ref)

    matcher = CosineMatcher(match_threshold=0.60)
    result = matcher.match_embedding(-ref, store)

    assert result.status in (RecognitionStatus.UNKNOWN, RecognitionStatus.LOW_CONFIDENCE)
    # Critical: must never force a match on anti-correlated vectors
    assert result.status != RecognitionStatus.MATCHED


def test_match_top_1_from_multiple_identities():
    """The closest identity in embedding space should be returned."""
    store = InMemoryIdentityStore()
    ref_a = make_unit_vec(seed=10)
    ref_b = make_unit_vec(seed=20)

    store.add_identity("person_A", ref_a)
    store.add_identity("person_B", ref_b)

    matcher = CosineMatcher(match_threshold=0.50)
    result = matcher.match_embedding(ref_a.copy(), store)

    assert result.identity_id == "person_A"
    assert result.status == RecognitionStatus.MATCHED
