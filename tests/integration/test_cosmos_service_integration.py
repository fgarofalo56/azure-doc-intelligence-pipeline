"""Integration tests for Cosmos DB service.

Tests actual Azure Cosmos DB operations including:
- Document CRUD operations
- Query operations with partition keys
- Multi-tenant queries
- Idempotency operations
- Retry count tracking

Requires COSMOS_ENDPOINT environment variable with managed identity access.
"""

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
def test_doc_id():
    """Generate unique document ID for test isolation."""
    return f"cosmos_test_{uuid4().hex[:8]}"


@pytest.fixture
def test_source_file(test_doc_id):
    """Generate unique source file path for test isolation."""
    return f"cosmos-integration-test/{test_doc_id}.pdf"


class TestDocumentCRUD:
    """Tests for basic document CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_document(self, cosmos_service, test_doc_id, test_source_file):
        """Test saving a document to Cosmos DB."""
        document = {
            "id": test_doc_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "modelId": "integration-test-model",
            "fields": {"vendor": "Test Corp", "amount": 1500.00},
            "confidence": {"vendor": 0.98, "amount": 0.95},
        }

        saved = await cosmos_service.save_document_result(document)

        assert saved["id"] == test_doc_id
        assert saved["sourceFile"] == test_source_file
        assert saved["status"] == "completed"

        # Cleanup
        await cosmos_service.delete_document(test_doc_id, test_source_file)

    @pytest.mark.asyncio
    async def test_get_document(self, cosmos_service, test_doc_id, test_source_file):
        """Test retrieving a document by ID and partition key."""
        # Create document first
        document = {
            "id": test_doc_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "fields": {"testField": "testValue"},
        }
        await cosmos_service.save_document_result(document)

        # Retrieve
        retrieved = await cosmos_service.get_document(test_doc_id, test_source_file)

        assert retrieved is not None
        assert retrieved["id"] == test_doc_id
        assert retrieved["fields"]["testField"] == "testValue"

        # Cleanup
        await cosmos_service.delete_document(test_doc_id, test_source_file)

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, cosmos_service):
        """Test getting a document that doesn't exist returns None."""
        result = await cosmos_service.get_document(
            "nonexistent_id_12345",
            "nonexistent/file.pdf"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_document(self, cosmos_service, test_doc_id, test_source_file):
        """Test deleting a document."""
        # Create document
        document = {
            "id": test_doc_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        await cosmos_service.save_document_result(document)

        # Delete
        deleted = await cosmos_service.delete_document(test_doc_id, test_source_file)
        assert deleted is True

        # Verify deleted
        result = await cosmos_service.get_document(test_doc_id, test_source_file)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self, cosmos_service):
        """Test deleting a document that doesn't exist returns False."""
        deleted = await cosmos_service.delete_document(
            "nonexistent_delete_12345",
            "nonexistent/delete.pdf"
        )
        assert deleted is False

    @pytest.mark.asyncio
    async def test_upsert_document(self, cosmos_service, test_doc_id, test_source_file):
        """Test upsert behavior - update existing document."""
        # Create initial document
        document = {
            "id": test_doc_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "fields": {"original": True},
        }
        await cosmos_service.save_document_result(document)

        # Update via upsert
        document["status"] = "completed"
        document["fields"]["updated"] = True
        await cosmos_service.save_document_result(document)

        # Verify update
        retrieved = await cosmos_service.get_document(test_doc_id, test_source_file)
        assert retrieved["status"] == "completed"
        assert retrieved["fields"]["original"] is True
        assert retrieved["fields"]["updated"] is True

        # Cleanup
        await cosmos_service.delete_document(test_doc_id, test_source_file)


class TestQueryOperations:
    """Tests for document query operations."""

    @pytest.mark.asyncio
    async def test_query_documents(self, cosmos_service, test_source_file):
        """Test querying documents with SQL."""
        test_id = f"query_test_{uuid4().hex[:8]}"

        # Create test document
        document = {
            "id": test_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        await cosmos_service.save_document_result(document)

        # Query with partition key
        results = await cosmos_service.query_documents(
            query="SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": test_id}],
            partition_key=test_source_file,
        )

        assert len(results) == 1
        assert results[0]["id"] == test_id

        # Cleanup
        await cosmos_service.delete_document(test_id, test_source_file)

    @pytest.mark.asyncio
    async def test_query_by_source_file(self, cosmos_service):
        """Test query_by_source_file for all forms from a PDF."""
        test_source = f"multi-form-test/{uuid4().hex[:8]}.pdf"
        form_ids = []

        # Create multiple form documents from same source
        for i in range(3):
            doc_id = f"form_{i}_{uuid4().hex[:8]}"
            form_ids.append(doc_id)
            document = {
                "id": doc_id,
                "sourceFile": test_source,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "formNumber": i + 1,
                "status": "completed",
            }
            await cosmos_service.save_document_result(document)

        # Query all documents for source file
        results = await cosmos_service.query_by_source_file(test_source)

        assert len(results) == 3
        form_numbers = [r["formNumber"] for r in results]
        assert sorted(form_numbers) == [1, 2, 3]

        # Cleanup
        for doc_id in form_ids:
            await cosmos_service.delete_document(doc_id, test_source)

    @pytest.mark.asyncio
    async def test_get_document_status(self, cosmos_service):
        """Test getting document status."""
        test_source = f"status-test/{uuid4().hex[:8]}.pdf"
        doc_id = test_source.replace("/", "_").replace(".", "_")

        # Create document
        document = {
            "id": doc_id,
            "sourceFile": test_source,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "processing",
        }
        await cosmos_service.save_document_result(document)

        # Get status
        status = await cosmos_service.get_document_status(test_source)
        assert status == "processing"

        # Update status
        document["status"] = "completed"
        await cosmos_service.save_document_result(document)

        status = await cosmos_service.get_document_status(test_source)
        assert status == "completed"

        # Cleanup
        await cosmos_service.delete_document(doc_id, test_source)

    @pytest.mark.asyncio
    async def test_get_document_status_nonexistent(self, cosmos_service):
        """Test getting status for nonexistent document returns None."""
        status = await cosmos_service.get_document_status("nonexistent/status.pdf")
        assert status is None


class TestMultiTenantOperations:
    """Tests for multi-tenant document operations."""

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, cosmos_service):
        """Test querying documents by tenant ID."""
        tenant_id = f"tenant_{uuid4().hex[:8]}"
        doc_ids = []

        # Create documents for tenant
        for i in range(2):
            source_file = f"tenant-test/{tenant_id}_{i}.pdf"
            doc_id = source_file.replace("/", "_").replace(".", "_")
            doc_ids.append((doc_id, source_file))

            document = {
                "id": doc_id,
                "sourceFile": source_file,
                "tenantId": tenant_id,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            }
            await cosmos_service.save_document_result(document)

        # Query by tenant
        results = await cosmos_service.query_by_tenant(tenant_id)

        assert len(results) >= 2
        for r in results:
            assert r["tenantId"] == tenant_id

        # Cleanup
        for doc_id, source_file in doc_ids:
            await cosmos_service.delete_document(doc_id, source_file)

    @pytest.mark.asyncio
    async def test_query_by_tenant_with_status_filter(self, cosmos_service):
        """Test querying tenant documents filtered by status."""
        tenant_id = f"tenant_status_{uuid4().hex[:8]}"
        doc_ids = []

        # Create documents with different statuses
        statuses = ["completed", "completed", "failed"]
        for i, status in enumerate(statuses):
            source_file = f"tenant-status/{tenant_id}_{i}.pdf"
            doc_id = source_file.replace("/", "_").replace(".", "_")
            doc_ids.append((doc_id, source_file))

            document = {
                "id": doc_id,
                "sourceFile": source_file,
                "tenantId": tenant_id,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "status": status,
            }
            await cosmos_service.save_document_result(document)

        # Query by tenant with status filter
        results = await cosmos_service.query_by_tenant(tenant_id, status="completed")

        completed_count = sum(1 for r in results if r["tenantId"] == tenant_id)
        assert completed_count >= 2

        # Cleanup
        for doc_id, source_file in doc_ids:
            await cosmos_service.delete_document(doc_id, source_file)


class TestRetryOperations:
    """Tests for retry count tracking."""

    @pytest.mark.asyncio
    async def test_increment_retry_count(self, cosmos_service, test_doc_id, test_source_file):
        """Test incrementing retry count."""
        # Create document
        document = {
            "id": test_doc_id,
            "sourceFile": test_source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "retryCount": 0,
        }
        await cosmos_service.save_document_result(document)

        # Increment retry
        new_count = await cosmos_service.increment_retry_count(test_doc_id, test_source_file)
        assert new_count == 1

        # Verify document updated
        retrieved = await cosmos_service.get_document(test_doc_id, test_source_file)
        assert retrieved["retryCount"] == 1
        assert retrieved["status"] == "pending"  # Reset for retry

        # Increment again
        new_count = await cosmos_service.increment_retry_count(test_doc_id, test_source_file)
        assert new_count == 2

        # Cleanup
        await cosmos_service.delete_document(test_doc_id, test_source_file)

    @pytest.mark.asyncio
    async def test_increment_retry_count_nonexistent(self, cosmos_service):
        """Test incrementing retry count for nonexistent document raises error."""
        from services.cosmos_service import CosmosError

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_service.increment_retry_count(
                "nonexistent_retry_12345",
                "nonexistent/retry.pdf"
            )

        assert "not found" in str(exc_info.value)


class TestDeleteOperations:
    """Tests for bulk delete operations."""

    @pytest.mark.asyncio
    async def test_delete_by_source_file(self, cosmos_service):
        """Test deleting all documents for a source file."""
        test_source = f"bulk-delete-test/{uuid4().hex[:8]}.pdf"

        # Create multiple form documents
        for i in range(3):
            doc_id = f"delete_form_{i}_{uuid4().hex[:8]}"
            document = {
                "id": doc_id,
                "sourceFile": test_source,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "formNumber": i + 1,
            }
            await cosmos_service.save_document_result(document)

        # Delete all
        deleted_count = await cosmos_service.delete_by_source_file(test_source)
        assert deleted_count == 3

        # Verify deleted
        results = await cosmos_service.query_by_source_file(test_source)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_delete_by_source_file_empty(self, cosmos_service):
        """Test delete_by_source_file with no matching documents."""
        deleted_count = await cosmos_service.delete_by_source_file(
            f"nonexistent/{uuid4().hex}.pdf"
        )
        assert deleted_count == 0


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_save_document_missing_id(self, cosmos_service):
        """Test saving document without ID raises error."""
        from services.cosmos_service import CosmosError

        document = {
            "sourceFile": "test/file.pdf",
            "status": "completed",
        }

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_service.save_document_result(document)

        assert "id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_document_missing_partition_key(self, cosmos_service):
        """Test saving document without sourceFile raises error."""
        from services.cosmos_service import CosmosError

        document = {
            "id": "test_id",
            "status": "completed",
        }

        with pytest.raises(CosmosError) as exc_info:
            await cosmos_service.save_document_result(document)

        assert "sourcefile" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_document_converts_numeric_id(self, cosmos_service):
        """Test that numeric IDs are converted to strings."""
        test_source = f"numeric-id-test/{uuid4().hex[:8]}.pdf"

        document = {
            "id": 12345,  # Numeric ID
            "sourceFile": test_source,
            "status": "completed",
        }

        saved = await cosmos_service.save_document_result(document)
        assert saved["id"] == "12345"  # Should be string
        assert isinstance(saved["id"], str)

        # Cleanup
        await cosmos_service.delete_document("12345", test_source)
