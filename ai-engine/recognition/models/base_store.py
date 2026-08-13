from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


class BaseIdentityStore(ABC):
    """
    Abstract Base Interface for Identity Reference Stores.
    Decouples similarity matching from storage backend.
    """

    @abstractmethod
    def add_identity(
        self,
        identity_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store reference embedding for an identity.
        """
        pass

    @abstractmethod
    def get_identity(self, identity_id: str) -> Optional[np.ndarray]:
        """
        Retrieve reference embedding for specified identity_id.
        """
        pass

    @abstractmethod
    def remove_identity(self, identity_id: str) -> bool:
        """
        Remove identity from reference store.
        """
        pass

    @abstractmethod
    def list_identities(self) -> List[str]:
        """
        List all identity IDs present in store.
        """
        pass

    @abstractmethod
    def get_all_embeddings(self) -> Tuple[List[str], np.ndarray]:
        """
        Get tuple of (identity_ids list, 2D numpy array of shape (N, dim)).
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Purge all identities from store.
        """
        pass
