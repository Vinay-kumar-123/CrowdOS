import logging
import re
import sys
from app.core.settings import settings


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that redacts sensitive credentials, tokens, and secrets
    from log records before emission.
    """
    _URL_CRED_PATTERN = re.compile(r"://([^/@\s]+)@")
    _BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{10,}", re.IGNORECASE)
    _PWD_PATTERN = re.compile(r"(['\"]?(?:password|secret|camera_encryption_key)['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = self._URL_CRED_PATTERN.sub(r"://***:***@", record.msg)
            msg = self._BEARER_PATTERN.sub(r"\1[REDACTED_TOKEN]", msg)
            msg = self._PWD_PATTERN.sub(r"\1[REDACTED]\2", msg)
            record.msg = msg
        return True


def setup_logger(name: str = "crowdos") -> logging.Logger:
    """
    Configures structured, production-ready logging with sensitive data redaction.
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    return logger


logger = setup_logger()
