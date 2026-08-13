import math
from typing import Tuple, List, Optional
import numpy as np


class TrackCropper:
    """
    Safely crops tracked person bounding box regions from video frame matrices with margin padding.
    """

    def __init__(self, default_padding: float = 0.05):
        self.default_padding = default_padding

    def crop_person_region(
        self,
        frame: np.ndarray,
        person_bbox: List[float],
        padding: Optional[float] = None
    ) -> Tuple[Optional[np.ndarray], List[int]]:
        """
        Crop person region from frame given bounding box [x1, y1, x2, y2].
        Returns (cropped_np_array, [crop_x1, crop_y1, crop_x2, crop_y2]).
        """
        if frame is None or frame.size == 0 or not person_bbox or len(person_bbox) < 4:
            return None, [0, 0, 0, 0]

        h_frame, w_frame = frame.shape[:2]
        x1, y1, x2, y2 = [float(v) for v in person_bbox[:4]]

        # NaN / Inf validation
        for val in [x1, y1, x2, y2]:
            if math.isnan(val) or math.isinf(val):
                return None, [0, 0, 0, 0]

        pad_ratio = padding if padding is not None else self.default_padding
        w_box = max(0.0, x2 - x1)
        h_box = max(0.0, y2 - y1)

        if w_box <= 1.0 or h_box <= 1.0:
            return None, [0, 0, 0, 0]

        # Apply margin padding
        px = w_box * pad_ratio
        py = h_box * pad_ratio

        cx1 = max(0, int(floor_int(x1 - px)))
        cy1 = max(0, int(floor_int(y1 - py)))
        cx2 = min(w_frame, int(ceil_int(x2 + px)))
        cy2 = min(h_frame, int(ceil_int(y2 + py)))

        if cx2 <= cx1 or cy2 <= cy1:
            return None, [0, 0, 0, 0]

        crop = frame[cy1:cy2, cx1:cx2].copy()
        return crop, [cx1, cy1, cx2, cy2]


def floor_int(v: float) -> int:
    return int(math.floor(v))


def ceil_int(v: float) -> int:
    return int(math.ceil(v))
