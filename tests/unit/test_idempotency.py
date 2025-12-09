"""Unit tests for idempotency module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.idempotency import (
    PROCESSING_VERSION,
    IdempotencyResult,
    check_and_generate_idempotency,
    check_idempotency,
    create_idempotent_document,
    generate_content_hash,
    generate_idempotency_key,
)


class TestGenerateIdempotencyKey:
    """Tests for generate_idempotency_key function."""

    def test_generates_32_char_key(self):
        """Test key is 32 characters long."""
        key = generate_idempotency_key(
            blob_name="folder/test.pdf",
            model_id="prebuilt-invoice",
        )
        assert len(key) == 32

    def test_same_inputs_same_key(self):
        """Test same inputs generate same key."""
        key1 = generate_idempotency_key(
            blob_name="folder/test.pdf",
            model_id="prebuilt-invoice",
            pages_per_form=2,
        )
        key2 = generate_idempotency_key(
            blob_name="folder/test.pdf",
            model_id="prebuilt-invoice",
            pages_per_form=2,
        )
        assert key1 == key2

    def test_different_blob_name_different_key(self):
        """Test different blob name generates different key."""
        key1 = generate_idempotency_key("file1.pdf", "model")
        key2 = generate_idempotency_key("file2.pdf", "model")
        assert key1 != key2

    def test_different_model_different_key(self):
        """Test different model generates different key."""
        key1 = generate_idempotency_key("file.pdf", "model-v1")
        key2 = generate_idempotency_key("file.pdf", "model-v2")
        assert key1 != key2

    def test_different_pages_per_form_different_key(self):
        """Test different pages_per_form generates different key."""
        key1 = generate_idempotency_key("file.pdf", "model", pages_per_form=1)
        key2 = generate_idempotency_key("file.pdf", "model", pages_per_form=2)
        assert key1 != key2

    def test_content_hash_affects_key(self):
        """Test content hash affects generated key."""
        key1 = generate_idempotency_key("file.pdf", "model", content_hash="abc123")
        key2 = generate_idempotency_key("file.pdf", "model", content_hash="def456")
        assert key1 != key2

    def test_no_content_hash_vs_with_hash(self):
        """Test key differs with and without content hash."""
        key1 = generate_idempotency_key("file.pdf", "model")
        key2 = generate_idempotency_key("file.pdf", "model", content_hash="abc123")
        assert key1 != key2

    def test_none_pages_per_form_uses_default(self):
        """Test None pages_per_form uses 'default' string."""
        key1 = generate_idempotency_key("file.pdf", "model", pages_per_form=None)
        key2 = generate_idempotency_key("file.pdf", "model")
        assert key1 == key2


class TestGenerateContentHash:
    """Tests for generate_content_hash function."""

    def test_generates_16_char_hash(self):
        """Test content hash is 16 characters long."""
        content = b"PDF content here"
        hash_value = generate_content_hash(content)
        assert len(hash_value) == 16

    def test_same_content_same_hash(self):
        """Test same content generates same hash."""
        content = b"PDF content here"
        hash1 = generate_content_hash(content)
        hash2 = generate_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test different content generates different hash."""
        hash1 = generate_content_hash(b"Content 1")
        hash2 = generate_content_hash(b"Content 2")
        assert hash1 != hash2

    def test_empty_content(self):
        """Test empty content generates valid hash."""
        hash_value = generate_content_hash(b"")
        assert len(hash_value) == 16


class TestCheckIdempotency:
    """Tests for check_idempotency function."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_no_existing_document(self, mock_cosmos):
        """Test when no existing document found."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])

        result = await check_idempotency(
            cosmos_service=mock_cosmos,
            idempotency_key="key123",
            source_file="folder/test.pdf",
        )

        assert result is None
        mock_cosmos.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_completed_document(self, mock_cosmos):
        """Test when existing completed document found."""
        existing_doc = {
            "id": "doc_123",
            "idempotencyKey": "key123",
            "status": "completed",
            "fields": {"vendorName": "Acme"},
        }
        mock_cosmos.query_documents = AsyncMock(return_value=[existing_doc])

        result = await check_idempotency(
            cosmos_service=mock_cosmos,
            idempotency_key="key123",
            source_file="folder/test.pdf",
        )

        assert result is not None
        assert result["id"] == "doc_123"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_query_uses_partition_key(self, mock_cosmos):
        """Test query uses partition key for efficiency."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])

        await check_idempotency(
            cosmos_service=mock_cosmos,
            idempotency_key="key123",
            source_file="folder/test.pdf",
        )

        # Verify partition_key is passed
        call_kwargs = mock_cosmos.query_documents.call_args.kwargs
        assert call_kwargs.get("partition_key") == "folder/test.pdf"

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, mock_cosmos):
        """Test exception during check returns None (fail open)."""
        mock_cosmos.query_documents = AsyncMock(side_effect=Exception("Cosmos error"))

        result = await check_idempotency(
            cosmos_service=mock_cosmos,
            idempotency_key="key123",
            source_file="folder/test.pdf",
        )

        # Should return None instead of raising
        assert result is None


class TestCreateIdempotentDocument:
    """Tests for create_idempotent_document function."""

    def test_adds_idempotency_fields(self):
        """Test idempotency fields are added."""
        base_doc = {"id": "doc_123", "fields": {"vendorName": "Acme"}}

        result = create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
        )

        assert result["idempotencyKey"] == "key123"
        assert result["processingVersion"] == PROCESSING_VERSION
        assert "idempotencyCreatedAt" in result

    def test_preserves_original_fields(self):
        """Test original document fields are preserved."""
        base_doc = {
            "id": "doc_123",
            "fields": {"vendorName": "Acme"},
            "sourceFile": "folder/test.pdf",
        }

        result = create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
        )

        assert result["id"] == "doc_123"
        assert result["fields"] == {"vendorName": "Acme"}
        assert result["sourceFile"] == "folder/test.pdf"

    def test_does_not_modify_original(self):
        """Test original document is not modified."""
        base_doc = {"id": "doc_123"}

        create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
        )

        assert "idempotencyKey" not in base_doc

    def test_adds_content_hash_when_provided(self):
        """Test content hash is added when provided."""
        base_doc = {"id": "doc_123"}

        result = create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
            content_hash="abc123def456",
        )

        assert result["contentHash"] == "abc123def456"

    def test_no_content_hash_when_not_provided(self):
        """Test no content hash field when not provided."""
        base_doc = {"id": "doc_123"}

        result = create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
        )

        assert "contentHash" not in result

    def test_idempotency_created_at_is_iso_format(self):
        """Test idempotencyCreatedAt is in ISO format."""
        base_doc = {"id": "doc_123"}

        result = create_idempotent_document(
            base_document=base_doc,
            idempotency_key="key123",
        )

        # Should be valid ISO format with 'T' separator
        assert "T" in result["idempotencyCreatedAt"]


class TestIdempotencyResult:
    """Tests for IdempotencyResult class."""

    def test_create_duplicate_result(self):
        """Test creating result indicating duplicate."""
        existing = {"id": "doc_123", "status": "completed"}
        result = IdempotencyResult(
            is_duplicate=True,
            existing_document=existing,
            idempotency_key="key123",
        )

        assert result.is_duplicate is True
        assert result.existing_document == existing
        assert result.idempotency_key == "key123"

    def test_create_non_duplicate_result(self):
        """Test creating result indicating not duplicate."""
        result = IdempotencyResult(
            is_duplicate=False,
            existing_document=None,
            idempotency_key="key456",
        )

        assert result.is_duplicate is False
        assert result.existing_document is None
        assert result.idempotency_key == "key456"

    def test_default_values(self):
        """Test default values for optional parameters."""
        result = IdempotencyResult(is_duplicate=False)

        assert result.is_duplicate is False
        assert result.existing_document is None
        assert result.idempotency_key == ""


class TestCheckAndGenerateIdempotency:
    """Tests for check_and_generate_idempotency function."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_non_duplicate_when_no_existing(self, mock_cosmos):
        """Test returns non-duplicate when no existing document."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])

        result = await check_and_generate_idempotency(
            cosmos_service=mock_cosmos,
            blob_name="folder/test.pdf",
            model_id="prebuilt-invoice",
        )

        assert result.is_duplicate is False
        assert result.existing_document is None
        assert len(result.idempotency_key) == 32

    @pytest.mark.asyncio
    async def test_returns_duplicate_when_existing(self, mock_cosmos):
        """Test returns duplicate when existing document found."""
        existing = {"id": "doc_123", "status": "completed"}
        mock_cosmos.query_documents = AsyncMock(return_value=[existing])

        result = await check_and_generate_idempotency(
            cosmos_service=mock_cosmos,
            blob_name="folder/test.pdf",
            model_id="prebuilt-invoice",
        )

        assert result.is_duplicate is True
        assert result.existing_document == existing

    @pytest.mark.asyncio
    async def test_passes_all_parameters(self, mock_cosmos):
        """Test all parameters affect the generated key."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])

        result1 = await check_and_generate_idempotency(
            cosmos_service=mock_cosmos,
            blob_name="test.pdf",
            model_id="model",
            pages_per_form=2,
            content_hash="abc123",
        )

        result2 = await check_and_generate_idempotency(
            cosmos_service=mock_cosmos,
            blob_name="test.pdf",
            model_id="model",
            pages_per_form=3,
            content_hash="abc123",
        )

        assert result1.idempotency_key != result2.idempotency_key

    @pytest.mark.asyncio
    async def test_handles_cosmos_error_gracefully(self, mock_cosmos):
        """Test handles cosmos error without raising."""
        mock_cosmos.query_documents = AsyncMock(side_effect=Exception("Error"))

        result = await check_and_generate_idempotency(
            cosmos_service=mock_cosmos,
            blob_name="test.pdf",
            model_id="model",
        )

        # Should not raise, and return non-duplicate (fail open)
        assert result.is_duplicate is False
        assert len(result.idempotency_key) == 32
