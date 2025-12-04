"""Service factory module.

Implements pseudo-dependency injection with singleton pattern.
Services are initialized once and reused for the function lifetime.
"""

from .blob_service import BlobService
from .cosmos_service import CosmosService
from .document_service import DocumentService
from .pdf_service import PdfService

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
    "get_document_service",
    "get_cosmos_service",
    "get_blob_service",
    "get_pdf_service",
    "reset_services",
]
