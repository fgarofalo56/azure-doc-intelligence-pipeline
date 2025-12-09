"""Service factory module.

Implements pseudo-dependency injection with singleton pattern.
Services are initialized once and reused for the function lifetime.
"""

from .blob_service import BlobService
from .cosmos_service import CosmosService
from .document_service import DocumentService
from .logging_service import (
    JsonFormatter,
    StructuredLogger,
    configure_json_logging,
    get_structured_logger,
)
from .idempotency import (
    PROCESSING_VERSION,
    IdempotencyResult,
    check_and_generate_idempotency,
    check_idempotency,
    create_idempotent_document,
    generate_content_hash,
    generate_idempotency_key,
)
from .job_service import (
    JobService,
    JobStatus,
    ProcessingJob,
    get_job_service,
    reset_job_service,
)
from .pdf_service import FormBoundary, PdfService, PdfSplitError
from .profiles import (
    FieldValidation,
    ProcessingProfile,
    create_profile_from_request,
    get_profile,
    list_profiles,
)
from .rate_limiter import RateLimitConfig, RateLimiter, get_rate_limiter
from .telemetry_service import TelemetryService, get_telemetry_service
from .webhook_service import WebhookService, get_webhook_service

# Global service instances
_document_service: DocumentService | None = None
_cosmos_service: CosmosService | None = None
_blob_service: BlobService | None = None
_pdf_service: PdfService | None = None


def get_document_service() -> DocumentService:
    """Get or create DocumentService singleton.

    Returns:
        DocumentService: Document Intelligence service instance.
    """
    global _document_service
    if _document_service is None:
        from config import get_config

        config = get_config()
        _document_service = DocumentService(
            endpoint=config.doc_intel_endpoint,
            api_key=config.doc_intel_api_key,
            max_concurrent=config.max_concurrent_requests,
            max_retries=config.doc_intel_max_retries,
            initial_retry_delay=config.retry_initial_delay,
        )
    return _document_service


def get_cosmos_service() -> CosmosService:
    """Get or create CosmosService singleton.

    Returns:
        CosmosService: Cosmos DB service instance.
    """
    global _cosmos_service
    if _cosmos_service is None:
        from config import get_config

        config = get_config()
        _cosmos_service = CosmosService(
            endpoint=config.cosmos_endpoint,
            database_name=config.cosmos_database,
            container_name=config.cosmos_container,
        )
    return _cosmos_service


def get_blob_service() -> BlobService | None:
    """Get or create BlobService singleton.

    Returns:
        BlobService | None: Blob service instance, or None if not configured.
    """
    global _blob_service
    if _blob_service is None:
        from config import get_config

        config = get_config()
        if config.storage_connection_string:
            _blob_service = BlobService(
                connection_string=config.storage_connection_string,
                sas_expiry_hours=config.sas_token_expiry_hours,
            )
    return _blob_service


def get_pdf_service(pages_per_form: int = 2) -> PdfService:
    """Get or create PdfService singleton.

    Args:
        pages_per_form: Number of pages per form (default 2).

    Returns:
        PdfService: PDF service instance.
    """
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PdfService(pages_per_form=pages_per_form)
    return _pdf_service


def reset_services() -> None:
    """Reset service instances (for testing).

    This allows tests to re-initialize services with different configurations.
    """
    global _document_service, _cosmos_service, _blob_service, _pdf_service
    _document_service = None
    _cosmos_service = None
    _blob_service = None
    _pdf_service = None


__all__ = [
    "DocumentService",
    "CosmosService",
    "BlobService",
    "PdfService",
    "PdfSplitError",
    "FormBoundary",
    "TelemetryService",
    "WebhookService",
    "JobService",
    "JobStatus",
    "ProcessingJob",
    "JsonFormatter",
    "StructuredLogger",
    "RateLimitConfig",
    "RateLimiter",
    "ProcessingProfile",
    "FieldValidation",
    "IdempotencyResult",
    "PROCESSING_VERSION",
    "get_document_service",
    "get_cosmos_service",
    "get_blob_service",
    "get_pdf_service",
    "get_telemetry_service",
    "get_webhook_service",
    "get_job_service",
    "get_structured_logger",
    "configure_json_logging",
    "get_rate_limiter",
    "get_profile",
    "list_profiles",
    "create_profile_from_request",
    "generate_idempotency_key",
    "generate_content_hash",
    "check_idempotency",
    "check_and_generate_idempotency",
    "create_idempotent_document",
    "reset_services",
    "reset_job_service",
]
