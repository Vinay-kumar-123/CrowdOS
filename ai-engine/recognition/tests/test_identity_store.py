"""Tests for InMemoryIdentityStore."""
import numpy as np
import pytest
from recognition.models.in_memory_store import InMemoryIdentityStore


def make_vec(seed: int, dim: int = 512) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_store_add_and_list():
    store = InMemoryIdentityStore()
    store.add_identity("alice", make_vec(1))
    store.add_identity("bob", make_vec(2))
    identities = store.list_identities()
    assert "alice" in identities
    assert "bob" in identities
    assert len(identities) == 2


def test_store_get_identity():
    store = InMemoryIdentityStore()
    vec = make_vec(10)
    store.add_identity("carol", vec)
    retrieved = store.get_identity("carol")
    assert retrieved is not None
    assert np.allclose(retrieved, vec, atol=1e-5)


def test_store_get_missing_identity_returns_none():
    store = InMemoryIdentityStore()
    assert store.get_identity("does_not_exist") is None


def test_store_remove_identity():
    store = InMemoryIdentityStore()
    store.add_identity("dave", make_vec(3))
    assert "dave" in store.list_identities()
    store.remove_identity("dave")
    assert "dave" not in store.list_identities()


def test_store_clear():
    store = InMemoryIdentityStore()
    store.add_identity("p1", make_vec(1))
    store.add_identity("p2", make_vec(2))
    store.clear()
    assert store.list_identities() == []


def test_store_get_all_embeddings():
    store = InMemoryIdentityStore()
    store.add_identity("x1", make_vec(1))
    store.add_identity("x2", make_vec(2))
    ids, matrix = store.get_all_embeddings()
    assert len(ids) == 2
    assert matrix.shape == (2, 512)


def test_store_empty_get_all_embeddings():
    store = InMemoryIdentityStore()
    ids, matrix = store.get_all_embeddings()
    assert ids == []
    assert matrix.shape[0] == 0


def test_store_thread_safety():
    """Concurrent writes to the store must not corrupt state."""
    import threading
    store = InMemoryIdentityStore()
    errors = []

    def add_many(thread_id: int):
        try:
            for i in range(50):
                store.add_identity(f"p_t{thread_id}_{i}", make_vec(thread_id * 100 + i))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_many, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(store.list_identities()) == 250
