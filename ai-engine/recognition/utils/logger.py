import logging
import sys
import json
from datetime import datetime, timezone


class RecognitionJSONFormatter(logging.Formatter):
    """
    Structured JSON Formatter for AI Face Recognition & Identity Association Engine events.
    Strictly redacts any sensitive raw face embeddings or image data.
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
            "recognition_id", "camera_id", "track_id", "detection_id", "face_id",
            "identity_id", "identity_status", "quality_status", "quality_score",
            "similarity_score", "processing_time_ms", "device_used", "frame_number"
        ]
        for attr in context_attrs:
            if hasattr(record, attr):
                val = getattr(record, attr)
                # Safeguard against accidental embedding logging
                if isinstance(val, (list, tuple)) and len(val) > 10:
                    log_object[attr] = "[REDACTED_VECTOR]"
                else:
                    log_object[attr] = val

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object)


def setup_recognition_logger(name: str = "crowdos.recognition") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(RecognitionJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


recognition_logger = setup_recognition_logger()
