"""Unit tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError


class TestProcessingStatus:
    """Tests for ProcessingStatus enum."""

    def test_status_values(self):
        """Test all status enum values exist."""
        from src.functions.models import ProcessingStatus

        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.COMPLETED == "completed"
        assert ProcessingStatus.FAILED == "failed"
        assert ProcessingStatus.PARTIAL == "partial"


class TestProcessDocumentRequest:
    """Tests for ProcessDocumentRequest model."""

    def test_valid_request(self):
        """Test valid request parsing."""
        from src.functions.models import ProcessDocumentRequest

        data = {
            "blobUrl": "https://storage.blob.core.windows.net/pdfs/test.pdf",
            "blobName": "incoming/test.pdf",
        }
        req = ProcessDocumentRequest(**data)

        assert str(req.blob_url) == "https://storage.blob.core.windows.net/pdfs/test.pdf"
        assert req.blob_name == "incoming/test.pdf"
        assert req.model_id is None
        assert req.webhook_url is None

    def test_with_optional_fields(self):
        """Test request with optional fields."""
        from src.functions.models import ProcessDocumentRequest

        data = {
            "blobUrl": "https://storage.blob.core.windows.net/pdfs/test.pdf",
            "blobName": "incoming/test.pdf",
            "modelId": "custom-model-v1",
            "webhookUrl": "https://webhook.example.com/notify",
        }
        req = ProcessDocumentRequest(**data)

        assert req.model_id == "custom-model-v1"
        assert str(req.webhook_url) == "https://webhook.example.com/notify"

    def test_missing_blob_url(self):
        """Test error when blobUrl is missing."""
        from src.functions.models import ProcessDocumentRequest

        with pytest.raises(ValidationError) as exc:
            ProcessDocumentRequest(blobName="test.pdf")

        # Pydantic uses the alias in error messages
        assert "bloburl" in str(exc.value).lower()

    def test_missing_blob_name(self):
        """Test error when blobName is missing."""
        from src.functions.models import ProcessDocumentRequest

        with pytest.raises(ValidationError) as exc:
            ProcessDocumentRequest(blobUrl="https://storage.blob.core.windows.net/test.pdf")

        # Pydantic uses the alias in error messages
        assert "blobname" in str(exc.value).lower()

    def test_invalid_blob_name_not_pdf(self):
        """Test error when blobName is not a PDF."""
        from src.functions.models import ProcessDocumentRequest

        with pytest.raises(ValidationError) as exc:
            ProcessDocumentRequest(
                blobUrl="https://storage.blob.core.windows.net/test.txt",
                blobName="test.txt",
            )

        assert "pdf" in str(exc.value).lower()

    def test_invalid_url(self):
        """Test error on invalid URL."""
        from src.functions.models import ProcessDocumentRequest

        with pytest.raises(ValidationError):
            ProcessDocumentRequest(
                blobUrl="not-a-valid-url",
                blobName="test.pdf",
            )


class TestReprocessRequest:
    """Tests for ReprocessRequest model."""

    def test_defaults(self):
        """Test default values."""
        from src.functions.models import ReprocessRequest

        req = ReprocessRequest()

        assert req.model_id is None
        assert req.force is False
        assert req.webhook_url is None

    def test_with_values(self):
        """Test with explicit values."""
        from src.functions.models import ReprocessRequest

        req = ReprocessRequest(
            modelId="new-model",
            force=True,
            webhookUrl="https://webhook.example.com",
        )

        assert req.model_id == "new-model"
        assert req.force is True


class TestDeleteDocumentRequest:
    """Tests for DeleteDocumentRequest model."""

    def test_defaults(self):
        """Test default values."""
        from src.functions.models import DeleteDocumentRequest

        req = DeleteDocumentRequest()

        assert req.delete_splits is True
        assert req.delete_original is False

    def test_with_values(self):
        """Test with explicit values."""
        from src.functions.models import DeleteDocumentRequest

        req = DeleteDocumentRequest(deleteSplits=False, deleteOriginal=True)

        assert req.delete_splits is False
        assert req.delete_original is True


class TestBatchProcessRequest:
    """Tests for BatchProcessRequest model."""

    def test_valid_request(self):
        """Test valid batch request."""
        from src.functions.models import BatchProcessRequest

        req = BatchProcessRequest(
            blobs=[
                {"blobUrl": "https://storage.blob.core.windows.net/a.pdf", "blobName": "a.pdf"},
                {"blobUrl": "https://storage.blob.core.windows.net/b.pdf", "blobName": "b.pdf"},
            ]
        )

        assert len(req.blobs) == 2
        assert req.model_id is None
        assert req.parallel is True

    def test_empty_blobs_error(self):
        """Test error on empty blobs list."""
        from src.functions.models import BatchProcessRequest

        with pytest.raises(ValidationError):
            BatchProcessRequest(blobs=[])

    def test_too_many_blobs_error(self):
        """Test error when too many blobs."""
        from src.functions.models import BatchProcessRequest

        with pytest.raises(ValidationError):
            BatchProcessRequest(
                blobs=[{"blobUrl": f"https://s.blob/{i}.pdf", "blobName": f"{i}.pdf"} for i in range(51)]
            )


class TestCostEstimateRequest:
    """Tests for CostEstimateRequest model."""

    def test_with_blob_url(self):
        """Test with blob URL."""
        from src.functions.models import CostEstimateRequest

        req = CostEstimateRequest(blobUrl="https://storage.blob.core.windows.net/test.pdf")

        assert req.blob_url is not None
        assert req.page_count is None

    def test_with_page_count(self):
        """Test with page count."""
        from src.functions.models import CostEstimateRequest

        req = CostEstimateRequest(pageCount=100)

        assert req.page_count == 100
        assert req.blob_url is None

    def test_invalid_page_count_negative(self):
        """Test error on negative page count."""
        from src.functions.models import CostEstimateRequest

        with pytest.raises(ValidationError):
            CostEstimateRequest(pageCount=0)

    def test_invalid_page_count_too_large(self):
        """Test error on page count too large."""
        from src.functions.models import CostEstimateRequest

        with pytest.raises(ValidationError):
            CostEstimateRequest(pageCount=10001)


class TestMultiModelRequest:
    """Tests for MultiModelRequest model."""

    def test_valid_request(self):
        """Test valid multi-model request."""
        from src.functions.models import MultiModelRequest

        req = MultiModelRequest(
            blobUrl="https://storage.blob.core.windows.net/test.pdf",
            blobName="test.pdf",
            modelMapping={"1-2": "model-a", "3-4": "model-b"},
        )

        assert req.model_mapping == {"1-2": "model-a", "3-4": "model-b"}


class TestFormResult:
    """Tests for FormResult model."""

    def test_valid_result(self):
        """Test valid form result."""
        from src.functions.models import FormResult, ProcessingStatus

        result = FormResult(
            formNumber=1,
            documentId="doc_123",
            pageRange="1-2",
            status=ProcessingStatus.COMPLETED,
        )

        assert result.form_number == 1
        assert result.document_id == "doc_123"
        assert result.page_range == "1-2"
        assert result.status == ProcessingStatus.COMPLETED
        assert result.error is None


class TestProcessDocumentResponse:
    """Tests for ProcessDocumentResponse model."""

    def test_success_response(self):
        """Test successful response."""
        from src.functions.models import ProcessDocumentResponse, ProcessingStatus

        resp = ProcessDocumentResponse(
            status=ProcessingStatus.COMPLETED,
            processedAt=datetime.now(),
            formsProcessed=3,
            totalForms=3,
        )

        assert resp.status == ProcessingStatus.COMPLETED
        assert resp.forms_processed == 3


class TestDocumentStatusResponse:
    """Tests for DocumentStatusResponse model."""

    def test_status_response(self):
        """Test status response."""
        from src.functions.models import DocumentStatusResponse, ProcessingStatus

        resp = DocumentStatusResponse(
            status=ProcessingStatus.COMPLETED,
            documentId="doc_123",
            sourceFile="incoming/test.pdf",
        )

        assert resp.document_id == "doc_123"
        assert resp.source_file == "incoming/test.pdf"


class TestBatchStatusResponse:
    """Tests for BatchStatusResponse model."""

    def test_batch_status(self):
        """Test batch status response."""
        from src.functions.models import BatchStatusResponse, DocumentStatusResponse, ProcessingStatus

        doc = DocumentStatusResponse(
            status=ProcessingStatus.COMPLETED,
            documentId="doc_1",
            sourceFile="test.pdf",
        )

        resp = BatchStatusResponse(
            sourceFile="test.pdf",
            totalForms=3,
            completed=2,
            failed=1,
            pending=0,
            documents=[doc],
        )

        assert resp.total_forms == 3
        assert resp.completed == 2
        assert len(resp.documents) == 1


class TestDeleteDocumentResponse:
    """Tests for DeleteDocumentResponse model."""

    def test_delete_response(self):
        """Test delete response."""
        from src.functions.models import DeleteDocumentResponse

        resp = DeleteDocumentResponse(
            status="success",
            deletedDocuments=5,
            deletedBlobs=10,
        )

        assert resp.deleted_documents == 5
        assert resp.deleted_blobs == 10
        assert len(resp.errors) == 0


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response(self):
        """Test health response."""
        from src.functions.models import HealthResponse

        resp = HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            services={"storage": "healthy", "cosmos": "healthy"},
        )

        assert resp.status == "healthy"
        assert resp.version == "2.0.0"


class TestCostEstimateResponse:
    """Tests for CostEstimateResponse model."""

    def test_cost_response(self):
        """Test cost estimate response."""
        from src.functions.models import CostEstimateResponse

        resp = CostEstimateResponse(
            pageCount=100,
            formsCount=50,
            modelType="prebuilt",
            estimatedCostUsd=0.10,
        )

        assert resp.page_count == 100
        assert resp.forms_count == 50
        assert resp.estimated_cost_usd == 0.10


class TestBatchProcessResponse:
    """Tests for BatchProcessResponse model."""

    def test_batch_response(self):
        """Test batch process response."""
        from src.functions.models import BatchProcessResponse

        resp = BatchProcessResponse(
            status="completed",
            batchId="batch_123",
            totalBlobs=10,
            processed=8,
            failed=2,
        )

        assert resp.batch_id == "batch_123"
        assert resp.total_blobs == 10


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self):
        """Test error response."""
        from src.functions.models import ErrorResponse

        resp = ErrorResponse(error="Something went wrong", details={"code": 500})

        assert resp.status == "error"
        assert resp.error == "Something went wrong"
        assert resp.details == {"code": 500}


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_webhook_payload(self):
        """Test webhook payload."""
        from src.functions.models import ProcessingStatus, WebhookPayload

        payload = WebhookPayload(
            sourceFile="test.pdf",
            status=ProcessingStatus.COMPLETED,
            processedAt=datetime.now(),
            formsProcessed=3,
            totalForms=3,
            documentIds=["doc_1", "doc_2", "doc_3"],
        )

        assert payload.event == "document.processed"
        assert payload.source_file == "test.pdf"
        assert len(payload.document_ids) == 3


class TestExtractedDocument:
    """Tests for ExtractedDocument model."""

    def test_extracted_document(self):
        """Test extracted document model."""
        from src.functions.models import ExtractedDocument, ProcessingStatus

        doc = ExtractedDocument(
            id="doc_123",
            sourceFile="test.pdf",
            processedAt=datetime.now(),
            modelId="prebuilt-layout",
            status=ProcessingStatus.COMPLETED,
            fields={"vendorName": "Acme Corp"},
            confidence={"vendorName": 0.95},
        )

        assert doc.id == "doc_123"
        assert doc.source_file == "test.pdf"
        assert doc.form_number == 1
        assert doc.retry_count == 0
