import logging
import sys
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for production camera infrastructure logging.
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
        if hasattr(record, "camera_id"):
            log_object["camera_id"] = record.camera_id
        if hasattr(record, "event_type"):
            log_object["event_type"] = record.event_type
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)


def setup_camera_logger(name: str = "crowdos.camera") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


camera_logger = setup_camera_logger()
