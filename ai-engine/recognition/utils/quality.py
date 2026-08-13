from typing import Tuple, Optional
import cv2
import numpy as np
from pydantic import BaseModel, Field
from recognition.config.settings import recognition_settings
from recognition.results.schema import FaceQualityStatus


class FaceQualityResult(BaseModel):
    """
    Structured outcome of face quality assessment.
    """
    score: float = Field(..., description="Overall face quality score between 0.0 and 1.0")
    status: FaceQualityStatus = Field(..., description="Detailed quality classification status")
    is_usable: bool = Field(..., description="Whether the face meets minimum quality threshold for embedding")
    blur_score: float = Field(default=0.0, description="Laplacian variance blur score")
    brightness_score: float = Field(default=0.0, description="Mean pixel brightness [0.0, 255.0]")
    face_width: int = Field(default=0)
    face_height: int = Field(default=0)


def compute_laplacian_blur(image_gray: np.ndarray) -> float:
    """
    Compute variance of Laplacian as a proxy for image sharpness/focus.
    Higher values indicate sharper focus; low values indicate blur.
    """
    if image_gray is None or image_gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(image_gray, cv2.CV_64F).var())


def compute_brightness(image_gray: np.ndarray) -> float:
    """
    Compute mean intensity of image grayscale pixels.
    """
    if image_gray is None or image_gray.size == 0:
        return 0.0
    return float(np.mean(image_gray))


def assess_face_quality(
    face_crop: np.ndarray,
    detection_confidence: float = 1.0,
    landmarks: Optional[np.ndarray] = None,
    min_size: int = recognition_settings.MIN_FACE_SIZE,
    blur_thresh: float = recognition_settings.BLUR_THRESHOLD,
    min_brightness: float = recognition_settings.MIN_BRIGHTNESS,
    max_brightness: float = recognition_settings.MAX_BRIGHTNESS,
    min_confidence: float = recognition_settings.MIN_FACE_CONFIDENCE,
) -> FaceQualityResult:
    """
    Evaluate structural and optical quality of a detected face crop.
    """
    if face_crop is None or face_crop.size == 0:
        return FaceQualityResult(
            score=0.0,
            status=FaceQualityStatus.QUALITY_POOR,
            is_usable=False,
            blur_score=0.0,
            brightness_score=0.0,
            face_width=0,
            face_height=0
        )

    h, w = face_crop.shape[:2]

    # 1. Detection confidence check
    if detection_confidence < min_confidence:
        return FaceQualityResult(
            score=round(detection_confidence, 2),
            status=FaceQualityStatus.QUALITY_LOW_CONFIDENCE,
            is_usable=False,
            blur_score=0.0,
            brightness_score=0.0,
            face_width=w,
            face_height=h
        )

    # 2. Face dimensions check
    if w < min_size or h < min_size:
        return FaceQualityResult(
            score=0.2,
            status=FaceQualityStatus.QUALITY_TOO_SMALL,
            is_usable=False,
            blur_score=0.0,
            brightness_score=0.0,
            face_width=w,
            face_height=h
        )

    # Convert to grayscale if BGR/RGB
    if len(face_crop.shape) == 3:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = face_crop

    # 3. Blur Assessment
    blur_val = compute_laplacian_blur(gray)
    if blur_val < blur_thresh:
        return FaceQualityResult(
            score=round(min(1.0, blur_val / (blur_thresh + 1e-5)) * 0.4, 2),
            status=FaceQualityStatus.QUALITY_BLURRY,
            is_usable=False,
            blur_score=round(blur_val, 2),
            brightness_score=round(compute_brightness(gray), 2),
            face_width=w,
            face_height=h
        )

    # 4. Brightness Assessment
    bright_val = compute_brightness(gray)
    if bright_val < min_brightness or bright_val > max_brightness:
        return FaceQualityResult(
            score=0.4,
            status=FaceQualityStatus.QUALITY_POOR,
            is_usable=False,
            blur_score=round(blur_val, 2),
            brightness_score=round(bright_val, 2),
            face_width=w,
            face_height=h
        )

    # 5. Composite Quality Score
    normalized_size = min(1.0, (w * h) / (128.0 * 128.0))
    normalized_blur = min(1.0, blur_val / 200.0)
    overall_score = float(np.clip(
        0.4 * normalized_size + 0.4 * normalized_blur + 0.2 * detection_confidence,
        0.0, 1.0
    ))

    is_usable = overall_score >= recognition_settings.QUALITY_THRESHOLD

    return FaceQualityResult(
        score=round(overall_score, 2),
        status=FaceQualityStatus.QUALITY_GOOD if is_usable else FaceQualityStatus.QUALITY_POOR,
        is_usable=is_usable,
        blur_score=round(blur_val, 2),
        brightness_score=round(bright_val, 2),
        face_width=w,
        face_height=h
    )
