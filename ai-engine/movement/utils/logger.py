import logging
import sys
import json
from datetime import datetime, timezone


class MovementJSONFormatter(logging.Formatter):
    """
    Structured JSON Formatter for Movement Engine events.
    Strictly redacts any raw face embeddings or biometric image data.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Contextual metadata attributes (Redact raw embeddings or images!)
        context_attrs = [
            "event_id", "event_type", "camera_id", "gate_id", "track_id",
            "detection_id", "face_id", "identity_id", "identity_status",
            "direction", "confidence", "dwell_time", "current_occupancy",
            "journey_id", "frame_number", "event_source"
        ]
        for attr in context_attrs:
            if hasattr(record, attr):
                val = getattr(record, attr)
                if isinstance(val, (list, tuple)) and len(val) > 10:
                    log_object[attr] = "[REDACTED_VECTOR]"
                else:
                    log_object[attr] = val

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object)


def setup_movement_logger(name: str = "crowdos.movement") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(MovementJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


movement_logger = setup_movement_logger()
