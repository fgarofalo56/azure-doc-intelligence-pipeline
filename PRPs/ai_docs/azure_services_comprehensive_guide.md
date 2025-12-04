# Azure Services Comprehensive Guide
## Azure Document Intelligence PDF Processing Pipeline

**Last Updated:** 2025-12-04
**Purpose:** Implementation-critical documentation for all Azure services used in this pipeline

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service-by-Service Breakdown](#service-by-service-breakdown)
   - [Azure Functions](#1-azure-functions)
   - [Azure Document Intelligence](#2-azure-document-intelligence)
   - [Azure Cosmos DB](#3-azure-cosmos-db)
   - [Azure Blob Storage](#4-azure-blob-storage)
   - [Azure Key Vault](#5-azure-key-vault)
   - [Azure Synapse Analytics](#6-azure-synapse-analytics)
   - [Azure Log Analytics](#7-azure-log-analytics)
   - [Azure Application Insights](#8-azure-application-insights)
3. [Architecture Connection Diagram](#architecture-connection-diagram)
4. [Required IAM/RBAC Roles](#required-iamrbac-roles)
5. [SKU Recommendations](#sku-recommendations)
6. [Cost Optimization Tips](#cost-optimization-tips)
7. [Integration Points](#integration-points)
8. [Common Issues & Troubleshooting](#common-issues--troubleshooting)

---

## Architecture Overview

This pipeline automates document processing through the following flow:

```
PDF Upload → Blob Storage → Synapse Pipeline → Azure Function → Document Intelligence → Cosmos DB
                                    ↓
                         Key Vault (Secrets) + App Insights (Monitoring)
```

### Key Capabilities
- **Automated extraction** of structured data from PDFs using custom AI models
- **Orchestrated processing** via Synapse Analytics pipelines
- **Persistent storage** in Cosmos DB with partition-optimized queries
- **Secure secrets management** through Key Vault with managed identities
- **End-to-end monitoring** with Application Insights and Log Analytics

---

## Service-by-Service Breakdown

### 1. Azure Functions

#### Purpose & Capabilities
Azure Functions provides serverless compute to process documents on-demand, triggered by Synapse pipelines. This project uses **Python 3.10+ with the v2 programming model** on the **Functions v4 runtime**.

#### Configuration Requirements

**Runtime Settings:**
```json
{
  "FUNCTIONS_WORKER_RUNTIME": "python",
  "FUNCTIONS_EXTENSION_VERSION": "~4",
  "AzureWebJobsStorage": "connection-string-or-managed-identity",
  "DOC_INTEL_ENDPOINT": "https://<region>.cognitiveservices.azure.com/",
  "COSMOS_DATABASE": "DocumentsDB"
}
```

**Connection Methods:**
- **Preferred:** Managed Identity for Cosmos DB, Blob Storage, Key Vault
- **Required for Document Intelligence:** SAS token generation (Document Intelligence cannot access private blobs directly)
- **Function Key:** Stored in Key Vault as `FunctionAppHostKey` for Synapse authentication

**Networking:**
- Can be deployed with private endpoints for VNet integration
- Requires outbound access to Document Intelligence (public endpoint)
- Synapse must be able to reach Function App (via function key authentication)

#### Security Best Practices
1. **Use Managed Identity** for all Azure service connections (Cosmos, Storage, Key Vault)
2. **Store function keys** in Key Vault, not in pipeline definitions
3. **Generate short-lived SAS tokens** (1-hour expiry) for blob access
4. **Enable Application Insights** for security monitoring and diagnostics
5. **Disable remote debugging** in production environments

#### Integration Points
- **Synapse Analytics:** HTTP-triggered function calls via LS_AzureFunction linked service
- **Blob Storage:** Generates SAS tokens for Document Intelligence access
- **Document Intelligence:** Sends blob URLs with SAS tokens for analysis
- **Cosmos DB:** Writes extracted data with partition key `sourceFile`
- **Key Vault:** Retrieves secrets using managed identity

#### Common Issues & Troubleshooting

**Rate Limits:**
- Consumption Plan: No specific rate limit (scales automatically)
- Premium Plan: Limited by configured instances

**Timeout Settings:**
- Default: 5 minutes (Consumption), 30 minutes (Premium)
- Increase in `host.json` for long-running document processing:
```json
{
  "functionTimeout": "00:10:00"
}
```

**Error Codes:**
- `401 Unauthorized`: Check managed identity permissions or function key
- `500 Internal Server Error`: Check Application Insights logs for stack traces
- `503 Service Unavailable`: Function app scaling or cold start issues

#### Python v2 Programming Model
```python
import azure.functions as func
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

@app.route(route="process", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def process_document(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered function using v2 model decorators."""
    blob_url = req.params.get('blobUrl')
    # Process document...
    return func.HttpResponse("Success", status_code=200)
```

**Key v2 Features:**
- Decorator-based function definitions (`@app.route`, `@app.blob_trigger`)
- Simplified folder structure (no `function.json` files)
- Blueprint support for modular function organization
- SDK type bindings (requires runtime 4.34+, Python 3.10+)

---

### 2. Azure Document Intelligence

#### Purpose & Capabilities
Azure Document Intelligence (formerly Form Recognizer) extracts text, key-value pairs, tables, and structure from PDFs using pre-trained and custom models. This project uses **API version 2024-02-29-preview**.

#### Configuration Requirements

**Endpoint Format:**
```
https://{endpoint}/documentintelligence/documentModels/{modelId}:analyze?api-version=2024-02-29-preview
```

**Regional Availability (2024-02-29-preview):**
- East US
- West US2
- West Europe

**SDK Version (Python):**
```bash
pip install azure-ai-documentintelligence==1.0.0b2
```

**Required Settings:**
- `DOC_INTEL_ENDPOINT`: Service endpoint URL
- `DOC_INTEL_KEY`: API key (store in Key Vault) or use Managed Identity
- `MODEL_ID`: Custom model ID for document extraction

**Python SDK Example:**
```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

client = DocumentIntelligenceClient(
    endpoint=os.environ["DOC_INTEL_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["DOC_INTEL_KEY"])
)

# Analyze document from URL (requires SAS token for private blobs)
poller = client.begin_analyze_document(
    model_id="custom-model-v1",
    analyze_request={"urlSource": blob_url_with_sas}
)
result = poller.result()  # Blocks until completion
```

#### Security Best Practices
1. **Private blob access:** Document Intelligence cannot access private blobs—generate SAS tokens via Azure Function
2. **Rotate API keys** regularly if not using managed identity
3. **Monitor API calls** in Application Insights for anomalous patterns
4. **Use custom models** instead of pre-built models for sensitive document types
5. **Enable logging** for all Document Intelligence operations

#### Integration Points
- **Azure Functions:** Receives blob URLs with SAS tokens for analysis
- **Blob Storage:** Reads source PDFs (requires SAS token if private)
- **Key Vault:** Stores Document Intelligence API keys

#### Common Issues & Troubleshooting

**Rate Limits:**
- Default: **15 TPS (transactions per second)**
- Solution: Implement exponential backoff retry logic
```python
from azure.core.pipeline.policies import RetryPolicy

retry_policy = RetryPolicy(retry_total=5, retry_backoff_factor=1.0)
```

**Async Operation Delays:**
- Large PDFs (>50 pages) can take **30+ seconds**
- Set appropriate timeouts in Synapse Web Activity (10 minutes recommended)
- Monitor with `begin_analyze_document().result()` or poll status

**Error Codes:**
- `400 Bad Request`: Invalid model ID or malformed request
- `403 Forbidden`: SAS token expired or invalid permissions
- `429 Too Many Requests`: Rate limit exceeded (implement retry with backoff)
- `500 Internal Server Error`: Azure service issue (retry after delay)

**Preview API Considerations:**
- **2024-02-29-preview is retiring**: Migrate to **2024-11-30 (GA)** for production
- Preview APIs have limited SLA guarantees
- Check [changelog](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/versioning/changelog-release-history?view=doc-intel-4.0.0) for breaking changes

---

### 3. Azure Cosmos DB

#### Purpose & Capabilities
Azure Cosmos DB (NoSQL API) provides globally distributed, low-latency storage for extracted document data. This project uses **partition key `sourceFile`** for optimal query performance.

#### Configuration Requirements

**Connection String Format:**
```
AccountEndpoint=https://<account-name>.documents.azure.com:443/;AccountKey=<key>;
```

**Partition Strategy:**
- **Partition Key:** `sourceFile` (e.g., "folder/document.pdf")
- **ID Format:** `folder_document_pdf` (derived from blob path)
- **Rationale:** Enables efficient single-partition queries when retrieving by source file

**Database/Container Settings:**
- Database: `DocumentsDB`
- Container: `ExtractedDocuments`
- Throughput: 400 RU/s minimum (autoscale recommended)
- Indexing: Automatic (default policy indexes all properties)

**Connection Methods:**
- **Preferred:** Managed Identity (no keys in code)
```python
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

client = CosmosClient(
    url="https://<account>.documents.azure.com",
    credential=DefaultAzureCredential()
)
```
- **Alternative:** Connection string from Key Vault

**Networking:**
- Private endpoint support for VNet integration
- Firewall rules for IP whitelisting
- Service endpoint policies for subnet-level control

#### Security Best Practices
1. **Use Managed Identity** instead of connection strings
2. **Enable Synapse Link** for analytics (requires analytical store)
3. **Implement RBAC** with roles:
   - `Cosmos DB Built-in Data Contributor` for read/write
   - `Cosmos DB Built-in Data Reader` for read-only
4. **Enable audit logging** in Diagnostic Settings
5. **Rotate account keys** if using connection strings (90-day cycle)

#### Integration Points
- **Azure Functions:** Writes extracted documents using managed identity
- **Synapse Analytics:** Reads data via Synapse Link or linked service
- **Key Vault:** Stores connection strings (if not using managed identity)

#### Common Issues & Troubleshooting

**Partition Key Errors:**
- **Error:** "PartitionKey value must be supplied for this operation"
- **Solution:** Always include `sourceFile` in document writes
```python
document = {
    "id": "folder_document_pdf",
    "sourceFile": "folder/document.pdf",  # Required!
    "fields": {...}
}
container.create_item(document)
```

**Cross-Partition Queries:**
- **Issue:** Expensive queries without partition key filter
- **Solution:** Always filter by `sourceFile` in queries
```sql
-- Good (single partition)
SELECT * FROM c WHERE c.sourceFile = 'folder/document.pdf'

-- Bad (cross-partition scan)
SELECT * FROM c WHERE c.docType = 'invoice'
```

**RU/s Throttling:**
- **Error:** HTTP 429 (Too Many Requests)
- **Solution:**
  - Increase provisioned throughput (400 → 1000+ RU/s)
  - Enable autoscale (scales between 10% and 100% of max)
  - Implement retry logic in SDK

**Existing Mode Auto-Creation:**
- When `deploymentMode=existing`, database/container are **automatically created** if missing
- **Synapse Link:** Must be enabled at account level first (Portal), then set `enableExistingCosmosAnalyticalStore=true`

**Error Codes:**
- `400 Bad Request`: Invalid document format or partition key mismatch
- `409 Conflict`: Document with same ID already exists (use upsert)
- `429 Too Many Requests`: RU/s limit exceeded (retry with exponential backoff)

---

### 4. Azure Blob Storage

#### Purpose & Capabilities
Azure Blob Storage stores source PDFs and acts as the ingestion point for the pipeline. This project uses **Azure Blob Storage (Standard tier)** with hierarchical namespace disabled.

#### Configuration Requirements

**Connection String Format:**
```
DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net
```

**Container Structure:**
```
pdf-documents/
  ├── incoming/          # Upload PDFs here to trigger pipeline
  ├── processed/         # Move completed files here
  └── failed/            # Move failed documents here
```

**Connection Methods:**
- **Preferred:** Managed Identity with RBAC roles
```python
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

blob_service = BlobServiceClient(
    account_url="https://<account>.blob.core.windows.net",
    credential=DefaultAzureCredential()
)
```
- **Alternative:** Connection string from Key Vault or `AzureWebJobsStorage` for Functions

**Networking:**
- Private endpoint for VNet-only access
- Firewall rules for IP restrictions
- Service endpoints for subnet-level access

#### Security Best Practices
1. **Use Managed Identity** instead of storage keys
2. **Disable Shared Key access** to enforce Azure AD authentication
```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  properties: {
    allowSharedKeyAccess: false  // Enforce managed identity
  }
}
```
3. **Generate short-lived SAS tokens** (1-hour expiry) for Document Intelligence
```python
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

sas_token = generate_blob_sas(
    account_name=account_name,
    container_name=container_name,
    blob_name=blob_name,
    account_key=account_key,
    permission=BlobSasPermissions(read=True),
    expiry=datetime.utcnow() + timedelta(hours=1)
)
blob_url_with_sas = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
```
4. **Enable soft delete** for blob recovery (7-30 day retention)
5. **Monitor blob access** with Storage Analytics logging

#### Integration Points
- **Synapse Analytics:** Reads blob metadata via LS_AzureBlobStorage linked service
- **Azure Functions:** Generates SAS tokens for Document Intelligence access
- **Document Intelligence:** Reads PDFs using SAS-authenticated URLs

#### Common Issues & Troubleshooting

**SAS Token Errors:**
- **Error:** `403 Forbidden` or `ResourceNotFound`
- **Causes:**
  - SAS token expired (check clock skew between services)
  - Insufficient permissions (`BlobSasPermissions(read=True)` required)
  - Storage account firewall blocking Document Intelligence IP
- **Solution:** Extend SAS expiry, verify permissions, add Document Intelligence IPs to allow list

**Managed Identity Permissions:**
- **Required RBAC Roles:**
  - `Storage Blob Data Contributor` (read/write/delete)
  - `Storage Blob Data Reader` (read-only for Document Intelligence)
- **Assign at container level** for least privilege

**URL Encoding:**
- **Issue:** Blob names with spaces fail in Synapse pipelines
- **Solution:** Use `encodeUriComponent()` in pipeline expressions
```json
{
  "blobUrl": "@concat('https://storage.blob.core.windows.net/', encodeUriComponent(item().name))"
}
```

**Error Codes:**
- `403 Forbidden`: Authentication failure (expired SAS or missing RBAC role)
- `404 Not Found`: Blob does not exist or container name incorrect
- `500 Internal Server Error`: Storage service issue (retry after delay)

---

### 5. Azure Key Vault

#### Purpose & Capabilities
Azure Key Vault securely stores secrets (API keys, connection strings), certificates, and cryptographic keys. This project uses **Azure Key Vault with RBAC permission model** instead of legacy access policies.

#### Configuration Requirements

**Vault URI Format:**
```
https://<vault-name>.vault.azure.net/
```

**Secrets Stored:**
- `FunctionAppHostKey`: Function app master key for Synapse authentication
- `DocIntelKey`: Document Intelligence API key (if not using managed identity)
- `CosmosConnectionString`: Cosmos DB connection string (if not using managed identity)

**Connection Methods:**
- **Preferred:** Managed Identity with RBAC
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

secret_client = SecretClient(
    vault_url="https://<vault>.vault.azure.net",
    credential=DefaultAzureCredential()
)
secret = secret_client.get_secret("FunctionAppHostKey")
print(secret.value)
```
- **Alternative:** Service principal with client ID/secret (not recommended)

**Networking:**
- Private endpoint for VNet-only access
- Firewall rules for IP restrictions
- Service endpoints for subnet-level access

#### Security Best Practices
1. **Use RBAC permission model** (not access policies)
   - Set `enableRbacAuthorization: true` in Bicep
   - Legacy access policies lack PIM support and have known vulnerabilities
2. **Assign minimal RBAC roles:**
   - `Key Vault Secrets User`: Read secret values (for apps)
   - `Key Vault Secrets Officer`: Create/update/delete secrets (for admins)
   - `Key Vault Reader`: View metadata only (insufficient for apps)
3. **Use Azure Privileged Identity Management (PIM)** for JIT admin access
4. **Enable soft delete** (90-day retention) and purge protection
5. **Monitor with Diagnostic Settings** (log all secret accesses to Log Analytics)
6. **Separate Key Vaults per environment** (dev/test/prod)

#### RBAC Roles Reference

| Role | Permissions | Use Case |
|------|-------------|----------|
| `Key Vault Administrator` | Full control (secrets, keys, certs, RBAC) | Break-glass admin access (use PIM) |
| `Key Vault Secrets Officer` | Create/update/delete secrets (no RBAC) | Automated secret rotation scripts |
| `Key Vault Secrets User` | Read secret values only | Application runtime access |
| `Key Vault Reader` | View metadata (NOT secret values) | Auditing, inventory (insufficient for apps) |

**Critical:** Assigning `Key Vault Reader` to a managed identity will **NOT** allow it to read secret values. Use `Key Vault Secrets User` instead.

#### Integration Points
- **Azure Functions:** Retrieves secrets using managed identity (`@Microsoft.KeyVault(SecretUri=...)`)
- **Synapse Analytics:** Accesses secrets via LS_KeyVault linked service
- **Function Key Storage:** Synapse retrieves `FunctionAppHostKey` for HTTP authentication

#### Common Issues & Troubleshooting

**Access Denied Errors:**
- **Error:** `403 Forbidden` or "The user, group or application does not have secrets get permission"
- **Root Causes:**
  1. Assigned `Key Vault Reader` (reads metadata only, not secret values)
  2. RBAC role not propagated yet (can take 5-10 minutes)
  3. Firewall blocking managed identity's IP
  4. Access policy conflict (both RBAC and access policies enabled)
- **Solution:**
  1. Assign `Key Vault Secrets User` role to managed identity
  2. Wait 10 minutes for role propagation
  3. Add managed identity IP to firewall allow list
  4. Disable access policies (`enableRbacAuthorization: true` in Bicep)

**Synapse Linked Service Errors:**
- **Issue:** "Failed to get secret from Key Vault"
- **Solution:** Ensure Synapse workspace managed identity has `Key Vault Secrets User` role

**Secret Rotation:**
- **Best Practice:** Rotate secrets every 90 days
- **Automation:** Use Azure Automation or Logic Apps to rotate and update Key Vault
- **Zero-downtime rotation:** Use dual-key strategy (old and new keys active during rotation period)

**Error Codes:**
- `403 Forbidden`: Insufficient RBAC permissions (assign `Key Vault Secrets User`)
- `404 Not Found`: Secret does not exist or vault name incorrect
- `503 Service Unavailable`: Key Vault service issue (rare, retry after delay)

---

### 6. Azure Synapse Analytics

#### Purpose & Capabilities
Azure Synapse Analytics orchestrates the document processing workflow via pipelines. This project uses **Synapse pipelines** (similar to Azure Data Factory) with **serverless SQL pools** for ad-hoc queries.

#### Configuration Requirements

**Linked Services (Required):**
1. **LS_AzureFunction**: Connects to Function App via function key (stored in Key Vault)
2. **LS_AzureBlobStorage**: Reads blob metadata (managed identity)
3. **LS_CosmosDB**: Reads/writes Cosmos DB (managed identity)
4. **LS_KeyVault**: Retrieves secrets (Synapse managed identity with `Key Vault Secrets User`)

**Pipeline Components:**
- **ForEach Activity**: Iterates over blobs in source folder (max 50 parallel)
- **Web Activity**: Calls Azure Function with blob URL
- **Copy Activity**: Moves processed blobs to `processed/` folder
- **Delete Activity**: Archives failed documents to `failed/` folder

**Artifact Folder Structure (Critical):**
```
src/synapse/
  ├── linkedService/       # SINGULAR (not linkedServices)
  │   ├── LS_AzureFunction.json
  │   ├── LS_AzureBlobStorage.json
  │   ├── LS_CosmosDB.json
  │   └── LS_KeyVault.json
  ├── pipeline/            # SINGULAR
  │   └── ProcessPDFsWithDocIntelligence.json
  ├── dataset/             # SINGULAR
  ├── notebook/            # SINGULAR
  └── sqlscript/           # SINGULAR
```

**File Name = Resource Name Rule:**
```json
// LS_AzureFunction.json MUST contain:
{
  "name": "LS_AzureFunction",  // Must match filename
  "properties": { ... }
}
```

#### Security Best Practices
1. **Use Managed Identity** for all linked services (avoid keys)
2. **Store function key in Key Vault** (not hardcoded in pipeline)
3. **Enable Git integration** (Azure DevOps or GitHub) for version control
4. **Separate workspaces per environment** (dev/test/prod)
5. **Monitor with Log Analytics** (enable Diagnostic Settings)
6. **Limit ForEach parallelism** (default 50, reduce to 10-20 to avoid throttling)

#### Integration Points
- **Azure Functions:** Calls HTTP trigger via Web Activity
- **Blob Storage:** Reads blob list via GetMetadata and ForEach activities
- **Cosmos DB:** (Optional) Reads processed data for analytics
- **Key Vault:** Retrieves function key via LS_KeyVault linked service

#### Common Issues & Troubleshooting

**Web Activity Timeouts:**
- **Default:** 1 minute (too short for document processing)
- **Symptom:** "The operation has timed out" error
- **Solution:** Increase timeout in Web Activity settings:
```json
{
  "type": "WebActivity",
  "typeProperties": {
    "url": "@variables('functionUrl')",
    "method": "POST",
    "timeout": "00:10:00"  // 10 minutes
  }
}
```

**ForEach Parallelism Throttling:**
- **Issue:** Hitting rate limits (Document Intelligence 15 TPS, Cosmos DB RU/s)
- **Solution:** Reduce `batchCount` in ForEach activity:
```json
{
  "type": "ForEach",
  "typeProperties": {
    "items": "@activity('GetBlobs').output.childItems",
    "batchCount": 10,  // Default 50, reduce to avoid throttling
    "isSequential": false
  }
}
```

**Artifact Deployment Errors:**
- **Error:** "Failed to deploy pipeline: Resource not found"
- **Causes:**
  1. Folder names are plural (`linkedServices/` instead of `linkedService/`)
  2. File name doesn't match resource name (`LS_Function.json` but `"name": "LS_AzureFunction"`)
  3. Linked service not deployed before pipeline that references it
- **Solution:**
  1. Use singular folder names (`linkedService/`, `pipeline/`, `dataset/`)
  2. Ensure filename matches `"name"` field in JSON
  3. Deploy in order: linked services → datasets → pipelines

**GitHub Integration:**
- **Configuration in Bicep:**
```bicep
accountName: 'your-github-username'
repositoryName: 'your-repo-name'
collaborationBranch: 'main'
rootFolder: '/src/synapse'  // Points to artifact root
```
- **Artifact folder:** Synapse expects `linkedService/`, `pipeline/`, etc. directly under `rootFolder`

**Serverless SQL Pool Pricing:**
- **Model:** Pay-per-query ($5/TB data processed)
- **Optimization:** Query Parquet/compressed files to reduce data scanned
- **Cost Control:** Set budgets per day/week/month in T-SQL

**Error Codes:**
- `401 Unauthorized`: Function key missing or invalid (check Key Vault secret)
- `404 Not Found`: Function URL incorrect or app not running
- `500 Internal Server Error`: Function execution failed (check Application Insights)
- `503 Service Unavailable`: Synapse service issue (rare, retry after delay)

---

### 7. Azure Log Analytics

#### Purpose & Capabilities
Azure Log Analytics collects and analyzes telemetry from all Azure services, providing centralized logging and query capabilities. This project uses **Log Analytics workspace** as the backend for Application Insights and diagnostic logs.

#### Configuration Requirements

**Workspace Settings:**
- **Retention:** 30 days free (Auxiliary/Basic Logs), 31+ days charged
- **Ingestion:** Pay-as-you-go or commitment tiers (100 GB/day minimum)
- **Location:** Should match Function App region for reduced latency

**Diagnostic Settings (Enable on all resources):**
```json
{
  "logs": [
    {"category": "FunctionAppLogs", "enabled": true},
    {"category": "AllMetrics", "enabled": true}
  ],
  "workspaceId": "/subscriptions/.../Microsoft.OperationalInsights/workspaces/..."
}
```

**KQL Query Examples:**
```kql
// Function execution times
requests
| where cloud_RoleName == "function-app-name"
| summarize avg(duration), percentile(duration, 95) by bin(timestamp, 1h)

// Document Intelligence errors
traces
| where message contains "DocumentAnalysisError"
| project timestamp, message, severityLevel
| order by timestamp desc

// Cosmos DB throttling
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where statusCode_s == "429"
| summarize count() by bin(TimeGenerated, 5m)
```

#### Security Best Practices
1. **Centralized workspace** across subscriptions (common for enterprises)
2. **Use RBAC** for access control:
   - `Log Analytics Reader`: Query logs only
   - `Log Analytics Contributor`: Manage workspace settings
3. **Cross-subscription support:** Workspace can be in different subscription/RG
```bicep
// Reference Log Analytics in different subscription
scope: resourceGroup(existingLogAnalyticsSubscriptionId, existingLogAnalyticsResourceGroup)
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: existingLogAnalyticsWorkspaceName
}
```
4. **Enable audit logging** for workspace changes
5. **Set retention policies** per table (30-730 days)

#### Integration Points
- **Application Insights:** Uses Log Analytics as backend storage
- **All Azure Resources:** Send diagnostic logs via Diagnostic Settings
- **Synapse Analytics:** Query logs via serverless SQL or Spark notebooks

#### Common Issues & Troubleshooting

**Log Ingestion Delays:**
- **Typical latency:** 1-5 minutes from event to query availability
- **Cause:** Log Analytics batches ingestion for efficiency
- **Solution:** Wait 5 minutes before querying recent logs

**Commitment Tier Lock-In:**
- **Constraint:** 31-day commitment period after selecting/changing tier
- **Implication:** Cannot reduce tier or switch to pay-as-you-go for 31 days
- **Solution:** Start with pay-as-you-go, monitor usage for 1-2 months, then commit

**Cross-Subscription Access:**
- **Scenario:** Log Analytics in central monitoring subscription
- **Requirement:** RBAC roles assigned at workspace level
- **Solution:** Grant managed identities `Log Analytics Reader` role

**Cost Spikes:**
- **Causes:**
  - Verbose logging enabled (Debug/Trace level)
  - High-frequency metrics (1-minute intervals)
  - Large blob reads logged in Storage Analytics
- **Solutions:**
  - Set log level to Warning/Error in production
  - Use 5-minute metric intervals
  - Disable Storage Analytics logs for infrequent containers

**Error Codes:**
- `403 Forbidden`: Insufficient RBAC permissions (assign `Log Analytics Reader`)
- `404 Not Found`: Workspace ID incorrect or workspace deleted
- `429 Too Many Requests`: Query throttling (reduce query frequency)

---

### 8. Azure Application Insights

#### Purpose & Capabilities
Azure Application Insights provides application performance monitoring (APM) with distributed tracing, exception tracking, and live metrics. This project uses **workspace-based Application Insights** (backed by Log Analytics).

#### Configuration Requirements

**Application Settings (Function App):**
```json
{
  "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=...;IngestionEndpoint=https://<region>.applicationinsights.azure.com/",
  "ApplicationInsightsAgent_EXTENSION_VERSION": "~3",  // For Python
  "APPINSIGHTS_INSTRUMENTATIONKEY": "<legacy-key>"     // Optional (legacy)
}
```

**Sampling Configuration (`host.json`):**
```json
{
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "maxTelemetryItemsPerSecond": 20,  // Reduce for cost control
        "excludedTypes": "Request"          // Always sample requests
      }
    }
  }
}
```

**Connection Methods:**
- **Preferred:** Connection string from Application Insights resource
- **Injected automatically** by Azure Functions runtime (no code changes needed)

#### Security Best Practices
1. **Use workspace-based mode** (not classic Application Insights)
2. **Enable sampling** to reduce costs (default: 5 items/sec)
3. **Sanitize PII** in custom telemetry (don't log sensitive data)
4. **Standardize custom dimensions** for traceability:
```python
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger.info("Processing document", extra={
    "custom_dimensions": {
        "FlowName": "DocumentProcessing",
        "BlobName": blob_name,
        "ModelId": model_id
    }
})
```
5. **Archive old data** (>90 days) to Blob Storage using Continuous Export
6. **Define naming conventions** for events and metrics across apps

#### Integration Points
- **Azure Functions:** Automatic instrumentation (no code changes required)
- **Log Analytics:** Queries use `requests`, `traces`, `exceptions` tables
- **Synapse Analytics:** Can ingest logs via Log Analytics linked service

#### Common Issues & Troubleshooting

**Missing Telemetry:**
- **Cause 1:** Application Insights not configured (`APPLICATIONINSIGHTS_CONNECTION_STRING` missing)
- **Cause 2:** Sampling rate too aggressive (missing non-critical events)
- **Solution:**
  1. Verify connection string in Function App settings
  2. Increase `maxTelemetryItemsPerSecond` or disable sampling for critical operations

**High Costs:**
- **Cause:** Excessive logging (Debug/Trace level in production)
- **Solution:**
  1. Set log level to Warning/Error in `host.json`:
  ```json
  {
    "logging": {
      "logLevel": {
        "default": "Warning",
        "Function": "Information"
      }
    }
  }
  ```
  2. Enable sampling (5-20 items/sec)
  3. Archive data older than 90 days to Blob Storage

**Live Metrics Not Showing:**
- **Cause:** Using legacy instrumentation key (not connection string)
- **Solution:** Update to connection string format:
```
InstrumentationKey=...;IngestionEndpoint=https://<region>.applicationinsights.azure.com/
```

**OpenTelemetry Integration:**
- **Latest approach:** Use Azure Monitor OpenTelemetry Distro
```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)
```
- **Benefits:** Vendor-neutral, standardized instrumentation, future-proof

**KQL Queries:**
```kql
// Slowest function executions (95th percentile)
requests
| where cloud_RoleName == "function-app-name"
| summarize percentile(duration, 95) by operation_Name
| order by percentile_duration_95 desc

// Exception rates by type
exceptions
| summarize count() by type, bin(timestamp, 1h)
| render timechart
```

**Error Codes:**
- `403 Forbidden`: Instrumentation key/connection string invalid
- `429 Too Many Requests`: Ingestion throttling (reduce telemetry volume)
- `500 Internal Server Error`: Application Insights service issue (retry)

---

## Architecture Connection Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER UPLOADS PDF                               │
│                                 ↓                                       │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Azure Blob Storage (incoming/)                                 │   │
│  │  - Stores source PDFs                                          │   │
│  │  - Managed Identity: Storage Blob Data Contributor            │   │
│  └────────────┬───────────────────────────────────────────────────┘   │
│               │                                                         │
│               ↓                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Azure Synapse Analytics                                        │   │
│  │  - GetMetadata Activity → List blobs in incoming/              │   │
│  │  - ForEach Activity → Process each blob (batchCount: 10-20)   │   │
│  │    ├─→ Web Activity → Call Azure Function                     │   │
│  │    ├─→ Copy Activity → Move to processed/                     │   │
│  │    └─→ Upon Failure → Move to failed/                         │   │
│  │  Managed Identity: Storage Blob Data Contributor              │   │
│  └────────────┬───────────────────────────────────────────────────┘   │
│               │                                                         │
│               ↓ (HTTP POST with blob URL)                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Azure Functions (Python v2 Model)                             │   │
│  │  - HTTP-triggered function (func key auth)                     │   │
│  │  - Generates SAS token for blob (1-hour expiry)                │   │
│  │  - Calls Document Intelligence with SAS URL                    │   │
│  │  - Writes extracted data to Cosmos DB                          │   │
│  │  Managed Identity:                                             │   │
│  │    - Storage Blob Data Contributor (SAS generation)            │   │
│  │    - Cosmos DB Built-in Data Contributor (write)               │   │
│  │    - Key Vault Secrets User (read secrets)                     │   │
│  └────┬───────────────────────┬──────────────────────┬─────────────┘   │
│       │                       │                      │                 │
│       ↓                       ↓                      ↓                 │
│  ┌──────────────┐  ┌──────────────────────┐  ┌─────────────────┐    │
│  │ Azure Key    │  │ Azure Document       │  │ Azure Cosmos DB │    │
│  │ Vault        │  │ Intelligence         │  │ (NoSQL API)     │    │
│  │              │  │                      │  │                 │    │
│  │ Stores:      │  │ - Custom model:     │  │ - Database:     │    │
│  │ - Function   │  │   custom-model-v1   │  │   DocumentsDB   │    │
│  │   key        │  │ - API: 2024-02-29   │  │ - Partition key:│    │
│  │ - Doc Intel  │  │   -preview          │  │   sourceFile    │    │
│  │   API key    │  │ - Rate limit: 15 TPS│  │ - Throughput:   │    │
│  │              │  │ - Timeout: 30+ sec  │  │   400-1000 RU/s │    │
│  │ RBAC:        │  │   for large PDFs    │  │                 │    │
│  │ Key Vault    │  │                      │  │ RBAC:           │    │
│  │ Secrets User │  │ Accessed via:       │  │ Cosmos DB       │    │
│  └──────────────┘  │ - Managed Identity  │  │ Built-in Data   │    │
│                    │   (preferred)       │  │ Contributor     │    │
│                    │ - API Key (Key Vault│  └─────────────────┘    │
│                    │   fallback)         │                         │
│                    └──────────────────────┘                         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Monitoring & Logging                                       │    │
│  │                                                              │    │
│  │  Azure Log Analytics                                        │    │
│  │  ├─ Workspace: Centralized log storage                     │    │
│  │  ├─ Retention: 30 days free, 31+ days charged              │    │
│  │  ├─ Ingestion: Pay-as-you-go or commitment tiers           │    │
│  │  └─ Queries: KQL for troubleshooting and analytics         │    │
│  │         ↑                                                   │    │
│  │         │                                                   │    │
│  │  Azure Application Insights                                │    │
│  │  ├─ Workspace-based mode (uses Log Analytics)              │    │
│  │  ├─ Automatic instrumentation (Function Apps)              │    │
│  │  ├─ Sampling: 5-20 items/sec (cost control)                │    │
│  │  ├─ Custom dimensions: FlowName, BlobName, ModelId         │    │
│  │  └─ Distributed tracing across services                    │    │
│  │         ↑                                                   │    │
│  │         └─── All services send diagnostic logs             │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘

DATA FLOW:
1. User uploads PDF to Blob Storage (incoming/)
2. Synapse pipeline triggers (schedule/tumbling window/storage event)
3. Synapse GetMetadata lists all blobs in incoming/
4. Synapse ForEach iterates (parallel: 10-20), calls Azure Function per blob
5. Function generates 1-hour SAS token for blob
6. Function calls Document Intelligence with SAS URL
7. Document Intelligence analyzes PDF (async, 30+ sec for large files)
8. Function writes extracted data to Cosmos DB (partition key: sourceFile)
9. Synapse moves blob to processed/ (success) or failed/ (error)
10. All operations logged to Application Insights → Log Analytics
```

---

## Required IAM/RBAC Roles

### Azure Functions Managed Identity

Assign these roles to the **Function App's system-assigned managed identity**:

| Service | Role | Scope | Purpose |
|---------|------|-------|---------|
| **Blob Storage** | `Storage Blob Data Contributor` | Storage Account or Container | Generate SAS tokens, read blobs |
| **Cosmos DB** | `Cosmos DB Built-in Data Contributor` | Cosmos DB Account | Write extracted documents |
| **Key Vault** | `Key Vault Secrets User` | Key Vault | Read Document Intelligence API key |
| **Application Insights** | (Automatic) | N/A | Telemetry ingestion via connection string |

**Bicep Example:**
```bicep
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  identity: {
    type: 'SystemAssigned'
  }
}

// Storage Blob Data Contributor
resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, functionApp.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, functionApp.id, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: functionApp.identity.principalId
    scope: cosmosAccount.id
  }
}

// Key Vault Secrets User
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  name: guid(keyVault.id, functionApp.id, '4633458b-17de-408a-b874-0445c86b69e6')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Synapse Workspace Managed Identity

Assign these roles to the **Synapse Workspace's system-assigned managed identity**:

| Service | Role | Scope | Purpose |
|---------|------|-------|---------|
| **Blob Storage** | `Storage Blob Data Contributor` | Storage Account or Container | Read blob metadata, move files |
| **Key Vault** | `Key Vault Secrets User` | Key Vault | Read function key for HTTP calls |
| **Cosmos DB** | `Cosmos DB Built-in Data Reader` (optional) | Cosmos DB Account | Query processed data (if using Synapse Link) |

**Bicep Example:**
```bicep
resource synapse 'Microsoft.Synapse/workspaces@2021-06-01' = {
  identity: {
    type: 'SystemAssigned'
  }
}

// Storage Blob Data Contributor
resource synapseBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, synapse.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: synapse.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User
resource synapseKeyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  name: guid(keyVault.id, synapse.id, '4633458b-17de-408a-b874-0445c86b69e6')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: synapse.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Developer/Admin Access

Assign these roles to **developers and administrators** (not services):

| Service | Role | Scope | Purpose |
|---------|------|-------|---------|
| **Function App** | `Website Contributor` | Function App | Deploy code, view logs |
| **Key Vault** | `Key Vault Secrets Officer` | Key Vault | Create/update secrets (use PIM for JIT) |
| **Log Analytics** | `Log Analytics Contributor` | Workspace | Query logs, create dashboards |
| **Synapse** | `Synapse Administrator` | Workspace | Manage pipelines, linked services |
| **Cosmos DB** | `Cosmos DB Account Contributor` | Account | Manage throughput, containers |

### Cross-Resource-Group Considerations

When resources are in different resource groups (common in existing deployments):

```bicep
// Reference existing resource in different RG
resource existingStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: existingStorageAccountName
  scope: resourceGroup(existingStorageAccountResourceGroup)  // Different RG
}

// Assign role across RGs
resource crossRgRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: existingStorage  // Uses scope from 'existing' resource
  name: guid(existingStorage.id, functionApp.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Cross-Subscription Considerations

For Log Analytics in a different subscription (centralized monitoring):

```bicep
// Reference Log Analytics in different subscription
resource existingLogAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: existingLogAnalyticsWorkspaceName
  scope: resourceGroup(existingLogAnalyticsSubscriptionId, existingLogAnalyticsResourceGroup)
}

// Use the workspace ID in Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  properties: {
    WorkspaceResourceId: existingLogAnalytics.id  // Cross-subscription reference
  }
}
```

### Role Propagation Delays

**Important:** RBAC role assignments can take **5-10 minutes** to propagate. If you encounter `403 Forbidden` errors immediately after deployment:

1. Wait 10 minutes for role propagation
2. Restart the Function App to refresh managed identity token cache
3. Verify role assignment in Azure Portal → IAM → Role assignments

---

## SKU Recommendations

### Development Environment

| Service | SKU | Justification | Monthly Cost (Estimate) |
|---------|-----|---------------|-------------------------|
| **Azure Functions** | Consumption Plan | Pay-per-execution, auto-scaling | $0 (within free tier: 1M executions) |
| **Document Intelligence** | F0 (Free) or S0 (Standard) | F0: 500 pages/month free; S0: $1.50/1000 pages | $0 (F0) or ~$15 (S0, 10K pages) |
| **Cosmos DB** | Serverless | No provisioned throughput, pay per RU | $5-20 (light usage) |
| **Blob Storage** | Standard (LRS) | Locally redundant, sufficient for dev | $2-5 (100 GB) |
| **Key Vault** | Standard | No hardware security module (HSM) | $0.03 per 10K operations (~$1/month) |
| **Synapse** | Serverless SQL Pool only | Pay-per-query, no dedicated pools | $0 (no queries) to $5 (ad-hoc queries) |
| **Log Analytics** | Pay-as-you-go | No commitment tier, 30-day retention | $0 (5 GB/day free) to $10 (10 GB/day) |
| **Application Insights** | Workspace-based (via Log Analytics) | Included in Log Analytics costs | Included above |
| **Total Estimated** | | | **$5-60/month** |

**Notes:**
- Use **single region** (East US or West US2) to minimize egress charges
- **Disable premium features** (premium Functions plan, dedicated Synapse pools)
- **Set RU/s limits** in Cosmos DB to prevent runaway costs

### Production Environment

| Service | SKU | Justification | Monthly Cost (Estimate) |
|---------|-----|---------------|-------------------------|
| **Azure Functions** | Premium EP1 Plan | No cold starts, VNet integration, 3.5 GB RAM | $146/month (1 instance) |
| **Document Intelligence** | S0 (Standard) | High throughput, SLA-backed | $50-200 (depends on volume) |
| **Cosmos DB** | Autoscale (1000-4000 RU/s) | Dynamic scaling, 99.99% SLA | $58/month (1000 RU/s avg) to $234 (4000 RU/s) |
| **Blob Storage** | Standard (GRS) | Geo-redundant, high availability | $10-30 (1 TB) |
| **Key Vault** | Standard | Sufficient for most workloads (Premium for HSM if required) | $0.03 per 10K operations (~$5/month) |
| **Synapse** | Serverless SQL + 1 Spark Pool (Small) | Serverless: $5/TB; Spark: $0.167/hour (~$120/month 24/7) | $120-150/month |
| **Log Analytics** | Commitment Tier (100 GB/day) | 30% savings over pay-as-you-go | $196/month (100 GB/day) |
| **Application Insights** | Workspace-based (via Log Analytics) | Included in Log Analytics costs | Included above |
| **Total Estimated** | | | **$585-850/month** |

**Notes:**
- Use **geo-redundant storage (GRS)** for disaster recovery
- Enable **Synapse dedicated SQL pools** only if serverless is insufficient
- Consider **3-year reserved instances** for Functions (save ~30%)
- **Autoscale Cosmos DB** based on workload patterns (start at 1000 RU/s)

### Federal/Government (FedRAMP High)

| Service | SKU | Justification | Monthly Cost (Estimate) |
|---------|-----|---------------|-------------------------|
| **Azure Functions** | Premium EP1 Plan (Gov regions) | FedRAMP High authorized | ~$180/month (Gov pricing +20%) |
| **Document Intelligence** | S0 (Gov endpoint) | `https://usgovvirginia.api.cognitive.microsoft.us` | ~$60-240 (Gov pricing +20%) |
| **Cosmos DB** | Autoscale (Gov regions) | 99.99% SLA, FedRAMP High | ~$70-280 (Gov pricing +20%) |
| **Blob Storage** | Standard (GRS, Gov regions) | Geo-redundant across Gov regions | ~$12-36 (Gov pricing +20%) |
| **Key Vault** | Premium (HSM-backed) | FIPS 140-2 Level 2 HSM required | $1.11 per key/month (~$50/month) |
| **Synapse** | Serverless SQL only (Gov regions) | Limited Gov region availability | ~$6/TB + queries |
| **Log Analytics** | Pay-as-you-go (Gov regions) | Commitment tiers not available in all Gov regions | ~$3/GB (~$100-300/month) |
| **Application Insights** | Workspace-based (Gov regions) | Limited Gov region availability | Included above |
| **Total Estimated** | | | **$478-1142/month** |

**Federal Compliance Notes:**
- **Authorized regions:** USGov Virginia, USGov Arizona, USGov Texas
- **Use Government endpoints:**
  - Document Intelligence: `https://{location}.api.cognitive.microsoft.us`
  - Cosmos DB: `https://{accountName}.documents.azure.us`
- **Premium Key Vault required** for FIPS 140-2 Level 2 compliance
- **Enable audit logging** for all services (FISMA compliance)
- **Private endpoints mandatory** for all services (no public internet access)

---

## Cost Optimization Tips

### General Strategies

1. **Use Managed Identities** (eliminates key rotation overhead and reduces Key Vault operations)
2. **Enable Application Insights sampling** (5-20 items/sec reduces ingestion costs by 70-90%)
3. **Set Log Analytics retention to 30 days** (free tier), archive older data to Blob Storage
4. **Use Cosmos DB serverless** for dev/test (pay-per-RU instead of provisioned throughput)
5. **Delete unused resources** (dev environments should be stopped outside business hours)

### Service-Specific Optimizations

#### Azure Functions
- **Consumption Plan for dev/test:** Free tier covers 1M executions/month
- **Premium Plan for prod:** 1-year reserved instance saves ~17% ($146 → $121/month)
- **Reduce cold starts:** Use Premium Plan or increase timeout in Consumption Plan
- **Function timeout:** Set to minimum required (5-10 minutes) to avoid unnecessary charges

#### Document Intelligence
- **Batch processing:** Process multiple documents in parallel (up to 15 TPS)
- **Use custom models:** More accurate extraction = fewer manual corrections
- **Monitor rate limits:** Implement exponential backoff to avoid repeated 429 errors
- **F0 tier for dev:** 500 pages/month free (sufficient for testing)

#### Cosmos DB
- **Autoscale vs. provisioned:**
  - Autoscale: Best for variable workloads (scales 10%-100% of max)
  - Provisioned: Best for steady workloads (lower cost per RU)
- **Serverless for dev:** No minimum RU/s, pay per operation
- **Free tier:** 1000 RU/s + 25 GB storage free (lifetime, one account per subscription)
- **Partition strategy:** Always query with partition key to avoid cross-partition scans

#### Blob Storage
- **Lifecycle management:** Move blobs to Cool/Archive tiers after 30 days
```bicep
resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'archiveOldPdfs'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['processed/']
            }
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 30
                }
                tierToArchive: {
                  daysAfterModificationGreaterThan: 90
                }
              }
            }
          }
        }
      ]
    }
  }
}
```
- **Delete soft-deleted blobs:** Soft delete retention (7 days) incurs storage charges
- **Use LRS for dev:** Locally redundant (cheapest), GRS for prod (geo-redundant)

#### Azure Synapse
- **Serverless SQL only:** No dedicated SQL pools for this workload (saves $1000+/month)
- **Optimize queries:** Use Parquet/compressed files to reduce data scanned ($5/TB)
- **Set cost controls:** Daily/weekly/monthly budgets to prevent runaway costs
```sql
-- Set daily budget (100 GB processed = $0.50)
EXEC sp_set_data_processed_limit
    @type = 'daily',
    @limit_tb = 0.1;  -- 100 GB/day
```

#### Log Analytics
- **Commitment tiers:** Save 30% if ingesting >100 GB/day consistently
- **Basic Logs:** $0.65/GB (vs. $2.99/GB Analytics Logs) for non-query-intensive logs
- **Auxiliary Logs:** $0.50/GB for rarely queried logs (8-day retention)
- **Delete verbose logs:** Disable Debug/Trace logging in production
```bicep
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  properties: {
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: 30  // Free tier, longer = charges
        }
      }
    ]
  }
}
```

### Cost Monitoring

1. **Enable Azure Cost Management alerts:**
   - Set budget to 80% of expected monthly spend
   - Configure email notifications to team
2. **Use Azure Advisor recommendations:**
   - Identifies underutilized resources (idle Function Apps, low RU/s Cosmos DBs)
3. **Tag resources by environment:**
```bicep
tags: {
  Environment: 'Production'
  Project: 'DocumentProcessing'
  CostCenter: 'IT-DataServices'
}
```
4. **Review monthly cost breakdown:**
   - Azure Portal → Cost Management → Cost Analysis
   - Export to Excel for detailed analysis

### Estimated Monthly Cost Comparison

| Scenario | Azure Functions | Document Intelligence | Cosmos DB | Blob Storage | Synapse | Monitoring | **Total** |
|----------|----------------|----------------------|-----------|--------------|---------|------------|-----------|
| **Dev (low usage)** | $0 (free tier) | $0-15 (F0/S0) | $5 (serverless) | $2 (100 GB, LRS) | $0-5 (no queries) | $0-10 (5 GB/day) | **$7-37** |
| **Prod (moderate)** | $146 (Premium EP1) | $50-100 (10-20K pages) | $58 (1000 RU/s autoscale) | $20 (1 TB, GRS) | $120 (serverless + small Spark pool) | $196 (100 GB/day commitment) | **$590-640** |
| **Prod (high volume)** | $292 (Premium EP2, 2 instances) | $200 (40K+ pages) | $234 (4000 RU/s autoscale) | $30 (1 TB, GRS) | $150 (serverless + queries) | $392 (200 GB/day commitment) | **$1298** |

---

## Integration Points

### Function App → Document Intelligence

**Method:** HTTP POST with SAS-authenticated blob URL

**Code Example:**
```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

# Generate SAS token (1-hour expiry)
sas_token = generate_blob_sas(
    account_name=storage_account_name,
    container_name=container_name,
    blob_name=blob_name,
    account_key=storage_account_key,  # From AzureWebJobsStorage
    permission=BlobSasPermissions(read=True),
    expiry=datetime.utcnow() + timedelta(hours=1)
)
blob_url_with_sas = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

# Call Document Intelligence
client = DocumentIntelligenceClient(
    endpoint=os.environ["DOC_INTEL_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["DOC_INTEL_KEY"])
)
poller = client.begin_analyze_document(
    model_id="custom-model-v1",
    analyze_request={"urlSource": blob_url_with_sas}
)
result = poller.result()  # Blocks for 30+ seconds
```

**Required Permissions:**
- Function App: `Storage Blob Data Contributor` on storage account (to generate SAS)
- Document Intelligence: No permissions needed (uses SAS token)

**Common Issues:**
- **403 Forbidden:** SAS token expired or incorrect permissions
- **429 Rate Limit:** Document Intelligence TPS exceeded (implement retry)
- **Timeout:** Large PDFs take 30+ seconds (increase function timeout)

---

### Function App → Cosmos DB

**Method:** Managed Identity with Cosmos DB SDK

**Code Example:**
```python
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

# Managed Identity connection (no keys!)
client = CosmosClient(
    url=os.environ["COSMOS_ENDPOINT"],
    credential=DefaultAzureCredential()
)
database = client.get_database_client("DocumentsDB")
container = database.get_container_client("ExtractedDocuments")

# Write document (partition key: sourceFile)
document = {
    "id": blob_name.replace("/", "_").replace(".pdf", ""),
    "sourceFile": blob_name,  # Partition key
    "processedAt": datetime.utcnow().isoformat(),
    "modelId": "custom-model-v1",
    "fields": {
        "vendorName": result.documents[0].fields["VendorName"].value,
        "invoiceTotal": result.documents[0].fields["InvoiceTotal"].value
    }
}
container.upsert_item(document)  # Upsert to handle re-processing
```

**Required Permissions:**
- Function App: `Cosmos DB Built-in Data Contributor` on Cosmos account

**Common Issues:**
- **403 Forbidden:** Managed identity role not assigned or not propagated yet (wait 10 min)
- **409 Conflict:** Document ID already exists (use `upsert_item` instead of `create_item`)
- **429 Rate Limit:** RU/s exceeded (increase throughput or enable autoscale)

---

### Synapse → Function App

**Method:** HTTP Web Activity with function key authentication

**Linked Service Configuration (LS_AzureFunction):**
```json
{
  "name": "LS_AzureFunction",
  "properties": {
    "type": "AzureFunction",
    "typeProperties": {
      "functionAppUrl": "https://func-doc-processing.azurewebsites.net",
      "functionKey": {
        "type": "AzureKeyVaultSecret",
        "store": {
          "referenceName": "LS_KeyVault",
          "type": "LinkedServiceReference"
        },
        "secretName": "FunctionAppHostKey"
      }
    }
  }
}
```

**Pipeline Web Activity:**
```json
{
  "name": "CallProcessFunction",
  "type": "WebActivity",
  "typeProperties": {
    "url": "https://func-doc-processing.azurewebsites.net/api/process",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "blobUrl": "@concat('https://storage.blob.core.windows.net/pdf-documents/', item().name)",
      "blobName": "@item().name"
    },
    "authentication": {
      "type": "MSI",  // Uses Synapse managed identity (NOT function key)
      "resource": "https://func-doc-processing.azurewebsites.net"
    },
    "timeout": "00:10:00"  // 10 minutes (increase for large PDFs)
  }
}
```

**Important:** Function key is used by Synapse Web Activity (NOT managed identity). The linked service retrieves the key from Key Vault.

**Required Permissions:**
- Synapse Workspace: `Key Vault Secrets User` on Key Vault (to read function key)

**Common Issues:**
- **401 Unauthorized:** Function key missing/invalid (verify Key Vault secret `FunctionAppHostKey`)
- **Timeout:** Web Activity default is 1 min (increase to 10 min for document processing)
- **404 Not Found:** Function URL incorrect or function app not running

---

### Synapse → Blob Storage

**Method:** Managed Identity with GetMetadata and Copy activities

**Linked Service Configuration (LS_AzureBlobStorage):**
```json
{
  "name": "LS_AzureBlobStorage",
  "properties": {
    "type": "AzureBlobStorage",
    "typeProperties": {
      "serviceEndpoint": "https://storage-account.blob.core.windows.net",
      "authenticationType": "MSI"
    }
  }
}
```

**GetMetadata Activity (list blobs):**
```json
{
  "name": "GetBlobs",
  "type": "GetMetadata",
  "typeProperties": {
    "dataset": {
      "referenceName": "DS_BlobStorage",
      "type": "DatasetReference",
      "parameters": {
        "folderPath": "pdf-documents/incoming"
      }
    },
    "fieldList": ["childItems"],
    "storeSettings": {
      "type": "AzureBlobStorageReadSettings",
      "recursive": false
    }
  }
}
```

**Copy Activity (move blob):**
```json
{
  "name": "MoveToProcessed",
  "type": "Copy",
  "inputs": [
    {
      "referenceName": "DS_SourceBlob",
      "type": "DatasetReference",
      "parameters": {
        "fileName": "@item().name"
      }
    }
  ],
  "outputs": [
    {
      "referenceName": "DS_DestinationBlob",
      "type": "DatasetReference",
      "parameters": {
        "fileName": "@item().name"
      }
    }
  ],
  "typeProperties": {
    "source": {
      "type": "BinarySource"
    },
    "sink": {
      "type": "BinarySink"
    }
  }
}
```

**Required Permissions:**
- Synapse Workspace: `Storage Blob Data Contributor` on storage account

**Common Issues:**
- **403 Forbidden:** Managed identity role not assigned (assign `Storage Blob Data Contributor`)
- **URL encoding:** Blob names with spaces require `encodeUriComponent()` in expressions
- **ForEach parallelism:** Reduce `batchCount` to 10-20 to avoid throttling

---

### Synapse → Key Vault

**Method:** Linked service with managed identity

**Linked Service Configuration (LS_KeyVault):**
```json
{
  "name": "LS_KeyVault",
  "properties": {
    "type": "AzureKeyVault",
    "typeProperties": {
      "baseUrl": "https://kv-doc-processing.vault.azure.net/"
    }
  }
}
```

**Usage in Pipeline (retrieve function key):**
```json
{
  "type": "AzureKeyVaultSecret",
  "store": {
    "referenceName": "LS_KeyVault",
    "type": "LinkedServiceReference"
  },
  "secretName": "FunctionAppHostKey"
}
```

**Required Permissions:**
- Synapse Workspace: `Key Vault Secrets User` on Key Vault

**Common Issues:**
- **403 Forbidden:** Assigned `Key Vault Reader` instead of `Key Vault Secrets User` (reader cannot read secret values)
- **Secret not found:** Secret name typo or secret deleted
- **Firewall:** Key Vault firewall blocking Synapse managed identity IP

---

## Common Issues & Troubleshooting

### 1. Function App Deployment Fails

**Symptom:** `func azure functionapp publish` errors with authentication failure

**Root Causes:**
1. Not logged in to Azure CLI: `az login`
2. Incorrect subscription selected: `az account set --subscription <subscription-id>`
3. Function App not running: Start in Azure Portal

**Solution:**
```bash
# Login
az login

# Set subscription
az account set --subscription "Your Subscription Name"

# Deploy
cd src/functions
func azure functionapp publish func-doc-processing --python
```

---

### 2. Document Intelligence Rate Limiting

**Symptom:** HTTP 429 errors in Application Insights logs

**Root Causes:**
1. Default rate limit: 15 TPS (transactions per second)
2. Synapse ForEach parallelism too high (default 50)

**Solution:**
```python
# Implement exponential backoff retry
from azure.core.exceptions import HttpResponseError
import time

max_retries = 5
for attempt in range(max_retries):
    try:
        result = poller.result()
        break
    except HttpResponseError as e:
        if e.status_code == 429 and attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
            time.sleep(wait_time)
        else:
            raise
```

**Synapse Pipeline Fix:**
```json
{
  "type": "ForEach",
  "typeProperties": {
    "batchCount": 10  // Reduce from default 50
  }
}
```

---

### 3. Cosmos DB Cross-Partition Queries

**Symptom:** High RU consumption, slow queries

**Root Cause:** Query not filtering by partition key (`sourceFile`)

**Solution:**
```python
# BAD: Cross-partition query (scans all partitions)
query = "SELECT * FROM c WHERE c.docType = 'invoice'"
items = list(container.query_items(query, enable_cross_partition_query=True))

# GOOD: Single-partition query (filters by partition key)
query = "SELECT * FROM c WHERE c.sourceFile = @sourceFile"
parameters = [{"name": "@sourceFile", "value": "folder/document.pdf"}]
items = list(container.query_items(query, parameters=parameters))
```

---

### 4. Blob SAS Token Expiration

**Symptom:** Document Intelligence returns 403 Forbidden

**Root Causes:**
1. SAS token expired (1-hour default)
2. Clock skew between Function App and Document Intelligence
3. Blob name URL not encoded (spaces cause issues)

**Solution:**
```python
# Generate SAS with clock skew buffer (start 15 min ago, expire 1 hour from now)
from datetime import datetime, timedelta

sas_token = generate_blob_sas(
    account_name=account_name,
    container_name=container_name,
    blob_name=blob_name,
    account_key=account_key,
    permission=BlobSasPermissions(read=True),
    start=datetime.utcnow() - timedelta(minutes=15),  # Clock skew buffer
    expiry=datetime.utcnow() + timedelta(hours=1)
)

# URL encode blob name (handles spaces)
from urllib.parse import quote
blob_name_encoded = quote(blob_name, safe='')
blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name_encoded}?{sas_token}"
```

---

### 5. Synapse Artifact Deployment Errors

**Symptom:** "Resource not found" or "Invalid reference" errors

**Root Causes:**
1. Folder names are plural (`linkedServices/` instead of `linkedService/`)
2. File name doesn't match resource name in JSON
3. Linked service not deployed before pipeline that references it

**Solution:**
```bash
# Correct folder structure (SINGULAR names)
src/synapse/
  ├── linkedService/       # Not linkedServices
  ├── pipeline/            # Not pipelines
  └── dataset/             # Not datasets

# File name MUST match JSON "name" field
# LS_AzureFunction.json:
{
  "name": "LS_AzureFunction",  // Must match filename
  "properties": { ... }
}

# Deploy in order (linked services first)
az synapse linked-service create --workspace-name <workspace> --name LS_KeyVault --file @src/synapse/linkedService/LS_KeyVault.json
az synapse linked-service create --workspace-name <workspace> --name LS_AzureFunction --file @src/synapse/linkedService/LS_AzureFunction.json
az synapse pipeline create --workspace-name <workspace> --name ProcessPDFs --file @src/synapse/pipeline/ProcessPDFsWithDocIntelligence.json
```

---

### 6. Key Vault Access Denied

**Symptom:** "The user, group or application does not have secrets get permission"

**Root Causes:**
1. Assigned `Key Vault Reader` (reads metadata only, not secret values)
2. RBAC role not propagated (can take 5-10 minutes)
3. Firewall blocking managed identity IP

**Solution:**
```bicep
// WRONG: Key Vault Reader (insufficient)
resource wrongRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '21090545-7ca7-4776-b22c-e363652d74d2')  // Key Vault Reader
  }
}

// CORRECT: Key Vault Secrets User
resource correctRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')  // Key Vault Secrets User
  }
}

// Verify role assignment
az role assignment list --assignee <managed-identity-object-id> --scope <key-vault-resource-id>

// Wait 10 minutes for propagation, then restart Function App
az functionapp restart --name func-doc-processing --resource-group rg-doc-processing
```

---

### 7. Function App Cold Starts

**Symptom:** First request after inactivity takes 10-20 seconds

**Root Cause:** Consumption Plan spins down instances after 20 minutes of inactivity

**Solutions:**
1. **Use Premium Plan:** No cold starts (always-on instances)
```bicep
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  sku: {
    name: 'EP1'  // Premium Plan
    tier: 'ElasticPremium'
  }
}
```
2. **Increase timeout in Synapse Web Activity:** Account for cold start delay
```json
{
  "timeout": "00:10:00"  // 10 minutes (includes cold start)
}
```
3. **Warm-up ping:** Synapse pipeline can include a warm-up call before ForEach loop

---

### 8. Cosmos DB Partition Key Mismatch

**Symptom:** `PartitionKey value must be supplied for this operation`

**Root Cause:** Document written without `sourceFile` field, but container has partition key `/sourceFile`

**Solution:**
```python
# Always include partition key in document
document = {
    "id": "folder_document_pdf",
    "sourceFile": "folder/document.pdf",  # Required!
    "fields": {...}
}
container.upsert_item(document)

# Point queries must also specify partition key
container.read_item(
    item="folder_document_pdf",
    partition_key="folder/document.pdf"  # Must match sourceFile value
)
```

---

### 9. Log Analytics Query Delays

**Symptom:** Recent logs not showing in queries

**Root Cause:** Log ingestion latency (1-5 minutes typical)

**Solution:**
```kql
// Use TimeGenerated >= ago(10m) to account for latency
requests
| where TimeGenerated >= ago(10m)
| where cloud_RoleName == "function-app-name"
| order by timestamp desc
```

---

### 10. Bicep Deployment Fails (Cross-RG Role Assignments)

**Symptom:** "The scope '/subscriptions/.../resourceGroups/rg-existing/providers/Microsoft.Storage/storageAccounts/storage' cannot perform write operation because following scope(s) are locked"

**Root Cause:** Attempting to create role assignment in RG with read-only lock

**Solution:**
```bicep
// Use subscription-level deployment for cross-RG role assignments
targetScope = 'subscription'

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-doc-processing'
  location: 'eastus'
}

// Reference existing storage in different RG
resource existingStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: 'existingstorage'
  scope: resourceGroup('rg-existing')  // Different RG
}

// Role assignment at subscription scope (bypasses RG lock)
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(existingStorage.id, functionApp.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: existingStorage  // Uses existing resource scope
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

---

## Sources

### Azure Functions
- [Python developer reference for Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Functions runtime versions overview](https://learn.microsoft.com/en-us/azure/azure-functions/functions-versions)
- [Pricing - Functions](https://azure.microsoft.com/en-us/pricing/details/functions/)
- [Azure Functions Premium plan](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan)

### Azure Document Intelligence
- [What's new in Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/whats-new?view=doc-intel-4.0.0)
- [Document Intelligence changelog, release history, and migration guide](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/versioning/changelog-release-history?view=doc-intel-4.0.0)
- [Document Intelligence Rest API Version-2024-02-29-preview](https://learn.microsoft.com/en-us/answers/questions/1614006/document-intelligence-rest-api-version-2024-02-29)

### Azure Cosmos DB
- [Pricing - Azure Cosmos DB](https://azure.microsoft.com/en-us/pricing/details/cosmos-db/autoscale-provisioned/)
- [Pricing Model for Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/how-pricing-works)
- [Azure Cosmos DB Lifetime Free Tier](https://learn.microsoft.com/en-us/azure/cosmos-db/free-tier)

### Azure Blob Storage
- [Security recommendations for Blob storage](https://learn.microsoft.com/en-us/azure/storage/blobs/security-recommendations)
- [Authorize access to blobs using Microsoft Entra ID](https://learn.microsoft.com/en-us/azure/storage/blobs/authorize-access-azure-active-directory)
- [Architecture Best Practices for Azure Blob Storage](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-blob-storage)

### Azure Key Vault
- [Grant permission to applications to access an Azure key vault using Azure RBAC](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide)
- [Secure your Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/security-features)
- [Migrate to Azure role-based access control](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-migration)

### Azure Synapse Analytics
- [Pricing - Azure Synapse Analytics](https://azure.microsoft.com/en-us/pricing/details/synapse-analytics/)
- [Cost management for serverless SQL pool](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/data-processed)
- [Batch Processing Triggered Pipeline Runs in Azure Synapse](https://endjin.com/blog/2025/10/batch-triggered-pipeline-runs-azure-synapse)
- [Analytics end-to-end with Azure Synapse](https://learn.microsoft.com/en-us/azure/architecture/example-scenario/dataplate2e/data-platform-end-to-end)

### Azure Log Analytics
- [Azure Monitor Logs cost calculations and options](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/cost-logs)
- [Pricing - Azure Monitor](https://azure.microsoft.com/en-us/pricing/details/monitor/)
- [Change pricing tier for Log Analytics workspace](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/change-pricing-tier)

### Azure Application Insights
- [Architecture Best Practices for Azure Monitor Application Insights](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/application-insights)
- [Application Insights OpenTelemetry observability overview](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
- [Azure Application Insights Best Practices](https://devblogs.microsoft.com/premier-developer/azure-application-insights-best-practices/)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-04
**Maintained By:** Azure Document Intelligence PDF Processing Pipeline Team
