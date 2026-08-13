import logging
import sys
import json
from datetime import datetime, timezone


class TrackingJSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for AI Multi-Object Person Tracking Engine events.
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

        # Contextual attributes
        context_attrs = [
            "track_id", "camera_id", "state_transition", "tracking_fps",
            "latency_ms", "active_tracks", "lost_tracks", "tracker_name",
            "frame_number", "event_type"
        ]
        for attr in context_attrs:
            if hasattr(record, attr):
                log_object[attr] = getattr(record, attr)

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object)


def setup_tracking_logger(name: str = "crowdos.tracking") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(TrackingJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


tracking_logger = setup_tracking_logger()
