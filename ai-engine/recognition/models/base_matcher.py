from abc import ABC, abstractmethod
from typing import Dict, Any
import numpy as np
from recognition.models.base_store import BaseIdentityStore
from recognition.results.schema import RecognitionStatus


class MatchResult:
    """
    Standardized result payload of a similarity matching evaluation.
    """
    def __init__(
        self,
        identity_id: str,
        similarity_score: float,
        status: RecognitionStatus,
        threshold_used: float
    ):
        self.identity_id = identity_id
        self.similarity_score = float(similarity_score)
        self.status = status
        self.threshold_used = float(threshold_used)


class BaseFaceMatcher(ABC):
    """
    Abstract Base Interface for Face Similarity Matchers.
    """

    @abstractmethod
    def match_embedding(
        self,
        embedding: np.ndarray,
        identity_store: BaseIdentityStore
    ) -> MatchResult:
        """
        Match a query embedding against identity reference store.
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get matcher algorithm information.
        """
        pass
