"""
Global logger for the Northstar Deletion Audit Agent.

Logs to both sys.stdout and log.txt using the format:
    %(asctime)s - %(name)s - %(levelname)s - %(message)s

Provides get_logger(name) so every module gets its own named logger while
sharing the same handlers. Also exposes convenience helpers log_system(),
log_error(), and log_chat() for structured transcript entries.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Resolve log.txt relative to this file's package location so it always lands
# in the project root regardless of the current working directory.
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "log.txt")
_LOG_FILE = os.path.abspath(_LOG_FILE)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str = "deletion_audit") -> logging.Logger:
    """Return a configured logger writing to both log.txt and sys.stdout."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    # Rotating file handler -> log.txt
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


# Module-level default logger for convenience imports.
logger = get_logger("deletion_audit")


def log_system(message: str) -> None:
    """Log a system-level event."""
    logger.info("[SYSTEM] %s", message)


def log_error(message: str) -> None:
    """Log an error event."""
    logger.error("[ERROR] %s", message)


def log_chat(role: str, message: str) -> None:
    """Log a chat-transcript entry (user / assistant)."""
    logger.info("[CHAT %s] %s", role.upper(), message)
