# Azure Document Intelligence Python SDK - Implementation Patterns

**Last Updated:** 2025-12-02
**SDK Version:** azure-ai-documentintelligence 1.0.2+
**API Version:** 2024-11-30 (GA)
**Python Version:** 3.10+

## Quick Reference

```python
# Installation
pip install azure-ai-documentintelligence
pip install aiohttp  # For async support

# Environment Variables Required
DOCUMENTINTELLIGENCE_ENDPOINT=https://YOUR_RESOURCE.cognitiveservices.azure.com
DOCUMENTINTELLIGENCE_API_KEY=YOUR_KEY
```

---

## 1. Custom Model Analysis with begin_analyze_document()

### Basic Sync Pattern

```python
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult

# Initialize client
endpoint = os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"]
key = os.environ["DOCUMENTINTELLIGENCE_API_KEY"]
model_id = "your-custom-model-id"

client = DocumentIntelligenceClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(key)
)

# Analyze from local file
with open("path/to/document.pdf", "rb") as f:
    poller = client.begin_analyze_document(
        model_id=model_id,
        body=f
    )
    result: AnalyzeResult = poller.result()  # Blocks until complete

# Analyze from URL (requires SAS token for private blobs)
poller = client.begin_analyze_document(
    model_id=model_id,
    analyze_request=AnalyzeDocumentRequest(url_source=blob_url_with_sas)
)
result: AnalyzeResult = poller.result()
```

### Async Pattern (Recommended for Concurrent Processing)

```python
import asyncio
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

async def analyze_document_async(blob_url: str, model_id: str) -> dict:
    """Async document analysis with proper resource cleanup."""
    endpoint = os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"]
    key = os.environ["DOCUMENTINTELLIGENCE_API_KEY"]

    async with DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    ) as client:
        poller = await client.begin_analyze_document(
            model_id=model_id,
            analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
        )
        result = await poller.result()
        return result

# Process multiple documents concurrently
async def process_batch(urls: list[str], model_id: str):
    tasks = [analyze_document_async(url, model_id) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Long-Running Operation Pattern

```python
# Check operation status without blocking
poller = client.begin_analyze_document(model_id, body=file)

# Poll with timeout
import time
timeout_seconds = 300  # 5 minutes
start_time = time.time()

while not poller.done():
    if time.time() - start_time > timeout_seconds:
        raise TimeoutError("Document analysis exceeded timeout")
    time.sleep(10)  # Poll every 10 seconds
    status = poller.status()
    print(f"Status: {status}")

result = poller.result()
```

---

## 2. Field Extraction from AnalyzeResult

### Basic Field Access Pattern

```python
def extract_fields(result: AnalyzeResult) -> dict[str, Any]:
    """Extract fields from Document Intelligence result."""
    extracted_data = {}

    if not result.documents:
        return extracted_data

    for document in result.documents:
        print(f"Document type: {document.doc_type}")
        print(f"Overall confidence: {document.confidence}")

        if not document.fields:
            continue

        for field_name, field_value in document.fields.items():
            # Extract value based on type
            value = extract_field_value(field_value)
            confidence = field_value.get("confidence", 0.0)

            extracted_data[field_name] = {
                "value": value,
                "confidence": confidence,
                "type": field_value.get("type")
            }

    return extracted_data
```

### Field Type Handling

```python
from typing import Any

def extract_field_value(field: dict) -> Any:
    """Extract value from field based on type."""
    # String fields
    if field.get("valueString"):
        return field["valueString"]

    # Number fields
    if field.get("valueNumber") is not None:
        return field["valueNumber"]

    # Date fields
    if field.get("valueDate"):
        return field["valueDate"]

    # Time fields
    if field.get("valueTime"):
        return field["valueTime"]

    # Currency fields (complex type)
    if field.get("valueCurrency"):
        currency = field["valueCurrency"]
        return {
            "amount": currency.get("amount"),
            "currencyCode": currency.get("currencyCode", "USD")
        }

    # Address fields
    if field.get("valueAddress"):
        address = field["valueAddress"]
        return {
            "streetAddress": address.get("streetAddress"),
            "city": address.get("city"),
            "state": address.get("state"),
            "postalCode": address.get("postalCode"),
            "country": address.get("country")
        }

    # Array/List fields
    if field.get("valueArray"):
        return [extract_field_value(item) for item in field["valueArray"]]

    # Object fields (nested)
    if field.get("valueObject"):
        obj = field["valueObject"]
        return {
            key: extract_field_value(val)
            for key, val in obj.items()
        }

    # Fallback to content
    return field.get("content")

# Example: Invoice Items Extraction
def extract_invoice_items(invoice_fields: dict) -> list[dict]:
    """Extract line items from invoice."""
    items = invoice_fields.get("Items")
    if not items or not items.get("valueArray"):
        return []

    line_items = []
    for item in items["valueArray"]:
        obj = item.get("valueObject", {})

        # Extract unit price with currency
        unit_price = obj.get("UnitPrice", {})
        currency_data = unit_price.get("valueCurrency", {})

        line_item = {
            "description": obj.get("Description", {}).get("content", ""),
            "quantity": obj.get("Quantity", {}).get("valueNumber", 0),
            "unit_price": currency_data.get("amount", 0.0),
            "currency_code": currency_data.get("currencyCode", "USD"),
            "amount": obj.get("Amount", {}).get("valueCurrency", {}).get("amount", 0.0)
        }
        line_items.append(line_item)

    return line_items
```

### Confidence Thresholds

```python
def validate_extraction(fields: dict, min_confidence: float = 0.7) -> tuple[dict, list[str]]:
    """Validate extracted fields meet confidence threshold."""
    validated = {}
    low_confidence_fields = []

    for field_name, field_data in fields.items():
        confidence = field_data.get("confidence", 0.0)

        if confidence >= min_confidence:
            validated[field_name] = field_data["value"]
        else:
            low_confidence_fields.append(
                f"{field_name} (confidence: {confidence:.2f})"
            )

    return validated, low_confidence_fields
```

---

## 3. Error Handling and Retry Patterns

### Exception Hierarchy

```python
from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ClientAuthenticationError,
    ResourceNotFoundError,
    ServiceRequestError,
)

def handle_document_intelligence_errors(func):
    """Decorator for comprehensive error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientAuthenticationError as e:
            print(f"Authentication failed: {e.message}")
            # Check credentials/key vault
            raise
        except ResourceNotFoundError as e:
            print(f"Resource not found: {e.message}")
            # Check model_id or blob URL
            raise
        except HttpResponseError as e:
            if e.status_code == 429:
                print("Rate limit exceeded (429)")
                # Implement retry with backoff
                raise RateLimitError(f"TPS limit reached: {e.message}") from e
            elif e.status_code == 408:
                print("Request timeout (408)")
                # Document too large or service issue
                raise TimeoutError(f"Operation timed out: {e.message}") from e
            else:
                print(f"HTTP error {e.status_code}: {e.message}")
                raise
        except ServiceRequestError as e:
            print(f"Network error: {e.message}")
            # Retry with exponential backoff
            raise
        except AzureError as e:
            print(f"Azure SDK error: {e.message}")
            raise
    return wrapper
```

### Exponential Backoff Retry Pattern

```python
import time
import random
from functools import wraps

class RateLimitError(Exception):
    """Custom exception for rate limiting."""
    pass

def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """Decorator implementing exponential backoff retry logic."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except HttpResponseError as e:
                    if e.status_code == 429:
                        # Check for Retry-After header
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            delay = float(retry_after)

                        if attempt == max_retries - 1:
                            raise RateLimitError(
                                f"Rate limit exceeded after {max_retries} retries"
                            ) from e

                        # Add jitter to prevent thundering herd
                        if jitter:
                            delay_with_jitter = delay * (0.5 + random.random())
                        else:
                            delay_with_jitter = delay

                        print(f"Rate limited. Retrying in {delay_with_jitter:.2f}s "
                              f"(attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay_with_jitter)

                        # Exponential backoff
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        raise
                except (ServiceRequestError, TimeoutError) as e:
                    if attempt == max_retries - 1:
                        raise

                    print(f"Transient error. Retrying in {delay:.2f}s")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise Exception(f"Operation failed after {max_retries} retries")
        return wrapper
    return decorator

# Usage
@retry_with_exponential_backoff(max_retries=5, initial_delay=2.0)
def analyze_with_retry(client, model_id: str, file_path: str):
    """Analyze document with automatic retry on rate limits."""
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document(model_id=model_id, body=f)
        return poller.result()
```

### Custom Retry Policy

```python
from azure.core.pipeline.policies import RetryPolicy

# Create custom retry policy
retry_policy = RetryPolicy(
    retry_total=5,                # Maximum retry attempts
    retry_backoff_factor=2,       # Exponential backoff factor
    retry_backoff_max=60,         # Maximum backoff time (seconds)
    retry_on_status_codes=[408, 429, 500, 502, 503, 504]
)

# Apply to client (advanced usage)
from azure.core.pipeline import Pipeline
from azure.core.pipeline.transport import RequestsTransport

client = DocumentIntelligenceClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(key),
    transport=RequestsTransport(),
    retry_policy=retry_policy
)
```

---

## 4. SAS URL Generation for Blob Storage

### Generate Blob SAS Token

```python
from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    generate_blob_sas,
    BlobSasPermissions
)

def generate_blob_sas_url(
    account_name: str,
    account_key: str,
    container_name: str,
    blob_name: str,
    expiry_hours: int = 1
) -> str:
    """Generate SAS URL for blob access."""
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
    )

    blob_url = (
        f"https://{account_name}.blob.core.windows.net/"
        f"{container_name}/{blob_name}?{sas_token}"
    )

    return blob_url

# Usage with Document Intelligence
def analyze_blob_with_sas(
    blob_path: str,
    model_id: str,
    storage_account_name: str,
    storage_account_key: str,
    container_name: str
) -> AnalyzeResult:
    """Analyze blob using SAS URL."""
    # Generate SAS URL
    blob_url = generate_blob_sas_url(
        account_name=storage_account_name,
        account_key=storage_account_key,
        container_name=container_name,
        blob_name=blob_path,
        expiry_hours=2
    )

    # Analyze with Document Intelligence
    client = DocumentIntelligenceClient(
        endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["DOCUMENTINTELLIGENCE_API_KEY"])
    )

    poller = client.begin_analyze_document(
        model_id=model_id,
        analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
    )

    return poller.result()
```

### Container-Level SAS for Model Training

```python
from azure.storage.blob import ContainerSasPermissions, generate_container_sas

def generate_container_sas_url(
    account_name: str,
    account_key: str,
    container_name: str,
    expiry_days: int = 7
) -> str:
    """Generate container-level SAS URL for custom model training."""
    sas_token = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        account_key=account_key,
        permission=ContainerSasPermissions(read=True, list=True),
        expiry=datetime.utcnow() + timedelta(days=expiry_days)
    )

    container_url = (
        f"https://{account_name}.blob.core.windows.net/"
        f"{container_name}?{sas_token}"
    )

    return container_url

# Build custom model with container SAS
from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient
from azure.ai.documentintelligence.models import (
    BuildDocumentModelRequest,
    DocumentBuildMode,
    AzureBlobContentSource,
)
import uuid

def build_custom_model(container_sas_url: str, model_description: str):
    """Build custom Document Intelligence model."""
    admin_client = DocumentIntelligenceAdministrationClient(
        endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["DOCUMENTINTELLIGENCE_API_KEY"])
    )

    poller = admin_client.begin_build_document_model(
        BuildDocumentModelRequest(
            model_id=str(uuid.uuid4()),
            build_mode=DocumentBuildMode.TEMPLATE,
            azure_blob_source=AzureBlobContentSource(
                container_url=container_sas_url
            ),
            description=model_description
        )
    )

    model = poller.result()
    print(f"Custom model built: {model.model_id}")
    return model
```

---

## 5. Rate Limits and Quota Management

### Default Limits

- **Default TPS:** 15 transactions per second per resource per region
- **Analyze POST limit:** 15 TPS
- **Get operations (polling):** 15 TPS
- **Model management:** 15 TPS
- **List operations:** 15 TPS
- **S0 Tier:** 20 calls/min, 240 pages/min

### Enable Autoscaling

```bash
# Enable via Azure CLI
az resource update \
  --namespace Microsoft.CognitiveServices \
  --resource-type accounts \
  --set properties.dynamicThrottlingEnabled=true \
  --resource-group YOUR_RESOURCE_GROUP \
  --name YOUR_RESOURCE_NAME
```

### Best Practices to Avoid Rate Limiting

```python
import asyncio
from typing import List

async def process_documents_with_rate_limiting(
    blob_urls: List[str],
    model_id: str,
    max_concurrent: int = 10  # Stay below 15 TPS
):
    """Process documents with concurrency control."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(url: str):
        async with semaphore:
            try:
                result = await analyze_document_async(url, model_id)
                return {"url": url, "result": result, "error": None}
            except Exception as e:
                return {"url": url, "result": None, "error": str(e)}

    results = await asyncio.gather(
        *[process_with_semaphore(url) for url in blob_urls],
        return_exceptions=True
    )

    return results

# Batch processing with delays
def batch_process_documents(
    file_paths: List[str],
    model_id: str,
    batch_size: int = 10,
    delay_between_batches: float = 2.0
):
    """Process documents in batches to avoid rate limits."""
    results = []

    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        print(f"Processing batch {i // batch_size + 1}...")

        batch_results = [
            analyze_with_retry(client, model_id, path)
            for path in batch
        ]
        results.extend(batch_results)

        if i + batch_size < len(file_paths):
            time.sleep(delay_between_batches)

    return results
```

---

## 6. Common Pitfalls and Gotchas

### 1. Polling After Exception

**Problem:** After SDK exhausts retries on 429 errors, calling `poller.result()` again doesn't retry.

**Solution:** Catch exception at `begin_analyze_document()` level and restart operation.

```python
def analyze_with_full_retry(client, model_id: str, file_path: str, max_attempts: int = 3):
    """Retry entire operation, not just polling."""
    for attempt in range(max_attempts):
        try:
            with open(file_path, "rb") as f:
                poller = client.begin_analyze_document(model_id, body=f)
                return poller.result()
        except HttpResponseError as e:
            if e.status_code == 429 and attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

### 2. Large Document Timeouts

**Problem:** PDFs with 300+ pages timeout (408 error).

**Solution:**
- Split large PDFs into smaller chunks
- Increase Azure Function timeout (if applicable)
- Use async polling with longer timeouts

```python
async def analyze_large_document_async(blob_url: str, model_id: str, timeout_minutes: int = 10):
    """Handle large documents with extended timeout."""
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    async with DocumentIntelligenceClient(
        endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["DOCUMENTINTELLIGENCE_API_KEY"])
    ) as client:
        poller = await client.begin_analyze_document(
            model_id=model_id,
            analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
        )

        while not poller.done():
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Document processing exceeded {timeout_minutes} minutes")
            await asyncio.sleep(30)  # Poll every 30 seconds for large docs

        return await poller.result()
```

### 3. Field Access Patterns

**Problem:** Field structure varies by model type and document.

**Solution:** Always use `.get()` with defaults and check field presence.

```python
def safe_extract_field(fields: dict, field_name: str, default: Any = None) -> Any:
    """Safely extract field value with fallback."""
    field = fields.get(field_name)
    if not field:
        return default

    # Try common value types in order of priority
    value = (
        field.get("valueString") or
        field.get("valueNumber") or
        field.get("valueDate") or
        field.get("content") or
        default
    )

    return value
```

### 4. Model ID Confusion

**Problem:** Using document classifier model ID for extraction (or vice versa).

**Solution:**
- Custom classification models: Use `documentClassifiers` endpoint
- Custom extraction models: Use `documentModels` endpoint

```python
# Classification
from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient

admin_client = DocumentIntelligenceAdministrationClient(endpoint, credential)

# For classifiers - different endpoint
classifier = admin_client.get_classifier(classifier_id="my-classifier-id")

# For extraction models
model = admin_client.get_model(model_id="my-extraction-model-id")
```

### 5. SAS Token Expiration

**Problem:** SAS URLs expire during long-running operations.

**Solution:** Generate SAS tokens with sufficient expiry time (2+ hours for document processing).

```python
def analyze_with_sas_renewal(
    blob_path: str,
    model_id: str,
    storage_account_name: str,
    storage_account_key: str,
    container_name: str
):
    """Analyze with automatic SAS renewal."""
    # Generate SAS with 2-hour expiry
    blob_url = generate_blob_sas_url(
        account_name=storage_account_name,
        account_key=storage_account_key,
        container_name=container_name,
        blob_name=blob_path,
        expiry_hours=2  # Sufficient for long-running docs
    )

    client = DocumentIntelligenceClient(
        endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["DOCUMENTINTELLIGENCE_API_KEY"])
    )

    poller = client.begin_analyze_document(
        model_id=model_id,
        analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
    )

    return poller.result()
```

---

## 7. Production-Ready Pattern

```python
import os
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.exceptions import HttpResponseError

@dataclass
class DocumentProcessingConfig:
    """Configuration for document processing."""
    endpoint: str
    api_key: str
    model_id: str
    max_concurrent: int = 10
    max_retries: int = 5
    initial_retry_delay: float = 2.0
    min_confidence: float = 0.7

class DocumentIntelligenceProcessor:
    """Production-ready Document Intelligence processor."""

    def __init__(self, config: DocumentProcessingConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)

    async def process_document(self, blob_url: str) -> Dict[str, Any]:
        """Process single document with retry logic."""
        async with self.semaphore:
            for attempt in range(self.config.max_retries):
                try:
                    async with DocumentIntelligenceClient(
                        endpoint=self.config.endpoint,
                        credential=AzureKeyCredential(self.config.api_key)
                    ) as client:
                        poller = await client.begin_analyze_document(
                            self.config.model_id,
                            AnalyzeDocumentRequest(url_source=blob_url)
                        )
                        result = await poller.result()

                        # Extract and validate fields
                        fields = self._extract_fields(result)
                        validated, low_confidence = self._validate_confidence(fields)

                        return {
                            "blob_url": blob_url,
                            "status": "success",
                            "fields": validated,
                            "low_confidence_fields": low_confidence,
                            "model_id": result.model_id,
                            "error": None
                        }

                except HttpResponseError as e:
                    if e.status_code == 429 and attempt < self.config.max_retries - 1:
                        delay = self.config.initial_retry_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    return self._error_response(blob_url, e)

                except Exception as e:
                    return self._error_response(blob_url, e)

            return self._error_response(
                blob_url,
                Exception(f"Failed after {self.config.max_retries} retries")
            )

    async def process_batch(self, blob_urls: List[str]) -> List[Dict[str, Any]]:
        """Process batch of documents concurrently."""
        tasks = [self.process_document(url) for url in blob_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def _extract_fields(self, result) -> Dict[str, Any]:
        """Extract fields from result."""
        fields = {}
        if result.documents:
            for doc in result.documents:
                if doc.fields:
                    for name, field in doc.fields.items():
                        fields[name] = {
                            "value": extract_field_value(field),
                            "confidence": field.get("confidence", 0.0)
                        }
        return fields

    def _validate_confidence(self, fields: Dict) -> tuple[Dict, List[str]]:
        """Validate field confidence thresholds."""
        validated = {}
        low_confidence = []

        for name, data in fields.items():
            if data["confidence"] >= self.config.min_confidence:
                validated[name] = data["value"]
            else:
                low_confidence.append(f"{name} ({data['confidence']:.2f})")

        return validated, low_confidence

    def _error_response(self, blob_url: str, error: Exception) -> Dict[str, Any]:
        """Create error response."""
        return {
            "blob_url": blob_url,
            "status": "error",
            "fields": {},
            "low_confidence_fields": [],
            "model_id": None,
            "error": str(error)
        }

# Usage
async def main():
    config = DocumentProcessingConfig(
        endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
        api_key=os.environ["DOCUMENTINTELLIGENCE_API_KEY"],
        model_id="custom-invoice-model-v1",
        max_concurrent=12,
        min_confidence=0.75
    )

    processor = DocumentIntelligenceProcessor(config)

    blob_urls = [
        "https://storage.blob.core.windows.net/container/doc1.pdf?sp=r&...",
        "https://storage.blob.core.windows.net/container/doc2.pdf?sp=r&...",
        # ... more URLs
    ]

    results = await processor.process_batch(blob_urls)

    for result in results:
        if result["status"] == "success":
            print(f"Processed: {result['blob_url']}")
            print(f"Extracted fields: {result['fields']}")
        else:
            print(f"Failed: {result['blob_url']} - {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## References

- [Azure AI Document Intelligence Python SDK Documentation](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-documentintelligence-readme?view=azure-python)
- [Service Quotas and Limits](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0)
- [Azure SDK for Python GitHub Samples](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/documentintelligence/azure-ai-documentintelligence/samples)
- [Document Intelligence Code Samples](https://github.com/Azure-Samples/document-intelligence-code-samples)
- [Create SAS for Blob Storage with Python](https://learn.microsoft.com/en-us/azure/storage/blobs/sas-service-create-python)
- [Handling Errors in Azure SDK for Python](https://learn.microsoft.com/en-us/azure/developer/python/sdk/fundamentals/errors)

---

**Key Takeaways:**

1. Use async clients for concurrent processing (stay below 15 TPS default)
2. Implement exponential backoff for 429 rate limit errors
3. Check Retry-After header when available
4. Generate SAS tokens with 2+ hour expiry for long-running operations
5. Always validate field confidence scores
6. Handle different field types explicitly (string, number, date, currency, address, array)
7. Use semaphores to control concurrency and avoid rate limits
8. Enable autoscaling for production workloads
9. Large documents (300+ pages) may timeout - use async polling with extended timeouts
10. Restart entire operation on rate limit exhaustion (don't just retry poller)
