"""Configuration module for Azure Functions.

Loads configuration from environment variables with validation.
"""

import os
from dataclasses import dataclass


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""

    def __init__(self, missing_vars: list[str]) -> None:
        self.missing_vars = missing_vars
        super().__init__(f"Missing required environment variables: {', '.join(missing_vars)}")


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
            raise ConfigurationError(missing)

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
        )


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
