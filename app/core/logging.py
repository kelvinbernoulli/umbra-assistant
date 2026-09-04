"""
Structured logging configuration. Keeps ingestion pipeline traceable —
every log line from the pipeline should carry a request/document id so
you can follow one message end-to-end through normalize -> embed -> upsert.
"""

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Avoid duplicate handlers on reload
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers unless we're actively debugging them
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
