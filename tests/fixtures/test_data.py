"""Test data factories and constants.

Provides factory functions for creating test documents, processing jobs,
configuration objects, and sample API responses.

All factory functions accept **kwargs to allow easy customization
while providing sensible defaults.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# =============================================================================
# CONSTANTS - Sample URLs and connection strings for testing
# =============================================================================

SAMPLE_DOC_INTEL_ENDPOINT = "https://test-doc-intel.cognitiveservices.azure.com"
SAMPLE_COSMOS_ENDPOINT = "https://test-cosmos.documents.azure.com:443/"
SAMPLE_BLOB_URL = "https://teststorage.blob.core.windows.net/documents/test.pdf"
SAMPLE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=https;"
    "AccountName=teststorage;"
    "AccountKey=dGVzdGtleQ==;"
    "EndpointSuffix=core.windows.net"
)
SAMPLE_MODEL_ID = "prebuilt-layout"


# =============================================================================
# DOCUMENT FACTORIES
# =============================================================================


def create_sample_document(
    doc_id: str | None = None,
    source_file: str | None = None,
    status: str = "completed",
    **kwargs,
) -> dict[str, Any]:
    """Create a sample Cosmos DB document for testing.

    Args:
        doc_id: Document ID. Generated if not provided.
        source_file: Source PDF file path. Generated if not provided.
        status: Document status (completed, failed, processing).
        **kwargs: Additional fields to include/override.

    Returns:
        Dict representing a processed document.

    Example:
        # Default document
        doc = create_sample_document()

        # Custom document
        doc = create_sample_document(
            doc_id="custom_id",
            status="failed",
            error="Processing timeout",
        )
    """
    unique_id = uuid4().hex[:8]
    doc_id = doc_id or f"doc_{unique_id}"
    source_file = source_file or f"test-folder/{unique_id}.pdf"

    document = {
        "id": doc_id,
        "sourceFile": source_file,
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "modelId": SAMPLE_MODEL_ID,
        "modelConfidence": 0.95,
        "status": status,
        "fields": {
            "vendorName": "Test Vendor Corp",
            "invoiceTotal": 1500.00,
            "invoiceDate": "2024-01-15",
        },
        "confidence": {
            "vendorName": 0.98,
            "invoiceTotal": 0.95,
            "invoiceDate": 0.92,
        },
        "documentType": "extracted",
    }

    # Override with any provided kwargs
    document.update(kwargs)
    return document


def create_sample_form_result(
    form_number: int = 1,
    total_forms: int = 3,
    page_range: str = "1-2",
    **kwargs,
) -> dict[str, Any]:
    """Create a sample form extraction result for multi-page PDF.

    Args:
        form_number: Form number within the PDF (1-indexed).
        total_forms: Total number of forms in the source PDF.
        page_range: Page range for this form (e.g., "1-2").
        **kwargs: Additional fields to include/override.

    Returns:
        Dict representing an extracted form.

    Example:
        # Create result for form 2 of 5
        result = create_sample_form_result(
            form_number=2,
            total_forms=5,
            page_range="3-4",
        )
    """
    unique_id = uuid4().hex[:8]

    result = {
        "id": f"form_{unique_id}_form{form_number}",
        "sourceFile": f"test-folder/{unique_id}.pdf",
        "processedPdfUrl": f"https://storage.blob.core.windows.net/_splits/{unique_id}_form{form_number}.pdf",
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "formNumber": form_number,
        "totalForms": total_forms,
        "pageRange": page_range,
        "originalPageCount": total_forms * 2,
        "modelId": SAMPLE_MODEL_ID,
        "modelConfidence": 0.92,
        "docType": "invoice",
        "status": "completed",
        "fields": {
            "vendorName": f"Vendor {form_number}",
            "invoiceTotal": 100.00 * form_number,
        },
        "confidence": {
            "vendorName": 0.95,
            "invoiceTotal": 0.93,
        },
    }

    result.update(kwargs)
    return result


# =============================================================================
# JOB FACTORIES
# =============================================================================


def create_processing_job(
    job_id: str | None = None,
    blob_name: str | None = None,
    status: str = "pending",
    **kwargs,
) -> dict[str, Any]:
    """Create a sample processing job for testing.

    Args:
        job_id: Job ID. Generated if not provided.
        blob_name: Source blob name. Generated if not provided.
        status: Job status (pending, queued, processing, completed, failed).
        **kwargs: Additional fields to include/override.

    Returns:
        Dict representing a processing job.

    Example:
        # Create a completed job
        job = create_processing_job(
            status="completed",
            result={"forms_processed": 3},
        )

        # Create a failed job
        job = create_processing_job(
            status="failed",
            error="Rate limit exceeded",
        )
    """
    unique_id = uuid4().hex[:8]
    job_id = job_id or f"job_{unique_id}"
    blob_name = blob_name or f"incoming/{unique_id}.pdf"

    job = {
        "id": job_id,
        "jobId": job_id,
        "blobUrl": f"https://storage.blob.core.windows.net/documents/{blob_name}",
        "blobName": blob_name,
        "modelId": SAMPLE_MODEL_ID,
        "status": status,
        "profileName": None,
        "pagesPerForm": 2,
        "webhookUrl": None,
        "tenantId": None,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "startedAt": None,
        "completedAt": None,
        "progress": {},
        "result": None,
        "error": None,
        "retryCount": 0,
        "maxRetries": 3,
        "documentType": "job",
    }

    # Handle status-specific defaults
    if status == "processing":
        job["startedAt"] = datetime.now(timezone.utc).isoformat()
    elif status in ("completed", "partial"):
        job["startedAt"] = datetime.now(timezone.utc).isoformat()
        job["completedAt"] = datetime.now(timezone.utc).isoformat()
        job["result"] = kwargs.pop("result", {"formsProcessed": 3, "totalForms": 3})
    elif status == "failed":
        job["startedAt"] = datetime.now(timezone.utc).isoformat()
        job["completedAt"] = datetime.now(timezone.utc).isoformat()
        job["error"] = kwargs.pop("error", "Processing failed")

    job.update(kwargs)
    return job


# =============================================================================
# CONFIGURATION FACTORIES
# =============================================================================


def create_sample_config(**kwargs) -> dict[str, Any]:
    """Create a sample configuration dict for testing.

    Args:
        **kwargs: Configuration values to override defaults.

    Returns:
        Dict with configuration values.

    Example:
        config = create_sample_config(
            function_timeout=300,
            log_level="DEBUG",
        )
    """
    config = {
        "doc_intel_endpoint": SAMPLE_DOC_INTEL_ENDPOINT,
        "doc_intel_api_key": "test-api-key",
        "cosmos_endpoint": SAMPLE_COSMOS_ENDPOINT,
        "cosmos_database": "TestDB",
        "cosmos_container": "TestContainer",
        "storage_connection_string": SAMPLE_CONNECTION_STRING,
        "key_vault_name": "test-vault",
        "function_timeout": 230,
        "log_level": "INFO",
        "max_concurrent_requests": 10,
        "default_model_id": SAMPLE_MODEL_ID,
        "sas_token_expiry_hours": 1,
        "webhook_url": None,
        "dead_letter_container": "_dead_letter",
        "max_retry_attempts": 3,
        "dlq_retry_schedule": "0 */15 * * * *",
        "dlq_retry_batch_size": 10,
        "dlq_retry_enabled": True,
        "pages_per_form": 2,
        "concurrent_doc_intel_calls": 3,
        "doc_intel_max_retries": 5,
        "retry_initial_delay": 2.0,
        "batch_max_blobs": 50,
        "multi_tenant_enabled": False,
        "default_tenant_id": "default",
        "shutdown_timeout": 30,
    }

    config.update(kwargs)
    return config


# =============================================================================
# API RESPONSE FACTORIES
# =============================================================================


def create_document_intel_response(
    status: str = "succeeded",
    doc_type: str = "invoice",
    fields: dict[str, Any] | None = None,
    pages: int = 2,
    **kwargs,
) -> dict[str, Any]:
    """Create a sample Document Intelligence API response.

    Args:
        status: Response status (succeeded, running, failed).
        doc_type: Document type detected.
        fields: Extracted fields. Defaults to sample invoice fields.
        pages: Number of pages in the document.
        **kwargs: Additional fields to include/override.

    Returns:
        Dict mimicking Document Intelligence API response.

    Example:
        # Successful response
        response = create_document_intel_response()

        # Failed response
        response = create_document_intel_response(
            status="failed",
            error={"code": "InvalidDocument", "message": "..."},
        )
    """
    default_fields = {
        "vendorName": {
            "type": "string",
            "content": "Test Vendor Corp",
            "confidence": 0.95,
            "boundingRegions": [{"pageNumber": 1}],
        },
        "invoiceTotal": {
            "type": "currency",
            "content": "$1,500.00",
            "value": 1500.00,
            "confidence": 0.92,
            "boundingRegions": [{"pageNumber": 1}],
        },
        "invoiceDate": {
            "type": "date",
            "content": "January 15, 2024",
            "value": "2024-01-15",
            "confidence": 0.90,
            "boundingRegions": [{"pageNumber": 1}],
        },
    }

    response = {
        "status": status,
        "createdDateTime": datetime.now(timezone.utc).isoformat(),
        "lastUpdatedDateTime": datetime.now(timezone.utc).isoformat(),
        "analyzeResult": {
            "apiVersion": "2024-02-29-preview",
            "modelId": SAMPLE_MODEL_ID,
            "stringIndexType": "textElements",
            "content": "Sample document content...",
            "pages": [
                {
                    "pageNumber": i + 1,
                    "angle": 0,
                    "width": 8.5,
                    "height": 11,
                    "unit": "inch",
                    "words": [],
                    "lines": [],
                }
                for i in range(pages)
            ],
            "documents": [
                {
                    "docType": doc_type,
                    "boundingRegions": [{"pageNumber": 1}],
                    "confidence": 0.92,
                    "fields": fields or default_fields,
                }
            ],
        },
    }

    response.update(kwargs)
    return response


def create_webhook_payload(
    event_type: str = "processing.completed",
    job_id: str | None = None,
    status: str = "completed",
    **kwargs,
) -> dict[str, Any]:
    """Create a sample webhook notification payload.

    Args:
        event_type: Type of webhook event.
        job_id: Job ID. Generated if not provided.
        status: Processing status.
        **kwargs: Additional fields to include.

    Returns:
        Dict representing webhook payload.
    """
    job_id = job_id or f"job_{uuid4().hex[:8]}"

    payload = {
        "eventType": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "jobId": job_id,
            "status": status,
            "sourceFile": f"test-folder/{job_id}.pdf",
            "formsProcessed": 3,
            "totalForms": 3,
        },
    }

    payload.update(kwargs)
    return payload


def create_dead_letter_item(
    blob_name: str | None = None,
    reason: str = "rate_limit",
    retry_count: int = 0,
    **kwargs,
) -> dict[str, Any]:
    """Create a sample dead letter queue item.

    Args:
        blob_name: Source blob name. Generated if not provided.
        reason: Reason for dead letter (rate_limit, transient_error, etc.).
        retry_count: Number of previous retry attempts.
        **kwargs: Additional fields to include.

    Returns:
        Dict representing a DLQ item.
    """
    unique_id = uuid4().hex[:8]
    blob_name = blob_name or f"incoming/{unique_id}.pdf"

    item = {
        "id": f"dlq_{unique_id}",
        "blobName": blob_name,
        "blobUrl": f"https://storage.blob.core.windows.net/documents/{blob_name}",
        "modelId": SAMPLE_MODEL_ID,
        "reason": reason,
        "errorMessage": "Rate limit exceeded" if reason == "rate_limit" else "Error",
        "retryCount": retry_count,
        "maxRetries": 3,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "lastAttemptAt": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "documentType": "dead_letter",
    }

    item.update(kwargs)
    return item
