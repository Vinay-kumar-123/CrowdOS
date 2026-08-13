"""
Structured JSON Logger for CrowdOS Event Intelligence Engine.
Namespace: crowdos.intelligence
"""
import logging
import json
import sys
from datetime import datetime, timezone


class IntelligenceJSONFormatter(logging.Formatter):
    """
    JSON Formatter enforcing privacy guarantees.
    Sanitizes log records to guarantee zero biometric vectors or raw crops are emitted.
    """
    FORBIDDEN_KEYS = {"embedding", "face_crop", "biometric_vector", "raw_vector", "facial_embedding"}

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage()
        }

        # Include standard extra attributes if clean
        if hasattr(record, "__dict__"):
            for k, v in record.__dict__.items():
                if k not in log_obj and not k.startswith("_") and k not in ("args", "msg", "exc_info", "exc_text", "stack_info"):
                    if k in self.FORBIDDEN_KEYS:
                        continue
                    log_obj[k] = v

        return json.dumps(log_obj)


def setup_intelligence_logger() -> logging.Logger:
    logger = logging.getLogger("crowdos.intelligence")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(IntelligenceJSONFormatter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


intelligence_logger = setup_intelligence_logger()
