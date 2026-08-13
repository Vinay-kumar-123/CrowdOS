from typing import List, Tuple
import numpy as np


def tlbr_to_tlwh(tlbr: np.ndarray) -> np.ndarray:
    """
    Convert bounding box from [x1, y1, x2, y2] to [x1, y1, w, h].
    """
    ret = np.asarray(tlbr, dtype=np.float32).copy()
    ret[..., 2:] -= ret[..., :2]
    return ret


def tlwh_to_tlbr(tlwh: np.ndarray) -> np.ndarray:
    """
    Convert bounding box from [x1, y1, w, h] to [x1, y1, x2, y2].
    """
    ret = np.asarray(tlwh, dtype=np.float32).copy()
    ret[..., 2:] += ret[..., :2]
    return ret


def tlbr_to_cxcyah(tlbr: np.ndarray) -> np.ndarray:
    """
    Convert bounding box from [x1, y1, x2, y2] to center_x, center_y, aspect_ratio, height.
    Aspect ratio = width / height.
    """
    ret = np.asarray(tlbr, dtype=np.float32).copy()
    w = ret[..., 2] - ret[..., 0]
    h = ret[..., 3] - ret[..., 1]
    cx = ret[..., 0] + w / 2.0
    cy = ret[..., 1] + h / 2.0
    a = w / (h + 1e-6)
    return np.array([cx, cy, a, h], dtype=np.float32)


def cxcyah_to_tlbr(cxcyah: np.ndarray) -> np.ndarray:
    """
    Convert bounding box from [cx, cy, a, h] to [x1, y1, x2, y2].
    """
    cx, cy, a, h = cxcyah[0], cxcyah[1], cxcyah[2], cxcyah[3]
    w = a * h
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def calculate_center(tlbr: List[float]) -> Tuple[float, float]:
    """
    Calculate (cx, cy) from bounding box [x1, y1, x2, y2].
    """
    cx = (tlbr[0] + tlbr[2]) / 2.0
    cy = (tlbr[1] + tlbr[3]) / 2.0
    return (round(float(cx), 2), round(float(cy), 2))


def calculate_velocity_and_direction(
    curr_center: Tuple[float, float],
    prev_center: Tuple[float, float],
    dt_frames: int = 1
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Calculate velocity vector (vx, vy) in pixels/frame and normalized unit direction vector (dx, dy).
    """
    if dt_frames <= 0:
        dt_frames = 1

    vx = (curr_center[0] - prev_center[0]) / float(dt_frames)
    vy = (curr_center[1] - prev_center[1]) / float(dt_frames)

    speed = float(np.hypot(vx, vy))
    if speed > 1e-5:
        dx = vx / speed
        dy = vy / speed
    else:
        dx = 0.0
        dy = 0.0

    return (
        (round(float(vx), 2), round(float(vy), 2)),
        (round(float(dx), 4), round(float(dy), 4))
    )


def iou_batch(atlbrs: np.ndarray, btlbrs: np.ndarray) -> np.ndarray:
    """
    Compute Intersection over Union (IoU) matrix between set A of bounding boxes
    and set B of bounding boxes.
    Boxes are expected as Nx4 and Mx4 matrices in [x1, y1, x2, y2] format.
    Returns: NxM numpy array containing IoU values in range [0.0, 1.0].
    """
    if len(atlbrs) == 0 or len(btlbrs) == 0:
        return np.zeros((len(atlbrs), len(btlbrs)), dtype=np.float32)

    atlbrs = np.asarray(atlbrs, dtype=np.float32)
    btlbrs = np.asarray(btlbrs, dtype=np.float32)

    ious = np.zeros((len(atlbrs), len(btlbrs)), dtype=np.float32)

    for i, box_a in enumerate(atlbrs):
        x1_a, y1_a, x2_a, y2_a = box_a[:4]
        area_a = max(0.0, x2_a - x1_a) * max(0.0, y2_a - y1_a)

        for j, box_b in enumerate(btlbrs):
            x1_b, y1_b, x2_b, y2_b = box_b[:4]
            area_b = max(0.0, x2_b - x1_b) * max(0.0, y2_b - y1_b)

            inter_x1 = max(x1_a, x1_b)
            inter_y1 = max(y1_a, y1_b)
            inter_x2 = min(x2_a, x2_b)
            inter_y2 = min(y2_a, y2_b)

            inter_w = max(0.0, inter_x2 - inter_x1)
            inter_h = max(0.0, inter_y2 - inter_y1)
            inter_area = inter_w * inter_h

            union_area = area_a + area_b - inter_area
            if union_area > 0.0:
                ious[i, j] = inter_area / union_area

    return ious
