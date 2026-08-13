import math
from typing import Dict, List, Tuple
from datetime import datetime
from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
from tracking.utils.logger import tracking_logger


class TrackValidator:
    """
    Validator for Tracking Engine input detection payloads and output track schemas.
    Rejects invalid bounding boxes, NaN values, corrupt Track IDs, or out-of-order frame numbers.
    """

    def __init__(self):
        # Per-camera last observed frame number for monotonicity tracking
        self.last_frame_numbers: Dict[str, int] = {}

    def validate_tracked_person(self, person: TrackedPerson) -> Tuple[bool, str]:
        """
        Validate a single TrackedPerson object.
        Returns (is_valid, error_message).
        """
        # Track ID check
        if not person.track_id or not str(person.track_id).strip():
            return False, "Track ID cannot be empty"

        # Camera ID check
        if not person.camera_id or not str(person.camera_id).strip():
            return False, "Camera ID cannot be empty"

        # Frame number check
        if person.frame_number < 0:
            return False, f"Invalid negative frame number: {person.frame_number}"

        # Bounding box sanity checks
        bbox = person.bbox
        for val in [bbox.x1, bbox.y1, bbox.x2, bbox.y2]:
            if math.isnan(val) or math.isinf(val):
                return False, f"Bounding box contains NaN or Inf: {bbox}"

        if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
            return False, f"Invalid bounding box coordinates (x1 >= x2 or y1 >= y2): {bbox}"

        # Confidence bounds check
        if not (0.0 <= person.confidence <= 1.0):
            return False, f"Confidence score out of bounds [0.0, 1.0]: {person.confidence}"

        # Track state enum check
        if not isinstance(person.track_state, TrackState):
            try:
                TrackState(str(person.track_state))
            except ValueError:
                return False, f"Invalid TrackState value: {person.track_state}"

        # Timestamp format check
        try:
            datetime.fromisoformat(person.timestamp.replace("Z", "+00:00"))
        except Exception as e:
            return False, f"Invalid ISO 8601 timestamp string '{person.timestamp}': {e}"

        return True, ""

    def validate_tracking_result(self, result: TrackingResult) -> Tuple[bool, List[str]]:
        """
        Validate an entire Frame TrackingResult payload.
        Returns (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        if result.frame_number < 0:
            errors.append(f"Invalid frame_number: {result.frame_number}")

        cam_id = result.camera_id
        if cam_id in self.last_frame_numbers:
            last_frame = self.last_frame_numbers[cam_id]
            if result.frame_number < last_frame:
                errors.append(
                    f"Frame number regression detected for camera '{cam_id}': "
                    f"received {result.frame_number}, previous was {last_frame}"
                )

        self.last_frame_numbers[cam_id] = result.frame_number

        # Duplicate track ID check within frame
        seen_track_ids = set()
        valid_tracks: List[TrackedPerson] = []

        for person in result.tracks:
            is_valid, err = self.validate_tracked_person(person)
            if not is_valid:
                errors.append(f"Invalid TrackedPerson (Track ID '{person.track_id}'): {err}")
                continue

            if person.track_id in seen_track_ids:
                errors.append(f"Duplicate track_id '{person.track_id}' found in frame {result.frame_number}")
                continue

            seen_track_ids.add(person.track_id)
            valid_tracks.append(person)

        is_valid = len(errors) == 0
        if not is_valid:
            tracking_logger.warning(
                f"TrackValidator encountered {len(errors)} validation issues in frame {result.frame_number}: {errors}",
                extra={"camera_id": cam_id, "frame_number": result.frame_number}
            )

        return is_valid, errors

    def reset_camera(self, camera_id: str) -> None:
        if camera_id in self.last_frame_numbers:
            del self.last_frame_numbers[camera_id]
