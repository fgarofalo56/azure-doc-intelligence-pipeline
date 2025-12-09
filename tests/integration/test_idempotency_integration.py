"""Integration tests for idempotency module.

Tests idempotency checks with real Cosmos DB to verify:
- Duplicate detection with content hash
- Idempotency key generation consistency
- Processing version tracking
- Concurrent processing scenarios

Requires COSMOS_ENDPOINT environment variable with managed identity access.
"""

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def cosmos_service():
    """Create CosmosService with real credentials."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        pytest.skip("COSMOS_ENDPOINT not set")

    from services.cosmos_service import CosmosService

    return CosmosService(
        endpoint=endpoint,
        database_name=os.environ.get("COSMOS_DATABASE", "DocumentsDB"),
        container_name=os.environ.get("COSMOS_CONTAINER", "ProcessedDocuments"),
    )


@pytest.fixture
def test_blob_name():
    """Generate unique blob name for test isolation."""
    return f"idempotency-test/{uuid4().hex[:8]}.pdf"


class TestIdempotencyKeyGeneration:
    """Tests for idempotency key generation."""

    def test_generate_key_consistency(self):
        """Test that same inputs always generate same key."""
        from services.idempotency import generate_idempotency_key

        blob_name = "test/document.pdf"
        model_id = "prebuilt-invoice"

        key1 = generate_idempotency_key(blob_name, model_id)
        key2 = generate_idempotency_key(blob_name, model_id)

        assert key1 == key2
        assert len(key1) == 32

    def test_generate_key_with_content_hash(self):
        """Test key generation includes content hash."""
        from services.idempotency import generate_idempotency_key

        blob_name = "test/document.pdf"
        model_id = "prebuilt-invoice"

        key1 = generate_idempotency_key(blob_name, model_id, content_hash="abc123")
        key2 = generate_idempotency_key(blob_name, model_id, content_hash="abc123")
        key3 = generate_idempotency_key(blob_name, model_id, content_hash="def456")

        assert key1 == key2
        assert key1 != key3

    def test_generate_content_hash_consistency(self):
        """Test content hash generation is consistent."""
        from services.idempotency import generate_content_hash

        content = b"PDF file content here"

        hash1 = generate_content_hash(content)
        hash2 = generate_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 16


class TestIdempotencyCheckWithCosmos:
    """Tests for idempotency check against real Cosmos DB."""

    @pytest.mark.asyncio
    async def test_check_idempotency_no_existing(self, cosmos_service, test_blob_name):
        """Test idempotency check when no existing document."""
        from services.idempotency import check_idempotency, generate_idempotency_key

        key = generate_idempotency_key(test_blob_name, "prebuilt-invoice")

        result = await check_idempotency(
            cosmos_service=cosmos_service,
            idempotency_key=key,
            source_file=test_blob_name,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_check_idempotency_with_existing(self, cosmos_service, test_blob_name):
        """Test idempotency check detects existing document."""
        from services.idempotency import (
            check_idempotency,
            create_idempotent_document,
            generate_idempotency_key,
        )

        key = generate_idempotency_key(test_blob_name, "prebuilt-invoice")
        doc_id = f"idem_{uuid4().hex[:8]}"

        # Create existing document with idempotency key
        base_doc = {
            "id": doc_id,
            "sourceFile": test_blob_name,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "fields": {"vendor": "Test Corp"},
        }
        idem_doc = create_idempotent_document(base_doc, key)
        await cosmos_service.save_document_result(idem_doc)

        # Check idempotency - should find existing
        result = await check_idempotency(
            cosmos_service=cosmos_service,
            idempotency_key=key,
            source_file=test_blob_name,
        )

        assert result is not None
        assert result["id"] == doc_id
        assert result["idempotencyKey"] == key
        assert result["status"] == "completed"

        # Cleanup
        await cosmos_service.delete_document(doc_id, test_blob_name)

    @pytest.mark.asyncio
    async def test_check_and_generate_idempotency_new(self, cosmos_service, test_blob_name):
        """Test combined check and generate for new document."""
        from services.idempotency import check_and_generate_idempotency

        result = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=test_blob_name,
            model_id="prebuilt-invoice",
        )

        assert result.is_duplicate is False
        assert result.existing_document is None
        assert len(result.idempotency_key) == 32

    @pytest.mark.asyncio
    async def test_check_and_generate_idempotency_duplicate(self, cosmos_service, test_blob_name):
        """Test combined check and generate detects duplicate."""
        from services.idempotency import (
            check_and_generate_idempotency,
            create_idempotent_document,
            generate_idempotency_key,
        )

        model_id = "prebuilt-invoice"
        key = generate_idempotency_key(test_blob_name, model_id)
        doc_id = f"dup_{uuid4().hex[:8]}"

        # Create existing document
        base_doc = {
            "id": doc_id,
            "sourceFile": test_blob_name,
            "status": "completed",
        }
        idem_doc = create_idempotent_document(base_doc, key)
        await cosmos_service.save_document_result(idem_doc)

        # Check and generate - should find duplicate
        result = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=test_blob_name,
            model_id=model_id,
        )

        assert result.is_duplicate is True
        assert result.existing_document is not None
        assert result.existing_document["id"] == doc_id

        # Cleanup
        await cosmos_service.delete_document(doc_id, test_blob_name)


class TestIdempotentDocumentCreation:
    """Tests for creating idempotent documents."""

    @pytest.mark.asyncio
    async def test_create_and_save_idempotent_document(self, cosmos_service, test_blob_name):
        """Test creating and saving document with idempotency fields."""
        from services.idempotency import (
            PROCESSING_VERSION,
            create_idempotent_document,
            generate_idempotency_key,
        )

        key = generate_idempotency_key(test_blob_name, "test-model")
        doc_id = f"create_{uuid4().hex[:8]}"

        base_doc = {
            "id": doc_id,
            "sourceFile": test_blob_name,
            "status": "completed",
            "fields": {"amount": 100.50},
        }

        idem_doc = create_idempotent_document(
            base_document=base_doc,
            idempotency_key=key,
            content_hash="abc123def456",
        )

        # Save to Cosmos
        saved = await cosmos_service.save_document_result(idem_doc)

        assert saved["idempotencyKey"] == key
        assert saved["processingVersion"] == PROCESSING_VERSION
        assert saved["contentHash"] == "abc123def456"
        assert "idempotencyCreatedAt" in saved
        assert saved["fields"]["amount"] == 100.50

        # Cleanup
        await cosmos_service.delete_document(doc_id, test_blob_name)

    @pytest.mark.asyncio
    async def test_processing_version_tracked(self, cosmos_service, test_blob_name):
        """Test that processing version is properly tracked."""
        from services.idempotency import (
            PROCESSING_VERSION,
            create_idempotent_document,
            generate_idempotency_key,
        )

        key = generate_idempotency_key(test_blob_name, "test-model")
        doc_id = f"version_{uuid4().hex[:8]}"

        base_doc = {"id": doc_id, "sourceFile": test_blob_name, "status": "completed"}
        idem_doc = create_idempotent_document(base_doc, key)

        await cosmos_service.save_document_result(idem_doc)

        # Retrieve and check version
        retrieved = await cosmos_service.get_document(doc_id, test_blob_name)
        assert retrieved["processingVersion"] == PROCESSING_VERSION

        # Cleanup
        await cosmos_service.delete_document(doc_id, test_blob_name)


class TestConcurrentIdempotencyChecks:
    """Tests for concurrent idempotency scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_idempotency_checks(self, cosmos_service):
        """Test concurrent checks don't cause duplicates."""
        from services.idempotency import check_and_generate_idempotency

        blob_name = f"concurrent-test/{uuid4().hex[:8]}.pdf"
        model_id = "prebuilt-invoice"

        # Simulate concurrent checks
        async def check_once():
            return await check_and_generate_idempotency(
                cosmos_service=cosmos_service,
                blob_name=blob_name,
                model_id=model_id,
            )

        # Run 5 concurrent checks
        results = await asyncio.gather(*[check_once() for _ in range(5)])

        # All should generate the same key
        keys = [r.idempotency_key for r in results]
        assert len(set(keys)) == 1  # All keys should be identical

        # All should be non-duplicate (no existing document yet)
        assert all(r.is_duplicate is False for r in results)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_checks_with_existing(self, cosmos_service):
        """Test concurrent checks all detect existing document."""
        from services.idempotency import (
            check_and_generate_idempotency,
            create_idempotent_document,
            generate_idempotency_key,
        )

        blob_name = f"concurrent-existing/{uuid4().hex[:8]}.pdf"
        model_id = "prebuilt-invoice"

        # Create existing document first
        key = generate_idempotency_key(blob_name, model_id)
        doc_id = f"existing_{uuid4().hex[:8]}"
        base_doc = {"id": doc_id, "sourceFile": blob_name, "status": "completed"}
        idem_doc = create_idempotent_document(base_doc, key)
        await cosmos_service.save_document_result(idem_doc)

        # Concurrent checks should all detect duplicate
        async def check_once():
            return await check_and_generate_idempotency(
                cosmos_service=cosmos_service,
                blob_name=blob_name,
                model_id=model_id,
            )

        results = await asyncio.gather(*[check_once() for _ in range(5)])

        # All should detect duplicate
        assert all(r.is_duplicate is True for r in results)
        assert all(r.existing_document["id"] == doc_id for r in results)

        # Cleanup
        await cosmos_service.delete_document(doc_id, blob_name)


class TestContentHashIdempotency:
    """Tests for content-hash based idempotency."""

    @pytest.mark.asyncio
    async def test_different_content_different_key(self, cosmos_service):
        """Test that different content hashes generate different keys."""
        from services.idempotency import check_and_generate_idempotency

        blob_name = f"content-hash-test/{uuid4().hex[:8]}.pdf"
        model_id = "prebuilt-invoice"

        result1 = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=blob_name,
            model_id=model_id,
            content_hash="hash_v1",
        )

        result2 = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=blob_name,
            model_id=model_id,
            content_hash="hash_v2",
        )

        # Different content should generate different keys
        assert result1.idempotency_key != result2.idempotency_key

    @pytest.mark.asyncio
    async def test_reprocessing_detects_same_content(self, cosmos_service):
        """Test that reprocessing same content is detected as duplicate."""
        from services.idempotency import (
            check_and_generate_idempotency,
            create_idempotent_document,
            generate_idempotency_key,
        )

        blob_name = f"reprocess-test/{uuid4().hex[:8]}.pdf"
        model_id = "prebuilt-invoice"
        content_hash = "same_content_hash_123"

        # First processing
        key = generate_idempotency_key(blob_name, model_id, content_hash=content_hash)
        doc_id = f"first_{uuid4().hex[:8]}"
        base_doc = {"id": doc_id, "sourceFile": blob_name, "status": "completed"}
        idem_doc = create_idempotent_document(base_doc, key, content_hash=content_hash)
        await cosmos_service.save_document_result(idem_doc)

        # Second processing attempt with same content
        result = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=blob_name,
            model_id=model_id,
            content_hash=content_hash,
        )

        assert result.is_duplicate is True
        assert result.existing_document["contentHash"] == content_hash

        # Cleanup
        await cosmos_service.delete_document(doc_id, blob_name)
