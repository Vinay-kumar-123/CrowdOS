import numpy as np
from typing import Tuple, Dict, Any
from detection.config.settings import detection_settings


class Preprocessor:
    """
    Image Preprocessing module handling aspect-ratio preserving letterbox resizing
    and format conversions prior to YOLO model inference.
    """
    def __init__(self, target_size: int = None):
        self.target_size = target_size or detection_settings.IMG_SIZE

    def letterbox(
        self,
        image: np.ndarray,
        new_shape: Tuple[int, int] = None,
        color: Tuple[int, int, int] = (114, 114, 114),
    ) -> Tuple[np.ndarray, Tuple[float, float], Tuple[int, int]]:
        """
        Resize and pad image while maintaining aspect ratio (letterbox).
        Returns (padded_image, (scale_w, scale_h), (pad_w, pad_h)).
        Falls back to pure NumPy operations when OpenCV is unavailable.
        """
        if new_shape is None:
            new_shape = (self.target_size, self.target_size)

        h, w = image.shape[:2]
        target_w, target_h = new_shape

        # Compute scale factor
        scale = min(target_w / w, target_h / h)
        unpadded_w = int(round(w * scale))
        unpadded_h = int(round(h * scale))

        # Compute symmetric padding
        pad_w = (target_w - unpadded_w) // 2
        pad_h = (target_h - unpadded_h) // 2
        pad_w_right = target_w - unpadded_w - pad_w
        pad_h_bottom = target_h - unpadded_h - pad_h

        # Resize
        try:
            import cv2
            resized = cv2.resize(image, (unpadded_w, unpadded_h), interpolation=cv2.INTER_LINEAR)
        except ImportError:
            # NumPy nearest-neighbor resize fallback
            y_idx = (np.arange(unpadded_h) * h / unpadded_h).astype(int)
            x_idx = (np.arange(unpadded_w) * w / unpadded_w).astype(int)
            resized = image[np.ix_(y_idx, x_idx)]

        # Apply padding
        try:
            import cv2
            padded = cv2.copyMakeBorder(
                resized,
                pad_h, pad_h_bottom, pad_w, pad_w_right,
                cv2.BORDER_CONSTANT,
                value=color,
            )
        except ImportError:
            # NumPy padding fallback
            padded = np.full((target_h, target_w, image.shape[2]), color[0], dtype=np.uint8)
            if image.shape[2] == 3:
                padded[:, :] = color
            padded[pad_h:pad_h + unpadded_h, pad_w:pad_w + unpadded_w] = resized

        return padded, (scale, scale), (pad_w, pad_h)

    def preprocess(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Full preprocessing pipeline: Letterbox resize & metadata collection.
        """
        orig_h, orig_w = image.shape[:2]
        padded_img, scale, pad = self.letterbox(image)

        return {
            "processed_image": padded_img,
            "original_shape": (orig_w, orig_h),
            "scale": scale,
            "pad": pad,
        }
