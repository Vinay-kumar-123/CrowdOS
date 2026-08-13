import threading
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from recognition.models.base_store import BaseIdentityStore


class InMemoryIdentityStore(BaseIdentityStore):
    """
    Thread-safe In-Memory Reference Identity Store for Sprint 5.
    Stores identity_id -> reference_embedding (512-D L2-normalized numpy array).

    PRIVACY NOTICE: Strictly in-memory store for synthetic dev/test data.
    Zero persistent database (MongoDB/SQL) integration.
    """

    def __init__(self):
        self._store: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add_identity(
        self,
        identity_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not identity_id or embedding is None:
            return False

        vec = np.asarray(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm  # Ensure L2 normalization

        with self._lock:
            self._store[identity_id] = vec
            self._metadata[identity_id] = metadata or {}
        return True

    def get_identity(self, identity_id: str) -> Optional[np.ndarray]:
        with self._lock:
            vec = self._store.get(identity_id)
            return vec.copy() if vec is not None else None

    def remove_identity(self, identity_id: str) -> bool:
        with self._lock:
            if identity_id in self._store:
                del self._store[identity_id]
                if identity_id in self._metadata:
                    del self._metadata[identity_id]
                return True
            return False

    def list_identities(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def get_all_embeddings(self) -> Tuple[List[str], np.ndarray]:
        with self._lock:
            ids = list(self._store.keys())
            if not ids:
                return [], np.empty((0, 512), dtype=np.float32)
            matrix = np.vstack([self._store[i] for i in ids])
            return ids, matrix

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._metadata.clear()
