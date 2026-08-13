from typing import List, Tuple, Sequence, Any
import numpy as np
from tracking.utils.bounding_box import iou_batch

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def linear_assignment(
    cost_matrix: np.ndarray,
    thresh: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Solve linear assignment problem given a cost matrix and cost threshold.
    Returns:
      matches: array of shape (N, 2) with (row_idx, col_idx)
      unmatched_rows: array of unmatched row indices
      unmatched_cols: array of unmatched column indices
    """
    if cost_matrix.size == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(cost_matrix.shape[0], dtype=int),
            np.arange(cost_matrix.shape[1], dtype=int)
        )

    if HAS_SCIPY:
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
    else:
        # Fallback greedy assignment if scipy is unavailable
        row_ind, col_ind = [], []
        costs_flat = []
        for r in range(cost_matrix.shape[0]):
            for c in range(cost_matrix.shape[1]):
                costs_flat.append((cost_matrix[r, c], r, c))
        costs_flat.sort(key=lambda x: x[0])
        used_r, used_c = set(), set()
        for cost, r, c in costs_flat:
            if r not in used_r and c not in used_c:
                used_r.add(r)
                used_c.add(c)
                row_ind.append(r)
                col_ind.append(c)
        row_ind = np.array(row_ind, dtype=int)
        col_ind = np.array(col_ind, dtype=int)

    matches, unmatched_a, unmatched_b = [], [], []

    for val in range(cost_matrix.shape[0]):
        if val not in row_ind:
            unmatched_a.append(val)
    for val in range(cost_matrix.shape[1]):
        if val not in col_ind:
            unmatched_b.append(val)

    for r, c in zip(row_ind, col_ind):
        if cost_matrix[r, c] > thresh:
            unmatched_a.append(r)
            unmatched_b.append(c)
        else:
            matches.append([r, c])

    if len(matches) == 0:
        matches = np.empty((0, 2), dtype=int)
    else:
        matches = np.array(matches, dtype=int)

    return matches, np.array(unmatched_a, dtype=int), np.array(unmatched_b, dtype=int)


def iou_distance(
    atracks: Sequence[Any],
    btracks: Sequence[Any]
) -> np.ndarray:
    """
    Compute IoU distance matrix between two track/detection sequences.
    Distance = 1.0 - IoU.
    """
    if len(atracks) == 0 or len(btracks) == 0:
        return np.zeros((len(atracks), len(btracks)), dtype=np.float32)

    atlbrs = [track.tlbr for track in atracks]
    btlbrs = [track.tlbr for track in btracks]

    ious = iou_batch(np.asarray(atlbrs), np.asarray(btlbrs))
    cost_matrix = 1.0 - ious
    return cost_matrix
