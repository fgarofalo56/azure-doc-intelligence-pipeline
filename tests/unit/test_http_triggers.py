"""Unit tests for HTTP trigger functions."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


def create_mock_request(body=None, method="POST", route_params=None, params=None):
    """Create a mock HTTP request for testing."""
    import azure.functions as func

    if body is None:
        body = {}

    return func.HttpRequest(
        method=method,
        body=json.dumps(body).encode("utf-8") if isinstance(body, dict) else body,
        url="/api/process",
        headers={"Content-Type": "application/json"},
        route_params=route_params or {},
        params=params or {},
    )


@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch("function_app.get_config") as mock:
        config = MagicMock()
        config.default_model_id = "prebuilt-layout"
        config.pages_per_form = 2
        config.concurrent_doc_intel_calls = 3
        mock.return_value = config
        yield config


@pytest.fixture
def mock_document_service():
    """Mock DocumentService."""
    with patch("function_app.get_document_service") as mock:
        service = AsyncMock()
        service.analyze_document = AsyncMock(
            return_value={
                "modelId": "custom-model-v1",
                "docType": "invoice",
                "modelConfidence": 0.95,
                "status": "completed",
                "fields": {"vendorName": "Acme Corp"},
                "confidence": {"vendorName": 0.98},
                "error": None,
            }
        )
        mock.return_value = service
        yield service


@pytest.fixture
def mock_cosmos_service():
    """Mock CosmosService."""
    with patch("function_app.get_cosmos_service") as mock:
        service = AsyncMock()
        service.save_document_result = AsyncMock(return_value={"id": "folder_test_pdf"})
        service.get_document = AsyncMock(
            return_value={
                "id": "folder_test_pdf",
                "sourceFile": "folder/test.pdf",
                "status": "completed",
                "processedAt": "2024-01-15T10:30:00Z",
            }
        )
        # Return empty list for idempotency check (no duplicate)
        service.query_documents = AsyncMock(return_value=[])
        mock.return_value = service
        yield service


@pytest.fixture
def mock_blob_service():
    """Mock BlobService."""
    with patch("function_app.get_blob_service") as mock:
        service = MagicMock()
        service.generate_sas_url = MagicMock(
            return_value="https://storage.blob.core.windows.net/pdfs/folder/test.pdf?sas=token"
        )
        service.parse_blob_url = MagicMock(return_value=("pdfs", "folder/test.pdf"))
        service.download_blob = MagicMock(return_value=b"%PDF-1.4 fake pdf content")
        service.list_blobs = MagicMock(return_value=[])
        mock.return_value = service
        yield service


@pytest.fixture
def mock_pdf_service():
    """Mock PdfService."""
    with patch("function_app.get_pdf_service") as mock:
        service = MagicMock()
        # Return page count of 2 (single form)
        service.get_page_count = MagicMock(return_value=2)
        # Return single chunk (no splitting needed for 2-page PDF)
        service.split_pdf = MagicMock(
            return_value=[
                (b"chunk1_bytes", {"start_page": 1, "end_page": 2, "form_number": 1})
            ]
        )
        mock.return_value = service
        yield service


class TestProcessDocument:
    """Tests for ProcessDocument HTTP trigger."""

    @pytest.mark.asyncio
    async def test_process_document_success(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service, mock_pdf_service
    ):
        """Test successful document processing."""
        from function_app import process_document

        req = create_mock_request(
            body={
                "blobUrl": "https://storage.blob.core.windows.net/pdfs/folder/test.pdf?sas=...",
                "blobName": "folder/test.pdf",
                "modelId": "custom-model-v1",
            }
        )

        response = await process_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "success"
        assert body["documentId"] == "folder_test_pdf"
        assert "processedAt" in body

        mock_document_service.analyze_document.assert_called_once()
        mock_cosmos_service.save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_missing_blob_url(self, mock_config):
        """Test error when blobUrl is missing."""
        from function_app import process_document

        req = create_mock_request(body={"blobName": "test.pdf"})

        response = await process_document(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "error" in body
        assert "blobUrl" in body["error"]

    @pytest.mark.asyncio
    async def test_process_document_missing_blob_name(self, mock_config):
        """Test error when blobName is missing."""
        from function_app import process_document

        req = create_mock_request(
            body={"blobUrl": "https://storage.blob.core.windows.net/test.pdf"}
        )

        response = await process_document(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "error" in body
        assert "blobName" in body["error"]

    @pytest.mark.asyncio
    async def test_process_document_invalid_json(self, mock_config):
        """Test error on invalid JSON body."""
        from function_app import process_document

        req = create_mock_request(body=b"invalid json")

        response = await process_document(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "error" in body
        assert "Invalid JSON" in body["error"]

    @pytest.mark.asyncio
    async def test_process_document_rate_limit_error(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service, mock_pdf_service
    ):
        """Test rate limit error handling."""
        from function_app import process_document

        from services.document_service import RateLimitError

        mock_document_service.analyze_document.side_effect = RateLimitError("Rate limit exceeded")

        req = create_mock_request(
            body={
                "blobUrl": "https://storage.blob.core.windows.net/test.pdf",
                "blobName": "test.pdf",
            }
        )

        response = await process_document(req)

        assert response.status_code == 429
        body = json.loads(response.get_body().decode())
        assert "rate limit" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_process_document_processing_error(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service, mock_pdf_service
    ):
        """Test document processing error handling."""
        from function_app import process_document

        from services.document_service import DocumentProcessingError

        mock_document_service.analyze_document.side_effect = DocumentProcessingError(
            "test.pdf", "Model not found"
        )

        req = create_mock_request(
            body={
                "blobUrl": "https://storage.blob.core.windows.net/test.pdf",
                "blobName": "test.pdf",
            }
        )

        response = await process_document(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "error" in body
        # Should save error document to Cosmos
        mock_cosmos_service.save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_cosmos_error(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service, mock_pdf_service
    ):
        """Test Cosmos DB error handling."""
        from function_app import process_document

        from services.cosmos_service import CosmosError

        mock_cosmos_service.save_document_result.side_effect = CosmosError(
            "save", "Connection failed"
        )

        req = create_mock_request(
            body={
                "blobUrl": "https://storage.blob.core.windows.net/test.pdf",
                "blobName": "test.pdf",
            }
        )

        response = await process_document(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Database error" in body["error"]

    @pytest.mark.asyncio
    async def test_process_document_uses_default_model(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service, mock_pdf_service
    ):
        """Test that default model ID is used when not specified."""
        from function_app import process_document

        req = create_mock_request(
            body={
                "blobUrl": "https://storage.blob.core.windows.net/test.pdf",
                "blobName": "test.pdf",
                # No modelId specified
            }
        )

        response = await process_document(req)

        assert response.status_code == 200
        # Should use default model from config
        call_args = mock_document_service.analyze_document.call_args
        assert call_args.kwargs["model_id"] == "prebuilt-layout"


class TestGetDocumentStatus:
    """Tests for GetDocumentStatus HTTP trigger."""

    @pytest.mark.asyncio
    async def test_get_status_found(self, mock_cosmos_service):
        """Test getting status of existing document."""
        from function_app import get_document_status

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "folder/test.pdf"},
        )

        response = await get_document_status(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "completed"
        assert body["documentId"] == "folder_test_pdf"

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, mock_cosmos_service):
        """Test getting status of non-existent document."""
        from function_app import get_document_status

        mock_cosmos_service.get_document.return_value = None

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "nonexistent.pdf"},
        )

        response = await get_document_status(req)

        assert response.status_code == 404
        body = json.loads(response.get_body().decode())
        assert body["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_status_missing_blob_name(self, mock_cosmos_service):
        """Test error when blob_name not in path."""
        from function_app import get_document_status

        req = create_mock_request(
            method="GET",
            body={},
            route_params={},  # Missing blob_name
        )

        response = await get_document_status(req)

        assert response.status_code == 400


class TestHealthCheck:
    """Tests for Health HTTP trigger."""

    @pytest.mark.asyncio
    async def test_health_check(self, mock_config, mock_blob_service):
        """Test health check returns healthy status."""
        from function_app import health_check

        # Configure mock config with required endpoints
        mock_config.doc_intel_endpoint = "https://doc-intel.cognitiveservices.azure.com"
        mock_config.cosmos_endpoint = "https://cosmos.documents.azure.com"

        # Mock list_blobs for blob trigger health check
        mock_blob_service.list_blobs = MagicMock(return_value=[])

        req = create_mock_request(method="GET", body={})

        response = await health_check(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "healthy"
        assert "timestamp" in body
        assert "services" in body

    @pytest.mark.asyncio
    async def test_health_check_storage_not_configured(self):
        """Test health check when storage is not configured."""
        from function_app import health_check

        with patch("function_app.get_blob_service") as mock_blob:
            mock_blob.return_value = None
            with patch("function_app.get_config") as mock_config_fn:
                config = MagicMock()
                config.doc_intel_endpoint = "https://test.cognitiveservices.azure.com"
                config.cosmos_endpoint = "https://test.documents.azure.com"
                mock_config_fn.return_value = config

                req = create_mock_request(method="GET", body={})
                response = await health_check(req)

                assert response.status_code == 200
                body = json.loads(response.get_body().decode())
                assert body["services"]["storage"] == "not_configured"

    @pytest.mark.asyncio
    async def test_health_check_blob_trigger_error(self, mock_config, mock_blob_service):
        """Test health check with blob trigger error."""
        from function_app import health_check

        mock_config.doc_intel_endpoint = "https://test.cognitiveservices.azure.com"
        mock_config.cosmos_endpoint = "https://test.documents.azure.com"
        mock_blob_service.list_blobs.side_effect = Exception("Storage error")

        req = create_mock_request(method="GET", body={})
        response = await health_check(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["blobTrigger"]["status"] == "unhealthy"


class TestReprocessDocument:
    """Tests for ReprocessDocument HTTP trigger."""

    @pytest.fixture
    def mock_services(self):
        """Set up all mock services for reprocess tests."""
        with patch("function_app.get_config") as mock_config_fn, \
             patch("function_app.get_cosmos_service") as mock_cosmos_fn, \
             patch("function_app.get_blob_service") as mock_blob_fn, \
             patch("function_app.get_document_service") as mock_doc_fn, \
             patch("function_app.get_pdf_service") as mock_pdf_fn, \
             patch("function_app.get_telemetry_service") as mock_telemetry_fn, \
             patch("function_app.get_webhook_service") as mock_webhook_fn:

            config = MagicMock()
            config.default_model_id = "prebuilt-layout"
            config.max_retry_attempts = 3
            config.webhook_url = None
            config.pages_per_form = 2
            config.concurrent_doc_intel_calls = 3
            mock_config_fn.return_value = config

            cosmos = AsyncMock()
            cosmos.query_by_source_file = AsyncMock(return_value=[
                {"id": "doc1", "sourceFile": "test.pdf", "status": "failed", "retryCount": 0}
            ])
            cosmos.save_document_result = AsyncMock()
            cosmos.increment_retry_count = AsyncMock()
            cosmos.query_documents = AsyncMock(return_value=[])  # No duplicates
            mock_cosmos_fn.return_value = cosmos

            blob = MagicMock()
            blob.client = MagicMock()
            blob.client.account_name = "teststorage"
            blob.download_blob = MagicMock(return_value=b"%PDF-1.4 fake")
            blob.generate_sas_url = MagicMock(return_value="https://test.blob?sas=token")
            blob.parse_blob_url = MagicMock(return_value=("pdfs", "test.pdf"))
            mock_blob_fn.return_value = blob

            doc = AsyncMock()
            doc.analyze_document = AsyncMock(return_value={
                "modelId": "prebuilt-layout",
                "status": "completed",
                "modelConfidence": 0.95,
                "fields": {},
                "confidence": {},
            })
            doc.validate_model = AsyncMock()
            mock_doc_fn.return_value = doc

            pdf = MagicMock()
            pdf.get_page_count = MagicMock(return_value=2)
            mock_pdf_fn.return_value = pdf

            telemetry = MagicMock()
            telemetry.track_operation = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value={}), __exit__=MagicMock()))
            telemetry.track_dead_letter = MagicMock()
            mock_telemetry_fn.return_value = telemetry

            webhook = AsyncMock()
            mock_webhook_fn.return_value = webhook

            yield {
                "config": config,
                "cosmos": cosmos,
                "blob": blob,
                "doc": doc,
                "pdf": pdf,
                "telemetry": telemetry,
            }

    @pytest.mark.asyncio
    async def test_reprocess_success(self, mock_services):
        """Test successful document reprocessing."""
        from function_app import reprocess_document

        req = create_mock_request(
            method="POST",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
        )

        response = await reprocess_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "success"
        assert body["retryCount"] == 1

    @pytest.mark.asyncio
    async def test_reprocess_missing_blob_name(self):
        """Test error when blob_name missing."""
        from function_app import reprocess_document

        req = create_mock_request(
            method="POST",
            body={},
            route_params={},
        )

        response = await reprocess_document(req)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reprocess_document_not_found(self, mock_services):
        """Test reprocess when document not found."""
        from function_app import reprocess_document

        mock_services["cosmos"].query_by_source_file.return_value = []

        req = create_mock_request(
            method="POST",
            body={},
            route_params={"blob_name": "nonexistent.pdf"},
        )

        response = await reprocess_document(req)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reprocess_already_completed(self, mock_services):
        """Test reprocess when already completed without force."""
        from function_app import reprocess_document

        mock_services["cosmos"].query_by_source_file.return_value = [
            {"id": "doc1", "status": "completed", "retryCount": 0}
        ]

        req = create_mock_request(
            method="POST",
            body={"force": False},
            route_params={"blob_name": "test.pdf"},
        )

        response = await reprocess_document(req)

        assert response.status_code == 409
        body = json.loads(response.get_body().decode())
        assert "already completed" in body["error"]

    @pytest.mark.asyncio
    async def test_reprocess_max_retries_exceeded(self, mock_services):
        """Test reprocess when max retries exceeded."""
        from function_app import reprocess_document

        mock_services["cosmos"].query_by_source_file.return_value = [
            {"id": "doc1", "status": "failed", "retryCount": 5}
        ]

        req = create_mock_request(
            method="POST",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await reprocess_document(req)

        assert response.status_code == 410
        mock_services["telemetry"].track_dead_letter.assert_called_once()


class TestGetBatchStatus:
    """Tests for GetBatchStatus HTTP trigger."""

    @pytest.mark.asyncio
    async def test_batch_status_success(self, mock_cosmos_service):
        """Test getting batch status."""
        from function_app import get_batch_status

        mock_cosmos_service.query_by_source_file.return_value = [
            {"id": "doc1", "formNumber": 1, "status": "completed", "totalForms": 2},
            {"id": "doc2", "formNumber": 2, "status": "failed", "totalForms": 2},
        ]

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "multi-page.pdf"},
        )

        response = await get_batch_status(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["totalForms"] == 2
        assert body["completed"] == 1
        assert body["failed"] == 1
        assert len(body["documents"]) == 2

    @pytest.mark.asyncio
    async def test_batch_status_not_found(self, mock_cosmos_service):
        """Test batch status when not found."""
        from function_app import get_batch_status

        mock_cosmos_service.query_by_source_file.return_value = []

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "nonexistent.pdf"},
        )

        response = await get_batch_status(req)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_status_missing_blob_name(self, mock_cosmos_service):
        """Test batch status with missing blob_name."""
        from function_app import get_batch_status

        req = create_mock_request(
            method="GET",
            body={},
            route_params={},
        )

        response = await get_batch_status(req)

        assert response.status_code == 400


class TestDeleteDocument:
    """Tests for DeleteDocument HTTP trigger."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_cosmos_service, mock_blob_service):
        """Test successful document deletion."""
        from function_app import delete_document

        mock_cosmos_service.delete_by_source_file = AsyncMock(return_value=2)
        mock_blob_service.list_blobs.return_value = ["_splits/test_form1.pdf"]
        mock_blob_service.delete_blob = MagicMock()

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
            params={"deleteSplits": "true", "deleteOriginal": "false"},
        )

        response = await delete_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["deletedDocuments"] == 2

    @pytest.mark.asyncio
    async def test_delete_missing_blob_name(self, mock_cosmos_service):
        """Test delete with missing blob_name."""
        from function_app import delete_document

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={},
        )

        response = await delete_document(req)

        assert response.status_code == 400


class TestEstimateCost:
    """Tests for EstimateCost HTTP trigger."""

    @pytest.mark.asyncio
    async def test_estimate_cost_with_page_count(self):
        """Test cost estimation with page count."""
        from function_app import estimate_cost

        req = create_mock_request(
            body={"pageCount": 10, "modelId": "prebuilt-layout"}
        )

        response = await estimate_cost(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["pageCount"] == 10
        assert body["formsCount"] == 5
        assert body["modelType"] == "prebuilt"
        assert "estimatedCostUsd" in body

    @pytest.mark.asyncio
    async def test_estimate_cost_custom_model(self):
        """Test cost estimation with custom model."""
        from function_app import estimate_cost

        req = create_mock_request(
            body={"pageCount": 20, "modelId": "custom-invoice-model"}
        )

        response = await estimate_cost(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["modelType"] == "custom"
        assert body["pricing"]["analysisCostPerPage"] == 0.01

    @pytest.mark.asyncio
    async def test_estimate_cost_with_blob_url(self, mock_blob_service, mock_pdf_service):
        """Test cost estimation with blob URL."""
        from function_app import estimate_cost

        mock_pdf_service.get_page_count.return_value = 6

        req = create_mock_request(
            body={"blobUrl": "https://storage.blob.core.windows.net/pdfs/test.pdf"}
        )

        response = await estimate_cost(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["pageCount"] == 6

    @pytest.mark.asyncio
    async def test_estimate_cost_missing_params(self):
        """Test cost estimation with missing parameters."""
        from function_app import estimate_cost

        req = create_mock_request(body={})

        response = await estimate_cost(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "blobUrl or pageCount" in body["error"]

    @pytest.mark.asyncio
    async def test_estimate_cost_invalid_json(self):
        """Test cost estimation with invalid JSON."""
        from function_app import estimate_cost

        req = create_mock_request(body=b"not json")

        response = await estimate_cost(req)

        assert response.status_code == 400


class TestBatchProcess:
    """Tests for BatchProcess HTTP trigger."""

    @pytest.fixture
    def mock_batch_services(self):
        """Set up mocks for batch processing."""
        with patch("function_app.get_config") as mock_config_fn, \
             patch("function_app.get_blob_service") as mock_blob_fn, \
             patch("function_app.get_document_service") as mock_doc_fn, \
             patch("function_app.get_cosmos_service") as mock_cosmos_fn, \
             patch("function_app.get_pdf_service") as mock_pdf_fn, \
             patch("function_app.get_telemetry_service") as mock_telemetry_fn, \
             patch("function_app.get_webhook_service") as mock_webhook_fn:

            config = MagicMock()
            config.default_model_id = "prebuilt-layout"
            config.webhook_url = None
            config.pages_per_form = 2
            config.concurrent_doc_intel_calls = 3
            config.batch_max_blobs = 50
            mock_config_fn.return_value = config

            blob = MagicMock()
            blob.download_blob = MagicMock(return_value=b"%PDF-1.4")
            blob.generate_sas_url = MagicMock(return_value="https://test?sas=x")
            blob.parse_blob_url = MagicMock(return_value=("pdfs", "test.pdf"))
            mock_blob_fn.return_value = blob

            doc = AsyncMock()
            doc.analyze_document = AsyncMock(return_value={
                "modelId": "prebuilt-layout",
                "status": "completed",
                "modelConfidence": 0.9,
                "fields": {},
                "confidence": {},
            })
            mock_doc_fn.return_value = doc

            cosmos = AsyncMock()
            cosmos.save_document_result = AsyncMock()
            cosmos.query_documents = AsyncMock(return_value=[])  # No duplicates
            mock_cosmos_fn.return_value = cosmos

            pdf = MagicMock()
            pdf.get_page_count = MagicMock(return_value=2)
            mock_pdf_fn.return_value = pdf

            telemetry = MagicMock()
            telemetry.track_operation = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value={}), __exit__=MagicMock()))
            telemetry.track_batch_processing = MagicMock()
            mock_telemetry_fn.return_value = telemetry

            webhook = AsyncMock()
            mock_webhook_fn.return_value = webhook

            yield {"config": config, "blob": blob, "doc": doc, "cosmos": cosmos, "webhook": webhook}

    @pytest.mark.asyncio
    async def test_batch_process_success(self, mock_batch_services):
        """Test successful batch processing."""
        from function_app import batch_process

        req = create_mock_request(
            body={
                "blobs": [
                    {"blobUrl": "https://test/doc1.pdf", "blobName": "doc1.pdf"},
                    {"blobUrl": "https://test/doc2.pdf", "blobName": "doc2.pdf"},
                ],
                "parallel": True,
            }
        )

        response = await batch_process(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "success"
        assert body["totalBlobs"] == 2
        assert body["processed"] == 2

    @pytest.mark.asyncio
    async def test_batch_process_empty_blobs(self):
        """Test batch processing with no blobs."""
        from function_app import batch_process

        req = create_mock_request(body={"blobs": []})

        response = await batch_process(req)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_process_too_many_blobs(self):
        """Test batch processing with too many blobs."""
        from function_app import batch_process

        req = create_mock_request(
            body={"blobs": [{"blobUrl": f"https://test/{i}.pdf", "blobName": f"{i}.pdf"} for i in range(51)]}
        )

        response = await batch_process(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "Maximum 50" in body["error"]

    @pytest.mark.asyncio
    async def test_batch_process_invalid_json(self):
        """Test batch processing with invalid JSON."""
        from function_app import batch_process

        req = create_mock_request(body=b"invalid")

        response = await batch_process(req)

        assert response.status_code == 400


class TestProcessMultiModel:
    """Tests for ProcessMultiModel HTTP trigger."""

    @pytest.mark.asyncio
    async def test_multi_model_missing_fields(self):
        """Test multi-model processing with missing fields."""
        from function_app import process_multi_model

        req = create_mock_request(body={"blobUrl": "https://test.pdf"})

        response = await process_multi_model(req)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_multi_model_missing_mapping(self):
        """Test multi-model processing without model mapping."""
        from function_app import process_multi_model

        req = create_mock_request(
            body={"blobUrl": "https://test.pdf", "blobName": "test.pdf"}
        )

        response = await process_multi_model(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "modelMapping" in body["error"]

    @pytest.mark.asyncio
    async def test_multi_model_invalid_json(self):
        """Test multi-model processing with invalid JSON."""
        from function_app import process_multi_model

        req = create_mock_request(body=b"not json")

        response = await process_multi_model(req)

        assert response.status_code == 400


class TestProcessPdfInternal:
    """Tests for process_pdf_internal function."""

    @pytest.fixture
    def mock_all_services(self):
        """Mock all services for internal processing tests."""
        with patch("function_app.get_config") as mock_config_fn, \
             patch("function_app.get_blob_service") as mock_blob_fn, \
             patch("function_app.get_document_service") as mock_doc_fn, \
             patch("function_app.get_cosmos_service") as mock_cosmos_fn, \
             patch("function_app.get_pdf_service") as mock_pdf_fn, \
             patch("function_app.get_telemetry_service") as mock_telemetry_fn, \
             patch("function_app.get_webhook_service") as mock_webhook_fn:

            config = MagicMock()
            config.webhook_url = None
            config.pages_per_form = 2
            config.concurrent_doc_intel_calls = 3
            mock_config_fn.return_value = config

            blob = MagicMock()
            blob.download_blob = MagicMock(return_value=b"%PDF-1.4 content")
            blob.generate_sas_url = MagicMock(return_value="https://test?sas=x")
            blob.parse_blob_url = MagicMock(return_value=("pdfs", "test.pdf"))
            blob.upload_blob = MagicMock(return_value="https://test/_splits/chunk.pdf")
            mock_blob_fn.return_value = blob

            doc = AsyncMock()
            doc.analyze_document = AsyncMock(return_value={
                "modelId": "custom-model",
                "status": "completed",
                "modelConfidence": 0.95,
                "docType": "invoice",
                "fields": {"vendor": "Test"},
                "confidence": {"vendor": 0.98},
            })
            mock_doc_fn.return_value = doc

            cosmos = AsyncMock()
            cosmos.save_document_result = AsyncMock()
            cosmos.query_documents = AsyncMock(return_value=[])  # No duplicates
            mock_cosmos_fn.return_value = cosmos

            pdf = MagicMock()
            mock_pdf_fn.return_value = pdf

            telemetry = MagicMock()
            telemetry.track_operation = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value={}), __exit__=MagicMock()))
            telemetry.track_form_processed = MagicMock()
            mock_telemetry_fn.return_value = telemetry

            webhook = AsyncMock()
            webhook.notify_processing_complete = AsyncMock()
            mock_webhook_fn.return_value = webhook

            yield {
                "config": config, "blob": blob, "doc": doc, "cosmos": cosmos,
                "pdf": pdf, "telemetry": telemetry, "webhook": webhook
            }

    @pytest.mark.asyncio
    async def test_process_single_page_pdf(self, mock_all_services):
        """Test processing single-page PDF (no splitting)."""
        from function_app import process_pdf_internal

        mock_all_services["pdf"].get_page_count.return_value = 2

        result = await process_pdf_internal(
            blob_url="https://test.blob/pdfs/doc.pdf",
            blob_name="doc.pdf",
            model_id="custom-model",
        )

        assert result["status"] == "success"
        assert result["formsProcessed"] == 1
        mock_all_services["cosmos"].save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_multi_page_pdf(self, mock_all_services):
        """Test processing multi-page PDF with splitting."""
        from function_app import process_pdf_internal

        mock_all_services["pdf"].get_page_count.return_value = 6
        mock_all_services["pdf"].split_pdf.return_value = [
            (b"chunk1", 1, 2),
            (b"chunk2", 3, 4),
            (b"chunk3", 5, 6),
        ]

        result = await process_pdf_internal(
            blob_url="https://test.blob/pdfs/multi.pdf",
            blob_name="multi.pdf",
            model_id="custom-model",
        )

        assert result["status"] == "success"
        assert result["totalForms"] == 3
        assert result["formsProcessed"] == 3
        assert mock_all_services["cosmos"].save_document_result.call_count == 3

    @pytest.mark.asyncio
    async def test_process_with_webhook(self, mock_all_services):
        """Test processing with webhook notification."""
        from function_app import process_pdf_internal

        mock_all_services["pdf"].get_page_count.return_value = 2
        mock_all_services["config"].webhook_url = "https://webhook.example.com"

        result = await process_pdf_internal(
            blob_url="https://test.blob/pdfs/doc.pdf",
            blob_name="doc.pdf",
            model_id="custom-model",
        )

        assert result["status"] == "success"
        mock_all_services["webhook"].notify_processing_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_blob_service_not_configured(self):
        """Test processing when blob service not configured."""
        from function_app import process_pdf_internal
        from services.blob_service import BlobServiceError

        with patch("function_app.get_blob_service") as mock_blob, \
             patch("function_app.get_config"), \
             patch("function_app.get_telemetry_service"):
            mock_blob.return_value = None

            with pytest.raises(BlobServiceError):
                await process_pdf_internal(
                    blob_url="https://test.blob/doc.pdf",
                    blob_name="doc.pdf",
                    model_id="model",
                )


class TestErrorHandlers:
    """Tests for various error handling scenarios."""

    @pytest.mark.asyncio
    async def test_configuration_error(self):
        """Test ConfigurationError handling in process_document."""
        from function_app import process_document
        from config import ConfigurationError

        with patch("function_app.get_config") as mock_config:
            mock_config.side_effect = ConfigurationError(["DOC_INTEL_ENDPOINT"])

            req = create_mock_request(
                body={"blobUrl": "https://test.pdf", "blobName": "test.pdf"}
            )

            response = await process_document(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "Configuration error" in body["error"]

    @pytest.mark.asyncio
    async def test_pdf_split_error(
        self, mock_config, mock_document_service, mock_cosmos_service, mock_blob_service
    ):
        """Test PdfSplitError handling."""
        from function_app import process_document
        from services.pdf_service import PdfSplitError

        with patch("function_app.get_pdf_service") as mock_pdf:
            pdf_service = MagicMock()
            pdf_service.get_page_count.side_effect = PdfSplitError("Invalid PDF")
            mock_pdf.return_value = pdf_service

            req = create_mock_request(
                body={"blobUrl": "https://test.pdf", "blobName": "test.pdf"}
            )

            response = await process_document(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "split PDF" in body["error"]

    @pytest.mark.asyncio
    async def test_blob_service_error(self, mock_config, mock_document_service, mock_cosmos_service):
        """Test BlobServiceError handling."""
        from function_app import process_document
        from services.blob_service import BlobServiceError

        with patch("function_app.get_blob_service") as mock_blob:
            blob_service = MagicMock()
            blob_service.download_blob.side_effect = BlobServiceError("Connection failed")
            mock_blob.return_value = blob_service

            req = create_mock_request(
                body={"blobUrl": "https://test.pdf", "blobName": "test.pdf"}
            )

            response = await process_document(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "blob" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_unexpected_error(self, mock_config):
        """Test unexpected error handling."""
        from function_app import process_document

        with patch("function_app.get_blob_service") as mock_blob:
            mock_blob.side_effect = RuntimeError("Unexpected!")

            req = create_mock_request(
                body={"blobUrl": "https://test.pdf", "blobName": "test.pdf"}
            )

            response = await process_document(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "Internal server error" in body["error"]


class TestGetDocumentStatusErrors:
    """Tests for GetDocumentStatus error handling."""

    @pytest.mark.asyncio
    async def test_get_status_cosmos_error(self, mock_cosmos_service):
        """Test GetDocumentStatus with CosmosError."""
        from function_app import get_document_status
        from services.cosmos_service import CosmosError

        mock_cosmos_service.get_document.side_effect = CosmosError("get_document", "Connection failed")

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await get_document_status(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Database error" in body["error"]

    @pytest.mark.asyncio
    async def test_get_status_unexpected_error(self, mock_cosmos_service):
        """Test GetDocumentStatus with unexpected error."""
        from function_app import get_document_status

        mock_cosmos_service.get_document.side_effect = RuntimeError("Unexpected")

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await get_document_status(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Internal server error" in body["error"]


class TestGetBatchStatusErrors:
    """Tests for GetBatchStatus error handling."""

    @pytest.mark.asyncio
    async def test_batch_status_cosmos_error(self, mock_cosmos_service):
        """Test GetBatchStatus with CosmosError."""
        from function_app import get_batch_status
        from services.cosmos_service import CosmosError

        mock_cosmos_service.query_by_source_file.side_effect = CosmosError("query", "Query failed")

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await get_batch_status(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Database error" in body["error"]

    @pytest.mark.asyncio
    async def test_batch_status_unexpected_error(self, mock_cosmos_service):
        """Test GetBatchStatus with unexpected error."""
        from function_app import get_batch_status

        mock_cosmos_service.query_by_source_file.side_effect = RuntimeError("Unexpected")

        req = create_mock_request(
            method="GET",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await get_batch_status(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Internal server error" in body["error"]


class TestDeleteDocumentErrors:
    """Tests for DeleteDocument error handling."""

    @pytest.mark.asyncio
    async def test_delete_split_blob_error(self, mock_cosmos_service, mock_blob_service):
        """Test delete with split blob deletion error."""
        from function_app import delete_document
        from services.blob_service import BlobServiceError

        mock_cosmos_service.delete_by_source_file = AsyncMock(return_value=2)
        mock_blob_service.list_blobs.return_value = ["_splits/test_form1.pdf"]
        mock_blob_service.delete_blob.side_effect = BlobServiceError("Delete failed")

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
            params={"deleteSplits": "true", "deleteOriginal": "false"},
        )

        response = await delete_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "partial"
        assert len(body["errors"]) > 0

    @pytest.mark.asyncio
    async def test_delete_list_blobs_error(self, mock_cosmos_service, mock_blob_service):
        """Test delete with list blobs error."""
        from function_app import delete_document
        from services.blob_service import BlobServiceError

        mock_cosmos_service.delete_by_source_file = AsyncMock(return_value=2)
        mock_blob_service.list_blobs.side_effect = BlobServiceError("List failed")

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
            params={"deleteSplits": "true"},
        )

        response = await delete_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert "Failed to list" in str(body["errors"])

    @pytest.mark.asyncio
    async def test_delete_original_success(self, mock_cosmos_service, mock_blob_service):
        """Test delete with original blob deletion."""
        from function_app import delete_document

        mock_cosmos_service.delete_by_source_file = AsyncMock(return_value=1)
        mock_blob_service.list_blobs.return_value = []
        mock_blob_service.parse_blob_url.return_value = ("pdfs", "test.pdf")
        mock_blob_service.delete_blob = MagicMock()

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
            params={"deleteSplits": "false", "deleteOriginal": "true"},
        )

        response = await delete_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["deletedBlobs"] == 1

    @pytest.mark.asyncio
    async def test_delete_original_error(self, mock_cosmos_service, mock_blob_service):
        """Test delete with original blob deletion error."""
        from function_app import delete_document
        from services.blob_service import BlobServiceError

        mock_cosmos_service.delete_by_source_file = AsyncMock(return_value=1)
        mock_blob_service.list_blobs.return_value = []
        mock_blob_service.parse_blob_url.return_value = ("pdfs", "test.pdf")
        mock_blob_service.delete_blob.side_effect = BlobServiceError("Delete original failed")

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "pdfs/test.pdf"},
            params={"deleteSplits": "false", "deleteOriginal": "true"},
        )

        response = await delete_document(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert "Failed to delete original" in str(body["errors"])

    @pytest.mark.asyncio
    async def test_delete_cosmos_error(self, mock_cosmos_service):
        """Test delete with CosmosError."""
        from function_app import delete_document
        from services.cosmos_service import CosmosError

        mock_cosmos_service.delete_by_source_file.side_effect = CosmosError("delete", "Delete failed")

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await delete_document(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Database error" in body["error"]

    @pytest.mark.asyncio
    async def test_delete_unexpected_error(self, mock_cosmos_service):
        """Test delete with unexpected error."""
        from function_app import delete_document

        mock_cosmos_service.delete_by_source_file.side_effect = RuntimeError("Unexpected")

        req = create_mock_request(
            method="DELETE",
            body={},
            route_params={"blob_name": "test.pdf"},
        )

        response = await delete_document(req)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert "Internal server error" in body["error"]


class TestReprocessErrors:
    """Tests for ReprocessDocument error handling."""

    @pytest.mark.asyncio
    async def test_reprocess_unexpected_exception(self):
        """Test reprocess with unexpected exception."""
        from function_app import reprocess_document

        with patch("function_app.get_config") as mock_config, \
             patch("function_app.get_blob_service") as mock_blob, \
             patch("function_app.get_cosmos_service") as mock_cosmos:
            config = MagicMock()
            config.default_model_id = "prebuilt-layout"
            config.max_retry_attempts = 3
            mock_config.return_value = config

            blob_service = MagicMock()
            blob_service.generate_sas_url.return_value = "https://storage/test.pdf?sas=token"
            blob_service.client.account_name = "teststorage"
            mock_blob.return_value = blob_service

            cosmos = AsyncMock()
            # Return a failed document to pass initial checks
            cosmos.query_by_source_file.return_value = [
                {"id": "test_pdf", "status": "failed", "retryCount": 0}
            ]
            # Throw error when incrementing retry count
            cosmos.increment_retry_count.side_effect = RuntimeError("Unexpected error")
            mock_cosmos.return_value = cosmos

            req = create_mock_request(
                method="POST",
                body={},
                route_params={"blob_name": "test.pdf"},
            )

            response = await reprocess_document(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "Reprocess failed" in body["error"]


class TestProcessMultiModelComplete:
    """Complete tests for ProcessMultiModel endpoint."""

    @pytest.fixture
    def mock_all_services(self):
        """Mock all services needed for multi-model processing."""
        with patch("function_app.get_config") as mock_config, \
             patch("function_app.get_blob_service") as mock_blob, \
             patch("function_app.get_pdf_service") as mock_pdf, \
             patch("function_app.get_document_service") as mock_doc, \
             patch("function_app.get_cosmos_service") as mock_cosmos, \
             patch("function_app.get_webhook_service") as mock_webhook:

            config = MagicMock()
            config.default_model_id = "prebuilt-layout"
            mock_config.return_value = config

            blob_service = MagicMock()
            blob_service.download_blob.return_value = b"PDF content"
            blob_service.parse_blob_url.return_value = ("pdfs", "test.pdf")
            blob_service.upload_blob.return_value = "https://storage/pdfs/_splits/chunk.pdf"
            blob_service.generate_sas_url.return_value = "https://storage/pdfs/_splits/chunk.pdf?sas=token"
            mock_blob.return_value = blob_service

            pdf_service = MagicMock()
            pdf_service.get_page_count.return_value = 4
            pdf_service.extract_pages.return_value = b"Chunk PDF content"
            mock_pdf.return_value = pdf_service

            doc_service = AsyncMock()
            doc_service.analyze_document.return_value = {
                "modelId": "test-model",
                "status": "completed",
                "fields": {"test": "value"},
                "confidence": {"test": 0.95},
            }
            mock_doc.return_value = doc_service

            cosmos_service = AsyncMock()
            cosmos_service.save_document_result.return_value = {"id": "doc1"}
            mock_cosmos.return_value = cosmos_service

            webhook_service = AsyncMock()
            mock_webhook.return_value = webhook_service

            yield {
                "config": config,
                "blob": blob_service,
                "pdf": pdf_service,
                "doc": doc_service,
                "cosmos": cosmos_service,
                "webhook": webhook_service,
            }

    @pytest.mark.asyncio
    async def test_multi_model_success(self, mock_all_services):
        """Test successful multi-model processing."""
        from function_app import process_multi_model

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {
                    "1-2": "model-a",
                    "3-4": "model-b",
                },
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "success"
        assert body["rangesProcessed"] == 2
        assert body["totalRanges"] == 2

    @pytest.mark.asyncio
    async def test_multi_model_page_out_of_bounds(self, mock_all_services):
        """Test multi-model with page range out of bounds."""
        from function_app import process_multi_model

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {
                    "1-2": "model-a",
                    "5-6": "model-b",  # Out of bounds (doc has 4 pages)
                },
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "partial"
        assert body["rangesProcessed"] == 1
        # Check for out of bounds error
        failed_results = [r for r in body["results"] if r["status"] == "failed"]
        assert len(failed_results) == 1
        assert "out of bounds" in failed_results[0]["error"]

    @pytest.mark.asyncio
    async def test_multi_model_processing_error(self, mock_all_services):
        """Test multi-model with processing error for one range."""
        from function_app import process_multi_model

        # Make second analysis fail
        mock_all_services["doc"].analyze_document.side_effect = [
            {"modelId": "model-a", "status": "completed", "fields": {}},
            Exception("Processing failed"),
        ]

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {
                    "1-2": "model-a",
                    "3-4": "model-b",
                },
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "partial"

    @pytest.mark.asyncio
    async def test_multi_model_all_fail(self, mock_all_services):
        """Test multi-model when all ranges fail."""
        from function_app import process_multi_model

        mock_all_services["doc"].analyze_document.side_effect = Exception("All fail")

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {
                    "1-2": "model-a",
                    "3-4": "model-b",
                },
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["status"] == "failed"
        assert body["rangesProcessed"] == 0

    @pytest.mark.asyncio
    async def test_multi_model_with_webhook(self, mock_all_services):
        """Test multi-model with webhook notification."""
        from function_app import process_multi_model

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {"1-2": "model-a"},
                "webhookUrl": "https://webhook.example.com/notify",
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        mock_all_services["webhook"].notify_processing_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_model_storage_not_configured(self):
        """Test multi-model when storage not configured."""
        from function_app import process_multi_model

        with patch("function_app.get_config") as mock_config, \
             patch("function_app.get_blob_service") as mock_blob:
            mock_config.return_value = MagicMock()
            mock_blob.return_value = None

            req = create_mock_request(
                body={
                    "blobUrl": "https://test.pdf",
                    "blobName": "test.pdf",
                    "modelMapping": {"1-2": "model"},
                }
            )

            response = await process_multi_model(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "Storage not configured" in body["error"]

    @pytest.mark.asyncio
    async def test_multi_model_exception(self):
        """Test multi-model with top-level exception."""
        from function_app import process_multi_model

        with patch("function_app.get_config") as mock_config, \
             patch("function_app.get_blob_service") as mock_blob:
            mock_config.return_value = MagicMock()
            mock_blob.side_effect = RuntimeError("Service unavailable")

            req = create_mock_request(
                body={
                    "blobUrl": "https://test.pdf",
                    "blobName": "test.pdf",
                    "modelMapping": {"1-2": "model"},
                }
            )

            response = await process_multi_model(req)

            assert response.status_code == 500
            body = json.loads(response.get_body().decode())
            assert "Multi-model processing failed" in body["error"]

    @pytest.mark.asyncio
    async def test_multi_model_single_page_range(self, mock_all_services):
        """Test multi-model with single page (e.g., '3' instead of '3-4')."""
        from function_app import process_multi_model

        req = create_mock_request(
            body={
                "blobUrl": "https://storage/pdfs/test.pdf",
                "blobName": "test.pdf",
                "modelMapping": {
                    "1": "model-a",  # Single page, no dash
                    "2-3": "model-b",
                },
            }
        )

        response = await process_multi_model(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["rangesProcessed"] == 2
