import logging
import sys
import json
from datetime import datetime, timezone


class DetectionJSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for AI Detection Engine events.
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
        if hasattr(record, "model_name"):
            log_object["model_name"] = record.model_name
        if hasattr(record, "inference_time_ms"):
            log_object["inference_time_ms"] = record.inference_time_ms
        if hasattr(record, "detections_count"):
            log_object["detections_count"] = record.detections_count
        if hasattr(record, "camera_id"):
            log_object["camera_id"] = record.camera_id
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)


def setup_detection_logger(name: str = "crowdos.detection") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(DetectionJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


detection_logger = setup_detection_logger()
