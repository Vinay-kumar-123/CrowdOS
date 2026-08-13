from typing import Dict, Any
import numpy as np
from recognition.models.base_matcher import BaseFaceMatcher, MatchResult
from recognition.models.base_store import BaseIdentityStore
from recognition.results.schema import RecognitionStatus
from recognition.config.settings import recognition_settings


class CosineMatcher(BaseFaceMatcher):
    """
    Cosine Similarity Matcher for 512-D L2-normalized face embeddings.
    Computes dot product similarity score against identity reference store.
    """

    def __init__(
        self,
        match_threshold: float = recognition_settings.MATCH_THRESHOLD,
        low_confidence_threshold: float = recognition_settings.LOW_CONFIDENCE_THRESHOLD
    ):
        self.match_threshold = match_threshold
        self.low_confidence_threshold = low_confidence_threshold

    def match_embedding(
        self,
        embedding: np.ndarray,
        identity_store: BaseIdentityStore
    ) -> MatchResult:
        if embedding is None or embedding.size == 0:
            return MatchResult(
                identity_id="UNKNOWN",
                similarity_score=0.0,
                status=RecognitionStatus.UNKNOWN,
                threshold_used=self.match_threshold
            )

        # Ensure query vector is L2 normalized
        query_vec = np.asarray(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(query_vec)
        if norm > 1e-6:
            query_vec = query_vec / norm

        ids, ref_matrix = identity_store.get_all_embeddings()
        if not ids or ref_matrix.shape[0] == 0:
            return MatchResult(
                identity_id="UNKNOWN",
                similarity_score=0.0,
                status=RecognitionStatus.UNKNOWN,
                threshold_used=self.match_threshold
            )

        # Compute cosine similarity dot products (since vectors are L2-normalized)
        similarities = np.dot(ref_matrix, query_vec)
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        best_id = ids[best_idx]

        if best_score >= self.match_threshold:
            return MatchResult(
                identity_id=best_id,
                similarity_score=best_score,
                status=RecognitionStatus.MATCHED,
                threshold_used=self.match_threshold
            )
        elif best_score >= self.low_confidence_threshold:
            return MatchResult(
                identity_id=best_id,
                similarity_score=best_score,
                status=RecognitionStatus.LOW_CONFIDENCE,
                threshold_used=self.match_threshold
            )
        else:
            return MatchResult(
                identity_id="UNKNOWN",
                similarity_score=best_score,
                status=RecognitionStatus.UNKNOWN,
                threshold_used=self.match_threshold
            )

    def get_info(self) -> Dict[str, Any]:
        return {
            "matcher_name": "CosineMatcher",
            "match_threshold": self.match_threshold,
            "low_confidence_threshold": self.low_confidence_threshold
        }
