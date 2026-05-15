"""Shared test fixtures and factories for FormExtraction tests.

This module provides reusable mock factories and test data generators
for consistent testing across the codebase. Import fixtures from here
to avoid duplication and ensure consistent test patterns.

Usage:
    from tests.fixtures import (
        create_mock_cosmos_service,
        create_mock_blob_service,
        create_sample_document,
        create_sample_processing_job,
    )
"""

from .mock_services import (
    MockBlobService,
    MockCosmosService,
    MockDocumentService,
    create_mock_blob_service,
    create_mock_cosmos_service,
    create_mock_document_service,
    create_mock_http_request,
    create_mock_queue_client,
)
from .test_data import (
    SAMPLE_BLOB_URL,
    SAMPLE_CONNECTION_STRING,
    SAMPLE_COSMOS_ENDPOINT,
    SAMPLE_DOC_INTEL_ENDPOINT,
    SAMPLE_MODEL_ID,
    create_dead_letter_item,
    create_document_intel_response,
    create_processing_job,
    create_sample_config,
    create_sample_document,
    create_sample_form_result,
    create_webhook_payload,
)

__all__ = [
    # Mock services
    "MockBlobService",
    "MockCosmosService",
    "MockDocumentService",
    "create_mock_blob_service",
    "create_mock_cosmos_service",
    "create_mock_document_service",
    "create_mock_http_request",
    "create_mock_queue_client",
    # Test data factories
    "create_sample_document",
    "create_processing_job",
    "create_sample_config",
    "create_sample_form_result",
    "create_document_intel_response",
    "create_webhook_payload",
    "create_dead_letter_item",
    # Constants
    "SAMPLE_BLOB_URL",
    "SAMPLE_CONNECTION_STRING",
    "SAMPLE_COSMOS_ENDPOINT",
    "SAMPLE_DOC_INTEL_ENDPOINT",
    "SAMPLE_MODEL_ID",
]
