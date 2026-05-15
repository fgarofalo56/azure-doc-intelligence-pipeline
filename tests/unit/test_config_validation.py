"""Unit tests for configuration validation."""

import pytest

from config import (
    Config,
    ConfigurationError,
    ValidationError,
    reset_config,
    validate_config,
)


@pytest.fixture
def valid_config() -> Config:
    """Create a valid configuration for testing."""
    return Config(
        doc_intel_endpoint="https://test.cognitiveservices.azure.com",
        doc_intel_api_key="test-api-key",
        cosmos_endpoint="https://test.documents.azure.com:443/",
        cosmos_database="TestDatabase",
        cosmos_container="TestContainer",
        storage_connection_string="DefaultEndpointsProtocol=https;...",
        key_vault_name="test-vault",
        function_timeout=230,
        log_level="INFO",
        max_concurrent_requests=10,
        default_model_id="prebuilt-layout",
        sas_token_expiry_hours=1,
        webhook_url=None,
        dead_letter_container="_dead_letter",
        max_retry_attempts=3,
        dlq_retry_schedule="0 */15 * * * *",
        dlq_retry_batch_size=10,
        dlq_retry_enabled=True,
        pages_per_form=2,
        concurrent_doc_intel_calls=3,
        doc_intel_max_retries=5,
        retry_initial_delay=2.0,
        batch_max_blobs=50,
        multi_tenant_enabled=False,
        default_tenant_id="default",
        shutdown_timeout=30,
    )


@pytest.fixture(autouse=True)
def cleanup_config():
    """Reset config singleton after each test."""
    yield
    reset_config()


class TestValidationError:
    """Tests for ValidationError class."""

    def test_validation_error_str_with_value(self) -> None:
        """Test ValidationError string representation with value."""
        error = ValidationError("test_field", "Test message", "bad_value")
        assert str(error) == "test_field: Test message (got: 'bad_value')"

    def test_validation_error_str_without_value(self) -> None:
        """Test ValidationError string representation without value."""
        error = ValidationError("test_field", "Test message")
        assert str(error) == "test_field: Test message"


class TestConfigValidation:
    """Tests for Config.validate() method."""

    def test_valid_config_passes_validation(self, valid_config: Config) -> None:
        """Test that valid configuration passes all validation."""
        errors = valid_config.validate()
        assert len(errors) == 0

    def test_validate_config_function(self, valid_config: Config) -> None:
        """Test validate_config function with valid config."""
        # Should not raise
        validate_config(valid_config)


class TestUrlValidation:
    """Tests for URL validation."""

    def test_valid_https_url(self, valid_config: Config) -> None:
        """Test that valid HTTPS URL passes."""
        valid_config.doc_intel_endpoint = "https://test.cognitiveservices.azure.com"
        errors = valid_config.validate()
        url_errors = [e for e in errors if e.field == "doc_intel_endpoint"]
        assert len(url_errors) == 0

    def test_valid_http_url(self, valid_config: Config) -> None:
        """Test that valid HTTP URL passes (for local development)."""
        valid_config.doc_intel_endpoint = "http://localhost:8080"
        errors = valid_config.validate()
        url_errors = [e for e in errors if e.field == "doc_intel_endpoint"]
        assert len(url_errors) == 0

    def test_empty_url_fails(self, valid_config: Config) -> None:
        """Test that empty URL fails validation."""
        valid_config.doc_intel_endpoint = ""
        errors = valid_config.validate()
        url_errors = [e for e in errors if e.field == "doc_intel_endpoint"]
        assert len(url_errors) == 1
        assert "empty" in url_errors[0].message.lower()

    def test_url_without_scheme_fails(self, valid_config: Config) -> None:
        """Test that URL without scheme fails."""
        valid_config.doc_intel_endpoint = "test.cognitiveservices.azure.com"
        errors = valid_config.validate()
        url_errors = [e for e in errors if e.field == "doc_intel_endpoint"]
        assert len(url_errors) >= 1

    def test_url_with_invalid_scheme_fails(self, valid_config: Config) -> None:
        """Test that URL with invalid scheme fails."""
        valid_config.doc_intel_endpoint = "ftp://test.cognitiveservices.azure.com"
        errors = valid_config.validate()
        url_errors = [e for e in errors if e.field == "doc_intel_endpoint"]
        assert len(url_errors) == 1
        assert "http or https" in url_errors[0].message

    def test_webhook_url_validation_when_set(self, valid_config: Config) -> None:
        """Test that webhook URL is validated when provided."""
        valid_config.webhook_url = "not-a-valid-url"
        errors = valid_config.validate()
        webhook_errors = [e for e in errors if e.field == "webhook_url"]
        assert len(webhook_errors) >= 1

    def test_webhook_url_not_validated_when_none(self, valid_config: Config) -> None:
        """Test that None webhook URL is not validated."""
        valid_config.webhook_url = None
        errors = valid_config.validate()
        webhook_errors = [e for e in errors if e.field == "webhook_url"]
        assert len(webhook_errors) == 0


class TestNumericRangeValidation:
    """Tests for numeric range validation."""

    def test_function_timeout_valid(self, valid_config: Config) -> None:
        """Test valid function timeout."""
        valid_config.function_timeout = 230
        errors = valid_config.validate()
        timeout_errors = [e for e in errors if e.field == "function_timeout"]
        assert len(timeout_errors) == 0

    def test_function_timeout_too_low(self, valid_config: Config) -> None:
        """Test function timeout below minimum."""
        valid_config.function_timeout = 0
        errors = valid_config.validate()
        timeout_errors = [e for e in errors if e.field == "function_timeout"]
        assert len(timeout_errors) == 1
        assert "1" in timeout_errors[0].message

    def test_function_timeout_too_high(self, valid_config: Config) -> None:
        """Test function timeout above maximum."""
        valid_config.function_timeout = 1000
        errors = valid_config.validate()
        timeout_errors = [e for e in errors if e.field == "function_timeout"]
        assert len(timeout_errors) == 1

    def test_max_concurrent_requests_range(self, valid_config: Config) -> None:
        """Test max concurrent requests validation."""
        valid_config.max_concurrent_requests = 150
        errors = valid_config.validate()
        concurrency_errors = [e for e in errors if e.field == "max_concurrent_requests"]
        assert len(concurrency_errors) == 1

    def test_pages_per_form_valid(self, valid_config: Config) -> None:
        """Test valid pages per form."""
        valid_config.pages_per_form = 2
        errors = valid_config.validate()
        pages_errors = [e for e in errors if e.field == "pages_per_form"]
        assert len(pages_errors) == 0

    def test_pages_per_form_too_low(self, valid_config: Config) -> None:
        """Test pages per form below minimum."""
        valid_config.pages_per_form = 0
        errors = valid_config.validate()
        pages_errors = [e for e in errors if e.field == "pages_per_form"]
        assert len(pages_errors) == 1

    def test_shutdown_timeout_valid_range(self, valid_config: Config) -> None:
        """Test shutdown timeout in valid range."""
        valid_config.shutdown_timeout = 60
        errors = valid_config.validate()
        timeout_errors = [e for e in errors if e.field == "shutdown_timeout"]
        assert len(timeout_errors) == 0

    def test_shutdown_timeout_too_low(self, valid_config: Config) -> None:
        """Test shutdown timeout below minimum."""
        valid_config.shutdown_timeout = 2
        errors = valid_config.validate()
        timeout_errors = [e for e in errors if e.field == "shutdown_timeout"]
        assert len(timeout_errors) == 1

    def test_retry_initial_delay_float(self, valid_config: Config) -> None:
        """Test that float values work for retry delay."""
        valid_config.retry_initial_delay = 1.5
        errors = valid_config.validate()
        delay_errors = [e for e in errors if e.field == "retry_initial_delay"]
        assert len(delay_errors) == 0


class TestLogLevelValidation:
    """Tests for log level validation."""

    @pytest.mark.parametrize(
        "level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug", "info"],
    )
    def test_valid_log_levels(self, valid_config: Config, level: str) -> None:
        """Test valid log levels (case-insensitive)."""
        valid_config.log_level = level
        errors = valid_config.validate()
        log_errors = [e for e in errors if e.field == "log_level"]
        assert len(log_errors) == 0

    def test_invalid_log_level(self, valid_config: Config) -> None:
        """Test invalid log level."""
        valid_config.log_level = "TRACE"
        errors = valid_config.validate()
        log_errors = [e for e in errors if e.field == "log_level"]
        assert len(log_errors) == 1
        assert "TRACE" in log_errors[0].value


class TestCronValidation:
    """Tests for CRON expression validation."""

    def test_valid_cron_expression(self, valid_config: Config) -> None:
        """Test valid 6-field CRON expression."""
        valid_config.dlq_retry_schedule = "0 */15 * * * *"
        errors = valid_config.validate()
        cron_errors = [e for e in errors if e.field == "dlq_retry_schedule"]
        assert len(cron_errors) == 0

    def test_valid_cron_with_ranges(self, valid_config: Config) -> None:
        """Test CRON with range syntax."""
        valid_config.dlq_retry_schedule = "0 0-30/5 * * * 1-5"
        errors = valid_config.validate()
        cron_errors = [e for e in errors if e.field == "dlq_retry_schedule"]
        assert len(cron_errors) == 0

    def test_cron_with_5_fields_fails(self, valid_config: Config) -> None:
        """Test that 5-field CRON (standard) fails for Azure Functions."""
        valid_config.dlq_retry_schedule = "*/15 * * * *"
        errors = valid_config.validate()
        cron_errors = [e for e in errors if e.field == "dlq_retry_schedule"]
        assert len(cron_errors) == 1
        assert "6 fields" in cron_errors[0].message

    def test_cron_with_invalid_chars(self, valid_config: Config) -> None:
        """Test CRON with invalid characters."""
        valid_config.dlq_retry_schedule = "0 @ * * * *"
        errors = valid_config.validate()
        cron_errors = [e for e in errors if e.field == "dlq_retry_schedule"]
        assert len(cron_errors) == 1


class TestContainerNameValidation:
    """Tests for container name validation."""

    def test_valid_container_name(self, valid_config: Config) -> None:
        """Test valid container name."""
        valid_config.dead_letter_container = "my-container"
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "dead_letter_container"]
        assert len(container_errors) == 0

    def test_underscore_prefix_allowed(self, valid_config: Config) -> None:
        """Test that underscore prefix is allowed for system containers."""
        valid_config.dead_letter_container = "_dead_letter"
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "dead_letter_container"]
        assert len(container_errors) == 0

    def test_container_name_too_short(self, valid_config: Config) -> None:
        """Test container name that's too short."""
        valid_config.dead_letter_container = "ab"
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "dead_letter_container"]
        assert len(container_errors) == 1
        assert "3-63" in container_errors[0].message

    def test_container_name_too_long(self, valid_config: Config) -> None:
        """Test container name that's too long."""
        valid_config.dead_letter_container = "a" * 64
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "dead_letter_container"]
        assert len(container_errors) == 1

    def test_container_name_uppercase_fails(self, valid_config: Config) -> None:
        """Test that uppercase container names fail."""
        valid_config.dead_letter_container = "MyContainer"
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "dead_letter_container"]
        assert len(container_errors) == 1


class TestCosmosNameValidation:
    """Tests for Cosmos DB database/container name validation."""

    def test_valid_cosmos_database_name(self, valid_config: Config) -> None:
        """Test valid Cosmos DB database name."""
        valid_config.cosmos_database = "TestDatabase"
        errors = valid_config.validate()
        db_errors = [e for e in errors if e.field == "cosmos_database"]
        assert len(db_errors) == 0

    def test_cosmos_name_with_invalid_chars(self, valid_config: Config) -> None:
        """Test Cosmos name with invalid characters."""
        valid_config.cosmos_database = "Test/Database"
        errors = valid_config.validate()
        db_errors = [e for e in errors if e.field == "cosmos_database"]
        assert len(db_errors) == 1
        assert "/" in db_errors[0].message

    def test_cosmos_name_with_backslash(self, valid_config: Config) -> None:
        """Test Cosmos name with backslash."""
        valid_config.cosmos_container = "Test\\Container"
        errors = valid_config.validate()
        container_errors = [e for e in errors if e.field == "cosmos_container"]
        assert len(container_errors) == 1

    def test_cosmos_name_with_hash(self, valid_config: Config) -> None:
        """Test Cosmos name with hash character."""
        valid_config.cosmos_database = "Test#Database"
        errors = valid_config.validate()
        db_errors = [e for e in errors if e.field == "cosmos_database"]
        assert len(db_errors) == 1

    def test_empty_cosmos_name_fails(self, valid_config: Config) -> None:
        """Test empty Cosmos name fails."""
        valid_config.cosmos_database = ""
        errors = valid_config.validate()
        db_errors = [e for e in errors if e.field == "cosmos_database"]
        assert len(db_errors) == 1


class TestValidateConfigFunction:
    """Tests for validate_config function."""

    def test_raises_on_invalid_config(self, valid_config: Config) -> None:
        """Test that validate_config raises ConfigurationError on invalid config."""
        valid_config.function_timeout = 0
        valid_config.log_level = "INVALID"

        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(valid_config)

        assert "2 error" in str(exc_info.value)
        assert len(exc_info.value.validation_errors) == 2

    def test_does_not_raise_on_valid_config(self, valid_config: Config) -> None:
        """Test that validate_config does not raise on valid config."""
        # Should not raise
        validate_config(valid_config)


class TestMultipleValidationErrors:
    """Tests for configs with multiple validation errors."""

    def test_multiple_errors_collected(self, valid_config: Config) -> None:
        """Test that multiple validation errors are collected."""
        valid_config.doc_intel_endpoint = "not-a-url"
        valid_config.cosmos_endpoint = "also-not-a-url"
        valid_config.function_timeout = 0
        valid_config.log_level = "INVALID"

        errors = valid_config.validate()
        assert len(errors) >= 4

    def test_validation_error_message_format(self, valid_config: Config) -> None:
        """Test that error messages include field, message, and value."""
        valid_config.function_timeout = -1
        errors = valid_config.validate()

        timeout_errors = [e for e in errors if e.field == "function_timeout"]
        assert len(timeout_errors) == 1

        error_str = str(timeout_errors[0])
        assert "function_timeout" in error_str
        assert "-1" in error_str
