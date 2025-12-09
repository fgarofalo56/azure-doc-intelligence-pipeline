"""Integration tests for end-to-end document processing.

These tests require deployed Azure resources and should only be run
when RUN_INTEGRATION_TESTS environment variable is set.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


# Skip all tests if integration tests not enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
)


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
