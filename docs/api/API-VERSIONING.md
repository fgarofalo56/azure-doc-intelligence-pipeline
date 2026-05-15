# API Versioning Strategy

This document explains the API versioning strategy, deprecation policy, and migration guidelines for the Document Processing Pipeline.

## Overview

The API uses **URL path versioning** with semantic versioning principles. All endpoints include a version prefix in the URL path.

```
https://<function-app>.azurewebsites.net/api/{version}/{endpoint}
```

Example: `https://myapp.azurewebsites.net/api/v1/process`

## Current Versions

| Version | Status | Release Date | Notes |
|---------|--------|--------------|-------|
| **v1** | Current | 2025-01-01 | Initial stable release |

## Version Lifecycle

Each API version follows a defined lifecycle:

```
Preview → Current → Deprecated → Sunset
```

### Stages

1. **Preview**: Beta version for testing (may have breaking changes)
2. **Current**: Recommended stable version
3. **Deprecated**: Supported but scheduled for removal
4. **Sunset**: No longer available

### Support Timeline

- **Preview**: 3 months before GA
- **Current**: Indefinite (until next major version)
- **Deprecated**: Minimum 6 months notice before sunset
- **Migration Period**: 3-6 months between deprecation and sunset

## Response Headers

All API responses include version headers:

| Header | Description | Example |
|--------|-------------|---------|
| `X-API-Version` | Version used for request | `v1` |
| `X-API-Current-Version` | Latest recommended version | `v1` |
| `Deprecation` | Present if version deprecated | `true` |
| `Sunset` | Date when version will be removed | `2025-12-31` |
| `X-API-Deprecation-Notice` | Human-readable deprecation message | See example below |

### Example Deprecated Response Headers

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-API-Version: v1
X-API-Current-Version: v2
Deprecation: true
Sunset: 2025-12-31
X-API-Deprecation-Notice: API version v1 is deprecated and will be removed on 2025-12-31. Please migrate to v2.
```

## Making Requests

### Specify Version in URL Path

```bash
# Explicit version (recommended)
curl https://myapp.azurewebsites.net/api/v1/process

# Version must be included in path
curl https://myapp.azurewebsites.net/api/v1/health
```

### Version Not Found

If an unsupported version is requested:

```json
{
  "status": "error",
  "error": "Unsupported API version",
  "apiVersion": "v99",
  "details": {
    "requestedVersion": "v99",
    "supportedVersions": ["v1"],
    "currentVersion": "v1"
  }
}
```

## Deprecation Policy

### What Triggers Deprecation?

- Major version release with breaking changes
- Security concerns requiring architectural changes
- Significant performance improvements in new version

### Deprecation Notice

When a version is deprecated:

1. **Announcement**: Blog post and changelog update
2. **Headers**: Deprecation headers added to responses
3. **Logs**: Warning logged for each deprecated endpoint call
4. **Documentation**: Migration guide published

### Breaking vs Non-Breaking Changes

**Non-breaking (added without version bump):**
- New optional fields in requests
- New fields in responses
- New endpoints
- New optional headers

**Breaking (requires new version):**
- Removing fields from requests/responses
- Changing field types or formats
- Removing endpoints
- Changing authentication methods
- Semantic changes to existing fields

## Migration Guide Template

When a new version is released, a migration guide will include:

### 1. Summary of Changes

```markdown
## v1 → v2 Migration

### Breaking Changes
- `processedDate` renamed to `processedAt` (ISO 8601 format)
- `formNumber` now zero-indexed (was one-indexed)

### New Features
- Batch processing endpoint: POST /api/v2/batch
- Async webhooks: new `webhookUrl` parameter

### Deprecated Features
- `customModel` parameter (use `modelId` instead)
```

### 2. Field Mapping

| v1 Field | v2 Field | Notes |
|----------|----------|-------|
| `processedDate` | `processedAt` | ISO 8601 format |
| `formNumber` | `formIndex` | Now zero-indexed |
| `customModel` | `modelId` | Name changed |

### 3. Code Examples

```python
# v1 (deprecated)
response = requests.post(
    "https://myapp.azurewebsites.net/api/v1/process",
    json={"blobUrl": url, "customModel": "model-1"}
)
result = response.json()
form_num = result["formNumber"]  # 1-indexed

# v2 (current)
response = requests.post(
    "https://myapp.azurewebsites.net/api/v2/process",
    json={"blobUrl": url, "modelId": "model-1"}
)
result = response.json()
form_idx = result["formIndex"]  # 0-indexed
```

## Version-Specific Features

### v1 Features

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/process` | POST | Process single document |
| `/api/v1/batch` | POST | Process multiple documents |
| `/api/v1/results/{id}` | GET | Get processing results |
| `/api/v1/status/{id}` | GET | Get job status |
| `/api/v1/health` | GET | Health check |
| `/api/v1/health/deep` | GET | Deep health check |
| `/api/v1/dlq/stats` | GET | Dead letter queue stats |

### v1 Request/Response Schema

See [Function API Documentation](function-api.md) for complete schema details.

## Best Practices for Clients

### 1. Always Specify Version

```python
# Good - explicit version
API_VERSION = "v1"
url = f"https://myapp.azurewebsites.net/api/{API_VERSION}/process"

# Bad - no version (may break)
url = "https://myapp.azurewebsites.net/api/process"
```

### 2. Check Response Headers

```python
response = requests.post(url, json=data)
if response.headers.get("Deprecation") == "true":
    sunset = response.headers.get("Sunset")
    logging.warning(f"API version deprecated, sunset: {sunset}")
```

### 3. Handle Version Errors

```python
if response.status_code == 400:
    error = response.json()
    if error.get("error") == "Unsupported API version":
        # Fall back to supported version
        supported = error["details"]["supportedVersions"]
        retry_with_version(supported[0])
```

### 4. Test Against Preview Versions

Before a new version goes current, test your integration:

```python
# Test in non-production
PREVIEW_VERSION = "v2-preview"
test_url = f"https://myapp-dev.azurewebsites.net/api/{PREVIEW_VERSION}/process"
```

## Implementation Details

### Server-Side Version Handling

The API uses a `version_gate` decorator for endpoint constraints:

```python
@version_gate(min_version="v1", deprecated_in="v2")
async def process_document(version: str, ...):
    # Endpoint available from v1, deprecated in v2
    pass
```

### Version Registry

Version metadata is maintained in `services/api_versioning.py`:

```python
VERSION_REGISTRY = {
    "v1": VersionInfo(
        version="v1",
        is_current=True,
        is_deprecated=False,
        release_date="2025-01-01",
        changelog=[
            "Initial stable API release",
            "Document processing endpoints",
            "Batch processing support",
        ],
    ),
}
```

## Authentication Strategy

### Primary Authentication: Azure Function Keys

This API uses **Azure Functions built-in authentication** as the primary auth mechanism. All endpoints require one of the following:

1. **Function Key (per-function)**: Grants access to a specific function
2. **Host Key**: Grants access to all functions in the Function App
3. **Master Key**: Admin access (should be protected)

#### Providing Function Keys

```bash
# Option 1: Query parameter (recommended for testing)
curl "https://myapp.azurewebsites.net/api/v1/process?code=YOUR_FUNCTION_KEY"

# Option 2: Header (recommended for production)
curl -H "x-functions-key: YOUR_FUNCTION_KEY" \
     "https://myapp.azurewebsites.net/api/v1/process"
```

#### Getting Function Keys

1. **Azure Portal**: Function App → Functions → Select Function → Function Keys
2. **Azure CLI**: `az functionapp function keys list --name <app-name> --function-name <func-name>`
3. **Key Vault**: Production deployments should store keys in Key Vault

### Rate Limiting

Sensitive endpoints have built-in rate limiting to prevent abuse:

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| `/api/process` | 100 req | 1 minute |
| `/api/reprocess/*` | 30 req | 1 minute |
| `/api/batch` | 10 req | 1 minute |
| `/api/jobs` | 50 req | 1 minute |

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699999999
```

When rate limited, you'll receive:

```json
{
  "status": "error",
  "error": "Rate limit exceeded",
  "retry_after": "60"
}
```

### Optional Secondary Authentication: API Key Header

For additional security layers (e.g., tenant isolation), the API supports an optional `X-API-Key` header:

```bash
# With additional API key (when configured)
curl -H "x-functions-key: FUNCTION_KEY" \
     -H "X-API-Key: TENANT_API_KEY" \
     "https://myapp.azurewebsites.net/api/v1/tenants/123/documents"
```

Set `API_KEY` environment variable to enable this layer. If not set, the decorator is bypassed.

### Security Best Practices

1. **Never expose Function Keys in client-side code**
2. **Use HTTPS only** (enforced by Azure Functions)
3. **Rotate keys regularly** (recommended: every 90 days)
4. **Use Key Vault** for production key storage
5. **Monitor for suspicious activity** via Application Insights
6. **Apply IP restrictions** for internal APIs via VNet integration

### Middleware Decorators

The API provides three middleware decorators in `middleware.py`:

| Decorator | Purpose | Usage |
|-----------|---------|-------|
| `@validate_request(Model)` | Request body validation via Pydantic | Applied to POST endpoints |
| `@rate_limit(endpoint="name")` | Per-endpoint rate limiting | Applied to sensitive endpoints |
| `@require_auth()` | Optional X-API-Key authentication | Applied to tenant-specific endpoints |

Example usage:

```python
from middleware import validate_request, rate_limit

@rate_limit(endpoint="batch")
@validate_request(BatchProcessRequest)
async def batch_process(req: func.HttpRequest, validated: BatchProcessRequest):
    # validated contains type-safe request data
    pass
```

## FAQ

### Q: What happens if I don't specify a version?

Currently, requests without a version prefix will fail. Always include the version in your URL path.

### Q: How long will deprecated versions be supported?

Minimum 6 months from deprecation announcement. Check the `Sunset` header for exact date.

### Q: Will my integration break immediately when a new version is released?

No. New versions are additive. Your existing v1 integration will continue to work until the sunset date.

### Q: How do I get notified of deprecations?

1. Monitor the `Deprecation` response header
2. Subscribe to repository releases
3. Check the changelog regularly

### Q: Can I request an extension for migration?

Contact the team before the sunset date. Extensions may be granted for enterprise customers with valid migration concerns.
