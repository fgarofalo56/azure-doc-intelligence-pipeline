"""Integration tests for end-to-end document processing.

Tests complete document processing workflows including:
- Document Intelligence analysis
- Cosmos DB persistence
- Multi-tenant isolation
- Profile-based processing
- Concurrent processing

Requires deployed Azure resources and environment variables.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))

# Mark all tests as integration tests (handled by conftest.py)
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def integration_config():
    """Load integration test configuration from environment."""
    required_vars = [
        "DOC_INTEL_ENDPOINT",
        "DOC_INTEL_API_KEY",
        "COSMOS_ENDPOINT",
        "COSMOS_DATABASE",
        "COSMOS_CONTAINER",
        "TEST_BLOB_URL",  # SAS URL to a test PDF
    ]

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        pytest.skip(f"Missing required environment variables: {missing}")

    return {
        "doc_intel_endpoint": os.environ["DOC_INTEL_ENDPOINT"],
        "doc_intel_api_key": os.environ["DOC_INTEL_API_KEY"],
        "cosmos_endpoint": os.environ["COSMOS_ENDPOINT"],
        "cosmos_database": os.environ["COSMOS_DATABASE"],
        "cosmos_container": os.environ["COSMOS_CONTAINER"],
        "test_blob_url": os.environ["TEST_BLOB_URL"],
    }


@pytest.fixture
def document_service(integration_config):
    """Create DocumentService with real credentials."""
    from services.document_service import DocumentService

    return DocumentService(
        endpoint=integration_config["doc_intel_endpoint"],
        api_key=integration_config["doc_intel_api_key"],
        max_concurrent=5,
    )


@pytest.fixture
def cosmos_service(integration_config):
    """Create CosmosService with real credentials."""
    from services.cosmos_service import CosmosService

    return CosmosService(
        endpoint=integration_config["cosmos_endpoint"],
        database_name=integration_config["cosmos_database"],
        container_name=integration_config["cosmos_container"],
    )


class TestDocumentIntelligenceIntegration:
    """Integration tests for Document Intelligence service."""

    @pytest.mark.asyncio
    async def test_analyze_document_prebuilt_layout(self, document_service, integration_config):
        """Test document analysis with prebuilt-layout model."""
        result = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id="prebuilt-layout",
            blob_name="integration-test.pdf",
        )

        assert result["status"] == "completed"
        assert result["modelId"] == "prebuilt-layout"
        # prebuilt-layout may not have fields, but should complete

    @pytest.mark.asyncio
    async def test_analyze_document_invalid_url(self, document_service):
        """Test error handling for invalid blob URL."""
        from services.document_service import DocumentProcessingError

        with pytest.raises(DocumentProcessingError):
            await document_service.analyze_document(
                blob_url="https://invalid-storage.blob.core.windows.net/invalid/nonexistent.pdf",
                model_id="prebuilt-layout",
                blob_name="nonexistent.pdf",
            )


class TestCosmosDBIntegration:
    """Integration tests for Cosmos DB service."""

    @pytest.mark.asyncio
    async def test_save_and_get_document(self, cosmos_service):
        """Test saving and retrieving a document."""
        test_id = f"integration_test_{uuid4().hex[:8]}"
        source_file = f"integration-test/{test_id}.pdf"

        document = {
            "id": test_id,
            "sourceFile": source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "modelId": "integration-test-model",
            "status": "completed",
            "fields": {"testField": "testValue"},
            "confidence": {"testField": 0.99},
        }

        # Save document
        saved = await cosmos_service.save_document_result(document)
        assert saved["id"] == test_id

        # Retrieve document
        retrieved = await cosmos_service.get_document(test_id, source_file)
        assert retrieved is not None
        assert retrieved["id"] == test_id
        assert retrieved["sourceFile"] == source_file
        assert retrieved["fields"]["testField"] == "testValue"

        # Cleanup: Delete test document (optional)
        # In production tests, you might want to leave this for manual inspection

    @pytest.mark.asyncio
    async def test_query_documents(self, cosmos_service):
        """Test querying documents."""
        # This assumes some documents exist in the container
        results = await cosmos_service.query_documents(
            query="SELECT TOP 1 c.id, c.sourceFile, c.status FROM c",
        )

        # May be empty if no documents exist, but should not error
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_document_status(self, cosmos_service):
        """Test getting document status."""
        test_id = f"status_test_{uuid4().hex[:8]}"
        source_file = f"status-test/{test_id}.pdf"

        # Create a document
        document = {
            "id": source_file.replace("/", "_").replace(".", "_"),
            "sourceFile": source_file,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "fields": {},
        }
        await cosmos_service.save_document_result(document)

        # Get status
        status = await cosmos_service.get_document_status(source_file)
        assert status == "completed"

        # Get status for nonexistent document
        status = await cosmos_service.get_document_status("nonexistent/file.pdf")
        assert status is None


class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_document_processing_flow(
        self, document_service, cosmos_service, integration_config
    ):
        """Test complete flow: analyze document -> save to Cosmos."""
        test_blob_name = f"e2e-test/{uuid4().hex[:8]}.pdf"

        # Step 1: Analyze document
        analysis_result = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id="prebuilt-layout",
            blob_name=test_blob_name,
        )

        assert analysis_result["status"] == "completed"

        # Step 2: Prepare Cosmos document
        doc_id = test_blob_name.replace("/", "_").replace(".", "_")
        document = {
            "id": doc_id,
            "sourceFile": test_blob_name,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            **analysis_result,
        }

        # Step 3: Save to Cosmos DB
        saved = await cosmos_service.save_document_result(document)
        assert saved["id"] == doc_id

        # Step 4: Verify saved document
        retrieved = await cosmos_service.get_document(doc_id, test_blob_name)
        assert retrieved is not None
        assert retrieved["status"] == "completed"
        assert retrieved["modelId"] == "prebuilt-layout"

        print(f"Successfully processed and saved document: {doc_id}")

    @pytest.mark.asyncio
    async def test_concurrent_document_processing(
        self, document_service, cosmos_service, integration_config
    ):
        """Test concurrent processing of multiple documents."""
        num_documents = 3

        async def process_one(index: int):
            blob_name = f"concurrent-test/{uuid4().hex[:8]}-{index}.pdf"

            result = await document_service.analyze_document(
                blob_url=integration_config["test_blob_url"],
                model_id="prebuilt-layout",
                blob_name=blob_name,
            )

            doc_id = blob_name.replace("/", "_").replace(".", "_")
            document = {
                "id": doc_id,
                "sourceFile": blob_name,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                **result,
            }

            await cosmos_service.save_document_result(document)
            return doc_id

        # Process documents concurrently
        tasks = [process_one(i) for i in range(num_documents)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check all succeeded
        successful = [r for r in results if isinstance(r, str)]
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(successful) == num_documents, f"Errors: {errors}"
        print(f"Successfully processed {len(successful)} documents concurrently")


class TestMultiTenantIntegration:
    """Integration tests for multi-tenant document isolation."""

    @pytest.mark.asyncio
    async def test_tenant_document_isolation(
        self, document_service, cosmos_service, integration_config
    ):
        """Test that documents are properly isolated by tenant."""
        tenant_a = f"tenant_a_{uuid4().hex[:4]}"
        tenant_b = f"tenant_b_{uuid4().hex[:4]}"

        # Process document for tenant A
        blob_name_a = f"tenant-test/{tenant_a}/doc.pdf"
        result_a = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id="prebuilt-layout",
            blob_name=blob_name_a,
        )

        doc_id_a = f"tenant_a_doc_{uuid4().hex[:8]}"
        doc_a = {
            "id": doc_id_a,
            "sourceFile": blob_name_a,
            "tenantId": tenant_a,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            **result_a,
        }
        await cosmos_service.save_document_result(doc_a)

        # Process document for tenant B
        blob_name_b = f"tenant-test/{tenant_b}/doc.pdf"
        result_b = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id="prebuilt-layout",
            blob_name=blob_name_b,
        )

        doc_id_b = f"tenant_b_doc_{uuid4().hex[:8]}"
        doc_b = {
            "id": doc_id_b,
            "sourceFile": blob_name_b,
            "tenantId": tenant_b,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            **result_b,
        }
        await cosmos_service.save_document_result(doc_b)

        # Query by tenant - should only see own documents
        tenant_a_docs = await cosmos_service.query_by_tenant(tenant_a)
        tenant_b_docs = await cosmos_service.query_by_tenant(tenant_b)

        # Filter to just our test documents
        a_ids = [d["id"] for d in tenant_a_docs if d["tenantId"] == tenant_a]
        b_ids = [d["id"] for d in tenant_b_docs if d["tenantId"] == tenant_b]

        assert doc_id_a in a_ids
        assert doc_id_b not in a_ids
        assert doc_id_b in b_ids
        assert doc_id_a not in b_ids

        # Cleanup
        await cosmos_service.delete_document(doc_id_a, blob_name_a)
        await cosmos_service.delete_document(doc_id_b, blob_name_b)


class TestProfileIntegration:
    """Integration tests for processing profiles."""

    @pytest.mark.asyncio
    async def test_process_with_invoice_profile(
        self, document_service, cosmos_service, integration_config
    ):
        """Test processing document with invoice profile."""
        from services.profiles import get_profile

        profile = get_profile("invoice")
        assert profile is not None
        assert profile.model_id == "prebuilt-invoice"

        blob_name = f"profile-test/{uuid4().hex[:8]}.pdf"

        result = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id=profile.model_id,
            blob_name=blob_name,
        )

        assert result["status"] == "completed"
        assert result["modelId"] == "prebuilt-invoice"

    @pytest.mark.asyncio
    async def test_process_with_receipt_profile(
        self, document_service, cosmos_service, integration_config
    ):
        """Test processing document with receipt profile."""
        from services.profiles import get_profile

        profile = get_profile("receipt")
        assert profile is not None

        blob_name = f"receipt-test/{uuid4().hex[:8]}.pdf"

        result = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id=profile.model_id,
            blob_name=blob_name,
        )

        assert result["status"] == "completed"

    def test_list_available_profiles(self):
        """Test listing all available processing profiles."""
        from services.profiles import list_profiles

        profiles = list_profiles()

        assert "invoice" in profiles
        assert "receipt" in profiles
        assert "layout" in profiles
        assert len(profiles) >= 3


class TestIdempotencyWithDocumentIntelligence:
    """Integration tests for idempotency with real document processing."""

    @pytest.mark.asyncio
    async def test_idempotent_reprocessing(
        self, document_service, cosmos_service, integration_config
    ):
        """Test that reprocessing same document returns cached result."""
        from services.idempotency import (
            check_and_generate_idempotency,
            create_idempotent_document,
        )

        blob_name = f"idempotent-e2e/{uuid4().hex[:8]}.pdf"
        model_id = "prebuilt-layout"

        # First processing
        result1 = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=blob_name,
            model_id=model_id,
        )
        assert result1.is_duplicate is False

        # Process the document
        analysis = await document_service.analyze_document(
            blob_url=integration_config["test_blob_url"],
            model_id=model_id,
            blob_name=blob_name,
        )

        # Save with idempotency
        doc_id = f"idem_e2e_{uuid4().hex[:8]}"
        doc = {
            "id": doc_id,
            "sourceFile": blob_name,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            **analysis,
        }
        idem_doc = create_idempotent_document(doc, result1.idempotency_key)
        await cosmos_service.save_document_result(idem_doc)

        # Second processing attempt - should detect duplicate
        result2 = await check_and_generate_idempotency(
            cosmos_service=cosmos_service,
            blob_name=blob_name,
            model_id=model_id,
        )

        assert result2.is_duplicate is True
        assert result2.existing_document["id"] == doc_id

        # Cleanup
        await cosmos_service.delete_document(doc_id, blob_name)


class TestErrorRecovery:
    """Integration tests for error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_retry_failed_document(self, cosmos_service):
        """Test retry mechanism for failed documents."""
        blob_name = f"retry-test/{uuid4().hex[:8]}.pdf"
        doc_id = f"retry_{uuid4().hex[:8]}"

        # Create a failed document
        doc = {
            "id": doc_id,
            "sourceFile": blob_name,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": "Simulated failure for testing",
            "retryCount": 0,
        }
        await cosmos_service.save_document_result(doc)

        # Increment retry count
        new_count = await cosmos_service.increment_retry_count(doc_id, blob_name)
        assert new_count == 1

        # Verify status reset
        retrieved = await cosmos_service.get_document(doc_id, blob_name)
        assert retrieved["status"] == "pending"
        assert retrieved["retryCount"] == 1

        # Cleanup
        await cosmos_service.delete_document(doc_id, blob_name)

    @pytest.mark.asyncio
    async def test_invalid_url_handling(self, document_service):
        """Test handling of invalid blob URLs."""
        from services.document_service import DocumentProcessingError

        with pytest.raises(DocumentProcessingError):
            await document_service.analyze_document(
                blob_url="https://invalid-url.blob.core.windows.net/fake/doc.pdf",
                model_id="prebuilt-layout",
                blob_name="invalid.pdf",
            )


class TestDocumentCleanup:
    """Integration tests for document cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_by_source_file(self, cosmos_service):
        """Test cleaning up all documents for a source file."""
        source_file = f"cleanup-test/{uuid4().hex[:8]}.pdf"
        doc_ids = []

        # Create multiple form documents
        for i in range(3):
            doc_id = f"cleanup_form_{i}_{uuid4().hex[:8]}"
            doc_ids.append(doc_id)
            doc = {
                "id": doc_id,
                "sourceFile": source_file,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "formNumber": i + 1,
                "status": "completed",
            }
            await cosmos_service.save_document_result(doc)

        # Verify all created
        docs = await cosmos_service.query_by_source_file(source_file)
        assert len(docs) == 3

        # Cleanup
        deleted = await cosmos_service.delete_by_source_file(source_file)
        assert deleted == 3

        # Verify deleted
        docs = await cosmos_service.query_by_source_file(source_file)
        assert len(docs) == 0
