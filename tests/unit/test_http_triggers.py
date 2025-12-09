"""Unit tests for HTTP trigger functions."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


def create_mock_request(body=None, method="POST", route_params=None):
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
    )


@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch("function_app.get_config") as mock:
        config = MagicMock()
        config.default_model_id = "prebuilt-layout"
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
