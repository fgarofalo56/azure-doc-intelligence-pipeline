"""Unit tests for the logging service."""

import json
import logging
import os
from unittest.mock import patch

import pytest


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_format_basic_message(self):
        """Test basic message formatting."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert data["location"]["file"] == "/path/to/file.py"
        assert data["location"]["line"] == 42

    def test_format_with_args(self):
        """Test message formatting with arguments."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Value is %d",
            args=(42,),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["message"] == "Value is 42"

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/file.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "Test error"
        assert "traceback" in data["exception"]

    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-123"
        record.user_id = "user-456"

        result = formatter.format(record)
        data = json.loads(result)

        assert "extra" in data
        assert data["extra"]["request_id"] == "req-123"
        assert data["extra"]["user_id"] == "user-456"

    def test_format_without_extra_fields(self):
        """Test formatting without extra fields."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter(include_extra=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.custom_field = "value"

        result = formatter.format(record)
        data = json.loads(result)

        assert "extra" not in data

    def test_format_non_serializable_extra(self):
        """Test handling non-JSON-serializable extra fields."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        # Add a non-serializable object
        record.complex_obj = object()

        result = formatter.format(record)
        data = json.loads(result)

        assert "extra" in data
        # Should be converted to string
        assert "object at" in data["extra"]["complex_obj"]

    def test_format_uses_environment_vars(self):
        """Test formatter uses environment variables."""
        from src.functions.services.logging_service import JsonFormatter

        with patch.dict(
            os.environ,
            {"WEBSITE_SITE_NAME": "my-function-app", "AZURE_FUNCTIONS_ENVIRONMENT": "Production"},
        ):
            formatter = JsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["service"] == "my-function-app"
        assert data["environment"] == "Production"

    def test_format_default_environment(self):
        """Test formatter uses defaults when env vars missing."""
        from src.functions.services.logging_service import JsonFormatter

        with patch.dict(os.environ, {}, clear=True):
            formatter = JsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["service"] == "local-functions"
        assert data["environment"] == "Development"

    def test_format_no_pathname(self):
        """Test formatting when pathname is None."""
        from src.functions.services.logging_service import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        # Should not include location when pathname is empty
        assert "location" not in data or not data.get("location", {}).get("file")


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_init(self):
        """Test logger initialization."""
        from src.functions.services.logging_service import StructuredLogger

        logger = StructuredLogger("test.module")

        assert logger._logger.name == "test.module"
        assert logger._context == {}

    def test_with_context(self):
        """Test creating logger with context."""
        from src.functions.services.logging_service import StructuredLogger

        logger = StructuredLogger("test")
        new_logger = logger.with_context(request_id="req-123", user="bob")

        assert new_logger._context["request_id"] == "req-123"
        assert new_logger._context["user"] == "bob"
        # Original logger unchanged
        assert logger._context == {}

    def test_with_context_chaining(self):
        """Test chaining context additions."""
        from src.functions.services.logging_service import StructuredLogger

        logger = StructuredLogger("test")
        new_logger = logger.with_context(a="1").with_context(b="2")

        assert new_logger._context["a"] == "1"
        assert new_logger._context["b"] == "2"

    def test_debug_logging(self, caplog):
        """Test debug level logging."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.DEBUG)
        logger = StructuredLogger("test")
        logger.debug("Debug message", key="value")

        assert "Debug message" in caplog.text

    def test_info_logging(self, caplog):
        """Test info level logging."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.INFO)
        logger = StructuredLogger("test")
        logger.info("Info message")

        assert "Info message" in caplog.text

    def test_warning_logging(self, caplog):
        """Test warning level logging."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.WARNING)
        logger = StructuredLogger("test")
        logger.warning("Warning message")

        assert "Warning message" in caplog.text

    def test_error_logging(self, caplog):
        """Test error level logging."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.ERROR)
        logger = StructuredLogger("test")
        logger.error("Error message")

        assert "Error message" in caplog.text

    def test_exception_logging(self, caplog):
        """Test exception logging with traceback."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.ERROR)
        logger = StructuredLogger("test")

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("Exception occurred")

        assert "Exception occurred" in caplog.text
        assert "ValueError" in caplog.text

    def test_logging_with_context(self, caplog):
        """Test logging includes context."""
        from src.functions.services.logging_service import StructuredLogger

        caplog.set_level(logging.INFO)
        logger = StructuredLogger("test").with_context(request_id="req-456")
        logger.info("Test message", extra_field="extra")

        # Context should be in the log record
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.request_id == "req-456"
        assert record.extra_field == "extra"


class TestConfigureJsonLogging:
    """Tests for configure_json_logging function."""

    def test_configure_with_json_format_env(self):
        """Test configuration with LOG_FORMAT=json."""
        from src.functions.services.logging_service import JsonFormatter, configure_json_logging

        with patch.dict(os.environ, {"LOG_FORMAT": "json"}, clear=False):
            configure_json_logging(level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert len(root_logger.handlers) > 0
        assert isinstance(root_logger.handlers[0].formatter, JsonFormatter)

    def test_configure_in_azure_environment(self):
        """Test configuration in Azure environment uses JSON."""
        from src.functions.services.logging_service import JsonFormatter, configure_json_logging

        with patch.dict(os.environ, {"WEBSITE_SITE_NAME": "my-app"}, clear=False):
            configure_json_logging(level="INFO")

        root_logger = logging.getLogger()
        assert isinstance(root_logger.handlers[0].formatter, JsonFormatter)

    def test_configure_local_environment(self):
        """Test configuration in local environment uses readable format."""
        from src.functions.services.logging_service import JsonFormatter, configure_json_logging

        # Clear Azure-related env vars
        env = {k: v for k, v in os.environ.items() if k not in ["WEBSITE_SITE_NAME", "LOG_FORMAT"]}
        with patch.dict(os.environ, env, clear=True):
            configure_json_logging(level="INFO")

        root_logger = logging.getLogger()
        assert not isinstance(root_logger.handlers[0].formatter, JsonFormatter)

    def test_configure_removes_existing_handlers(self):
        """Test configuration removes existing handlers."""
        from src.functions.services.logging_service import configure_json_logging

        root_logger = logging.getLogger()
        # Add some dummy handlers
        root_logger.addHandler(logging.StreamHandler())
        root_logger.addHandler(logging.StreamHandler())

        initial_count = len(root_logger.handlers)
        assert initial_count >= 2

        with patch.dict(os.environ, {}, clear=True):
            configure_json_logging(level="INFO")

        # Should have exactly one handler now
        assert len(root_logger.handlers) == 1

    def test_configure_invalid_level_defaults_to_info(self):
        """Test invalid level defaults to INFO."""
        from src.functions.services.logging_service import configure_json_logging

        with patch.dict(os.environ, {}, clear=True):
            configure_json_logging(level="INVALID")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO


class TestGetStructuredLogger:
    """Tests for get_structured_logger function."""

    def test_get_logger(self):
        """Test getting structured logger."""
        from src.functions.services.logging_service import StructuredLogger, get_structured_logger

        logger = get_structured_logger("my.module")

        assert isinstance(logger, StructuredLogger)
        assert logger._logger.name == "my.module"

    def test_get_logger_different_names(self):
        """Test getting loggers with different names."""
        from src.functions.services.logging_service import get_structured_logger

        logger1 = get_structured_logger("module.a")
        logger2 = get_structured_logger("module.b")

        assert logger1._logger.name == "module.a"
        assert logger2._logger.name == "module.b"
