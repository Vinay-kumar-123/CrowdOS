import math
from datetime import datetime
from typing import Tuple, List
from movement.events.schema import MovementEvent
from movement.utils.logger import movement_logger


class MovementEventValidator:
    """
    Validates MovementEvent payload integrity and field constraints.
    """

    def validate_event(self, event: MovementEvent) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not event.event_id or not str(event.event_id).strip():
            errors.append("event_id cannot be empty")

        if not event.camera_id or not str(event.camera_id).strip():
            errors.append("camera_id cannot be empty")

        if not event.gate_id or not str(event.gate_id).strip():
            errors.append("gate_id cannot be empty")

        if not event.track_id or not str(event.track_id).strip():
            errors.append("track_id cannot be empty")

        if not event.detection_id or not str(event.detection_id).strip():
            errors.append("detection_id cannot be empty")

        if not (0.0 <= event.confidence <= 1.0):
            errors.append(f"confidence out of bounds: {event.confidence}")

        if event.bounding_box is not None:
            bbox = event.bounding_box
            for val in [bbox.x1, bbox.y1, bbox.x2, bbox.y2]:
                if math.isnan(val) or math.isinf(val):
                    errors.append("bounding_box contains NaN or Inf")
            if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
                errors.append("bounding_box coordinates invalid (x1>=x2 or y1>=y2)")

        try:
            datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        except Exception:
            errors.append(f"Invalid timestamp ISO format: {event.timestamp}")

        is_valid = len(errors) == 0
        if not is_valid:
            movement_logger.warning(
                f"MovementEventValidator detected {len(errors)} issues in event {event.event_id}: {errors}"
            )

        return is_valid, errors
