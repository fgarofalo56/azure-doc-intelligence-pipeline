"""Structured JSON logging service for Log Analytics integration.

Provides JSON-formatted logs for better parsing and querying in Azure Log Analytics.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured log messages."""

    def __init__(self, include_extra: bool = True) -> None:
        """Initialize JSON formatter.

        Args:
            include_extra: Include extra fields from log record.
        """
        super().__init__()
        self.include_extra = include_extra
        self._service_name = os.environ.get("WEBSITE_SITE_NAME", "local-functions")
        self._environment = os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT", "Development")

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service_name,
            "environment": self._environment,
        }

        # Add location info
        if record.pathname:
            log_data["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from record
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                    "taskName",
                ):
                    try:
                        # Try to serialize the value
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)

            if extra_fields:
                log_data["extra"] = extra_fields

        return json.dumps(log_data, default=str)


class StructuredLogger:
    """Logger wrapper with structured logging support."""

    def __init__(self, name: str) -> None:
        """Initialize structured logger.

        Args:
            name: Logger name (usually __name__).
        """
        self._logger = logging.getLogger(name)
        self._context: dict[str, Any] = {}

    def with_context(self, **kwargs: Any) -> "StructuredLogger":
        """Create logger with additional context.

        Args:
            **kwargs: Context fields to include in logs.

        Returns:
            New logger with context.
        """
        new_logger = StructuredLogger(self._logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Log with structured data.

        Args:
            level: Log level.
            message: Log message.
            **kwargs: Additional fields.
        """
        extra = {**self._context, **kwargs}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(message, extra={**self._context, **kwargs})


def configure_json_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatting.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    # Only configure in production (Azure) - keep readable logs locally
    is_azure = os.environ.get("WEBSITE_SITE_NAME") is not None
    use_json = os.environ.get("LOG_FORMAT", "auto").lower() == "json" or is_azure

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler with appropriate formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(handler)


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        StructuredLogger instance.
    """
    return StructuredLogger(name)
