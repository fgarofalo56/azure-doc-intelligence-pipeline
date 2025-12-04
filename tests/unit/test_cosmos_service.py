"""Unit tests for CosmosService."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))

from services.cosmos_service import CosmosError, CosmosService


@pytest.fixture
def cosmos_service():
    """Create CosmosService instance for testing."""
    return CosmosService(
        endpoint="https://test-cosmos.documents.azure.com:443/",
        database_name="DocumentsDB",
        container_name="ExtractedDocuments",
    )


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "id": "folder_test_pdf",
        "sourceFile": "folder/test.pdf",
        "processedAt": "2024-01-15T10:30:00Z",
        "modelId": "custom-model-v1",
        "modelConfidence": 0.95,
        "status": "completed",
        "fields": {"vendorName": "Acme Corp"},
        "confidence": {"vendorName": 0.98},
    }


class TestCosmosServiceSave:
    """Tests for save_document_result method."""

    @pytest.mark.asyncio
    async def test_save_document_success(self, cosmos_service, sample_document):
        """Test successful document save."""
        mock_container = AsyncMock()
        mock_container.upsert_item = AsyncMock(return_value=sample_document)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                result = await cosmos_service.save_document_result(sample_document)

        assert result["id"] == "folder_test_pdf"
        mock_container.upsert_item.assert_called_once_with(body=sample_document)

    @pytest.mark.asyncio
    async def test_save_document_missing_id(self, cosmos_service):
        """Test error when document missing id field."""
        document = {"sourceFile": "test.pdf"}

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_service.save_document_result(document)

        assert exc_info.value.operation == "save"
        assert "id" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_save_document_missing_partition_key(self, cosmos_service):
        """Test error when document missing sourceFile partition key."""
        document = {"id": "test_doc"}

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_service.save_document_result(document)

        assert exc_info.value.operation == "save"
        assert "sourceFile" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_save_document_converts_integer_id(self, cosmos_service, sample_document):
        """Test that integer IDs are converted to strings."""
        sample_document["id"] = 12345  # Integer ID (problematic)

        mock_container = AsyncMock()
        mock_container.upsert_item = AsyncMock(return_value=sample_document)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                await cosmos_service.save_document_result(sample_document)

        # Verify ID was converted to string
        call_args = mock_container.upsert_item.call_args
        assert isinstance(call_args.kwargs["body"]["id"], str)

    @pytest.mark.asyncio
    async def test_save_document_cosmos_error(self, cosmos_service, sample_document):
        """Test CosmosError on database failure."""
        from azure.cosmos.exceptions import CosmosHttpResponseError

        # Create a properly configured Cosmos error
        mock_response = MagicMock()
        mock_response.status_code = 500
        cosmos_error = CosmosHttpResponseError(response=mock_response, message="Internal error")
        cosmos_error.message = "Internal error"

        mock_container = AsyncMock()
        # Use the exception directly as side_effect
        mock_container.upsert_item.side_effect = cosmos_error

        mock_database = MagicMock()
        mock_database.get_container_client.return_value = mock_container

        mock_client = AsyncMock()
        mock_client.get_database_client.return_value = mock_database
        mock_client.__aenter__.return_value = mock_client

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                with pytest.raises(CosmosError) as exc_info:
                    await cosmos_service.save_document_result(sample_document)

        assert exc_info.value.operation == "save"


class TestCosmosServiceGet:
    """Tests for get_document method."""

    @pytest.mark.asyncio
    async def test_get_document_success(self, cosmos_service, sample_document):
        """Test successful document retrieval."""
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value=sample_document)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                result = await cosmos_service.get_document(
                    doc_id="folder_test_pdf",
                    partition_key="folder/test.pdf",
                )

        assert result["id"] == "folder_test_pdf"
        mock_container.read_item.assert_called_once_with(
            item="folder_test_pdf",
            partition_key="folder/test.pdf",
        )

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, cosmos_service):
        """Test None return when document not found."""
        from azure.cosmos.exceptions import CosmosHttpResponseError

        mock_response = MagicMock()
        mock_response.status_code = 404
        not_found_error = CosmosHttpResponseError(response=mock_response, message="Not found")
        not_found_error.status_code = 404

        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(side_effect=not_found_error)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                result = await cosmos_service.get_document(
                    doc_id="nonexistent",
                    partition_key="nonexistent",
                )

        assert result is None


class TestCosmosServiceQuery:
    """Tests for query_documents method."""

    @pytest.mark.asyncio
    async def test_query_documents_success(self, cosmos_service, sample_document):
        """Test successful document query."""

        async def mock_query_items(*args, **kwargs):
            yield sample_document

        mock_container = MagicMock()
        mock_container.query_items = mock_query_items

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                result = await cosmos_service.query_documents(
                    query="SELECT * FROM c WHERE c.status = @status",
                    parameters=[{"name": "@status", "value": "completed"}],
                    partition_key="folder/test.pdf",
                )

        assert len(result) == 1
        assert result[0]["id"] == "folder_test_pdf"


class TestCosmosServiceGetStatus:
    """Tests for get_document_status method."""

    @pytest.mark.asyncio
    async def test_get_document_status_completed(self, cosmos_service, sample_document):
        """Test getting completed status."""
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value=sample_document)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                status = await cosmos_service.get_document_status("folder/test.pdf")

        assert status == "completed"

    @pytest.mark.asyncio
    async def test_get_document_status_not_found(self, cosmos_service):
        """Test None status when document not found."""
        from azure.cosmos.exceptions import CosmosHttpResponseError

        mock_response = MagicMock()
        mock_response.status_code = 404
        not_found_error = CosmosHttpResponseError(response=mock_response, message="Not found")
        not_found_error.status_code = 404

        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(side_effect=not_found_error)

        mock_database = MagicMock()
        mock_database.get_container_client = MagicMock(return_value=mock_container)

        mock_client = AsyncMock()
        mock_client.get_database_client = MagicMock(return_value=mock_database)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("services.cosmos_service.CosmosClient", return_value=mock_client):
            with patch("services.cosmos_service.DefaultAzureCredential"):
                status = await cosmos_service.get_document_status("nonexistent.pdf")

        assert status is None
