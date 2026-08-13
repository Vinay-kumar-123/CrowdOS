import math
from datetime import datetime
from typing import List, Tuple

from recognition.results.schema import (
    RecognitionResult, RecognizedPerson, RecognitionStatus, FaceQualityStatus
)
from recognition.utils.logger import recognition_logger


class RecognitionValidator:
    """
    Validates RecognitionResult payloads and individual RecognizedPerson entries.
    Enforces schema integrity and privacy boundaries.
    """

    def __init__(self):
        self.last_frame_numbers: dict = {}

    def validate_recognized_person(self, person: RecognizedPerson) -> Tuple[bool, str]:
        """Validate a single RecognizedPerson payload."""
        if not person.track_id or not str(person.track_id).strip():
            return False, "track_id cannot be empty"

        if not person.camera_id or not str(person.camera_id).strip():
            return False, "camera_id cannot be empty"

        if not person.detection_id or not str(person.detection_id).strip():
            return False, "detection_id cannot be empty"

        if person.frame_number < 0:
            return False, f"Invalid negative frame_number: {person.frame_number}"

        if not (0.0 <= person.face_confidence <= 1.0):
            return False, f"face_confidence out of bounds: {person.face_confidence}"

        if not (0.0 <= person.face_quality_score <= 1.0):
            return False, f"face_quality_score out of bounds: {person.face_quality_score}"

        if not (0.0 <= person.similarity_score <= 1.0):
            return False, f"similarity_score out of bounds: {person.similarity_score}"

        if person.face_bbox is not None:
            bbox = person.face_bbox
            for val in [bbox.x1, bbox.y1, bbox.x2, bbox.y2]:
                if math.isnan(val) or math.isinf(val):
                    return False, f"face_bbox contains NaN or Inf"
            if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
                return False, "face_bbox coordinates invalid (x1>=x2 or y1>=y2)"

        try:
            datetime.fromisoformat(person.timestamp.replace("Z", "+00:00"))
        except Exception:
            return False, f"Invalid timestamp format: {person.timestamp}"

        return True, ""

    def validate_recognition_result(
        self, result: RecognitionResult
    ) -> Tuple[bool, List[str]]:
        """Validate an entire frame RecognitionResult payload."""
        errors: List[str] = []

        if result.frame_number < 0:
            errors.append(f"Invalid frame_number: {result.frame_number}")

        cam_id = result.camera_id
        if cam_id in self.last_frame_numbers:
            last = self.last_frame_numbers[cam_id]
            if result.frame_number < last:
                errors.append(
                    f"Frame regression on camera '{cam_id}': "
                    f"received {result.frame_number}, previous was {last}"
                )
        self.last_frame_numbers[cam_id] = result.frame_number

        for person in result.recognized_persons:
            ok, err = self.validate_recognized_person(person)
            if not ok:
                errors.append(f"Invalid RecognizedPerson (track_id={person.track_id}): {err}")

        is_valid = len(errors) == 0
        if not is_valid:
            recognition_logger.warning(
                f"RecognitionValidator found {len(errors)} issues in frame {result.frame_number}",
                extra={"camera_id": cam_id, "frame_number": result.frame_number}
            )

        return is_valid, errors

    def reset_camera(self, camera_id: str) -> None:
        if camera_id in self.last_frame_numbers:
            del self.last_frame_numbers[camera_id]
