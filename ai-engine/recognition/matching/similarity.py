import numpy as np
from typing import Tuple


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two 1D vectors.
    Assumes inputs are already L2-normalized (dot product == cosine similarity).
    Returns float in range [-1.0, 1.0].
    """
    a = np.asarray(vec_a, dtype=np.float32).flatten()
    b = np.asarray(vec_b, dtype=np.float32).flatten()

    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))

    if norm_a < 1e-6 or norm_b < 1e-6:
        return 0.0

    return float(np.dot(a / norm_a, b / norm_b))


def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Cosine distance: 1 - cosine_similarity (range [0, 2]).
    """
    return 1.0 - cosine_similarity(vec_a, vec_b)


def batch_cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between a single query vector and a 2D matrix of reference vectors.
    Returns 1D array of similarity scores of shape (N,).
    """
    q = np.asarray(query, dtype=np.float32).flatten()
    M = np.asarray(matrix, dtype=np.float32)

    q_norm = float(np.linalg.norm(q))
    if q_norm < 1e-6 or M.shape[0] == 0:
        return np.zeros(M.shape[0], dtype=np.float32)

    q_unit = q / q_norm
    row_norms = np.linalg.norm(M, axis=1, keepdims=True)
    row_norms = np.where(row_norms < 1e-6, 1.0, row_norms)
    M_unit = M / row_norms

    return np.dot(M_unit, q_unit).astype(np.float32)
