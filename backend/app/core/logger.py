import logging
import sys
from app.core.settings import settings


def setup_logger(name: str = "crowdos") -> logging.Logger:
    """
    Configures structured, production-ready logging.
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
        logger.addHandler(handler)

    return logger


logger = setup_logger()
