"""
Structured logger for Sprint 8 Prediction Engine.
Namespace: crowdos.prediction
"""
import logging
import json


class _PredictionJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


def _create_prediction_logger() -> logging.Logger:
    logger = logging.getLogger("crowdos.prediction")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_PredictionJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.WARNING)  # Production: WARNING+
    return logger


prediction_logger = _create_prediction_logger()
