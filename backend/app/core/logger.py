import logging
import re
import sys
from app.core.settings import settings


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that redacts sensitive credentials, tokens, and secrets
    from log records before emission.

    Handles both pre-formatted messages (record.msg as str with no args)
    and unformatted messages where record.args contains substitution values
    (e.g. logger.info("URL: %s", rtsp_url)). In the latter case the filter
    evaluates the full formatted string, redacts it, and stores it back in
    record.msg while clearing record.args to prevent double-formatting.
    """
    _URL_CRED_PATTERN = re.compile(r"://([^/@\s]+)@")
    _BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{10,}", re.IGNORECASE)
    _PWD_PATTERN = re.compile(
        r"(['\"]?(?:password|secret|camera_encryption_key)['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
        re.IGNORECASE,
    )

    def _redact(self, text: str) -> str:
        text = self._URL_CRED_PATTERN.sub(r"://***:***@", text)
        text = self._BEARER_PATTERN.sub(r"\1[REDACTED_TOKEN]", text)
        text = self._PWD_PATTERN.sub(r"\1[REDACTED]\2", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        # When record.args is present the log message has not yet been
        # interpolated. Evaluate it now so that credential values embedded
        # as %s / %d / %(key)s arguments are also redacted.
        if record.args:
            try:
                formatted = record.getMessage()
            except Exception:
                formatted = str(record.msg)
            record.msg = self._redact(formatted)
            record.args = ()  # prevent double-interpolation by the handler
        elif isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        return True


def attach_sensitive_data_filter(logger_or_handler=None) -> None:
    """
    Attach a SensitiveDataFilter to each handler of the given logger
    (or the root logger when logger_or_handler is None).

    Avoids duplicate filters: if a SensitiveDataFilter is already attached
    to a handler it will not be added again.

    This is safe to call multiple times (idempotent).
    """
    target = logger_or_handler if logger_or_handler is not None else logging.getLogger()
    handlers = target.handlers if hasattr(target, "handlers") else [target]
    for handler in handlers:
        already_attached = any(
            isinstance(f, SensitiveDataFilter) for f in handler.filters
        )
        if not already_attached:
            handler.addFilter(SensitiveDataFilter())


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
