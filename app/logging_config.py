"""
Centralized logging configuration for PII redaction system.

Issue 9 fix: Replaces print() statements with structured logging.
"""
import logging
import sys
from app.config import get_settings

settings = get_settings()


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure structured logging for application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("sentinel")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)

    # Human-readable format
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


# Global logger instance
logger = setup_logging(level="DEBUG" if settings.api_debug else "INFO")


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance for module."""
    if name:
        return logging.getLogger(f"sentinel.{name}")
    return logger
