# 🔌 Azure Functions API Reference

> **Complete API documentation for the PDF Processing Pipeline**

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Authentication](#-authentication)
- [Endpoints](#-endpoints)
  - [POST /api/process](#post-apiprocess)
  - [POST /api/reprocess/{blob_name}](#post-apireprocessblob_name)
  - [GET /api/status/{blob_name}](#get-apistatusblob_name)
  - [GET /api/status/batch/{blob_name}](#get-apistatusbatchblob_name)
  - [DELETE /api/documents/{blob_name}](#delete-apidocumentsblob_name)
  - [POST /api/batch](#post-apibatch)
  - [POST /api/process-multi](#post-apiprocess-multi)
  - [POST /api/estimate-cost](#post-apiestimate-cost)
  - [GET /api/health](#get-apihealth)
- [Error Handling](#-error-handling)
- [Rate Limiting](#-rate-limiting)
- [Webhooks](#-webhooks)

---

## 🎯 Overview

The Azure Functions API provides RESTful endpoints for PDF document processing using Azure Document Intelligence.

**Base URL:**
- Local: `http://localhost:7071/api`
- Azure: `https://<function-app-name>.azurewebsites.net/api`

**Content Type:** `application/json`

---

## 🔐 Authentication

All endpoints require a function key (except `/api/health`).

```bash
# Header authentication
curl -H "x-functions-key: YOUR_FUNCTION_KEY" \
  https://<function-app>/api/process

# Query string authentication
curl "https://<function-app>/api/process?code=YOUR_FUNCTION_KEY"
```

---

## 📋 Endpoints

### POST /api/process

Process a single PDF document through Document Intelligence.

**Request Body:**

```json
{
  "blobUrl": "https://storage.blob.core.windows.net/pdfs/incoming/document.pdf",
  "blobName": "incoming/document.pdf",
  "modelId": "custom-model-v1",
  "webhookUrl": "https://example.com/webhook"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `blobUrl` | string | Yes | Full URL to the PDF blob |
| `blobName` | string | Yes | Blob path within container |
| `modelId` | string | No | Document Intelligence model ID (default: `prebuilt-layout`) |
| `webhookUrl` | string | No | Webhook URL for completion notification |

**Response (200 OK):**

```json
{
  "status": "success",
  "documentId": "incoming_document_pdf",
  "processedAt": "2024-01-15T10:30:00Z",
  "formsProcessed": 3,
  "totalForms": 3,
  "originalPageCount": 6,
  "results": [
    {
      "formNumber": 1,
      "documentId": "incoming_document_pdf_form1",
      "pageRange": "1-2",
      "status": "success"
    }
  ]
}
```

**Errors:**

| Code | Description |
|------|-------------|
| 400 | Invalid request body or missing required fields |
| 429 | Rate limit exceeded |
| 500 | Document processing failed |

---

### POST /api/reprocess/{blob_name}

Reprocess a previously failed document.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `blob_name` | string | URL-encoded blob path |

**Request Body (optional):**

```json
{
  "modelId": "new-model-v2",
  "force": true,
  "webhookUrl": "https://example.com/webhook"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `modelId` | string | (from config) | Override model ID |
| `force` | boolean | false | Reprocess even if status is completed |
| `webhookUrl` | string | null | Webhook for completion notification |

**Response (200 OK):**

```json
{
  "status": "success",
  "processedAt": "2024-01-15T10:30:00Z",
  "formsProcessed": 3,
  "retryCount": 1
}
```

**Errors:**

| Code | Description |
|------|-------------|
| 404 | No documents found for blob_name |
| 409 | Document already completed (use force=true) |
| 410 | Max retries exceeded (document in dead letter) |

---

### GET /api/status/{blob_name}

Get processing status for a single document.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `blob_name` | string | URL-encoded blob path |

**Response (200 OK):**

```json
{
  "status": "completed",
  "documentId": "incoming_document_pdf",
  "sourceFile": "incoming/document.pdf",
  "processedAt": "2024-01-15T10:30:00Z",
  "formNumber": 1,
  "totalForms": 1
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `pending` | Awaiting processing |
| `processing` | Currently being processed |
| `completed` | Successfully processed |
| `failed` | Processing failed |
| `partial` | Some forms failed |

---

### GET /api/status/batch/{blob_name}

Get status of all forms from a multi-page PDF.

**Response (200 OK):**

```json
{
  "sourceFile": "incoming/document.pdf",
  "totalForms": 3,
  "completed": 2,
  "failed": 1,
  "pending": 0,
  "documents": [
    {
      "documentId": "incoming_document_pdf_form1",
      "formNumber": 1,
      "pageRange": "1-2",
      "status": "completed",
      "processedAt": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### DELETE /api/documents/{blob_name}

Delete processed documents and optionally split PDFs.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deleteSplits` | boolean | true | Delete split PDFs from _splits/ |
| `deleteOriginal` | boolean | false | Delete original PDF |

**Response (200 OK):**

```json
{
  "status": "success",
  "deletedDocuments": 3,
  "deletedBlobs": 3,
  "errors": []
}
```

---

### POST /api/batch

Process multiple PDFs in a single request.

**Request Body:**

```json
{
  "blobs": [
    {"blobUrl": "https://...", "blobName": "doc1.pdf"},
    {"blobUrl": "https://...", "blobName": "doc2.pdf"}
  ],
  "modelId": "custom-model-v1",
  "webhookUrl": "https://example.com/webhook",
  "parallel": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blobs` | array | (required) | List of blobs (max 50) |
| `modelId` | string | (from config) | Model ID for all blobs |
| `webhookUrl` | string | null | Webhook for batch completion |
| `parallel` | boolean | true | Process in parallel or sequentially |

**Response (200 OK):**

```json
{
  "status": "partial",
  "batchId": "batch_20240115_103000",
  "totalBlobs": 5,
  "processed": 4,
  "failed": 1,
  "results": [
    {
      "blobName": "doc1.pdf",
      "status": "success",
      "formsProcessed": 3,
      "documentId": "doc1_pdf"
    }
  ]
}
```

---

### POST /api/process-multi

Process a PDF using different models for different page ranges.

**Request Body:**

```json
{
  "blobUrl": "https://storage.blob.core.windows.net/pdfs/document.pdf",
  "blobName": "document.pdf",
  "modelMapping": {
    "1-2": "form-type-a-model",
    "3-4": "form-type-b-model",
    "5-6": "form-type-c-model"
  },
  "webhookUrl": "https://example.com/webhook"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `blobUrl` | string | Yes | Full URL to the PDF blob |
| `blobName` | string | Yes | Blob path within container |
| `modelMapping` | object | Yes | Page ranges to model IDs |
| `webhookUrl` | string | No | Webhook for completion |

**Response (200 OK):**

```json
{
  "status": "success",
  "processedAt": "2024-01-15T10:30:00Z",
  "pageCount": 6,
  "rangesProcessed": 3,
  "totalRanges": 3,
  "results": [
    {
      "pageRange": "1-2",
      "modelId": "form-type-a-model",
      "documentId": "document_pdf_pages1-2",
      "status": "success"
    }
  ]
}
```

---

### POST /api/estimate-cost

Estimate processing costs before running extraction.

**Request Body:**

```json
{
  "blobUrl": "https://storage.blob.core.windows.net/pdfs/document.pdf",
  "pageCount": 50,
  "modelId": "custom-model-v1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `blobUrl` | string | No* | URL to PDF for page count |
| `pageCount` | integer | No* | Manual page count (1-10000) |
| `modelId` | string | No | Model ID for pricing tier |

*Either `blobUrl` or `pageCount` is required.

**Response (200 OK):**

```json
{
  "pageCount": 50,
  "formsCount": 25,
  "modelType": "custom",
  "pricing": {
    "readCostPerPage": 0.001,
    "analysisCostPerPage": 0.01,
    "currency": "USD"
  },
  "estimatedCostUsd": 0.55,
  "notes": [
    "Pricing based on Azure Document Intelligence standard tier",
    "Custom models: $10.00/1000 pages"
  ]
}
```

---

### GET /api/health

Health check endpoint with service status.

**Response (200 OK):**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "2.0.0",
  "services": {
    "storage": "healthy",
    "config": "healthy",
    "doc_intel": "configured",
    "cosmos": "configured"
  },
  "blobTrigger": {
    "status": "healthy",
    "container": "pdfs",
    "path": "incoming/",
    "pendingFiles": 5
  }
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `healthy` | All services operational |
| `degraded` | Some services unavailable |
| `unhealthy` | Critical services down |

---

## ⚠️ Error Handling

All errors return a consistent JSON structure:

```json
{
  "status": "error",
  "error": "Error message description",
  "details": {
    "blobName": "document.pdf",
    "validation_errors": [
      {
        "field": "blobUrl",
        "message": "field required",
        "type": "missing"
      }
    ]
  }
}
```

**HTTP Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (validation errors) |
| 401 | Unauthorized (missing function key) |
| 403 | Forbidden (invalid function key) |
| 404 | Not Found |
| 409 | Conflict (already exists) |
| 410 | Gone (max retries exceeded) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |

---

## 🚦 Rate Limiting

The API implements rate limiting to protect against abuse:

| Endpoint | Limit | Burst |
|----------|-------|-------|
| Default | 60/min | 10 |
| `/api/reprocess` | 10/min | 3 |
| `/api/batch` | 5/min | 2 |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705320600
Retry-After: 30
```

---

## 🔔 Webhooks

When `webhookUrl` is provided, a POST request is sent on completion:

```json
{
  "event": "document.processed",
  "sourceFile": "incoming/document.pdf",
  "status": "completed",
  "processedAt": "2024-01-15T10:30:00Z",
  "formsProcessed": 3,
  "totalForms": 3,
  "documentIds": [
    "incoming_document_pdf_form1",
    "incoming_document_pdf_form2",
    "incoming_document_pdf_form3"
  ]
}
```

**Webhook Requirements:**
- Must accept POST requests
- Should return 2xx status
- Timeout: 30 seconds
- Retries: 3 with exponential backoff

---

## 📝 Examples

### cURL Examples

```bash
# Process a document
curl -X POST "https://<function-app>/api/process?code=<key>" \
  -H "Content-Type: application/json" \
  -d '{
    "blobUrl": "https://storage.blob.core.windows.net/pdfs/incoming/doc.pdf",
    "blobName": "incoming/doc.pdf"
  }'

# Check status
curl "https://<function-app>/api/status/incoming%2Fdoc.pdf?code=<key>"

# Batch process
curl -X POST "https://<function-app>/api/batch?code=<key>" \
  -H "Content-Type: application/json" \
  -d '{
    "blobs": [
      {"blobUrl": "https://...", "blobName": "doc1.pdf"},
      {"blobUrl": "https://...", "blobName": "doc2.pdf"}
    ],
    "parallel": true
  }'
```

### Python Example

```python
import requests

API_URL = "https://<function-app>.azurewebsites.net/api"
API_KEY = "your-function-key"

# Process a document
response = requests.post(
    f"{API_URL}/process",
    headers={"x-functions-key": API_KEY},
    json={
        "blobUrl": "https://storage.blob.core.windows.net/pdfs/incoming/doc.pdf",
        "blobName": "incoming/doc.pdf",
        "modelId": "custom-model-v1"
    }
)

result = response.json()
print(f"Status: {result['status']}, Forms: {result['formsProcessed']}")
```

---

*Last Updated: December 2024*
*API Version: 2.0.0*
