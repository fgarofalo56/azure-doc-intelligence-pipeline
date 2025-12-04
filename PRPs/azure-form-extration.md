# PRP: Azure Document Intelligence PDF Processing Pipeline

## Goal

**Feature Goal**: Build a production-ready automated document processing pipeline that extracts structured data from PDF documents using Azure Document Intelligence custom models, orchestrated via Azure Synapse Analytics, and persists extracted data to Azure Cosmos DB.

**Deliverable**: Complete end-to-end solution with:
1. Bicep infrastructure templates (new deployment + existing resource modes)
2. Azure Function (Python v2) for PDF processing via Document Intelligence API
3. Synapse pipeline for batch orchestration
4. Cosmos DB container for extracted document storage
5. Comprehensive unit and integration tests

**Success Definition**: Pipeline successfully processes PDFs from blob storage, extracts fields with confidence scores, stores results in Cosmos DB, and handles errors gracefully with retry logic.

## User Persona

**Target User**: Data engineers and DevOps teams deploying document processing solutions in enterprise environments.

**Use Case**: Process incoming PDF documents (invoices, forms, contracts) at scale, extracting structured data for downstream analytics, reporting, or integration with business systems.

**User Journey**:
1. Deploy infrastructure via Bicep (new resources or existing)
2. Train/configure Document Intelligence custom model via Azure Studio
3. Upload PDFs to blob storage
4. Trigger Synapse pipeline (manual or scheduled)
5. Query extracted data from Cosmos DB

**Pain Points Addressed**:
- Manual data entry from PDF documents
- Inconsistent data extraction quality
- Lack of audit trail for processed documents
- No scalable batch processing capability

## Why

- **Automate manual document processing**: Eliminate repetitive manual data entry from PDF documents
- **Scalable enterprise pattern**: Handle batch processing of large document volumes with parallel execution (up to 50 concurrent)
- **Centralized data extraction**: Consolidate extracted document data in Cosmos DB for downstream analytics
- **Infrastructure as Code**: Ensure repeatable, auditable deployments via Bicep templates
- **Federal compliance ready**: Architecture supports FedRAMP and FISMA requirements for government workloads

## What

An end-to-end solution consisting of:

1. **Bicep Infrastructure Templates** - Deploy all Azure resources (or connect to existing ones)
2. **Azure Synapse Pipeline** - Orchestrate PDF processing workflow with ForEach parallelism
3. **Azure Function (Python v2)** - Async HTTP trigger processing PDFs via Document Intelligence API
4. **Cosmos DB Sink** - NoSQL storage with sourceFile partition key
5. **Unit & Integration Tests** - pytest coverage for all components

### Success Criteria

- [ ] Bicep templates deploy all required Azure resources successfully
- [ ] Bicep templates support using existing Azure resources via `deploymentMode` parameter
- [ ] Pipeline discovers all PDFs in configured blob container/folder
- [ ] Each PDF is processed through Document Intelligence custom model with <15 TPS rate limit handling
- [ ] Extracted fields are correctly mapped and saved to Cosmos DB with confidence scores
- [ ] Error handling captures failed documents with retry logic (exponential backoff)
- [ ] Unit tests pass: `uv run pytest tests/unit/ -v`
- [ ] Integration tests validate end-to-end flow

---

## All Needed Context

### Context Completeness Check

_Validated: If someone knew nothing about this codebase, they would have everything needed to implement this successfully using the patterns and AI docs referenced below._

### Documentation & References

```yaml
# MUST READ - Critical implementation references
- docfile: PRPs/ai_docs/azure_document_intelligence_patterns.md
  why: Production-ready patterns for custom model analysis, field extraction, retry logic
  section: All sections - especially "6. Common Pitfalls" and "7. Production-Ready Pattern"
  critical: |
    - Use async client with semaphore for concurrency control (stay below 15 TPS)
    - Implement exponential backoff for 429 rate limit errors
    - Generate SAS tokens with 2+ hour expiry for long-running operations
    - Always use .get() for field access - structure varies by model

- docfile: PRPs/ai_docs/azure_functions_python_v2_patterns.md
  why: HTTP trigger patterns, async Document Intelligence + Cosmos DB integration
  section: Sections 1-6 for HTTP triggers, DI pattern, async patterns
  critical: |
    - Use async def for HTTP triggers with I/O operations
    - Install aiohttp for async SDK support
    - 230-second hard limit for HTTP triggers (Azure Load Balancer)
    - Use Blueprint pattern for modular code organization

- docfile: PRPs/ai_docs/azure_synapse_pipeline_patterns.md
  why: Pipeline JSON patterns for GetMetadata, Filter, ForEach, Azure Function activities
  section: "Complete Pipeline Pattern" section has full working JSON
  critical: |
    - Set timeout to 10 minutes (default is only 1 minute!)
    - batchCount max is 50, recommend 10 for Document Intelligence rate limits
    - Filter output uses .output.value (not just .output)
    - Cannot nest ForEach loops - use ExecutePipeline instead

# Official Azure Documentation
- url: https://learn.microsoft.com/en-us/python/api/overview/azure/ai-documentintelligence-readme
  why: Document Intelligence Python SDK reference
  critical: Package is azure-ai-documentintelligence (NOT azure-ai-formrecognizer)

- url: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits
  why: Rate limits and quotas - 15 TPS default, S0 tier limits
  critical: Enable autoscaling for production workloads

- url: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/quickstart-python
  why: Cosmos DB Python SDK patterns
  critical: Partition key is required for all operations, use sourceFile

- url: https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python
  why: Python v2 programming model reference
  critical: Use decorators @app.route(), async functions for I/O

- url: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/modules
  why: Bicep module patterns and best practices
  critical: Use existing keyword for referencing deployed resources

- url: https://learn.microsoft.com/en-us/azure/data-factory/control-flow-azure-function-activity
  why: Azure Function activity configuration in Synapse
  critical: 230-second HTTP limit, use Durable Functions for longer operations
```

### Current Codebase Tree

```bash
# Greenfield project - no existing source code
azure-doc-intel-pipeline/
├── CLAUDE.md           # Project instructions
├── PRPs/
│   ├── README.md       # PRP concept documentation
│   ├── templates/      # PRP templates
│   └── ai_docs/        # AI documentation files (created by research)
│       ├── azure_document_intelligence_patterns.md
│       ├── azure_functions_python_v2_patterns.md
│       └── azure_synapse_pipeline_patterns.md
└── .claude/            # Claude Code configuration
```

### Desired Codebase Tree with Files to Create

```bash
azure-doc-intel-pipeline/
├── infra/
│   ├── main.bicep                    # Main deployment orchestrator
│   ├── modules/
│   │   ├── storage.bicep             # Storage account + containers
│   │   ├── document-intelligence.bicep # Cognitive Services FormRecognizer
│   │   ├── cosmos-db.bicep           # Cosmos DB account + database + container
│   │   ├── synapse.bicep             # Synapse workspace
│   │   ├── function-app.bicep        # Function App + App Service Plan
│   │   ├── key-vault.bicep           # Key Vault for secrets
│   │   └── existing-resources.bicep  # Reference existing resources
│   └── parameters/
│       ├── dev.bicepparam            # Development environment
│       ├── prod.bicepparam           # Production environment
│       └── existing.bicepparam       # Use existing resources mode
├── src/
│   └── functions/
│       ├── function_app.py           # Main entry point (v2 decorators)
│       ├── process_document.py       # Blueprint for document processing
│       ├── config.py                 # Configuration from environment
│       ├── services/
│       │   ├── __init__.py           # Service factory (pseudo-DI)
│       │   ├── document_service.py   # Document Intelligence async client
│       │   └── cosmos_service.py     # Cosmos DB async client
│       ├── requirements.txt          # Python dependencies
│       ├── host.json                 # Function host config
│       └── local.settings.template.json
├── src/synapse/
│   ├── pipelines/
│   │   └── process-pdfs-pipeline.json  # Main processing pipeline
│   ├── linkedServices/
│   │   ├── ls_blob_storage.json
│   │   ├── ls_azure_function.json
│   │   └── ls_cosmos_db.json
│   └── datasets/
│       └── ds_blob_binary.json
├── tests/
│   ├── unit/
│   │   ├── test_document_service.py
│   │   ├── test_cosmos_service.py
│   │   └── test_http_triggers.py
│   ├── integration/
│   │   └── test_end_to_end.py
│   └── fixtures/
│       └── sample_document_result.json
├── pyproject.toml                    # UV project configuration
└── README.md                         # Project documentation
```

### Known Gotchas & Library Quirks

```python
# CRITICAL: Document Intelligence rate limits
# Default: 15 TPS (transactions per second) per resource
# Solution: Use semaphore for concurrency control
semaphore = asyncio.Semaphore(10)  # Stay below 15 TPS

# CRITICAL: Polling after exception doesn't retry
# Once SDK exhausts retries, calling poller.result() again won't retry
# Solution: Catch exception and restart entire begin_analyze_document() call
for attempt in range(max_retries):
    try:
        poller = client.begin_analyze_document(model_id, body=file)
        return poller.result()
    except HttpResponseError as e:
        if e.status_code == 429:
            time.sleep(2 ** attempt)  # Must restart, not re-poll
            continue
        raise

# CRITICAL: SAS token expiration during long operations
# Large PDFs can take 30+ seconds to process
# Solution: Generate SAS tokens with 2+ hour expiry
sas_token = generate_blob_sas(..., expiry=datetime.utcnow() + timedelta(hours=2))

# CRITICAL: Cosmos DB partition key required
# Cannot change partition key after document creation
# Solution: Use sourceFile as partition key, derive ID from blob path
document = {
    "id": blob_name.replace("/", "_").replace(".", "_"),
    "sourceFile": blob_name,  # Partition key - immutable
    ...
}

# CRITICAL: Cosmos DB ID must be string
# Integer IDs silently fail
document = {"id": "12345", ...}  # Correct (string)
document = {"id": 12345, ...}    # WRONG (integer) - silent failure

# CRITICAL: Field value access varies by model
# Always use .get() with defaults
value = field.get("valueString") or field.get("valueNumber") or field.get("content")

# CRITICAL: Azure Functions HTTP timeout
# Hard 230-second limit (Azure Load Balancer)
# Solution: Use async patterns, or Durable Functions for >230s operations

# CRITICAL: Synapse Azure Function Activity timeout
# Default is only 1 minute!
# Solution: Always explicitly set to 10 minutes
"policy": {"timeout": "0:10:00", "retry": 2}

# CRITICAL: Synapse ForEach cannot be nested
# Solution: Use ExecutePipeline activity for multi-level loops

# CRITICAL: Filter activity output
# Use .output.value, not .output
"items": "@activity('FilterPDFFiles').output.value"  # Correct

# CRITICAL: Bicep storage account naming
# Lowercase only, no hyphens, 3-24 chars
var storageAccountName = toLower('${prefix}st${uniqueString(resourceGroup().id)}')

# CRITICAL: Document Intelligence kind is still 'FormRecognizer'
# Despite service rename, Bicep uses kind: 'FormRecognizer'
resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
    kind: 'FormRecognizer'  // Not 'DocumentIntelligence'
}
```

### Azure Services & API Versions (2024)

| Service | Bicep API Version | SDK Package |
|---------|-------------------|-------------|
| Storage Account | 2024-01-01 | azure-storage-blob |
| Cosmos DB | 2024-11-15 | azure-cosmos |
| Document Intelligence | 2024-10-01 (mgmt) / 2024-11-30 (API) | azure-ai-documentintelligence |
| Key Vault | 2024-11-01 | azure-keyvault-secrets |
| Function App | 2024-11-01 | azure-functions |
| Synapse | 2021-06-01 | N/A (JSON artifacts) |

### Python Dependencies

```toml
# pyproject.toml
[project]
name = "azure-doc-intel-pipeline"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "azure-ai-documentintelligence[aio]>=1.0.0",
    "azure-cosmos[aio]>=4.7.0",
    "azure-functions>=1.21.0",
    "azure-identity[aio]>=1.19.0",
    "azure-storage-blob>=12.19.0",
    "azure-keyvault-secrets>=4.8.0",
    "aiohttp>=3.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]
```

---

## Implementation Blueprint

### Data Models and Structure

```python
# Cosmos DB Document Schema
{
    "id": "folder_document_pdf",              # Derived from blob path (string!)
    "sourceFile": "folder/document.pdf",       # Partition key (immutable)
    "processedAt": "2024-01-15T10:30:00Z",     # ISO 8601 UTC
    "modelId": "custom-model-v1",              # Document Intelligence model
    "modelConfidence": 0.95,                   # Overall document confidence
    "docType": "invoice",                      # Detected document type
    "fields": {                                # Extracted field values
        "vendorName": "Acme Corp",
        "invoiceTotal": 1500.00,
        "invoiceDate": "2024-01-15"
    },
    "confidence": {                            # Per-field confidence scores
        "vendorName": 0.98,
        "invoiceTotal": 0.95,
        "invoiceDate": 0.97
    },
    "status": "completed",                     # completed | failed
    "error": null                              # Error message if failed
}
```

### Implementation Tasks (ordered by dependencies)

```yaml
Task 1: CREATE infra/modules/storage.bicep
  - IMPLEMENT: Storage account with pdfs and staging containers
  - FOLLOW pattern: PRPs/ai_docs/azure_document_intelligence_patterns.md (SAS generation)
  - NAMING: st${replace(resourceSuffix, '-', '')} (lowercase, no hyphens)
  - API VERSION: Microsoft.Storage/storageAccounts@2024-01-01
  - CRITICAL: Set minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false

Task 2: CREATE infra/modules/document-intelligence.bicep
  - IMPLEMENT: Cognitive Services account for Document Intelligence
  - KIND: 'FormRecognizer' (NOT 'DocumentIntelligence' - service renamed but kind unchanged)
  - API VERSION: Microsoft.CognitiveServices/accounts@2024-10-01
  - SKU: S0 for production (F0 for dev/test)
  - OUTPUT: endpoint, resourceId

Task 3: CREATE infra/modules/cosmos-db.bicep
  - IMPLEMENT: Cosmos DB account, database, container with serverless
  - PARTITION KEY: /sourceFile (immutable, high cardinality)
  - API VERSION: Microsoft.DocumentDB/databaseAccounts@2024-11-15
  - INDEXING: Consistent mode, include /* exclude /_etag
  - OUTPUT: endpoint, databaseName, containerName

Task 4: CREATE infra/modules/key-vault.bicep
  - IMPLEMENT: Key Vault with RBAC authorization
  - API VERSION: Microsoft.KeyVault/vaults@2024-11-01
  - CRITICAL: enableRbacAuthorization: true, enableSoftDelete: true

Task 5: CREATE infra/modules/function-app.bicep
  - IMPLEMENT: Function App with App Service Plan (Consumption)
  - API VERSION: Microsoft.Web/sites@2024-11-01
  - RUNTIME: python, version 3.10
  - APP SETTINGS: FUNCTIONS_EXTENSION_VERSION: ~4, FUNCTIONS_WORKER_RUNTIME: python
  - DEPENDENCIES: Storage account, Key Vault

Task 6: CREATE infra/modules/synapse.bicep
  - IMPLEMENT: Synapse workspace with managed identity
  - API VERSION: Microsoft.Synapse/workspaces@2021-06-01
  - CRITICAL: No 2024 API version available

Task 7: CREATE infra/modules/existing-resources.bicep
  - IMPLEMENT: References to pre-deployed resources using 'existing' keyword
  - PATTERN: resource x 'Type@version' existing = { name: param, scope: resourceGroup(rg) }
  - OUTPUT: Endpoints for each existing resource

Task 8: CREATE infra/main.bicep
  - IMPLEMENT: Main orchestrator with deploymentMode parameter
  - CONDITION: if (deploymentMode == 'new') for new resources
  - CONDITION: if (deploymentMode == 'existing') for existing resource refs
  - OUTPUTS: Conditional outputs using ternary operator

Task 9: CREATE infra/parameters/dev.bicepparam, prod.bicepparam, existing.bicepparam
  - IMPLEMENT: Environment-specific parameter files
  - FORMAT: using '../main.bicep' then param assignments

Task 10: CREATE src/functions/config.py
  - IMPLEMENT: Config class loading from environment variables
  - PATTERN: Required vars raise on missing, optional have defaults
  - FOLLOW: PRPs/ai_docs/azure_functions_python_v2_patterns.md Section 3

Task 11: CREATE src/functions/services/document_service.py
  - IMPLEMENT: Async Document Intelligence client with retry logic
  - FOLLOW pattern: PRPs/ai_docs/azure_document_intelligence_patterns.md Section 7
  - CRITICAL: Use semaphore for concurrency, exponential backoff for 429
  - ASYNC: Use azure.ai.documentintelligence.aio.DocumentIntelligenceClient

Task 12: CREATE src/functions/services/cosmos_service.py
  - IMPLEMENT: Async Cosmos DB client for upsert/query
  - FOLLOW pattern: PRPs/ai_docs/azure_functions_python_v2_patterns.md Section 5
  - CRITICAL: Always use async with for client lifecycle
  - PARTITION KEY: Required for all operations

Task 13: CREATE src/functions/services/__init__.py
  - IMPLEMENT: Service factory with singleton pattern (pseudo-DI)
  - PATTERN: get_document_service(), get_cosmos_service() functions
  - CRITICAL: Initialize once, reuse for function lifetime

Task 14: CREATE src/functions/function_app.py
  - IMPLEMENT: Main entry point with @app.route decorators
  - HTTP TRIGGER: POST /api/process with JSON body {blobUrl, blobName, modelId}
  - ASYNC: Use async def for all HTTP triggers
  - ERROR HANDLING: Return JSON with status, error fields
  - FOLLOW: PRPs/ai_docs/azure_functions_python_v2_patterns.md Section 6

Task 15: CREATE src/functions/requirements.txt, host.json, local.settings.template.json
  - REQUIREMENTS: azure-ai-documentintelligence[aio], azure-cosmos[aio], etc.
  - HOST.JSON: functionTimeout: "00:10:00"
  - LOCAL SETTINGS: Template with placeholders for endpoints

Task 16: CREATE src/synapse/pipelines/process-pdfs-pipeline.json
  - IMPLEMENT: Full pipeline with GetMetadata → Filter → ForEach → AzureFunction
  - FOLLOW pattern: PRPs/ai_docs/azure_synapse_pipeline_patterns.md "Complete Pipeline Pattern"
  - CRITICAL: Set timeout to 0:10:00, batchCount to 10
  - PARAMETERS: containerName, sourceFolderPath, storageAccountUrl, modelId

Task 17: CREATE src/synapse/linkedServices/*.json and datasets/*.json
  - IMPLEMENT: Linked services for blob storage, function app
  - AUTHENTICATION: SystemAssignedManagedIdentity preferred

Task 18: CREATE tests/unit/test_document_service.py
  - IMPLEMENT: Unit tests for DocumentService with mocked SDK
  - PATTERN: pytest-asyncio, AsyncMock for async methods
  - COVERAGE: analyze_document success, rate limit retry, timeout handling

Task 19: CREATE tests/unit/test_cosmos_service.py
  - IMPLEMENT: Unit tests for CosmosService with mocked SDK
  - COVERAGE: save_document_result, get_document_status, error handling

Task 20: CREATE tests/unit/test_http_triggers.py
  - IMPLEMENT: Unit tests for HTTP triggers
  - PATTERN: func.HttpRequest mock, service mocks
  - COVERAGE: Success path, missing params, invalid JSON, service errors
  - FOLLOW: PRPs/ai_docs/azure_functions_python_v2_patterns.md Section 7

Task 21: CREATE tests/integration/test_end_to_end.py
  - IMPLEMENT: Integration tests with real Azure resources
  - GUARD: Skip if RUN_INTEGRATION_TESTS not set
  - COVERAGE: Full flow from blob to Cosmos DB

Task 22: CREATE pyproject.toml and README.md
  - PYPROJECT: UV configuration with dependencies
  - README: Setup instructions, deployment guide, usage examples
```

### Implementation Patterns & Key Details

```python
# Document Service Pattern (from ai_docs)
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
import asyncio

class DocumentService:
    def __init__(self, endpoint: str, api_key: str, max_concurrent: int = 10):
        self.endpoint = endpoint
        self.credential = AzureKeyCredential(api_key)
        self.semaphore = asyncio.Semaphore(max_concurrent)  # Rate limit protection

    async def analyze_document(self, blob_url: str, model_id: str) -> dict:
        async with self.semaphore:  # CRITICAL: Concurrency control
            for attempt in range(3):  # CRITICAL: Retry from begin_analyze, not poller
                try:
                    async with DocumentIntelligenceClient(
                        self.endpoint, self.credential
                    ) as client:
                        poller = await client.begin_analyze_document(
                            model_id=model_id,
                            analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
                        )
                        result = await poller.result()
                        return self._extract_fields(result)
                except HttpResponseError as e:
                    if e.status_code == 429 and attempt < 2:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    raise

# Cosmos Service Pattern
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

class CosmosService:
    def __init__(self, endpoint: str, database: str, container: str):
        self.endpoint = endpoint
        self.database_name = database
        self.container_name = container
        self.credential = DefaultAzureCredential()

    async def save_document_result(self, document: dict) -> dict:
        async with CosmosClient(self.endpoint, self.credential) as client:
            database = client.get_database_client(self.database_name)
            container = database.get_container_client(self.container_name)
            return await container.upsert_item(body=document)

# HTTP Trigger Pattern
@app.function_name(name="ProcessDocument")
@app.route(route="process", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        blob_url = req_body.get("blobUrl")
        blob_name = req_body.get("blobName")
        model_id = req_body.get("modelId", "prebuilt-layout")

        if not blob_url or not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing blobUrl or blobName"}),
                status_code=400, mimetype="application/json"
            )

        doc_service = get_document_service()
        result = await doc_service.analyze_document(blob_url, model_id)

        cosmos_service = get_cosmos_service()
        document = {
            "id": blob_name.replace("/", "_").replace(".", "_"),
            "sourceFile": blob_name,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            **result
        }
        await cosmos_service.save_document_result(document)

        return func.HttpResponse(
            json.dumps({"status": "success", "documentId": document["id"]}),
            status_code=200, mimetype="application/json"
        )
    except Exception as e:
        logging.exception(e)
        return func.HttpResponse(
            json.dumps({"status": "error", "error": str(e)}),
            status_code=500, mimetype="application/json"
        )
```

### Integration Points

```yaml
BICEP OUTPUTS:
  - storageAccountName: Used in pipeline parameters
  - documentIntelligenceEndpoint: Used in Function App settings
  - cosmosDbEndpoint: Used in Function App settings
  - functionAppName: Used in Synapse linked service

FUNCTION APP SETTINGS:
  - DOC_INTEL_ENDPOINT: From Bicep output or existing resource
  - COSMOS_ENDPOINT: From Bicep output or existing resource
  - COSMOS_DATABASE: "DocumentsDB"
  - COSMOS_CONTAINER: "ExtractedDocuments"
  - KEY_VAULT_NAME: For secret retrieval
  - CUSTOM_MODEL_ID: From Document Intelligence Studio

SYNAPSE PIPELINE:
  - Linked Service: LS_AzureFunction with function app URL
  - Parameters: storageAccountUrl, containerName, sourceFolderPath, modelId
  - Output: Processed document IDs in Cosmos DB
```

---

## Validation Loop

### Level 1: Syntax & Style (Immediate Feedback)

```bash
# Bicep validation
az bicep build --file infra/main.bicep --stdout > /dev/null && echo "✅ Bicep syntax valid"
az bicep lint --file infra/main.bicep

# Python linting
uv run ruff check src/functions/ tests/
uv run ruff format src/functions/ tests/

# Type checking
uv run mypy src/functions/ --ignore-missing-imports

# JSON validation for Synapse artifacts
python -c "import json; json.load(open('src/synapse/pipelines/process-pdfs-pipeline.json'))" && echo "✅ Pipeline JSON valid"

# Expected: Zero errors. Fix before proceeding.
```

### Level 2: Unit Tests (Component Validation)

```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=src/functions --cov-report=term-missing

# Test specific components
uv run pytest tests/unit/test_document_service.py -v
uv run pytest tests/unit/test_cosmos_service.py -v
uv run pytest tests/unit/test_http_triggers.py -v

# Expected: All tests pass with >80% coverage
```

### Level 3: Bicep Deployment Validation

```bash
# What-if deployment (dry run)
az deployment group what-if \
  --resource-group rg-docprocessing-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Validate template
az deployment group validate \
  --resource-group rg-docprocessing-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Deploy infrastructure
az deployment group create \
  --resource-group rg-docprocessing-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Expected: Deployment succeeds with all outputs available
```

### Level 4: Integration Testing

```bash
# Start function locally
cd src/functions && func start &
sleep 5

# Test health endpoint
curl -s http://localhost:7071/api/health | jq .

# Test process endpoint with sample PDF
curl -X POST http://localhost:7071/api/process \
  -H "Content-Type: application/json" \
  -d '{"blobUrl": "https://storageaccount.blob.core.windows.net/pdfs/test.pdf?sas=...", "blobName": "test.pdf", "modelId": "prebuilt-layout"}' \
  | jq .

# Run integration tests (requires deployed resources)
RUN_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v

# Verify Cosmos DB document
az cosmosdb sql query \
  --account-name $COSMOS_ACCOUNT \
  --database-name DocumentsDB \
  --container-name ExtractedDocuments \
  --query "SELECT * FROM c WHERE c.sourceFile = 'test.pdf'"

# Expected: Document processed and saved to Cosmos DB
```

### Level 5: Synapse Pipeline Testing

```bash
# Import pipeline to Synapse
az synapse pipeline create \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name ProcessPDFsWithDocIntelligence \
  --file @src/synapse/pipelines/process-pdfs-pipeline.json

# Trigger pipeline run
az synapse pipeline create-run \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name ProcessPDFsWithDocIntelligence \
  --parameters sourceFolderPath=test containerName=pdfs

# Monitor pipeline run
az synapse pipeline-run show \
  --workspace-name $SYNAPSE_WORKSPACE \
  --run-id $RUN_ID

# Expected: Pipeline completes successfully, all PDFs processed
```

---

## Final Validation Checklist

### Technical Validation

- [ ] All 5 validation levels completed successfully
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] No linting errors: `uv run ruff check src/`
- [ ] No type errors: `uv run mypy src/functions/`
- [ ] Bicep templates deploy without errors

### Feature Validation

- [ ] Pipeline discovers PDFs in blob container
- [ ] Document Intelligence extracts fields with confidence scores
- [ ] Extracted data saved to Cosmos DB with correct schema
- [ ] Rate limiting handled with exponential backoff
- [ ] Failed documents logged with error details
- [ ] Both new and existing deployment modes work

### Code Quality Validation

- [ ] Follows patterns from ai_docs files
- [ ] Async patterns used for all I/O operations
- [ ] Error handling with structured JSON responses
- [ ] No hardcoded secrets (all via Key Vault or environment)
- [ ] Partition key (sourceFile) included in all Cosmos documents

### Security Validation

- [ ] Key Vault used for all secrets
- [ ] Managed Identity preferred over keys
- [ ] TLS 1.2 minimum enforced
- [ ] No public blob access
- [ ] RBAC authorization enabled

---

## Anti-Patterns to Avoid

- ❌ Don't use sync SDK calls in async functions (blocks event loop)
- ❌ Don't hardcode API keys in code or Bicep
- ❌ Don't use integer IDs for Cosmos DB documents (must be strings)
- ❌ Don't retry poller.result() after 429 - restart begin_analyze_document()
- ❌ Don't use azure-ai-formrecognizer package (deprecated, use azure-ai-documentintelligence)
- ❌ Don't set Synapse activity timeout < 10 minutes for document processing
- ❌ Don't exceed 15 TPS without implementing rate limiting
- ❌ Don't generate SAS tokens with < 2 hour expiry for document processing
- ❌ Don't nest ForEach loops in Synapse (use ExecutePipeline instead)
- ❌ Don't use Filter .output directly (must use .output.value)

---

## Confidence Score

**Implementation Success Likelihood: 9/10**

High confidence due to:
- Comprehensive AI docs with production-ready patterns
- Explicit gotchas documented from real-world research
- Clear task ordering with dependencies
- Specific API versions and package names
- Complete validation loop at all levels

Potential risks:
- Custom model training not automated (requires Azure Studio)
- Federal compliance endpoints need manual configuration
- Large PDF processing may require Durable Functions for >230s operations
