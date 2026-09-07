"""Logging setup for the worker processes.

The API process gets its logging from uvicorn; the CLI workers have no such
host, so they configure their own before anything starts emitting.
"""

import logging

from modules.shared.config import get_settings

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_configured = False


def configure_logging() -> None:
    """Send worker logs to stdout at the configured level, once."""
    global _configured
    if _configured:
        return

    level = getattr(logging, get_settings().app_log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT)
    _configured = True
