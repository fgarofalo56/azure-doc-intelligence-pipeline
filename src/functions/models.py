"""Pydantic models for API request/response validation.

Provides type-safe models for all API endpoints with automatic validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProcessingStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ============================================================================
# Request Models
# ============================================================================


class ProcessDocumentRequest(BaseModel):
    """Request body for POST /api/process endpoint."""

    blob_url: HttpUrl = Field(
        ...,
        alias="blobUrl",
        description="Full URL to the PDF blob (with or without SAS token)",
    )
    blob_name: str = Field(
        ...,
        alias="blobName",
        min_length=1,
        description="Blob path within container (e.g., 'incoming/document.pdf')",
    )
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        description="Document Intelligence model ID (defaults to prebuilt-layout)",
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        alias="webhookUrl",
        description="Optional webhook URL for completion notification",
    )

    model_config = {"populate_by_name": True}

    @field_validator("blob_name")
    @classmethod
    def validate_blob_name(cls, v: str) -> str:
        """Ensure blob name ends with .pdf."""
        if not v.lower().endswith(".pdf"):
            raise ValueError("blob_name must be a PDF file (.pdf extension)")
        return v


class ReprocessRequest(BaseModel):
    """Request body for POST /api/reprocess endpoint."""

    model_id: str | None = Field(
        default=None,
        alias="modelId",
        description="Override model ID for reprocessing",
    )
    force: bool = Field(
        default=False,
        description="Force reprocessing even if status is completed",
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        alias="webhookUrl",
        description="Optional webhook URL for completion notification",
    )

    model_config = {"populate_by_name": True}


class DeleteDocumentRequest(BaseModel):
    """Request body for DELETE /api/documents endpoint."""

    delete_splits: bool = Field(
        default=True,
        alias="deleteSplits",
        description="Also delete split PDFs from _splits/ folder",
    )
    delete_original: bool = Field(
        default=False,
        alias="deleteOriginal",
        description="Also delete original PDF from incoming/ folder",
    )

    model_config = {"populate_by_name": True}


class BatchProcessRequest(BaseModel):
    """Request body for POST /api/batch endpoint."""

    blobs: list[dict[str, str]] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of blobs to process (each with blobUrl and blobName)",
    )
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        description="Document Intelligence model ID (applies to all blobs)",
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        alias="webhookUrl",
        description="Webhook URL for batch completion notification",
    )
    parallel: bool = Field(
        default=True,
        description="Process blobs in parallel (default) or sequentially",
    )

    model_config = {"populate_by_name": True}


class CostEstimateRequest(BaseModel):
    """Request body for POST /api/estimate-cost endpoint."""

    blob_url: HttpUrl | None = Field(
        default=None,
        alias="blobUrl",
        description="URL to PDF for page count estimation",
    )
    page_count: int | None = Field(
        default=None,
        alias="pageCount",
        ge=1,
        le=10000,
        description="Manual page count if blob_url not provided",
    )
    model_id: str | None = Field(
        default=None,
        alias="modelId",
        description="Model ID to estimate pricing for",
    )

    model_config = {"populate_by_name": True}

    @field_validator("page_count")
    @classmethod
    def validate_page_count(cls, v: int | None, info: Any) -> int | None:
        """Ensure either blob_url or page_count is provided."""
        # Validation happens at runtime with both values
        return v


class MultiModelRequest(BaseModel):
    """Request body for POST /api/process-multi endpoint."""

    blob_url: HttpUrl = Field(
        ...,
        alias="blobUrl",
        description="Full URL to the PDF blob",
    )
    blob_name: str = Field(
        ...,
        alias="blobName",
        min_length=1,
        description="Blob path within container",
    )
    model_mapping: dict[str, str] = Field(
        ...,
        alias="modelMapping",
        description="Mapping of page ranges to model IDs (e.g., {'1-2': 'model-a', '3-4': 'model-b'})",
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        alias="webhookUrl",
        description="Optional webhook URL for completion notification",
    )

    model_config = {"populate_by_name": True}


# ============================================================================
# Response Models
# ============================================================================


class FormResult(BaseModel):
    """Result for a single processed form."""

    form_number: int = Field(..., alias="formNumber")
    document_id: str = Field(..., alias="documentId")
    page_range: str = Field(..., alias="pageRange")
    status: ProcessingStatus
    error: str | None = None

    model_config = {"populate_by_name": True}


class ProcessDocumentResponse(BaseModel):
    """Response for POST /api/process endpoint."""

    status: ProcessingStatus
    document_id: str | None = Field(default=None, alias="documentId")
    processed_at: datetime = Field(..., alias="processedAt")
    forms_processed: int = Field(..., alias="formsProcessed")
    total_forms: int | None = Field(default=None, alias="totalForms")
    original_page_count: int | None = Field(default=None, alias="originalPageCount")
    results: list[FormResult] | None = None

    model_config = {"populate_by_name": True}


class DocumentStatusResponse(BaseModel):
    """Response for GET /api/status endpoint."""

    status: ProcessingStatus
    document_id: str = Field(..., alias="documentId")
    source_file: str = Field(..., alias="sourceFile")
    processed_at: datetime | None = Field(default=None, alias="processedAt")
    form_number: int | None = Field(default=None, alias="formNumber")
    total_forms: int | None = Field(default=None, alias="totalForms")

    model_config = {"populate_by_name": True}


class BatchStatusResponse(BaseModel):
    """Response for GET /api/status/batch endpoint."""

    source_file: str = Field(..., alias="sourceFile")
    total_forms: int = Field(..., alias="totalForms")
    completed: int
    failed: int
    pending: int
    documents: list[DocumentStatusResponse]

    model_config = {"populate_by_name": True}


class DeleteDocumentResponse(BaseModel):
    """Response for DELETE /api/documents endpoint."""

    status: str
    deleted_documents: int = Field(..., alias="deletedDocuments")
    deleted_blobs: int = Field(..., alias="deletedBlobs")
    errors: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    """Response for GET /api/health endpoint."""

    status: str
    timestamp: datetime
    version: str = Field(default="2.0.0")
    services: dict[str, str] = Field(default_factory=dict)
    blob_trigger: dict[str, Any] | None = Field(
        default=None,
        alias="blobTrigger",
        description="Blob trigger health status",
    )

    model_config = {"populate_by_name": True}


class CostEstimateResponse(BaseModel):
    """Response for POST /api/estimate-cost endpoint."""

    page_count: int = Field(..., alias="pageCount")
    forms_count: int = Field(..., alias="formsCount")
    model_type: str = Field(..., alias="modelType")
    pricing: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_usd: float = Field(..., alias="estimatedCostUsd")
    notes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class BatchProcessResponse(BaseModel):
    """Response for POST /api/batch endpoint."""

    status: str
    batch_id: str = Field(..., alias="batchId")
    total_blobs: int = Field(..., alias="totalBlobs")
    processed: int
    failed: int
    results: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    """Standard error response."""

    status: str = "error"
    error: str
    details: dict[str, Any] | None = None


# ============================================================================
# Webhook Models
# ============================================================================


class WebhookPayload(BaseModel):
    """Payload sent to webhook URL on processing completion."""

    event: str = Field(
        default="document.processed",
        description="Event type",
    )
    source_file: str = Field(..., alias="sourceFile")
    status: ProcessingStatus
    processed_at: datetime = Field(..., alias="processedAt")
    forms_processed: int = Field(..., alias="formsProcessed")
    total_forms: int = Field(..., alias="totalForms")
    document_ids: list[str] = Field(..., alias="documentIds")
    error: str | None = None

    model_config = {"populate_by_name": True}


# ============================================================================
# Cosmos DB Document Models
# ============================================================================


class ExtractedDocument(BaseModel):
    """Document stored in Cosmos DB."""

    id: str
    source_file: str = Field(..., alias="sourceFile")
    processed_pdf_url: str | None = Field(default=None, alias="processedPdfUrl")
    processed_at: datetime = Field(..., alias="processedAt")
    form_number: int = Field(default=1, alias="formNumber")
    total_forms: int = Field(default=1, alias="totalForms")
    page_range: str | None = Field(default=None, alias="pageRange")
    original_page_count: int | None = Field(default=None, alias="originalPageCount")
    model_id: str = Field(..., alias="modelId")
    model_confidence: float | None = Field(default=None, alias="modelConfidence")
    doc_type: str | None = Field(default=None, alias="docType")
    fields: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    status: ProcessingStatus
    error: str | None = None
    retry_count: int = Field(default=0, alias="retryCount")

    model_config = {"populate_by_name": True}
