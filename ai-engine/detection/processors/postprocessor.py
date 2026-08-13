from typing import List, Dict, Any, Tuple
import numpy as np
from detection.config.settings import detection_settings
from detection.results.schema import BoundingBox, DetectionItem


class Postprocessor:
    """
    Postprocessing module filtering YOLO detection output EXCLUSIVELY for the 'person' class (Class ID 0).
    Filters by confidence threshold, rescales boxes to original frame dimensions, and generates DetectionItem outputs.
    """
    def __init__(
        self,
        confidence_threshold: float = None,
        person_class_id: int = None,
        max_detections: int = None,
    ):
        self.conf_thresh = confidence_threshold or detection_settings.CONFIDENCE_THRESHOLD
        self.person_class_id = person_class_id if person_class_id is not None else detection_settings.PERSON_CLASS_ID
        self.max_detections = max_detections or detection_settings.MAX_DETECTIONS

    def process_results(
        self,
        raw_results: Any,
        original_shape: Tuple[int, int],
    ) -> List[DetectionItem]:
        """
        Processes raw model inference output and returns a clean list of DetectionItem objects.
        Filters out any non-person object classes.
        """
        detections: List[DetectionItem] = []
        orig_w, orig_h = original_shape

        if raw_results is None or len(raw_results) == 0:
            return detections

        # Extract boxes from Ultralytics result object
        first_result = raw_results[0]
        if not hasattr(first_result, "boxes") or first_result.boxes is None:
            return detections

        boxes = first_result.boxes

        # Extract array values
        try:
            classes = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.array(boxes.cls)
            confidences = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.array(boxes.conf)
            xyxy_boxes = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.array(boxes.xyxy)
        except Exception:
            return detections

        count = 0
        for cls_id, conf, bbox in zip(classes, confidences, xyxy_boxes):
            if count >= self.max_detections:
                break

            # STRICT FILTERING: Class ID MUST be Person (Class 0)
            if int(cls_id) != self.person_class_id:
                continue

            # Confidence filtering
            if float(conf) < self.conf_thresh:
                continue

            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

            # Clip coordinates to original frame bounds
            x1_clamped = max(0.0, min(float(orig_w), x1))
            y1_clamped = max(0.0, min(float(orig_h), y1))
            x2_clamped = max(0.0, min(float(orig_w), x2))
            y2_clamped = max(0.0, min(float(orig_h), y2))

            width = x2_clamped - x1_clamped
            height = y2_clamped - y1_clamped
            center_x = x1_clamped + (width / 2.0)
            center_y = y1_clamped + (height / 2.0)

            item = DetectionItem(
                class_id=self.person_class_id,
                class_name="person",
                confidence=float(conf),
                bbox=BoundingBox(x1=x1_clamped, y1=y1_clamped, x2=x2_clamped, y2=y2_clamped),
                center=(center_x, center_y),
                width=width,
                height=height,
            )
            detections.append(item)
            count += 1

        return detections
