# 🔧 Troubleshooting Guide

> **Common issues and solutions for the PDF Processing Pipeline**

---

## 📑 Table of Contents

- [Quick Diagnostics](#-quick-diagnostics)
- [Document Intelligence Issues](#-document-intelligence-issues)
- [Cosmos DB Issues](#-cosmos-db-issues)
- [Storage Issues](#-storage-issues)
- [Function App Issues](#-function-app-issues)
- [Synapse Pipeline Issues](#-synapse-pipeline-issues)
- [Performance Issues](#-performance-issues)
- [Debugging Tools](#-debugging-tools)

---

## 🔍 Quick Diagnostics

### Health Check

```bash
# Check overall system health
curl https://<function-app>.azurewebsites.net/api/health

# Expected response
{
  "status": "healthy",
  "services": {
    "storage": "healthy",
    "config": "healthy",
    "doc_intel": "configured",
    "cosmos": "configured"
  },
  "blobTrigger": {
    "status": "healthy",
    "pendingFiles": 5
  }
}
```

### Quick Status Check

| Check | Command |
|-------|---------|
| Function App status | `az functionapp show --name <app> --query state` |
| Recent errors | `az monitor activity-log list --resource-group <rg> --status Failed` |
| Function logs | `az functionapp log tail --name <app> --resource-group <rg>` |

---

## 🤖 Document Intelligence Issues

### Error: 429 Rate Limit Exceeded

**Symptoms:**
- `HttpResponseError: 429 Too Many Requests`
- Processing slows down significantly

**Causes:**
- Exceeding 15 TPS limit
- Synapse ForEach parallelism too high

**Solutions:**

```python
# 1. Reduce concurrency in function_app.py
semaphore = asyncio.Semaphore(3)  # Reduce from 10 to 3

# 2. Reduce Synapse ForEach batch count
# In pipeline JSON:
"batchCount": 5  # Reduce from default
```

```bash
# 3. Check current rate limit
az cognitiveservices account show \
  --name <doc-intel-resource> \
  --resource-group <rg> \
  --query "properties.quotaLimit"
```

---

### Error: 403 Forbidden on Blob URL

**Symptoms:**
- `HttpResponseError: 403 Forbidden`
- "Cannot access source document"

**Causes:**
- SAS token expired
- Storage account firewall blocking access
- Document Intelligence cannot access private blobs

**Solutions:**

```python
# 1. Check SAS token generation
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
```

```bash
# 2. Check storage firewall
az storage account show \
  --name <storage-account> \
  --query "networkRuleSet.defaultAction"

# If "Deny", add exception for Azure services
az storage account update \
  --name <storage-account> \
  --default-action Allow
```

---

### Error: Model Not Found

**Symptoms:**
- `DocumentProcessingError: Model not found`
- Custom model returns 404

**Causes:**
- Model ID typo
- Model in different region
- Model not yet trained

**Solutions:**

```bash
# 1. List available models
az cognitiveservices account model list \
  --name <doc-intel-resource> \
  --resource-group <rg>

# 2. Check model status in Studio
# Visit: https://documentintelligence.ai.azure.com/studio
```

---

### Error: Low Confidence Scores

**Symptoms:**
- Fields extracted but confidence < 0.5
- Missing fields in output

**Causes:**
- Poor document quality
- Model not trained on similar documents
- Wrong model for document type

**Solutions:**

1. **Improve document quality:**
   - Scan at 300 DPI minimum
   - Ensure good contrast
   - Avoid skewed documents

2. **Retrain model:**
   - Add more training samples
   - Include edge cases
   - Label consistently

3. **Use appropriate model:**
   - Prebuilt for standard documents
   - Custom template for fixed layouts
   - Custom neural for variable layouts

---

## 🗄️ Cosmos DB Issues

### Error: 404 Database/Container Not Found

**Symptoms:**
- `CosmosError: Database not found`
- `ResourceNotFoundError: Container does not exist`

**Solutions:**

```bash
# 1. Create database
az cosmosdb sql database create \
  --account-name <cosmos-account> \
  --name DocumentsDB \
  --resource-group <rg>

# 2. Create container
az cosmosdb sql container create \
  --account-name <cosmos-account> \
  --database-name DocumentsDB \
  --name ExtractedData \
  --partition-key-path /sourceFile \
  --resource-group <rg>
```

---

### Error: 429 Request Rate Too Large

**Symptoms:**
- `CosmosError: 429 Request rate is large`
- High RU consumption

**Causes:**
- Cross-partition queries
- Insufficient RU/s provisioned
- No partition key in queries

**Solutions:**

```python
# 1. Always filter by partition key
query = "SELECT * FROM c WHERE c.sourceFile = @sourceFile"
```

```bash
# 2. Increase RU/s
az cosmosdb sql container throughput update \
  --account-name <cosmos-account> \
  --database-name DocumentsDB \
  --name ExtractedData \
  --throughput 1000
```

---

### Error: 403 Forbidden

**Symptoms:**
- `CosmosError: 403 Forbidden`
- "Request blocked by Cosmos DB firewall"

**Causes:**
- RBAC not configured
- IP not whitelisted
- Managed Identity not assigned

**Solutions:**

```bash
# 1. Assign RBAC role
az cosmosdb sql role assignment create \
  --account-name <cosmos-account> \
  --resource-group <rg> \
  --principal-id <function-app-principal-id> \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --scope "/"

# 2. Allow Azure services
az cosmosdb update \
  --name <cosmos-account> \
  --resource-group <rg> \
  --enable-public-network-access true
```

---

## 📦 Storage Issues

### Error: Blob Not Found

**Symptoms:**
- `BlobServiceError: Blob not found`
- 404 when accessing blob

**Solutions:**

```bash
# 1. Verify blob exists
az storage blob exists \
  --account-name <storage-account> \
  --container-name pdfs \
  --name incoming/document.pdf

# 2. Check container name
az storage container list \
  --account-name <storage-account> \
  --output table
```

---

### Error: SAS Token Invalid

**Symptoms:**
- `AuthenticationFailed: Server failed to authenticate`
- SAS token rejected

**Causes:**
- Clock skew
- Wrong permissions
- Expired token

**Solutions:**

```python
# Add clock skew buffer to SAS generation
start=datetime.utcnow() - timedelta(minutes=15)
expiry=datetime.utcnow() + timedelta(hours=1)
```

---

## ⚡ Function App Issues

### Error: Function Timeout

**Symptoms:**
- `Function execution timed out`
- Large PDFs fail

**Solutions:**

```json
// host.json - increase timeout
{
  "functionTimeout": "00:10:00"
}
```

```bash
# For consumption plan, max is 10 minutes
# For premium plan, can be unlimited
az functionapp config set \
  --name <function-app> \
  --resource-group <rg> \
  --function-app-scale-limit 200
```

---

### Error: Cold Start Delays

**Symptoms:**
- First request takes 10+ seconds
- Intermittent slow responses

**Solutions:**

1. **Enable Always On (Premium/Dedicated):**
   ```bash
   az functionapp config set \
     --name <function-app> \
     --resource-group <rg> \
     --always-on true
   ```

2. **Pre-warm instances:**
   ```bash
   # Set minimum instances
   az functionapp plan update \
     --name <app-service-plan> \
     --resource-group <rg> \
     --min-instances 1
   ```

---

### Error: Missing Environment Variable

**Symptoms:**
- `ConfigurationError: Missing required environment variables`
- Function fails on startup

**Solutions:**

```bash
# 1. List current settings
az functionapp config appsettings list \
  --name <function-app> \
  --resource-group <rg> \
  --output table

# 2. Add missing setting
az functionapp config appsettings set \
  --name <function-app> \
  --resource-group <rg> \
  --settings "DOC_INTEL_ENDPOINT=https://..."
```

---

## 🔄 Synapse Pipeline Issues

### Error: Web Activity Timeout

**Symptoms:**
- Pipeline fails after 1 minute
- Large PDFs timeout

**Solution:**

```json
// In pipeline JSON, increase timeout
{
  "type": "WebActivity",
  "typeProperties": {
    "timeout": "00:10:00"
  }
}
```

---

### Error: Function Key Not Found

**Symptoms:**
- `401 Unauthorized` from Function App
- Key Vault secret not accessible

**Solutions:**

```bash
# 1. Verify secret exists
az keyvault secret show \
  --vault-name <keyvault> \
  --name FunctionAppHostKey

# 2. Check Synapse managed identity access
az keyvault set-policy \
  --name <keyvault> \
  --object-id <synapse-identity> \
  --secret-permissions get list
```

---

### Error: Artifact Deployment Failed

**Symptoms:**
- Pipeline import fails
- "Invalid JSON" error

**Causes:**
- Plural folder names (linkedServices/ instead of linkedService/)
- Resource name mismatch

**Solutions:**

```bash
# Verify folder structure uses SINGULAR names
ls src/synapse/
# Should show: linkedService/ pipeline/ dataset/ notebook/

# Verify file name matches resource name
cat src/synapse/linkedService/LS_KeyVault.json | jq '.name'
# Should output: "LS_KeyVault"
```

---

## 🚀 Performance Issues

### Slow Document Processing

**Diagnosis:**

```kql
// Check processing times in App Insights
requests
| where name contains "ProcessDocument"
| summarize percentile(duration, 95), avg(duration) by bin(timestamp, 1h)
| render timechart
```

**Solutions:**

| Issue | Solution |
|-------|----------|
| Large PDFs | Split before processing |
| High concurrency | Reduce semaphore limit |
| Network latency | Use same region for all services |
| Cold starts | Enable Always On |

---

### High Cosmos DB RU Usage

**Diagnosis:**

```kql
// Check RU consumption
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| summarize sum(requestCharge_d) by bin(TimeGenerated, 1h)
```

**Solutions:**

1. Add indexes for frequently queried fields
2. Always filter by partition key
3. Increase provisioned RU/s
4. Use point reads instead of queries

---

## 🔧 Debugging Tools

### Azure CLI Commands

```bash
# Function logs (live)
az functionapp log tail --name <app> --resource-group <rg>

# Recent function invocations
az monitor app-insights query \
  --app <app-insights-name> \
  --analytics-query "requests | take 10"

# Check for errors
az monitor activity-log list \
  --resource-group <rg> \
  --status Failed \
  --max-events 20
```

### KQL Queries

```kql
// Find failed requests
requests
| where success == false
| project timestamp, name, resultCode, duration
| order by timestamp desc

// Check Document Intelligence errors
traces
| where message contains "DocumentAnalysisError"
| project timestamp, message, severityLevel

// Monitor rate limiting
traces
| where message contains "429" or message contains "Rate limit"
| summarize count() by bin(timestamp, 5m)
```

### Local Debugging

```bash
# Run with debug logging
LOG_LEVEL=DEBUG func start

# Test single endpoint
curl -X POST http://localhost:7071/api/process \
  -H "Content-Type: application/json" \
  -d '{"blobUrl": "...", "blobName": "test.pdf"}' \
  -v
```

---

## 📞 Getting Help

1. **Check logs first:** Most issues are visible in Application Insights
2. **Review CLAUDE.md:** Contains common gotchas and patterns
3. **Search issues:** Check GitHub issues for similar problems
4. **Open new issue:** Include logs, error messages, and reproduction steps

---

*Last Updated: December 2024*
