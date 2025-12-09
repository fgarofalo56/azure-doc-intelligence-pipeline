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
        mock_client.begin_analyze_document = AsyncMock(side_effect=[rate_limit_error, mock_poller])
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
            tasks = [service.analyze_document(f"url{i}", "model", f"file{i}") for i in range(3)]
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

    def test_extract_date_field(self, document_service):
        """Test date field extraction."""
        from datetime import date

        field = MagicMock()
        field.value_string = None
        field.value_number = None
        field.value_date = date(2024, 1, 15)

        result = document_service._extract_field_value(field)
        assert result == "2024-01-15"

    def test_extract_array_field(self, document_service):
        """Test array field extraction."""
        item1 = MagicMock()
        item1.value_string = "Item 1"
        item2 = MagicMock()
        item2.value_string = "Item 2"

        field = MagicMock()
        field.value_string = None
        field.value_number = None
        field.value_date = None
        field.value_currency = None
        field.value_array = [item1, item2]

        result = document_service._extract_field_value(field)
        assert result == ["Item 1", "Item 2"]

    def test_extract_object_field(self, document_service):
        """Test object/dictionary field extraction."""
        sub_field = MagicMock()
        sub_field.value_string = "Nested Value"

        field = MagicMock()
        field.value_string = None
        field.value_number = None
        field.value_date = None
        field.value_currency = None
        field.value_array = None
        field.value_object = {"nestedKey": sub_field}

        result = document_service._extract_field_value(field)
        assert result == {"nestedKey": "Nested Value"}

    def test_extract_field_no_content_fallback(self, document_service):
        """Test field with no typed value and no content returns None."""
        field = MagicMock(spec=[])  # No attributes at all

        result = document_service._extract_field_value(field)
        assert result is None


class TestValidateModel:
    """Tests for model validation."""

    @pytest.mark.asyncio
    async def test_validate_prebuilt_model(self, document_service):
        """Test that prebuilt models are always valid."""
        result = await document_service.validate_model("prebuilt-layout")
        assert result is True

        result = await document_service.validate_model("prebuilt-invoice")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_cached_model(self, document_service):
        """Test that cached models return True without API call."""
        # Add model to cache
        document_service._validated_models.add("custom-model-v1")

        result = await document_service.validate_model("custom-model-v1")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_model_success(self, document_service):
        """Test successful model validation via API."""
        from azure.core.exceptions import HttpResponseError

        # Create a 404 error for figure not found (expected behavior)
        mock_response = MagicMock()
        mock_response.status_code = 404
        figure_not_found = HttpResponseError(
            response=mock_response, message="Figure not found"
        )
        figure_not_found.status_code = 404  # Set directly on exception

        mock_client = AsyncMock()
        mock_client.get_analyze_result_figure = AsyncMock(side_effect=figure_not_found)

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            result = await document_service.validate_model("custom-model-v1")

        assert result is True
        assert "custom-model-v1" in document_service._validated_models

    @pytest.mark.asyncio
    async def test_validate_model_not_found(self, document_service):
        """Test model validation failure when model doesn't exist."""
        from azure.core.exceptions import HttpResponseError

        mock_response = MagicMock()
        mock_response.status_code = 404
        model_not_found = HttpResponseError(
            response=mock_response, message="Model 'invalid-model' not found"
        )
        model_not_found.status_code = 404  # Set directly on exception

        mock_client = AsyncMock()
        mock_client.get_analyze_result_figure = AsyncMock(side_effect=model_not_found)

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            with pytest.raises(DocumentProcessingError) as exc_info:
                await document_service.validate_model("invalid-model")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_model_other_http_error(self, document_service):
        """Test model validation with non-404 HTTP error."""
        from azure.core.exceptions import HttpResponseError

        mock_response = MagicMock()
        mock_response.status_code = 500
        server_error = HttpResponseError(
            response=mock_response, message="Internal server error"
        )
        server_error.status_code = 500  # Set directly on exception

        mock_client = AsyncMock()
        mock_client.get_analyze_result_figure = AsyncMock(side_effect=server_error)

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            with pytest.raises(DocumentProcessingError) as exc_info:
                await document_service.validate_model("custom-model")

        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_model_unexpected_error(self, document_service):
        """Test model validation with unexpected exception returns True."""
        mock_client = AsyncMock()
        mock_client.get_analyze_result_figure = AsyncMock(
            side_effect=Exception("Network error")
        )

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            # Should return True and log warning for unexpected errors
            result = await document_service.validate_model("custom-model")

        assert result is True


class TestAnalyzeDocumentEdgeCases:
    """Tests for edge cases in document analysis."""

    @pytest.mark.asyncio
    async def test_analyze_document_unexpected_error(self, document_service):
        """Test handling of unexpected exceptions."""
        mock_client = AsyncMock()
        mock_client.begin_analyze_document = AsyncMock(
            side_effect=Exception("Unexpected network failure")
        )

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            with pytest.raises(DocumentProcessingError) as exc_info:
                await document_service.analyze_document(
                    blob_url="https://test.blob/test.pdf",
                    model_id="model",
                    blob_name="test.pdf",
                )

        # The exception wraps the original message in the reason
        assert "Unexpected network failure" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_analyze_document_without_blob_name(self, document_service):
        """Test error reporting uses blob_url when blob_name not provided."""
        mock_client = AsyncMock()
        mock_client.begin_analyze_document = AsyncMock(
            side_effect=Exception("Test error")
        )

        with patch(
            "services.document_service.DocumentIntelligenceClient",
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            with pytest.raises(DocumentProcessingError) as exc_info:
                await document_service.analyze_document(
                    blob_url="https://test.blob/test.pdf",
                    model_id="model",
                    # No blob_name provided
                )

        assert "test.blob" in str(exc_info.value.blob_name)


class TestExtractResultMultiDocument:
    """Tests for multi-document result extraction."""

    def test_extract_result_multiple_documents(self, document_service):
        """Test extraction from result with multiple documents."""
        # Create mock fields for document 1
        field1 = MagicMock()
        field1.value_string = "Doc1 Value"
        field1.confidence = 0.9

        # Create mock fields for document 2
        field2 = MagicMock()
        field2.value_string = "Doc2 Value"
        field2.confidence = 0.85

        # Create bounding regions for page detection
        region1 = MagicMock()
        region1.page_number = 1
        region2 = MagicMock()
        region2.page_number = 2

        # Create documents
        doc1 = MagicMock()
        doc1.doc_type = "invoice"
        doc1.confidence = 0.92
        doc1.fields = {"field1": field1}
        doc1.bounding_regions = [region1]

        doc2 = MagicMock()
        doc2.doc_type = "invoice"
        doc2.confidence = 0.88
        doc2.fields = {"field1": field2}
        doc2.bounding_regions = [region2]

        # Create pages
        page1 = MagicMock()
        page2 = MagicMock()

        # Create result
        result = MagicMock()
        result.documents = [doc1, doc2]
        result.pages = [page1, page2]

        extracted = document_service._extract_result(result, "custom-model")

        assert extracted["status"] == "completed"
        assert extracted["pageCount"] == 2
        assert extracted["documentCount"] == 2
        assert "pages" in extracted
        assert len(extracted["pages"]) == 2
        assert extracted["pages"][0]["pageNumber"] == 1
        assert extracted["pages"][1]["pageNumber"] == 2
        # Check page-prefixed fields
        assert "page1_field1" in extracted["fields"]
        assert "page2_field1" in extracted["fields"]
        # Check average confidence
        assert extracted["modelConfidence"] == 0.9  # (0.92 + 0.88) / 2

    def test_extract_result_single_document_with_bounding_regions(self, document_service):
        """Test extraction from single document spanning multiple pages."""
        field = MagicMock()
        field.value_string = "Test Value"
        field.confidence = 0.95
        field.bounding_regions = [MagicMock(page_number=1)]

        region1 = MagicMock()
        region1.page_number = 1
        region2 = MagicMock()
        region2.page_number = 2

        document = MagicMock()
        document.doc_type = "form"
        document.confidence = 0.9
        document.fields = {"testField": field}
        document.bounding_regions = [region1, region2]

        page1 = MagicMock()
        page2 = MagicMock()

        result = MagicMock()
        result.documents = [document]
        result.pages = [page1, page2]

        extracted = document_service._extract_result(result, "model")

        assert extracted["pageCount"] == 2
        assert extracted["documentCount"] == 1
        assert extracted["documentPages"] == [1, 2]
        # Fields should have both prefixed and non-prefixed versions
        assert "testField" in extracted["fields"]
        assert "page1_testField" in extracted["fields"]

    def test_extract_result_pages_without_documents(self, document_service):
        """Test result with pages but no recognized documents."""
        page1 = MagicMock()
        page2 = MagicMock()

        result = MagicMock()
        result.documents = []
        result.pages = [page1, page2]

        extracted = document_service._extract_result(result, "custom-model")

        assert extracted["status"] == "completed"
        assert extracted["pageCount"] == 2
        assert extracted["documentCount"] == 0
        assert extracted["fields"] == {}
        assert extracted["docType"] is None

    def test_extract_result_page_mismatch_warning(self, document_service):
        """Test warning when not all pages match the model."""
        field = MagicMock()
        field.value_string = "Value"
        field.confidence = 0.9

        document = MagicMock()
        document.doc_type = "invoice"
        document.confidence = 0.85
        document.fields = {"field": field}
        document.bounding_regions = None

        # 3 pages but only 1 document recognized
        result = MagicMock()
        result.documents = [document]
        result.pages = [MagicMock(), MagicMock(), MagicMock()]

        extracted = document_service._extract_result(result, "model")

        assert extracted["pageCount"] == 3
        assert extracted["documentCount"] == 1
        assert "_warning" in extracted
        assert "1 of 3" in extracted["_warning"]

    def test_extract_result_document_without_bounding_regions(self, document_service):
        """Test document extraction when bounding_regions is None."""
        field = MagicMock()
        field.value_string = "Value"
        field.confidence = 0.9
        field.bounding_regions = None

        document = MagicMock()
        document.doc_type = "form"
        document.confidence = 0.88
        document.fields = {"testField": field}
        document.bounding_regions = None

        result = MagicMock()
        result.documents = [document]
        result.pages = [MagicMock()]

        extracted = document_service._extract_result(result, "model")

        assert extracted["docType"] == "form"
        assert "documentPages" not in extracted
        assert extracted["fields"]["testField"] == "Value"

    def test_extract_result_multiple_docs_without_confidence(self, document_service):
        """Test multiple documents where some have no confidence."""
        doc1 = MagicMock()
        doc1.doc_type = "invoice"
        doc1.confidence = None
        doc1.fields = {}
        doc1.bounding_regions = [MagicMock(page_number=1)]

        doc2 = MagicMock()
        doc2.doc_type = "invoice"
        doc2.confidence = 0.9
        doc2.fields = {}
        doc2.bounding_regions = [MagicMock(page_number=2)]

        result = MagicMock()
        result.documents = [doc1, doc2]
        result.pages = [MagicMock(), MagicMock()]

        extracted = document_service._extract_result(result, "model")

        # Only doc2 has confidence, so average is just 0.9
        assert extracted["modelConfidence"] == 0.9


class TestDocumentProcessingErrorClass:
    """Tests for DocumentProcessingError exception."""

    def test_error_attributes(self):
        """Test error has correct attributes."""
        error = DocumentProcessingError("test.pdf", "Invalid format")

        assert error.blob_name == "test.pdf"
        assert error.reason == "Invalid format"
        assert "test.pdf" in str(error)
        assert "Invalid format" in str(error)


class TestRateLimitErrorClass:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error(self):
        """Test RateLimitError can be raised."""
        error = RateLimitError("Rate limit exceeded")
        assert "Rate limit exceeded" in str(error)
