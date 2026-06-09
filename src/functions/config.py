"""Configuration module for Azure Functions.

Loads configuration from environment variables with validation.
Implements fail-fast pattern with comprehensive startup validation.
"""

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    def __init__(
        self,
        message: str,
        missing_vars: list[str] | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        self.missing_vars = missing_vars or []
        self.validation_errors = validation_errors or []
        super().__init__(message)


class ValidationError:
    """Individual validation error with context."""

    def __init__(self, field: str, message: str, value: str | None = None) -> None:
        self.field = field
        self.message = message
        self.value = value

    def __str__(self) -> str:
        if self.value is not None:
            return f"{self.field}: {self.message} (got: '{self.value}')"
        return f"{self.field}: {self.message}"


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Document Intelligence settings
    doc_intel_endpoint: str
    doc_intel_api_key: str

    # Cosmos DB settings
    cosmos_endpoint: str
    cosmos_database: str
    cosmos_container: str

    # Storage settings (for SAS token generation)
    storage_connection_string: str | None

    # Optional settings
    key_vault_name: str | None
    function_timeout: int
    log_level: str
    max_concurrent_requests: int
    default_model_id: str
    sas_token_expiry_hours: int

    # Webhook settings
    webhook_url: str | None

    # Dead letter settings
    dead_letter_container: str
    max_retry_attempts: int
    dlq_retry_schedule: str  # CRON expression for DLQ retry timer
    dlq_retry_batch_size: int  # Max items to process per timer run
    dlq_retry_enabled: bool  # Enable/disable automatic DLQ retry processing

    # PDF splitting settings
    pages_per_form: int  # Number of pages per form for PDF splitting

    # Concurrency and retry settings
    concurrent_doc_intel_calls: int  # Max concurrent Document Intelligence API calls
    doc_intel_max_retries: int  # Max retries for Document Intelligence API
    retry_initial_delay: float  # Initial delay for exponential backoff (seconds)
    batch_max_blobs: int  # Max blobs per batch request

    # Multi-tenant settings
    multi_tenant_enabled: bool  # Enable tenant isolation
    default_tenant_id: str  # Default tenant ID when not specified

    # Graceful shutdown settings
    shutdown_timeout: int  # Time allowed for graceful shutdown (seconds)

    @classmethod
    def from_environment(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config: Validated configuration instance.

        Raises:
            ConfigurationError: If required variables are missing.
        """
        required_vars = [
            "DOC_INTEL_ENDPOINT",
            "COSMOS_ENDPOINT",
            "COSMOS_DATABASE",
            "COSMOS_CONTAINER",
        ]

        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing)}",
                missing_vars=missing,
            )

        # API key can come from Key Vault reference or direct env var
        api_key = os.getenv("DOC_INTEL_API_KEY", "")

        # Storage connection string - try multiple common environment variable names
        storage_conn_str = (
            os.getenv("STORAGE_CONNECTION_STRING")
            or os.getenv("AzureWebJobsStorage")
            or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )

        return cls(
            doc_intel_endpoint=os.environ["DOC_INTEL_ENDPOINT"],
            doc_intel_api_key=api_key,
            cosmos_endpoint=os.environ["COSMOS_ENDPOINT"],
            cosmos_database=os.environ["COSMOS_DATABASE"],
            cosmos_container=os.environ["COSMOS_CONTAINER"],
            storage_connection_string=storage_conn_str,
            key_vault_name=os.getenv("KEY_VAULT_NAME"),
            function_timeout=int(os.getenv("FUNCTION_TIMEOUT", "230")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
            default_model_id=os.getenv("DEFAULT_MODEL_ID", "prebuilt-layout"),
            sas_token_expiry_hours=int(os.getenv("SAS_TOKEN_EXPIRY_HOURS", "1")),
            webhook_url=os.getenv("WEBHOOK_URL"),
            dead_letter_container=os.getenv("DEAD_LETTER_CONTAINER", "_dead_letter"),
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            dlq_retry_schedule=os.getenv(
                "DLQ_RETRY_SCHEDULE", "0 */15 * * * *"
            ),  # Every 15 minutes
            dlq_retry_batch_size=int(os.getenv("DLQ_RETRY_BATCH_SIZE", "10")),
            dlq_retry_enabled=os.getenv("DLQ_RETRY_ENABLED", "true").lower() == "true",
            # PDF splitting settings
            pages_per_form=int(os.getenv("PAGES_PER_FORM", "2")),
            # Concurrency and retry settings
            concurrent_doc_intel_calls=int(os.getenv("CONCURRENT_DOC_INTEL_CALLS", "3")),
            doc_intel_max_retries=int(os.getenv("DOC_INTEL_MAX_RETRIES", "5")),
            retry_initial_delay=float(os.getenv("RETRY_INITIAL_DELAY", "2.0")),
            batch_max_blobs=int(os.getenv("BATCH_MAX_BLOBS", "50")),
            # Multi-tenant settings
            multi_tenant_enabled=os.getenv("MULTI_TENANT_ENABLED", "false").lower() == "true",
            default_tenant_id=os.getenv("DEFAULT_TENANT_ID", "default"),
            # Graceful shutdown settings
            shutdown_timeout=int(os.getenv("SHUTDOWN_TIMEOUT", "30")),
        )

    def validate(self) -> list[ValidationError]:
        """Validate configuration values.

        Performs comprehensive validation of all configuration values:
        - URL format validation for endpoints
        - Numeric range validation
        - CRON expression format validation
        - Log level validation

        Returns:
            List of ValidationError objects (empty if valid).
        """
        errors: list[ValidationError] = []

        # Validate endpoint URLs
        errors.extend(self._validate_url("doc_intel_endpoint", self.doc_intel_endpoint))
        errors.extend(self._validate_url("cosmos_endpoint", self.cosmos_endpoint))

        if self.webhook_url:
            errors.extend(self._validate_url("webhook_url", self.webhook_url))

        # Validate numeric ranges
        errors.extend(self._validate_range("function_timeout", self.function_timeout, 1, 600))
        errors.extend(
            self._validate_range("max_concurrent_requests", self.max_concurrent_requests, 1, 100)
        )
        errors.extend(
            self._validate_range("sas_token_expiry_hours", self.sas_token_expiry_hours, 1, 168)
        )
        errors.extend(self._validate_range("max_retry_attempts", self.max_retry_attempts, 0, 10))
        errors.extend(
            self._validate_range("dlq_retry_batch_size", self.dlq_retry_batch_size, 1, 100)
        )
        errors.extend(self._validate_range("pages_per_form", self.pages_per_form, 1, 50))
        errors.extend(
            self._validate_range(
                "concurrent_doc_intel_calls", self.concurrent_doc_intel_calls, 1, 15
            )
        )
        errors.extend(
            self._validate_range("doc_intel_max_retries", self.doc_intel_max_retries, 0, 10)
        )
        errors.extend(
            self._validate_range("retry_initial_delay", self.retry_initial_delay, 0.1, 60.0)
        )
        errors.extend(self._validate_range("batch_max_blobs", self.batch_max_blobs, 1, 1000))
        errors.extend(self._validate_range("shutdown_timeout", self.shutdown_timeout, 5, 300))

        # Validate log level
        errors.extend(self._validate_log_level(self.log_level))

        # Validate CRON expression format
        errors.extend(self._validate_cron("dlq_retry_schedule", self.dlq_retry_schedule))

        # Validate container names
        errors.extend(
            self._validate_container_name("dead_letter_container", self.dead_letter_container)
        )

        # Validate database/container names
        errors.extend(self._validate_cosmos_name("cosmos_database", self.cosmos_database))
        errors.extend(self._validate_cosmos_name("cosmos_container", self.cosmos_container))

        return errors

    def _validate_url(self, field: str, url: str) -> list[ValidationError]:
        """Validate URL format."""
        errors: list[ValidationError] = []
        if not url:
            errors.append(ValidationError(field, "URL cannot be empty"))
            return errors

        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                errors.append(ValidationError(field, "URL must include scheme (http/https)", url))
            elif parsed.scheme not in ("http", "https"):
                errors.append(
                    ValidationError(
                        field, f"URL scheme must be http or https, got '{parsed.scheme}'", url
                    )
                )
            if not parsed.netloc:
                errors.append(ValidationError(field, "URL must include host", url))
        except Exception as e:
            errors.append(ValidationError(field, f"Invalid URL format: {e}", url))

        return errors

    def _validate_range(
        self, field: str, value: int | float, min_val: int | float, max_val: int | float
    ) -> list[ValidationError]:
        """Validate numeric value is within range."""
        if value < min_val or value > max_val:
            return [
                ValidationError(
                    field,
                    f"Value must be between {min_val} and {max_val}",
                    str(value),
                )
            ]
        return []

    def _validate_log_level(self, level: str) -> list[ValidationError]:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level.upper() not in valid_levels:
            return [
                ValidationError(
                    "log_level",
                    f"Must be one of: {', '.join(sorted(valid_levels))}",
                    level,
                )
            ]
        return []

    def _validate_cron(self, field: str, expression: str) -> list[ValidationError]:
        """Validate CRON expression format (6-field Azure Functions format)."""
        # Azure Functions uses 6-field CRON: second minute hour day month weekday
        # Basic pattern check - not exhaustive
        parts = expression.split()
        if len(parts) != 6:
            return [
                ValidationError(
                    field,
                    "CRON expression must have 6 fields (sec min hour day month weekday)",
                    expression,
                )
            ]

        # Basic validation of each field
        cron_pattern = re.compile(r"^[\d\*\/,\-]+$")
        for i, part in enumerate(parts):
            if not cron_pattern.match(part):
                return [
                    ValidationError(
                        field,
                        f"Invalid CRON field at position {i + 1}",
                        expression,
                    )
                ]

        return []

    def _validate_container_name(self, field: str, name: str) -> list[ValidationError]:
        """Validate blob container name format."""
        # Container names: 3-63 chars, lowercase letters, numbers, hyphens
        # Can start with underscore for special containers like _dead_letter
        if not name:
            return [ValidationError(field, "Container name cannot be empty")]

        if len(name) < 3 or len(name) > 63:
            return [
                ValidationError(
                    field,
                    "Container name must be 3-63 characters",
                    name,
                )
            ]

        # Allow underscore prefix and underscores for system containers (e.g., _dead_letter)
        # Standard Azure container names: lowercase letters, numbers, hyphens
        # Extended pattern for system containers: allow leading underscore and underscores in name
        if name.startswith("_"):
            # System container pattern: underscore prefix with letters, numbers, underscores
            if not re.match(r"^_[a-z0-9_]+$", name):
                return [
                    ValidationError(
                        field,
                        "System container name must use lowercase letters, numbers, and underscores",
                        name,
                    )
                ]
        else:
            # Standard Azure container name pattern
            if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", name):
                return [
                    ValidationError(
                        field,
                        "Container name must use lowercase letters, numbers, and hyphens",
                        name,
                    )
                ]

        return []

    def _validate_cosmos_name(self, field: str, name: str) -> list[ValidationError]:
        """Validate Cosmos DB database/container name."""
        if not name:
            return [ValidationError(field, "Name cannot be empty")]

        # Cosmos DB names: 1-255 chars, no /, \\, #, ?
        if len(name) > 255:
            return [ValidationError(field, "Name must be 255 characters or less", name)]

        invalid_chars = re.findall(r"[/\\#?]", name)
        if invalid_chars:
            return [
                ValidationError(
                    field,
                    f"Name contains invalid characters: {', '.join(set(invalid_chars))}",
                    name,
                )
            ]

        return []


def validate_config(config: Config) -> None:
    """Validate configuration and raise if invalid.

    This function should be called during application startup to
    implement fail-fast behavior. It validates all configuration
    values and raises a ConfigurationError with detailed messages
    if any validation fails.

    Args:
        config: Configuration instance to validate.

    Raises:
        ConfigurationError: If validation fails.
    """
    errors = config.validate()

    if errors:
        error_messages = [str(e) for e in errors]
        for error in errors:
            logger.error(f"Configuration validation failed: {error}")

        raise ConfigurationError(
            f"Configuration validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {msg}" for msg in error_messages),
            validation_errors=error_messages,
        )

    logger.info("Configuration validation passed")


def validate_startup() -> Config:
    """Validate configuration at startup and return config.

    Convenience function that loads and validates configuration
    in one call. Use this at application startup.

    Returns:
        Config: Validated configuration instance.

    Raises:
        ConfigurationError: If configuration is missing or invalid.
    """
    config = get_config()
    validate_config(config)
    return config


# Global config instance (initialized on first access)
_config: Config | None = None


def get_config() -> Config:
    """Get the application configuration (singleton).

    Returns:
        Config: Application configuration instance.
    """
    global _config
    if _config is None:
        _config = Config.from_environment()
    return _config


def reset_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config
    _config = None
