# Azure Functions Python v2 Programming Model - Implementation Patterns

> Research compiled: 2025-12-02
> Focus: HTTP triggers, async patterns, dependency injection, testing for Document Intelligence + Cosmos DB integration

---

## 1. HTTP Trigger Patterns

### Basic HTTP Trigger with Full Imports

```python
import azure.functions as func
import logging
import os
from typing import Any

app = func.FunctionApp()

@app.function_name(name="ProcessDocument")
@app.route(route="process", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def process_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing document request')

    # Get parameters from query string or body
    blob_url = req.params.get('blobUrl')
    if not blob_url:
        try:
            req_body = req.get_json()
            blob_url = req_body.get('blobUrl')
        except ValueError:
            return func.HttpResponse(
                "Invalid request body",
                status_code=400
            )

    if not blob_url:
        return func.HttpResponse(
            "Missing 'blobUrl' parameter",
            status_code=400
        )

    # Process document
    result = {"status": "success", "blobUrl": blob_url}

    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json",
        status_code=200
    )
```

### Async HTTP Trigger (Recommended for I/O-bound operations)

```python
import azure.functions as func
import logging
import asyncio
import json
from typing import Any

app = func.FunctionApp()

@app.function_name(name="ProcessDocumentAsync")
@app.route(route="process-async", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def process_document_async(req: func.HttpRequest) -> func.HttpResponse:
    """Async HTTP trigger for processing PDFs with Document Intelligence."""
    logging.info('Async processing request received')

    try:
        req_body = req.get_json()
        blob_url = req_body.get('blobUrl')
        model_id = req_body.get('modelId', 'prebuilt-layout')

        if not blob_url:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'blobUrl' in request body"}),
                mimetype="application/json",
                status_code=400
            )

        # Simulate async I/O operations (replace with actual async calls)
        await asyncio.sleep(0.1)  # Example async operation

        # Call Document Intelligence (async)
        # result = await analyze_document_async(blob_url, model_id)

        result = {
            "status": "completed",
            "blobUrl": blob_url,
            "modelId": model_id
        }

        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )

    except ValueError as ve:
        logging.error(f"Invalid JSON: {ve}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            mimetype="application/json",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Processing failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )
```

---

## 2. Project Structure (V2 with Blueprints)

```
<project_root>/
├── .venv/                          # Virtual environment
├── .vscode/                        # VS Code settings
├── src/
│   └── functions/
│       ├── function_app.py         # Main entry point (registers blueprints)
│       ├── document_processing.py  # Blueprint for doc processing functions
│       ├── health_check.py         # Blueprint for health/status endpoints
│       ├── config.py               # Configuration class
│       ├── services/               # Business logic
│       │   ├── __init__.py
│       │   ├── document_service.py
│       │   └── cosmos_service.py
│       ├── models/                 # Data models
│       │   ├── __init__.py
│       │   └── document_result.py
│       ├── requirements.txt        # Python dependencies
│       ├── host.json              # Function host config
│       ├── local.settings.json    # Local env vars (gitignored)
│       └── local.settings.template.json  # Template for local settings
├── tests/
│   ├── unit/
│   │   ├── test_document_processing.py
│   │   └── test_cosmos_service.py
│   ├── integration/
│   │   └── test_end_to_end.py
│   └── fixtures/
│       └── sample_request.json
├── .funcignore
└── .gitignore
```

### Using Blueprints for Modular Code

**document_processing.py** (Blueprint):
```python
import azure.functions as func
import logging

bp = func.Blueprint()

@bp.function_name(name="ProcessDocument")
@bp.route(route="process", methods=["POST"])
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing document via blueprint')
    # Implementation here
    return func.HttpResponse("Processed", status_code=200)

@bp.function_name(name="GetDocumentStatus")
@bp.route(route="status/{doc_id}", methods=["GET"])
async def get_status(req: func.HttpRequest) -> func.HttpResponse:
    doc_id = req.route_params.get('doc_id')
    return func.HttpResponse(f"Status for {doc_id}", status_code=200)
```

**function_app.py** (Main entry point):
```python
import azure.functions as func
from document_processing import bp as document_bp
from health_check import bp as health_bp

app = func.FunctionApp()

# Register blueprints
app.register_functions(document_bp)
app.register_functions(health_bp)
```

---

## 3. Dependency Injection & Configuration

### Configuration Class Pattern

**config.py**:
```python
import os
from typing import Optional

class Config:
    """Configuration loaded from environment variables."""

    # Required settings (will raise if not set)
    DOC_INTEL_ENDPOINT: str = os.environ["DOC_INTEL_ENDPOINT"]
    COSMOS_ENDPOINT: str = os.environ["COSMOS_ENDPOINT"]
    COSMOS_DATABASE: str = os.environ["COSMOS_DATABASE"]
    COSMOS_CONTAINER: str = os.environ["COSMOS_CONTAINER"]

    # Optional settings with defaults
    KEY_VAULT_NAME: Optional[str] = os.getenv("KEY_VAULT_NAME")
    FUNCTION_TIMEOUT: int = int(os.getenv("FUNCTION_TIMEOUT", "230"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def from_environment(cls) -> "Config":
        """Factory method to create config and validate required vars."""
        required = ["DOC_INTEL_ENDPOINT", "COSMOS_ENDPOINT",
                    "COSMOS_DATABASE", "COSMOS_CONTAINER"]
        missing = [var for var in required if not os.getenv(var)]

        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

        return cls()
```

### Key Vault Integration with Managed Identity

**Key Vault References in App Settings** (Preferred for static secrets):
```json
{
  "Values": {
    "CosmosConnectionString": "@Microsoft.KeyVault(SecretUri=https://myvault.vault.azure.net/secrets/CosmosConnection/)",
    "DocIntelApiKey": "@Microsoft.KeyVault(SecretUri=https://myvault.vault.azure.net/secrets/DocIntelKey/)"
  }
}
```

**Dynamic Key Vault Access** (for runtime secret retrieval):
```python
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class KeyVaultService:
    def __init__(self):
        key_vault_name = os.environ["KEY_VAULT_NAME"]
        kv_uri = f"https://{key_vault_name}.vault.azure.net"

        # Uses Managed Identity in Azure, local credentials locally
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=kv_uri, credential=credential)

    def get_secret(self, secret_name: str) -> str:
        """Retrieve a secret from Key Vault."""
        secret = self.client.get_secret(secret_name)
        return secret.value
```

### Pseudo-Dependency Injection Pattern

While Python doesn't have built-in DI like .NET, you can use this pattern:

```python
# services/__init__.py
from typing import Optional
from .document_service import DocumentService
from .cosmos_service import CosmosService

# Global service instances (initialized once)
_document_service: Optional[DocumentService] = None
_cosmos_service: Optional[CosmosService] = None

def get_document_service() -> DocumentService:
    """Get or create DocumentService singleton."""
    global _document_service
    if _document_service is None:
        from config import Config
        config = Config.from_environment()
        _document_service = DocumentService(config)
    return _document_service

def get_cosmos_service() -> CosmosService:
    """Get or create CosmosService singleton."""
    global _cosmos_service
    if _cosmos_service is None:
        from config import Config
        config = Config.from_environment()
        _cosmos_service = CosmosService(config)
    return _cosmos_service
```

**Usage in function**:
```python
from services import get_document_service, get_cosmos_service

@app.route(route="process")
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    doc_service = get_document_service()
    cosmos_service = get_cosmos_service()

    result = await doc_service.analyze_document(blob_url)
    await cosmos_service.save_result(result)

    return func.HttpResponse("Success", status_code=200)
```

---

## 4. Azure Document Intelligence Integration

### Async Document Intelligence Pattern

```python
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity.aio import DefaultAzureCredential
import logging
from typing import Dict, Any

class DocumentService:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.credential = DefaultAzureCredential()
        # Client created per request (recommended for async)

    async def analyze_document(
        self,
        blob_url: str,
        model_id: str = "prebuilt-layout"
    ) -> Dict[str, Any]:
        """
        Analyze a document using Document Intelligence.

        Args:
            blob_url: SAS URL to the blob
            model_id: Document Intelligence model ID

        Returns:
            Extracted document data
        """
        async with DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=self.credential
        ) as client:

            # Start analysis (long-running operation)
            poller = await client.begin_analyze_document(
                model_id=model_id,
                analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
            )

            # Wait for completion (can take 30+ seconds for large PDFs)
            result = await poller.result()

            # Extract fields
            fields = {}
            if result.documents:
                for doc in result.documents:
                    for field_name, field_value in doc.fields.items():
                        fields[field_name] = {
                            "value": field_value.value,
                            "confidence": field_value.confidence
                        }

            return {
                "status": "completed",
                "modelId": model_id,
                "fields": fields,
                "modelConfidence": result.confidence if hasattr(result, 'confidence') else None
            }
```

### Critical Gotchas

1. **Rate Limiting**: Document Intelligence has 15 TPS default limit
   - Implement exponential backoff
   - Use Durable Functions for high-volume processing

2. **Timeout Handling**: Long-running document analysis
   - HTTP trigger max: 230 seconds (Azure Load Balancer limit)
   - For longer processing: Use async request-reply pattern or Durable Functions

3. **Async Dependencies**: Install `aiohttp` for async SDK
   ```bash
   pip install azure-ai-documentintelligence[aio] aiohttp
   ```

---

## 5. Cosmos DB Async Integration

### Async Cosmos Client Pattern

```python
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey
from azure.identity.aio import DefaultAzureCredential
import logging
from typing import Dict, Any

class CosmosService:
    def __init__(self, endpoint: str, database_name: str, container_name: str):
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = container_name
        self.credential = DefaultAzureCredential()

    async def save_document_result(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save document processing result to Cosmos DB.

        Args:
            document: Document data with 'id' and 'sourceFile' (partition key)

        Returns:
            Created document
        """
        async with CosmosClient(
            url=self.endpoint,
            credential=self.credential
        ) as client:

            database = client.get_database_client(self.database_name)
            container = database.get_container_client(self.container_name)

            # Upsert document (insert or update)
            result = await container.upsert_item(body=document)

            logging.info(f"Saved document {document['id']} to Cosmos DB")
            return result

    async def get_document(self, doc_id: str, partition_key: str) -> Dict[str, Any]:
        """Retrieve document by ID and partition key."""
        async with CosmosClient(
            url=self.endpoint,
            credential=self.credential
        ) as client:

            database = client.get_database_client(self.database_name)
            container = database.get_container_client(self.container_name)

            # Read item (requires partition key)
            item = await container.read_item(
                item=doc_id,
                partition_key=partition_key
            )

            return item
```

### Best Practices for Cosmos DB

1. **Always use context manager** (`async with`) for client lifecycle
2. **Partition key is required** for all operations
3. **Avoid cross-partition queries** (expensive)
4. **Boolean values**: Use lowercase `"true"/"false"` (not Python's `True/False`)
5. **Page size**: Increase from default 100 for large result sets
6. **Retry logic**: SDK handles transient errors automatically

---

## 6. Error Handling Patterns

### Structured Error Responses

```python
import json
import logging
from typing import Dict, Any
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError

class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""
    def __init__(self, blob_name: str, reason: str):
        self.blob_name = blob_name
        self.reason = reason
        super().__init__(f"Failed to process {blob_name}: {reason}")

def create_error_response(
    error_message: str,
    status_code: int = 500,
    additional_data: Dict[str, Any] = None
) -> func.HttpResponse:
    """Create a standardized error response."""
    error_body = {
        "error": error_message,
        "status": "failed"
    }

    if additional_data:
        error_body.update(additional_data)

    return func.HttpResponse(
        json.dumps(error_body),
        mimetype="application/json",
        status_code=status_code
    )

@app.route(route="process")
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger with comprehensive error handling."""
    try:
        # Parse request
        req_body = req.get_json()
        blob_url = req_body.get('blobUrl')

        if not blob_url:
            return create_error_response(
                "Missing 'blobUrl' parameter",
                status_code=400
            )

        # Process document
        doc_service = get_document_service()
        result = await doc_service.analyze_document(blob_url)

        # Save to Cosmos
        cosmos_service = get_cosmos_service()
        await cosmos_service.save_document_result(result)

        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )

    except ValueError as ve:
        logging.error(f"Invalid request: {ve}")
        return create_error_response(
            "Invalid request body",
            status_code=400,
            additional_data={"details": str(ve)}
        )

    except ResourceNotFoundError as rnf:
        logging.error(f"Resource not found: {rnf}")
        return create_error_response(
            "Document or resource not found",
            status_code=404
        )

    except ServiceRequestError as sre:
        logging.error(f"Service error: {sre}")
        return create_error_response(
            "External service error",
            status_code=502,
            additional_data={"service": "Document Intelligence"}
        )

    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        return create_error_response(
            "Internal server error",
            status_code=500
        )
```

---

## 7. Testing Patterns with Pytest

### Project Structure for Tests

```
tests/
├── unit/
│   ├── __init__.py
│   ├── test_document_service.py
│   ├── test_cosmos_service.py
│   └── test_http_triggers.py
├── integration/
│   └── test_end_to_end.py
└── fixtures/
    ├── sample_request.json
    └── sample_document.pdf
```

### Unit Testing HTTP Triggers (v2 Model)

```python
# tests/unit/test_http_triggers.py
import pytest
import azure.functions as func
import json
from unittest.mock import patch, AsyncMock
from function_app import app

@pytest.fixture
def mock_document_service():
    """Mock DocumentService for testing."""
    with patch('services.get_document_service') as mock:
        service = AsyncMock()
        service.analyze_document.return_value = {
            "status": "completed",
            "fields": {"vendorName": {"value": "Acme Corp", "confidence": 0.95}}
        }
        mock.return_value = service
        yield service

@pytest.fixture
def mock_cosmos_service():
    """Mock CosmosService for testing."""
    with patch('services.get_cosmos_service') as mock:
        service = AsyncMock()
        service.save_document_result.return_value = {"id": "test_doc"}
        mock.return_value = service
        yield service

def test_process_document_success(mock_document_service, mock_cosmos_service):
    """Test successful document processing."""
    # Create mock HTTP request
    req = func.HttpRequest(
        method='POST',
        body=json.dumps({"blobUrl": "https://example.com/doc.pdf"}).encode('utf-8'),
        url='/api/process',
        headers={'Content-Type': 'application/json'}
    )

    # Get the function from the v2 app
    func_obj = app.get_functions()[0]  # Get first registered function
    response = func_obj(req)

    # Assertions
    assert response.status_code == 200
    assert "completed" in response.get_body().decode('utf-8')
    mock_document_service.analyze_document.assert_called_once()
    mock_cosmos_service.save_document_result.assert_called_once()

def test_process_document_missing_blob_url():
    """Test error handling for missing blobUrl."""
    req = func.HttpRequest(
        method='POST',
        body=json.dumps({}).encode('utf-8'),
        url='/api/process',
        headers={'Content-Type': 'application/json'}
    )

    func_obj = app.get_functions()[0]
    response = func_obj(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode('utf-8'))
    assert "error" in body

def test_process_document_invalid_json():
    """Test error handling for invalid JSON."""
    req = func.HttpRequest(
        method='POST',
        body=b'invalid json',
        url='/api/process',
        headers={'Content-Type': 'application/json'}
    )

    func_obj = app.get_functions()[0]
    response = func_obj(req)

    assert response.status_code == 400
```

### Testing with Blueprints (Alternative Pattern)

```python
# tests/unit/test_document_processing.py
import pytest
import azure.functions as func
from document_processing import bp

def test_process_document_blueprint():
    """Test blueprint function directly using .build().get_user_function()."""
    req = func.HttpRequest(
        method='POST',
        body=json.dumps({"blobUrl": "https://example.com/doc.pdf"}).encode('utf-8'),
        url='/api/process'
    )

    # Access the underlying function from blueprint
    process_func = bp.get_functions()[0].get_user_function()
    response = process_func(req)

    assert response.status_code == 200
```

### Async Testing Pattern

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_document_service_async():
    """Test async DocumentService methods."""
    from services.document_service import DocumentService

    service = DocumentService(endpoint="https://test.cognitiveservices.azure.com")

    # Mock the async client
    with patch.object(service, 'analyze_document', new_callable=AsyncMock) as mock:
        mock.return_value = {"status": "completed"}

        result = await service.analyze_document("https://example.com/doc.pdf")

        assert result["status"] == "completed"
        mock.assert_awaited_once()
```

### Integration Testing (with Real Azure Resources)

```python
# tests/integration/test_end_to_end.py
import pytest
import os
import asyncio

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_document_processing_pipeline():
    """
    Full integration test with real Azure services.
    Requires:
    - Azure resources deployed
    - Environment variables set
    - Run with: pytest tests/integration/ --run-integration
    """
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration tests disabled")

    from services import get_document_service, get_cosmos_service

    doc_service = get_document_service()
    cosmos_service = get_cosmos_service()

    # Use a test document
    blob_url = os.environ["TEST_BLOB_URL"]

    # Analyze document
    result = await doc_service.analyze_document(blob_url)
    assert result["status"] == "completed"

    # Save to Cosmos
    doc_id = f"test_{asyncio.current_task().get_name()}"
    result["id"] = doc_id
    result["sourceFile"] = "test/document.pdf"

    saved = await cosmos_service.save_document_result(result)
    assert saved["id"] == doc_id

    # Cleanup
    # await cosmos_service.delete_document(doc_id, "test/document.pdf")
```

---

## 8. Local Configuration Files

### local.settings.json (gitignored)

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",

    "DOC_INTEL_ENDPOINT": "https://your-instance.cognitiveservices.azure.com",
    "COSMOS_ENDPOINT": "https://your-cosmos.documents.azure.com:443/",
    "COSMOS_DATABASE": "DocumentsDB",
    "COSMOS_CONTAINER": "ProcessedDocuments",

    "KEY_VAULT_NAME": "your-keyvault-name",
    "FUNCTION_TIMEOUT": "230",
    "LOG_LEVEL": "INFO"
  }
}
```

### local.settings.template.json (checked into git)

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "<REPLACE_WITH_STORAGE_CONNECTION_STRING>",

    "DOC_INTEL_ENDPOINT": "<REPLACE_WITH_ENDPOINT>",
    "COSMOS_ENDPOINT": "<REPLACE_WITH_COSMOS_ENDPOINT>",
    "COSMOS_DATABASE": "DocumentsDB",
    "COSMOS_CONTAINER": "ProcessedDocuments",

    "KEY_VAULT_NAME": "<REPLACE_WITH_KEY_VAULT_NAME>",
    "FUNCTION_TIMEOUT": "230",
    "LOG_LEVEL": "INFO"
  }
}
```

### host.json

```json
{
  "version": "2.0",
  "logging": {
    "logLevel": {
      "default": "Information",
      "Host.Results": "Information",
      "Function": "Information",
      "Host.Aggregator": "Information"
    },
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "maxTelemetryItemsPerSecond": 20
      }
    }
  },
  "functionTimeout": "00:10:00",
  "extensions": {
    "http": {
      "routePrefix": "api"
    }
  }
}
```

### requirements.txt

```txt
azure-functions==1.21.0
azure-ai-documentintelligence[aio]==1.0.0b4
azure-cosmos[aio]==4.7.0
azure-identity[aio]==1.19.0
azure-keyvault-secrets==4.8.0
aiohttp==3.10.11
pydantic==2.10.3
```

---

## 9. Critical Gotchas & Best Practices

### Timeout Handling

1. **HTTP Trigger Timeout**: 230 seconds max (Azure Load Balancer)
   - For longer operations, use Durable Functions or async request-reply pattern
   - Set `functionTimeout` in host.json (default 5 min for Consumption, unlimited for Premium/Dedicated)

2. **Document Intelligence Timeout**: Large PDFs can take 30+ seconds
   ```python
   # Set custom timeout for HTTP client
   import httpx
   timeout = httpx.Timeout(60.0, connect=60.0)
   ```

### Async Best Practices

1. **Always use `async with` for clients**:
   ```python
   async with DocumentIntelligenceClient(...) as client:
       result = await client.begin_analyze_document(...)
   ```

2. **Install async dependencies**:
   ```bash
   pip install azure-ai-documentintelligence[aio] aiohttp
   ```

3. **All I/O should be async** in async functions (no blocking calls)

### Document Intelligence

1. **Rate Limiting**: 15 TPS default
   - Implement exponential backoff
   - Use queues for high-volume processing

2. **Model IDs**: Use correct model for your scenario
   - `prebuilt-layout`: General layout/tables
   - `prebuilt-invoice`: Invoice-specific
   - `custom-model-id`: Your custom trained model

3. **Long-Running Operations**: Use poller pattern
   ```python
   poller = await client.begin_analyze_document(...)
   result = await poller.result()  # Blocks until complete
   ```

### Cosmos DB

1. **Partition Key Required**: Always include in queries
2. **ID Uniqueness**: Per partition only (not globally unique)
3. **Boolean Values**: Use `"true"/"false"` (lowercase strings)
4. **Cross-Partition Queries**: Expensive - avoid if possible

### Testing

1. **Blueprint Testing**: Use `.get_functions()[0].get_user_function()` to access wrapped function
2. **Async Tests**: Mark with `@pytest.mark.asyncio`
3. **Mock External Services**: Never hit real Azure services in unit tests
4. **Integration Tests**: Gate with environment variable check

---

## 10. Common Patterns Summary

### Pattern: HTTP Trigger → Document Intelligence → Cosmos DB

```python
@app.route(route="process", methods=["POST"])
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # 1. Parse request
        req_body = req.get_json()
        blob_url = req_body['blobUrl']

        # 2. Analyze with Document Intelligence
        doc_service = get_document_service()
        analysis_result = await doc_service.analyze_document(
            blob_url,
            model_id="prebuilt-invoice"
        )

        # 3. Transform result
        document = {
            "id": generate_doc_id(blob_url),
            "sourceFile": extract_blob_name(blob_url),  # Partition key
            "processedAt": datetime.utcnow().isoformat(),
            "fields": analysis_result["fields"],
            "status": "completed"
        }

        # 4. Save to Cosmos DB
        cosmos_service = get_cosmos_service()
        saved_doc = await cosmos_service.save_document_result(document)

        # 5. Return success
        return func.HttpResponse(
            json.dumps(saved_doc),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.exception(e)
        return create_error_response(str(e), status_code=500)
```

---

## Resources & Documentation

### Official Documentation
- [Python v2 Programming Model](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Python v2 Triggers & Bindings](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-triggers-python)
- [Document Intelligence SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-documentintelligence-readme)
- [Cosmos DB Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/cosmos-readme)
- [Azure Functions Unit Testing Guide](https://github.com/Azure/azure-functions-python-worker/wiki/Unit-Testing-Guide)

### Sample Repositories
- [Azure Functions Python v2 Samples](https://github.com/Azure-Samples/azure-functions-python-v2)
- [Document Intelligence Code Samples](https://github.com/Azure-Samples/document-intelligence-code-samples)
- [Azure Functions Python Examples](https://github.com/csiebler/azure-functions-python-examples)
- [Async HTTP Trigger Example](https://github.com/miztiik/azure-function-http-trigger-async-function)

### Key Articles
- [Azure Functions v2 Python GA Announcement](https://techcommunity.microsoft.com/blog/azurecompute/azure-functions-v2-python-programming-model-is-generally-available/3827474)
- [Writing and Testing v2 Functions](https://medium.com/mesh-ai-technology-and-engineering/writing-and-testing-azure-functions-in-the-v2-python-programming-model-c391bd779ff6)
- [Cosmos DB Async IO](https://devblogs.microsoft.com/cosmosdb/run-parallel-crud-operations-with-python-async-io-for-azure-cosmos-db/)
- [Python Best Practices for Cosmos DB](https://docs.azure.cn/en-us/cosmos-db/nosql/best-practice-python)

---

**Last Updated**: 2025-12-02
**Focus Areas**: HTTP triggers, async patterns, Document Intelligence, Cosmos DB, pytest testing
