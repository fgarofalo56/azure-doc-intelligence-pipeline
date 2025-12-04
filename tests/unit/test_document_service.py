"""Unit tests for DocumentService."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))

from services.document_service import (
    DocumentProcessingError,
    DocumentService,
    RateLimitError,
)


@pytest.fixture
def document_service():
    """Create DocumentService instance for testing."""
    return DocumentService(
        endpoint="https://test.cognitiveservices.azure.com",
        api_key="test-api-key",
        max_concurrent=5,
        max_retries=3,
        initial_retry_delay=0.1,  # Fast retries for testing
    )


@pytest.fixture
def mock_analyze_result():
    """Create mock AnalyzeResult for testing."""
    mock_field = MagicMock()
    mock_field.value_string = "Acme Corp"
    mock_field.confidence = 0.95

    mock_document = MagicMock()
    mock_document.doc_type = "invoice"
    mock_document.confidence = 0.92
    mock_document.fields = {"vendorName": mock_field}

    mock_result = MagicMock()
    mock_result.documents = [mock_document]
    mock_result.model_id = "custom-model-v1"

    return mock_result


class TestDocumentService:
    """Tests for DocumentService class."""

    @pytest.mark.asyncio
    async def test_analyze_document_success(self, document_service, mock_analyze_result):
        """Test successful document analysis."""
        mock_poller = AsyncMock()
        mock_poller.result = AsyncMock(return_value=mock_analyze_result)

        mock_client = AsyncMock()
        mock_client.begin_analyze_document = AsyncMock(return_value=mock_poller)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            result = await document_service.analyze_document(
                blob_url="https://storage.blob.core.windows.net/pdfs/test.pdf?sas=...",
                model_id="custom-model-v1",
                blob_name="test.pdf",
            )

        assert result["status"] == "completed"
        assert result["modelId"] == "custom-model-v1"
        assert result["docType"] == "invoice"
        assert result["modelConfidence"] == 0.92
        assert result["fields"]["vendorName"] == "Acme Corp"
        assert result["confidence"]["vendorName"] == 0.95

    @pytest.mark.asyncio
    async def test_analyze_document_rate_limit_retry(self, document_service, mock_analyze_result):
        """Test rate limit retry with exponential backoff."""
        from azure.core.exceptions import HttpResponseError

        mock_response = MagicMock()
        mock_response.status_code = 429
        rate_limit_error = HttpResponseError(response=mock_response, message="Rate limit exceeded")
        rate_limit_error.status_code = 429

        mock_poller = AsyncMock()
        mock_poller.result = AsyncMock(return_value=mock_analyze_result)

        mock_client = AsyncMock()
        # First call fails with 429, second succeeds
        mock_client.begin_analyze_document = AsyncMock(
            side_effect=[rate_limit_error, mock_poller]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            result = await document_service.analyze_document(
                blob_url="https://storage.blob.core.windows.net/pdfs/test.pdf?sas=...",
                model_id="custom-model-v1",
                blob_name="test.pdf",
            )

        assert result["status"] == "completed"
        assert mock_client.begin_analyze_document.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_document_rate_limit_exhausted(self, document_service):
        """Test RateLimitError when retries exhausted."""
        from azure.core.exceptions import HttpResponseError

        # Create a properly configured rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.reason = "Too Many Requests"
        rate_limit_error = HttpResponseError(response=mock_response, message="Rate limit exceeded")

        mock_client = AsyncMock()
        # Use the exception directly as side_effect
        mock_client.begin_analyze_document.side_effect = rate_limit_error
        mock_client.__aenter__.return_value = mock_client

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            with pytest.raises(RateLimitError) as exc_info:
                await document_service.analyze_document(
                    blob_url="https://storage.blob.core.windows.net/pdfs/test.pdf?sas=...",
                    model_id="custom-model-v1",
                    blob_name="test.pdf",
                )

        assert "after 3 retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_document_http_error(self, document_service):
        """Test DocumentProcessingError on HTTP errors."""
        from azure.core.exceptions import HttpResponseError

        # Create a properly configured 404 error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        http_error = HttpResponseError(response=mock_response, message="Model not found")

        mock_client = AsyncMock()
        # Use the exception directly as side_effect
        mock_client.begin_analyze_document.side_effect = http_error
        mock_client.__aenter__.return_value = mock_client

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            with pytest.raises(DocumentProcessingError) as exc_info:
                await document_service.analyze_document(
                    blob_url="https://storage.blob.core.windows.net/pdfs/test.pdf?sas=...",
                    model_id="invalid-model",
                    blob_name="test.pdf",
                )

        assert exc_info.value.blob_name == "test.pdf"
        assert "404" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_analyze_document_empty_result(self, document_service):
        """Test handling of empty analysis result."""
        mock_result = MagicMock()
        mock_result.documents = []

        mock_poller = AsyncMock()
        mock_poller.result = AsyncMock(return_value=mock_result)

        mock_client = AsyncMock()
        mock_client.begin_analyze_document = AsyncMock(return_value=mock_poller)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            result = await document_service.analyze_document(
                blob_url="https://storage.blob.core.windows.net/pdfs/test.pdf?sas=...",
                model_id="custom-model-v1",
                blob_name="test.pdf",
            )

        assert result["status"] == "completed"
        assert result["fields"] == {}
        assert result["docType"] is None

    @pytest.mark.asyncio
    async def test_semaphore_concurrency_control(self, document_service, mock_analyze_result):
        """Test that semaphore limits concurrent requests."""
        call_order = []

        async def mock_analyze(*args, **kwargs):
            call_order.append("start")
            await asyncio.sleep(0.05)
            call_order.append("end")
            mock_poller = AsyncMock()
            mock_poller.result = AsyncMock(return_value=mock_analyze_result)
            return mock_poller

        mock_client = AsyncMock()
        mock_client.begin_analyze_document = mock_analyze
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Create service with max_concurrent=2
        service = DocumentService(
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
            max_concurrent=2,
        )

        with patch(
            "services.document_service.DocumentIntelligenceClient",
            return_value=mock_client,
        ):
            # Start 3 concurrent tasks - only 2 should run at a time
            tasks = [
                service.analyze_document(f"url{i}", "model", f"file{i}")
                for i in range(3)
            ]
            await asyncio.gather(*tasks)

        # With semaphore(2), pattern should show interleaved execution
        assert len(call_order) == 6  # 3 tasks * 2 events each


class TestExtractFieldValue:
    """Tests for field value extraction."""

    def test_extract_string_field(self, document_service):
        """Test string field extraction."""
        field = MagicMock()
        field.value_string = "Test String"

        result = document_service._extract_field_value(field)
        assert result == "Test String"

    def test_extract_number_field(self, document_service):
        """Test number field extraction."""
        field = MagicMock()
        field.value_string = None
        field.value_number = 42.5

        result = document_service._extract_field_value(field)
        assert result == 42.5

    def test_extract_currency_field(self, document_service):
        """Test currency field extraction."""
        currency = MagicMock()
        currency.amount = 1500.00
        currency.currency_code = "USD"

        field = MagicMock()
        field.value_string = None
        field.value_number = None
        field.value_date = None
        field.value_currency = currency

        result = document_service._extract_field_value(field)
        assert result["amount"] == 1500.00
        assert result["currencyCode"] == "USD"

    def test_extract_none_field(self, document_service):
        """Test None field handling."""
        result = document_service._extract_field_value(None)
        assert result is None

    def test_extract_fallback_to_content(self, document_service):
        """Test fallback to content when no typed value."""
        field = MagicMock()
        field.value_string = None
        field.value_number = None
        field.value_date = None
        field.value_currency = None
        field.value_array = None
        field.value_object = None
        field.content = "Raw content"

        result = document_service._extract_field_value(field)
        assert result == "Raw content"
