from typing import Optional
import numpy as np
import math


def l2_normalize(embedding: np.ndarray) -> Optional[np.ndarray]:
    """
    Compute L2-normalized unit vector from a face embedding.
    Returns None if the embedding is invalid (NaN, Inf, zero-norm).
    """
    if embedding is None:
        return None

    vec = np.asarray(embedding, dtype=np.float32).flatten()

    if vec.size == 0:
        return None

    if np.any(np.isnan(vec)) or np.any(np.isinf(vec)):
        return None

    norm = float(np.linalg.norm(vec))
    if norm < 1e-6:
        return None

    return (vec / norm).astype(np.float32)


def validate_embedding(
    embedding: np.ndarray,
    expected_dim: int
) -> tuple[bool, str]:
    """
    Validate embedding vector against expected dimension and numerical validity.
    Returns (is_valid: bool, error_message: str).
    """
    if embedding is None:
        return False, "Embedding is None"

    vec = np.asarray(embedding, dtype=np.float32).flatten()

    if vec.size == 0:
        return False, "Empty embedding vector"

    if vec.size != expected_dim:
        return False, f"Dimension mismatch: expected {expected_dim}, got {vec.size}"

    if np.any(np.isnan(vec)):
        return False, "Embedding contains NaN values"

    if np.any(np.isinf(vec)):
        return False, "Embedding contains Inf values"

    norm = float(np.linalg.norm(vec))
    if norm < 1e-6:
        return False, "Embedding has zero or near-zero norm"

    return True, ""
