"""
ResultValidator — Post-inference detection validation layer.

Validates every DetectionItem for geometric and semantic correctness before
it reaches downstream Sprint 4+ modules (Tracker, Counter, Alert Engine).

Rejects:
- Zero-area bounding boxes (width == 0 or height == 0)
- Out-of-frame bounding boxes (coordinates exceed image resolution)
- Invalid confidence scores (outside 0.0–1.0)
- Wrong class ID (non-person detections that leaked through)
- NaN / Inf coordinate values
"""
import math
from typing import List, Tuple

from detection.results.schema import DetectionItem
from detection.utils.logger import detection_logger


class ValidationError(Exception):
    """Raised when a detection cannot be salvaged by clamping — must be rejected."""
    pass


class ResultValidator:
    """
    Validates and sanitizes a list of DetectionItem objects against a given frame resolution.
    Invalid detections are logged and dropped. Valid detections are returned unchanged.
    """

    def __init__(self, person_class_id: int = 0):
        self.person_class_id = person_class_id

    def validate(
        self,
        detections: List[DetectionItem],
        frame_resolution: Tuple[int, int],
    ) -> List[DetectionItem]:
        """
        Validate each DetectionItem in the list against the given frame resolution.
        Returns a cleaned list containing only geometrically and semantically valid detections.

        Args:
            detections: Raw list of DetectionItem objects from Postprocessor.
            frame_resolution: (width, height) of the original frame.

        Returns:
            Filtered list of valid DetectionItem objects.
        """
        frame_w, frame_h = frame_resolution
        valid: List[DetectionItem] = []
        rejected = 0

        for det in detections:
            try:
                self._validate_class(det)
                self._validate_confidence(det)
                self._validate_coordinates(det, frame_w, frame_h)
                self._validate_geometry(det)
                valid.append(det)
            except ValidationError as e:
                rejected += 1
                detection_logger.warning(
                    f"[ResultValidator] Detection {det.detection_id} rejected: {e}"
                )

        if rejected > 0:
            detection_logger.info(
                f"[ResultValidator] {len(valid)} valid, {rejected} rejected detections."
            )

        return valid

    # ─── Private Validators ─────────────────────────────────────────────────

    def _validate_class(self, det: DetectionItem) -> None:
        if det.class_id != self.person_class_id:
            raise ValidationError(
                f"Non-person class_id={det.class_id} leaked through postprocessor."
            )

    def _validate_confidence(self, det: DetectionItem) -> None:
        if not (0.0 <= det.confidence <= 1.0):
            raise ValidationError(
                f"Confidence {det.confidence} is outside valid range [0.0, 1.0]."
            )
        if math.isnan(det.confidence) or math.isinf(det.confidence):
            raise ValidationError(f"Confidence is NaN or Inf.")

    def _validate_coordinates(self, det: DetectionItem, frame_w: int, frame_h: int) -> None:
        bbox = det.bbox
        coords = [bbox.x1, bbox.y1, bbox.x2, bbox.y2]

        # Check for NaN / Inf in any coordinate
        for coord in coords:
            if math.isnan(coord) or math.isinf(coord):
                raise ValidationError(f"BBox contains NaN or Inf coordinate: {coords}")

        # All coordinates must be within frame bounds
        if bbox.x1 < 0 or bbox.y1 < 0:
            raise ValidationError(
                f"BBox top-left ({bbox.x1}, {bbox.y1}) is outside frame."
            )
        if bbox.x2 > frame_w or bbox.y2 > frame_h:
            raise ValidationError(
                f"BBox bottom-right ({bbox.x2}, {bbox.y2}) exceeds frame ({frame_w}x{frame_h})."
            )

        # x2 must be greater than x1, y2 greater than y1
        if bbox.x2 <= bbox.x1 or bbox.y2 <= bbox.y1:
            raise ValidationError(
                f"BBox has non-positive dimensions: x1={bbox.x1}, x2={bbox.x2}, y1={bbox.y1}, y2={bbox.y2}"
            )

    def _validate_geometry(self, det: DetectionItem) -> None:
        # Zero-area or negative-area detection
        if det.width <= 0 or det.height <= 0:
            raise ValidationError(
                f"DetectionItem has zero or negative area: width={det.width}, height={det.height}"
            )
