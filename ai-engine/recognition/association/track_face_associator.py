import uuid
from typing import List, Optional, Tuple
import numpy as np

from recognition.models.base_detector import FaceDetectionItem
from recognition.utils.logger import recognition_logger


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """
    Compute Intersection over Union (IoU) between two bounding boxes in [x1, y1, x2, y2] format.
    """
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def is_face_within_person_box(
    face_bbox: List[float],
    person_bbox: List[float],
    containment_threshold: float = 0.50
) -> bool:
    """
    Determine whether a face bounding box belongs geometrically to the person's bounding box.
    Uses center containment check + partial overlap IoU.
    """
    fx1, fy1, fx2, fy2 = face_bbox[:4]
    px1, py1, px2, py2 = person_bbox[:4]

    # Check face center point lies inside person box
    face_cx = (fx1 + fx2) / 2.0
    face_cy = (fy1 + fy2) / 2.0
    center_inside = (px1 <= face_cx <= px2) and (py1 <= face_cy <= py2)

    # Check IoU overlap as secondary criterion
    iou = compute_iou(face_bbox, person_bbox)

    return center_inside or (iou >= containment_threshold)


class TrackFaceAssociator:
    """
    Associates face detections with tracked person bounding boxes.
    Preserves exact traceability: detection_id -> track_id -> face_id -> identity_id.

    CTO Rule: Faces that do not geometrically belong to the tracked person's bounding box
    are rejected without generating an identity result.
    """

    def __init__(self, containment_threshold: float = 0.50):
        self.containment_threshold = containment_threshold

    def associate(
        self,
        person_bbox: List[float],
        face_detections: List[FaceDetectionItem],
        camera_id: str,
        track_id: str,
        detection_id: str
    ) -> Optional[FaceDetectionItem]:
        """
        Select the best face detection that belongs to the tracked person's bounding box.
        Returns the associated FaceDetectionItem or None if no valid match found.
        """
        if not face_detections or not person_bbox:
            return None

        valid_faces: List[Tuple[float, FaceDetectionItem]] = []

        for face in face_detections:
            belongs = is_face_within_person_box(
                face.bbox, person_bbox,
                containment_threshold=self.containment_threshold
            )
            if belongs:
                valid_faces.append((face.confidence, face))
            else:
                recognition_logger.info(
                    f"Rejected face (face_id={face.face_id}) - does not belong to track {track_id} bounding box",
                    extra={
                        "camera_id": camera_id,
                        "track_id": track_id,
                        "detection_id": detection_id,
                        "face_id": face.face_id
                    }
                )

        if not valid_faces:
            return None

        # Return highest confidence face within the person bounding box
        best_face = max(valid_faces, key=lambda x: x[0])[1]
        return best_face
