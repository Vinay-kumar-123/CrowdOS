"""Tests for BaseFaceDetector, BaseFaceEmbedder, BaseFaceMatcher, BaseFaceRecognizer, BaseIdentityStore abstract contracts."""
import pytest
import numpy as np
from recognition.models.base_detector import BaseFaceDetector
from recognition.models.base_embedder import BaseFaceEmbedder
from recognition.models.base_matcher import BaseFaceMatcher
from recognition.models.base_recognizer import BaseFaceRecognizer
from recognition.models.base_store import BaseIdentityStore
from recognition.results.schema import RecognitionStatus
from recognition.models.base_matcher import MatchResult


def test_base_face_detector_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseFaceDetector()


def test_base_face_embedder_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseFaceEmbedder()


def test_base_face_matcher_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseFaceMatcher()


def test_base_face_recognizer_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseFaceRecognizer()


def test_base_identity_store_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseIdentityStore()


class ConcreteDetector(BaseFaceDetector):
    def initialize(self): return True
    def detect_faces(self, image, person_bbox=None): return []
    def get_info(self): return {"name": "ConcreteDetector"}


class ConcreteEmbedder(BaseFaceEmbedder):
    def initialize(self): return True
    def compute_embedding(self, face): return np.ones(512, dtype=np.float32)
    def get_embedding_dim(self): return 512
    def get_info(self): return {"name": "ConcreteEmbedder"}


class ConcreteStore(BaseIdentityStore):
    def __init__(self): self._data = {}
    def add_identity(self, id_, emb, meta=None): self._data[id_] = emb; return True
    def get_identity(self, id_): return self._data.get(id_)
    def remove_identity(self, id_): self._data.pop(id_, None); return True
    def list_identities(self): return list(self._data.keys())
    def get_all_embeddings(self):
        ids = list(self._data.keys())
        if not ids: return [], np.empty((0, 512), dtype=np.float32)
        return ids, np.vstack([self._data[i] for i in ids])
    def clear(self): self._data.clear()


class ConcreteMatcher(BaseFaceMatcher):
    def match_embedding(self, emb, store):
        return MatchResult("UNKNOWN", 0.0, RecognitionStatus.UNKNOWN, 0.60)
    def get_info(self): return {"name": "ConcreteMatcher"}


def test_concrete_detector_implements_contract():
    d = ConcreteDetector()
    assert d.initialize() is True
    assert d.detect_faces(np.zeros((100, 100, 3), dtype=np.uint8)) == []


def test_concrete_embedder_implements_contract():
    e = ConcreteEmbedder()
    assert e.initialize() is True
    emb = e.compute_embedding(np.zeros((112, 112, 3), dtype=np.uint8))
    assert emb is not None and emb.shape == (512,)


def test_concrete_store_implements_contract():
    store = ConcreteStore()
    vec = np.ones(512, dtype=np.float32) / np.sqrt(512)
    assert store.add_identity("test_001", vec) is True
    assert "test_001" in store.list_identities()
    store.clear()
    assert store.list_identities() == []


def test_concrete_matcher_returns_unknown_on_empty_store():
    store = ConcreteStore()
    matcher = ConcreteMatcher()
    result = matcher.match_embedding(np.ones(512, dtype=np.float32), store)
    assert result.status == RecognitionStatus.UNKNOWN
