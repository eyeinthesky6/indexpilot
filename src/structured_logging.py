"""Structured logging support (JSON format)"""

import json
import logging
import sys
from datetime import datetime
from typing import Any

from src.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON string
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add context if present
        if hasattr(record, "context"):
            log_data["context"] = record.context

        return json.dumps(log_data, default=str)


def is_structured_logging_enabled() -> bool:
    """Check if structured logging is enabled"""
    return _config_loader.get_bool("features.structured_logging.enabled", False)


def get_structured_logging_config() -> dict[str, Any]:
    """Get structured logging configuration"""
    return {
        "enabled": is_structured_logging_enabled(),
        "format": _config_loader.get_str(
            "features.structured_logging.format", "json"
        ),  # json or text
        "include_context": _config_loader.get_bool(
            "features.structured_logging.include_context", True
        ),
        "include_stack_trace": _config_loader.get_bool(
            "features.structured_logging.include_stack_trace", False
        ),
    }


def setup_structured_logging():
    """
    Set up structured logging if enabled.

    This should be called early in application startup.
    """
    config = get_structured_logging_config()

    if not config["enabled"]:
        return

    # Get root logger
    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Set JSON formatter
    formatter: logging.Formatter
    if config["format"] == "json":
        formatter = JSONFormatter()
    else:
        # Use standard formatter
        formatter: logging.Formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger.info("Structured logging enabled", extra={"format": config["format"]})


def log_with_context(
    level: int,
    message: str,
    context: dict[str, Any] | None = None,
    extra_fields: dict[str, Any] | None = None,
):
    """
    Log a message with structured context.

    Args:
        level: Log level (logging.INFO, etc.)
        message: Log message
        context: Additional context dict
        extra_fields: Extra fields to include
    """
    logger_instance = logging.getLogger(__name__)

    # Create log record with context
    record = logger_instance.makeRecord(
        logger_instance.name,
        level,
        "",
        0,
        message,
        (),
        None,
    )

    if context:
        record.context = context
    if extra_fields:
        record.extra_fields = extra_fields

    logger_instance.handle(record)


def get_logging_status() -> dict[str, Any]:
    """
    Get current logging configuration status.

    Returns:
        dict with logging status
    """
    config = get_structured_logging_config()
    root_logger = logging.getLogger()

    handlers_info = []
    for handler in root_logger.handlers:
        handlers_info.append(
            {
                "type": type(handler).__name__,
                "level": logging.getLevelName(handler.level),
                "formatter": type(handler.formatter).__name__ if handler.formatter else None,
            }
        )

    return {
        "structured_logging_enabled": config["enabled"],
        "format": config["format"],
        "root_level": logging.getLevelName(root_logger.level),
        "handlers": handlers_info,
        "include_context": config["include_context"],
    }
