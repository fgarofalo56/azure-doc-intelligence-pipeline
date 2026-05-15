# Test Fixtures

This directory contains reusable test fixtures and factory functions for the FormExtraction test suite.

## Overview

The fixtures module provides:
- **Mock service classes** - Configurable mocks for Azure services
- **Test data factories** - Functions to generate test documents, jobs, and API responses
- **Constants** - Sample URLs, connection strings, and other test constants

## Installation

The fixtures are automatically available when running tests. Import what you need:

```python
from tests.fixtures import (
    create_mock_cosmos_service,
    create_sample_document,
    create_processing_job,
)
```

## Mock Services

### MockCosmosService

A configurable mock for Cosmos DB operations:

```python
from tests.fixtures import create_mock_cosmos_service

# Basic usage
mock_cosmos = create_mock_cosmos_service()

# With custom return values
mock_cosmos = create_mock_cosmos_service(
    get_return_value={"id": "doc1", "status": "completed"},
    query_return_value=[{"id": "doc1"}, {"id": "doc2"}],
)

# Simulate failures
mock_cosmos = create_mock_cosmos_service(
    save_should_fail=True,
    save_failure_message="Connection timeout",
)

# Check saved documents
await mock_cosmos.save_document_result({"id": "test"})
assert len(mock_cosmos.saved_documents) == 1
```

### MockBlobService

A configurable mock for Azure Blob Storage:

```python
from tests.fixtures import create_mock_blob_service

# Basic usage
mock_blob = create_mock_blob_service()

# With pre-loaded blobs
mock_blob = create_mock_blob_service(
    get_return_value=b"PDF content here",
    list_return_value=["file1.pdf", "file2.pdf"],
)

# Upload and verify
mock_blob.upload_blob("container", "test.pdf", b"content")
assert "container/test.pdf" in mock_blob.stored_blobs
```

### MockDocumentService

A configurable mock for Document Intelligence:

```python
from tests.fixtures import create_mock_document_service

# Basic usage (returns default successful response)
mock_doc = create_mock_document_service()

# With custom response
mock_doc = create_mock_document_service(
    analyze_return_value={
        "status": "succeeded",
        "analyzeResult": {"documents": [...]},
    },
)

# Simulate failures
mock_doc = create_mock_document_service(
    analyze_should_fail=True,
    analyze_failure_message="Rate limit exceeded",
)

# Track call count
await mock_doc.analyze_document("url", "model")
assert mock_doc.call_count == 1
```

### HTTP Request Mock

Create mock Azure Functions HTTP requests:

```python
from tests.fixtures import create_mock_http_request

# POST request with JSON body
req = create_mock_http_request(
    method="POST",
    body={"blobUrl": "https://...", "modelId": "custom-model"},
)

# GET request with query params
req = create_mock_http_request(
    method="GET",
    params={"status": "completed"},
    route_params={"jobId": "job_123"},
)

# Access mock data
assert req.get_json() == {"blobUrl": "..."}
assert req.route_params["jobId"] == "job_123"
```

## Test Data Factories

### Documents

```python
from tests.fixtures import create_sample_document, create_sample_form_result

# Basic document
doc = create_sample_document()

# Custom document
doc = create_sample_document(
    doc_id="custom_id",
    source_file="custom/path.pdf",
    status="failed",
    error="Processing timeout",
)

# Multi-form result
result = create_sample_form_result(
    form_number=2,
    total_forms=5,
    page_range="3-4",
)
```

### Processing Jobs

```python
from tests.fixtures import create_processing_job

# Pending job
job = create_processing_job()

# Completed job
job = create_processing_job(
    status="completed",
    result={"formsProcessed": 3},
)

# Failed job
job = create_processing_job(
    status="failed",
    error="Rate limit exceeded",
)
```

### API Responses

```python
from tests.fixtures import create_document_intel_response

# Successful response
response = create_document_intel_response()

# Custom fields
response = create_document_intel_response(
    doc_type="receipt",
    fields={
        "total": {"content": "$25.00", "confidence": 0.95},
    },
    pages=1,
)

# Failed response
response = create_document_intel_response(
    status="failed",
    error={"code": "InvalidDocument"},
)
```

## Constants

Common test constants are available:

```python
from tests.fixtures import (
    SAMPLE_BLOB_URL,
    SAMPLE_CONNECTION_STRING,
    SAMPLE_COSMOS_ENDPOINT,
    SAMPLE_DOC_INTEL_ENDPOINT,
    SAMPLE_MODEL_ID,
)
```

## Best Practices

1. **Use factories for test data** - Avoid hardcoding test data in tests
2. **Customize with kwargs** - All factories accept `**kwargs` for overrides
3. **Check mock state** - Use `saved_documents`, `stored_blobs`, `call_count` to verify behavior
4. **Reset between tests** - Create new mocks for each test to avoid state leakage

## Example Test

```python
import pytest
from tests.fixtures import (
    create_mock_cosmos_service,
    create_sample_document,
    create_mock_http_request,
)


class TestDocumentProcessing:
    @pytest.fixture
    def mock_cosmos(self):
        return create_mock_cosmos_service()

    @pytest.mark.asyncio
    async def test_save_document(self, mock_cosmos):
        doc = create_sample_document(status="completed")

        result = await mock_cosmos.save_document_result(doc)

        assert len(mock_cosmos.saved_documents) == 1
        assert mock_cosmos.saved_documents[0]["status"] == "completed"

    def test_http_request_parsing(self):
        req = create_mock_http_request(
            body={"blobUrl": "https://test.blob.core.windows.net/docs/test.pdf"},
        )

        body = req.get_json()
        assert "blobUrl" in body
```
