from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class BaseFaceEmbedder(ABC):
    """
    Abstract Base Interface for all Face Embedders.
    Produces L2-normalized feature vectors for face recognition.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize embedding model and resources.
        """
        pass

    @abstractmethod
    def compute_embedding(self, aligned_face: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract L2-normalized feature vector from an aligned face crop.
        Returns 1D numpy array of shape (embedding_dimension,) or None on failure.
        """
        pass

    @abstractmethod
    def get_embedding_dim(self) -> int:
        """
        Get expected vector dimension (e.g. 512).
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get embedder metadata info.
        """
        pass
