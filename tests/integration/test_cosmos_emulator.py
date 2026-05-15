"""Emulator-based tests for Cosmos DB service.

These tests run against the Cosmos DB Linux Emulator for CI-friendly
integration testing without requiring real Azure Cosmos DB resources.

To run these tests:
1. Start Cosmos DB Emulator: docker compose up cosmos-emulator -d
2. Wait for it to be healthy: docker compose logs -f cosmos-emulator
3. Run tests: RUN_EMULATOR_TESTS=1 uv run pytest tests/integration/test_cosmos_emulator.py -v

Note: The Cosmos DB emulator takes 60+ seconds to start up fully.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Mark all tests in this module as emulator tests
pytestmark = pytest.mark.emulator


class TestCosmosEmulatorBasicCRUD:
    """Basic CRUD operations using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_save_and_get_document(
        self, cosmos_emulator_service, emulator_test_id, emulator_source_file
    ):
        """Test saving and retrieving a document."""
        document = {
            "id": emulator_test_id,
            "sourceFile": emulator_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "modelId": "emulator-test-model",
            "fields": {"vendor": "Test Corp", "amount": 1500.00},
            "confidence": {"vendor": 0.98, "amount": 0.95},
        }

        # Save
        saved = await cosmos_emulator_service.save_document_result(document)
        assert saved["id"] == emulator_test_id
        assert saved["status"] == "completed"

        # Retrieve
        retrieved = await cosmos_emulator_service.get_document(
            emulator_test_id, emulator_source_file
        )
        assert retrieved is not None
        assert retrieved["id"] == emulator_test_id
        assert retrieved["fields"]["vendor"] == "Test Corp"

        # Cleanup
        await cosmos_emulator_service.delete_document(emulator_test_id, emulator_source_file)

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, cosmos_emulator_service):
        """Test getting a document that doesn't exist."""
        result = await cosmos_emulator_service.get_document(
            f"nonexistent_{uuid4().hex}",
            "nonexistent/file.pdf"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_document(
        self, cosmos_emulator_service, emulator_test_id, emulator_source_file
    ):
        """Test deleting a document."""
        document = {
            "id": emulator_test_id,
            "sourceFile": emulator_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        await cosmos_emulator_service.save_document_result(document)

        # Delete
        deleted = await cosmos_emulator_service.delete_document(
            emulator_test_id, emulator_source_file
        )
        assert deleted is True

        # Verify deleted
        result = await cosmos_emulator_service.get_document(
            emulator_test_id, emulator_source_file
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_document(
        self, cosmos_emulator_service, emulator_test_id, emulator_source_file
    ):
        """Test upsert behavior - create then update."""
        # Create
        document = {
            "id": emulator_test_id,
            "sourceFile": emulator_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "processing",
            "fields": {"original": True},
        }
        await cosmos_emulator_service.save_document_result(document)

        # Update via upsert
        document["status"] = "completed"
        document["fields"]["updated"] = True
        await cosmos_emulator_service.save_document_result(document)

        # Verify
        retrieved = await cosmos_emulator_service.get_document(
            emulator_test_id, emulator_source_file
        )
        assert retrieved["status"] == "completed"
        assert retrieved["fields"]["original"] is True
        assert retrieved["fields"]["updated"] is True

        # Cleanup
        await cosmos_emulator_service.delete_document(emulator_test_id, emulator_source_file)


class TestCosmosEmulatorQueryOperations:
    """Query operations using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_query_documents(self, cosmos_emulator_service):
        """Test querying documents with SQL."""
        source_file = f"emulator-query-test/{uuid4().hex[:8]}.pdf"
        doc_id = f"query_test_{uuid4().hex[:8]}"

        document = {
            "id": doc_id,
            "sourceFile": source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        await cosmos_emulator_service.save_document_result(document)

        # Query
        results = await cosmos_emulator_service.query_documents(
            query="SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": doc_id}],
            partition_key=source_file,
        )

        assert len(results) == 1
        assert results[0]["id"] == doc_id

        # Cleanup
        await cosmos_emulator_service.delete_document(doc_id, source_file)

    @pytest.mark.asyncio
    async def test_query_by_source_file(self, cosmos_emulator_service):
        """Test querying all documents for a source file."""
        source_file = f"emulator-multi-form/{uuid4().hex[:8]}.pdf"
        doc_ids = []

        # Create multiple form documents
        for i in range(3):
            doc_id = f"form_{i}_{uuid4().hex[:8]}"
            doc_ids.append(doc_id)
            document = {
                "id": doc_id,
                "sourceFile": source_file,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "formNumber": i + 1,
                "status": "completed",
            }
            await cosmos_emulator_service.save_document_result(document)

        # Query
        results = await cosmos_emulator_service.query_by_source_file(source_file)

        assert len(results) == 3
        form_numbers = sorted([r["formNumber"] for r in results])
        assert form_numbers == [1, 2, 3]

        # Cleanup
        for doc_id in doc_ids:
            await cosmos_emulator_service.delete_document(doc_id, source_file)

    @pytest.mark.asyncio
    async def test_get_document_status(self, cosmos_emulator_service):
        """Test getting document status."""
        source_file = f"emulator-status/{uuid4().hex[:8]}.pdf"
        doc_id = source_file.replace("/", "_").replace(".", "_")

        document = {
            "id": doc_id,
            "sourceFile": source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "processing",
        }
        await cosmos_emulator_service.save_document_result(document)

        # Get status
        status = await cosmos_emulator_service.get_document_status(source_file)
        assert status == "processing"

        # Update status
        document["status"] = "completed"
        await cosmos_emulator_service.save_document_result(document)

        status = await cosmos_emulator_service.get_document_status(source_file)
        assert status == "completed"

        # Cleanup
        await cosmos_emulator_service.delete_document(doc_id, source_file)


class TestCosmosEmulatorMultiTenant:
    """Multi-tenant operations using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, cosmos_emulator_service):
        """Test querying documents by tenant ID."""
        tenant_id = f"tenant_{uuid4().hex[:8]}"
        doc_ids = []

        # Create documents for tenant
        for i in range(2):
            source_file = f"emulator-tenant/{tenant_id}_{i}.pdf"
            doc_id = f"tenant_doc_{i}_{uuid4().hex[:8]}"
            doc_ids.append((doc_id, source_file))

            document = {
                "id": doc_id,
                "sourceFile": source_file,
                "tenantId": tenant_id,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            }
            await cosmos_emulator_service.save_document_result(document)

        # Query by tenant
        results = await cosmos_emulator_service.query_by_tenant(tenant_id)

        assert len(results) >= 2
        for r in results:
            assert r["tenantId"] == tenant_id

        # Cleanup
        for doc_id, source_file in doc_ids:
            await cosmos_emulator_service.delete_document(doc_id, source_file)


class TestCosmosEmulatorRetryOperations:
    """Retry tracking operations using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_increment_retry_count(
        self, cosmos_emulator_service, emulator_test_id, emulator_source_file
    ):
        """Test incrementing retry count."""
        document = {
            "id": emulator_test_id,
            "sourceFile": emulator_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "retryCount": 0,
        }
        await cosmos_emulator_service.save_document_result(document)

        # Increment
        new_count = await cosmos_emulator_service.increment_retry_count(
            emulator_test_id, emulator_source_file
        )
        assert new_count == 1

        # Verify
        retrieved = await cosmos_emulator_service.get_document(
            emulator_test_id, emulator_source_file
        )
        assert retrieved["retryCount"] == 1
        assert retrieved["status"] == "pending"

        # Cleanup
        await cosmos_emulator_service.delete_document(emulator_test_id, emulator_source_file)


class TestCosmosEmulatorBulkOperations:
    """Bulk operations using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_delete_by_source_file(self, cosmos_emulator_service):
        """Test deleting all documents for a source file."""
        source_file = f"emulator-bulk-delete/{uuid4().hex[:8]}.pdf"

        # Create multiple documents
        for i in range(3):
            doc_id = f"bulk_delete_{i}_{uuid4().hex[:8]}"
            document = {
                "id": doc_id,
                "sourceFile": source_file,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "formNumber": i + 1,
            }
            await cosmos_emulator_service.save_document_result(document)

        # Bulk delete
        deleted_count = await cosmos_emulator_service.delete_by_source_file(source_file)
        assert deleted_count == 3

        # Verify deleted
        results = await cosmos_emulator_service.query_by_source_file(source_file)
        assert len(results) == 0


class TestCosmosEmulatorErrorHandling:
    """Error handling tests using Cosmos DB emulator."""

    @pytest.mark.asyncio
    async def test_save_document_missing_id(self, cosmos_emulator_service):
        """Test saving document without ID raises error."""
        from services.cosmos_service import CosmosError

        document = {
            "sourceFile": "emulator-test/file.pdf",
            "status": "completed",
        }

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_emulator_service.save_document_result(document)

        assert "id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_document_missing_partition_key(self, cosmos_emulator_service):
        """Test saving document without sourceFile raises error."""
        from services.cosmos_service import CosmosError

        document = {
            "id": f"test_{uuid4().hex[:8]}",
            "status": "completed",
        }

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_emulator_service.save_document_result(document)

        assert "sourcefile" in str(exc_info.value).lower()
