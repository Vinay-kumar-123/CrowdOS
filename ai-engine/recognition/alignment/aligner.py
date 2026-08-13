from typing import Optional, Tuple
import cv2
import numpy as np


# Standard reference 5-point facial landmarks for 112x112 face crop (InsightFace / ArcFace standard)
ARCFACE_REF_5PTS = np.array([
    [38.2946, 51.6963],  # Left eye
    [73.5318, 51.5014],  # Right eye
    [56.0252, 71.7366],  # Nose tip
    [41.5493, 92.3655],  # Left mouth corner
    [70.7299, 92.2041]   # Right mouth corner
], dtype=np.float32)


def align_face_5point(
    face_image: np.ndarray,
    landmarks: Optional[np.ndarray] = None,
    output_size: Tuple[int, int] = (112, 112)
) -> np.ndarray:
    """
    Perform 5-point similarity transformation alignment on a face crop.
    Aligns eyes, nose, and mouth to reference ArcFace coordinates and resizes to output_size.
    """
    if face_image is None or face_image.size == 0:
        return np.zeros((output_size[1], output_size[0], 3), dtype=np.uint8)

    if landmarks is not None and isinstance(landmarks, np.ndarray) and landmarks.shape == (5, 2):
        try:
            src_pts = landmarks.astype(np.float32)
            dst_pts = ARCFACE_REF_5PTS.copy()
            if output_size != (112, 112):
                sx = output_size[0] / 112.0
                sy = output_size[1] / 112.0
                dst_pts[:, 0] *= sx
                dst_pts[:, 1] *= sy

            M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
            if M is not None:
                aligned = cv2.warpAffine(
                    face_image, M, (output_size[0], output_size[1]),
                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
                )
                return aligned
        except Exception:
            pass

    # Fallback: aspect-ratio-preserving resize without alignment
    return cv2.resize(face_image, output_size, interpolation=cv2.INTER_LINEAR)
