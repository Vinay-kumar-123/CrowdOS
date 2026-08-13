import logging
import sys
from config.settings import ai_settings


def setup_ai_logger(name: str = "crowdos-ai") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(ai_settings.LOG_LEVEL.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


ai_logger = setup_ai_logger()
