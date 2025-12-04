# Azure Document Intelligence - Complete Reference Guide

**Last Updated:** 2025-12-04
**API Version:** 2024-11-30 (v4.0 GA)
**Studio URL:** https://documentintelligence.ai.azure.com/studio
**Pricing:** [Azure Document Intelligence Pricing](https://azure.microsoft.com/en-us/pricing/details/ai-document-intelligence/)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Custom Extraction Models](#2-custom-extraction-models)
3. [Document Intelligence Studio](#3-document-intelligence-studio)
4. [Best Practices](#4-best-practices)
5. [API Integration](#5-api-integration)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Overview

### What is Azure Document Intelligence?

Azure Document Intelligence (formerly Azure Form Recognizer) is an AI-powered document processing service that extracts text, key-value pairs, tables, and structures from documents. It uses machine learning models to understand document layouts and semantics.

**Key Capabilities:**
- **Prebuilt models**: Ready-to-use models for common document types (invoices, receipts, ID cards, W-2 forms)
- **Custom models**: Train your own models for organization-specific documents
- **Layout analysis**: Extract text, tables, selection marks, and document structure
- **Classification**: Automatically categorize documents by type

### API Versions

| Version | Status | Release Date | Key Features |
|---------|--------|--------------|--------------|
| **2024-11-30 (v4.0)** | **GA** | December 2024 | Overlapping fields, signature detection, table/row/cell confidence, Office document classification |
| 2024-07-31-preview | Preview | July 2024 | Preview features testing |
| 2024-02-29-preview | Preview | February 2024 | Advanced preview capabilities |
| 2023-07-31 (v3.1) | GA | July 2023 | Stable v3.1 features |
| 2022-08-31 (v3.0) | GA | August 2022 | v3.0 baseline |

**This Project Uses:** `2024-02-29-preview` (as specified in CLAUDE.md)

### Pricing Tiers

#### Free Tier (F0)
- **Custom Extraction:** 500 pages/month
- **Prebuilt Models:** 2,000 pages/month
- **Training:** Free for template models, first 10 hours free for neural models
- **Limitations:** Only first 2 pages analyzed per request

#### Standard Tier (S0)

**Custom Extraction Model Pricing (June 2024 - 40% reduction):**
- **$30 per 1,000 pages** (reduced from $50)
- Neural model training: **$3/hour** after first 10 hours free
- Template model training: **Free**

**Commitment Tiers (Prepaid):**
- Lower per-page costs with volume commitments
- Flexible pricing for enterprise workloads

**Deployment Options:**
- Cloud (Azure): Standard pricing
- Connected containers: Same as cloud
- Disconnected containers: Separate licensing

### Regional Availability

**Commercial Cloud:** Available in most Azure regions
**Government Cloud:** Azure Government (FedRAMP/FISMA compliant)
- `usgovvirginia`, `usgovarizona`, `usgovtexas`
- Government-specific endpoints: `https://<location>.api.cognitive.microsoft.us`

**Data Residency:**
- Document payloads stored temporarily (up to 24 hours) in same region as resource
- Each customer's data logically isolated
- Choose regional deployments for GDPR compliance (EU zones)

### Service Limits (Standard Tier)

| Resource | Default Limit | Notes |
|----------|--------------|-------|
| **TPS (Transactions Per Second)** | 15 TPS | Can request increase via support ticket |
| **Analyze POST** | 15 TPS | Rate limit per resource per region |
| **Get Operations (polling)** | 15 TPS | Status checks count toward limit |
| **Model Management** | 15 TPS | Build, list, delete operations |
| **Custom Neural Training** | 20 builds/month | v3.x API limit (open support request to increase) |
| **Training Data Size** | 50 MB (template), 1 GB (neural) | Per model training |
| **Training Pages** | 500 (template), 50,000 (neural) | Maximum pages per training dataset |
| **Custom Classification** | 2 GB total, 10,000 pages | For v4.0 GA |
| **Composed Models** | 200 models | Maximum models per composed model ID |

---

## 2. Custom Extraction Models

### Model Types Comparison

| Feature | **Custom Template** | **Custom Neural** | **Recommendation** |
|---------|---------------------|-------------------|-------------------|
| **Use Case** | Structured forms with consistent layout | Documents with varying layouts but same information | Start with neural, use template if layout is truly fixed |
| **Training Data** | Min 5 examples | Min 5 examples | 10-15 recommended for production |
| **Training Time** | Few minutes | Up to 30 minutes | Neural takes 10-20x longer |
| **Training Cost** | Free | $3/hour after first 10 hours | Template is more cost-effective for testing |
| **Document Support** | Fixed visual template required | Flexible layouts (e.g., W-2 forms from different companies) | Neural handles real-world variability better |
| **Max Training Data** | 50 MB, 500 pages | 1 GB, 50,000 pages | Neural supports larger datasets |
| **Supported Fields** | Key-value pairs, tables, selection marks, signatures, regions | Same as template + overlapping fields (v4.0) | Neural v4.0 adds overlapping field support |
| **Best For** | Bank checks, standardized government forms | Invoices, contracts, medical records | Most production use cases benefit from neural |
| **Accuracy** | High for identical layouts | High across layout variations | Neural generalizes better |

### When to Use Each Type

#### Custom Template Models ✅
- Forms with 100% consistent layout (e.g., scanned copies of same paper form)
- Fast training time required (rapid prototyping)
- Budget-conscious projects (free training)
- Simple forms with < 20 fields
- Example: Government form that hasn't changed in years

#### Custom Neural Models ✅ (Recommended for most cases)
- Documents with multiple layout variations (different vendors, versions)
- Complex documents (invoices, contracts, medical records)
- Forms that evolve over time (annual updates)
- Multi-page documents with varying structures
- Example: Purchase orders from different suppliers

#### Composed Models 🔀
- Multiple document types in single stream (invoices + receipts + contracts)
- Assign up to 200 custom models to single composed model ID
- Automatically routes to correct model based on document type
- Response includes `docType` property indicating which model was used
- Can compose template and neural models together across API versions

### Training Data Requirements

#### Minimum Requirements
- **5 examples** of same document type (minimum)
- **10-15 examples** recommended for production quality
- Documents must represent real-world variations

#### Document Format Guidelines

**Supported Formats:**
- PDF (text-based preferred over scanned)
- JPEG/JPG
- PNG
- BMP
- TIFF
- HEIF

**Best Practices:**
- **Resolution:** 300 DPI minimum for scanned documents
- **File Size:** Under 500 MB per file
- **Pages:** Max 2,000 pages per document for analysis
- **Orientation:** Correct rotation (Document Intelligence auto-detects, but clean data helps)
- **Quality:** Clear, high-contrast text
- **Variations:** Include all layout variations in training set

**Avoid:**
- Blurry or low-resolution scans
- Heavy shadows or glare
- Handwritten text (unless specifically training for it)
- Damaged or torn documents
- Documents with sensitive/redacted information in training data

#### Storage Requirements

**Azure Blob Storage Setup:**
1. Standard performance storage account
2. Container with training documents
3. Documents in root or subfolder (specify `Folder path` in Studio)
4. CORS enabled (Document Intelligence Studio configures automatically)
5. **SAS token with read + list permissions** for training

### Field Types Supported

| Field Type | Description | Example | Template | Neural |
|------------|-------------|---------|----------|--------|
| **String** | Text values | "John Doe", "Acme Corp" | ✅ | ✅ |
| **Number** | Numeric values | 1500, 3.14 | ✅ | ✅ |
| **Date** | Date values | "2024-12-04" | ✅ | ✅ |
| **Time** | Time values | "14:30:00" | ✅ | ✅ |
| **Currency** | Amount with code | {amount: 1500.00, currencyCode: "USD"} | ✅ | ✅ |
| **Address** | Structured address | {street, city, state, zip, country} | ✅ | ✅ |
| **Selection Mark** | Checkbox/radio | true/false, selected/unselected | ✅ | ✅ |
| **Signature** | Signature detection | Presence indicator | ✅ | ✅ (v4.0) |
| **Table** | Tabular data | Rows and columns | ✅ | ✅ |
| **Array** | Lists of items | Invoice line items | ✅ | ✅ |
| **Object** | Nested structures | Address within customer object | ✅ | ✅ |
| **Overlapping Fields** | Same location, different contexts | ✅ | ✅ (v4.0 GA) |

### Model Lifecycle

**Creation → Training → Testing → Deployment → Monitoring → Versioning**

#### Expiration Policy (v3.1+)
- Custom models expire **2 years** after creation (GA API builds)
- Models built with preview APIs may have different expiration
- Plan model refresh and retraining cycles
- **API Version Dependency:** Models depend on Layout API version used during training
  - Use same API version for analyze requests as training for best results
  - Mixing versions may degrade accuracy

#### Versioning Strategy
```
custom-invoice-model-v1  →  Initial production model
custom-invoice-model-v2  →  Improved accuracy (more training data)
custom-invoice-model-v3  →  Added new fields
```

**Best Practices:**
- Version naming convention: `<doc-type>-<purpose>-v<number>`
- Keep previous version active during testing
- A/B test new versions before full rollout
- Document changes in model descriptions
- Archive old models after migration

---

## 3. Document Intelligence Studio

### Access and Setup

**Studio URL:** https://documentintelligence.ai.azure.com/studio

**Regional URLs:**
- **Azure Government (Fairfax):** Government-specific Studio URL
- **Azure China (21Vianet):** China-specific Studio URL

### Prerequisites

#### Required Azure Resources
1. **Document Intelligence Resource** (Cognitive Services)
   - F0 (free) or S0 (standard) tier
   - Note region for endpoint construction
2. **Azure Blob Storage Account**
   - Standard performance tier
   - Container for training documents
   - CORS enabled (Studio configures automatically)
3. **Azure Subscription** with appropriate permissions

#### Required Azure RBAC Roles

| Role | Resource | Purpose | Required |
|------|----------|---------|----------|
| **Cognitive Services User** | Document Intelligence resource | Use Studio and API | ✅ |
| **Storage Blob Data Contributor** | Storage account | Create projects, label data | ✅ |
| **Storage Account Contributor** | Storage account | Configure CORS (one-time) | ✅ (one-time) |

### Step-by-Step: Creating a Custom Extraction Model

#### Phase 1: Project Setup (5-10 minutes)

1. **Navigate to Studio**
   - Go to https://documentintelligence.ai.azure.com/studio
   - First-time users: Initialize subscription, resource group, resource

2. **Create New Project**
   - Select **Custom extraction model** tile
   - Click **Create a project** button
   - **Project Configuration:**
     - **Project name:** `invoice-extraction-v1` (descriptive, versioned)
     - **Description:** (optional) "Extract vendor, total, date from supplier invoices"
     - Click **Continue**

3. **Configure Document Intelligence Resource**
   - **Subscription:** Select your Azure subscription
   - **Resource group:** Select or create resource group
   - **Document Intelligence resource:** Select existing or create new
   - **API version:** Choose `2024-11-30 (GA)` or `2024-02-29-preview`
   - Click **Continue**

4. **Configure Training Data Source**
   - **Storage account:** Select storage account with training documents
   - **Blob container:** Select container (e.g., `training-invoices`)
   - **Folder path:** Leave empty if documents in root, otherwise specify subfolder (e.g., `invoices/vendor-a`)
   - **CORS Check:** Studio verifies/configures CORS automatically
   - Click **Continue**

5. **Review and Create**
   - Review all settings
   - Click **Create Project**
   - Wait for project initialization (few seconds)

#### Phase 2: Document Labeling (15-30 minutes per document)

**Labeling Window Overview:**
- **Left panel:** List of uploaded documents
- **Center panel:** Current document with zoom/pan controls
- **Right panel:** Field list and properties

**Labeling Process:**

1. **Select First Document**
   - Click first document in left panel
   - Document renders in center panel

2. **Create Fields**
   - Click **➕ (plus) button** on top-right
   - **Field name:** `VendorName` (use camelCase or PascalCase)
   - **Field type:** String (select from dropdown)
   - **Description:** (optional) "Supplier company name"
   - Click **Add field**

3. **Label Field Values**
   - **Method 1: Text Selection**
     - Highlight text in document (e.g., "Acme Corporation")
     - Click field name in right panel (`VendorName`)
     - Labeled region appears with colored bounding box
   - **Method 2: Draw Region**
     - Click field name in right panel
     - Click **Draw region** icon
     - Click and drag to create bounding box
     - Adjust corners as needed

4. **Repeat for All Fields**
   - Create and label:
     - `InvoiceNumber` (String)
     - `InvoiceDate` (Date)
     - `InvoiceTotal` (Currency)
     - `VendorAddress` (Address)
     - `PaymentTerms` (String)
     - `LineItems` (Table) - special handling below

5. **Labeling Tables**
   - Click **Table** icon in toolbar
   - **Draw table region** around entire table
   - **Define columns:**
     - Click **Add column**
     - Column name: `Description`, `Quantity`, `UnitPrice`, `Amount`
     - Column type: String, Number, Currency, Currency
   - **Label cells:** Studio auto-detects cells, adjust if needed
   - **Dynamic rows:** Tables auto-expand for varying row counts

6. **Auto-Labeling (Time Saver) 🚀**
   - After labeling first document manually:
     - Click **Auto-label** button (v4.0 GA feature)
     - Select **Prebuilt model** (e.g., `prebuilt-invoice`) or trained model
     - Studio auto-labels similar fields
   - **Review auto-labels:**
     - Check for duplicate labels (common with auto-label)
     - Adjust bounding boxes if needed
     - Remove incorrect labels

7. **Label Remaining Documents**
   - Click next document in left panel
   - Use auto-label or manual labeling
   - **Minimum:** Label 5 documents
   - **Recommended:** Label 10-15 documents for production
   - **Include variations:** Different layouts, fonts, formats

#### Phase 3: Model Training (5-30 minutes)

1. **Initiate Training**
   - Click **Train** button (upper-right corner)
   - **Training Configuration:**
     - **Model ID:** Auto-generated UUID or custom name
       - Example: `invoice-model-v1-20241204`
     - **Build Mode:**
       - **Template:** Fast, free (few minutes)
       - **Neural:** Slow, paid after 10hrs (15-30 minutes)
     - **Description:** "Invoice extraction v1 - 15 training samples"
   - Click **Train**

2. **Monitor Training Progress**
   - Training status indicator appears
   - **Template:** Progress bar, 2-5 minutes
   - **Neural:** May show "Processing..." for 15-30 minutes
   - **Stuck Training?** See [Troubleshooting](#6-troubleshooting)

3. **Training Completion**
   - Success notification appears
   - Model moves to "Ready" state
   - **Model ID** displayed (copy this for API integration)

#### Phase 4: Testing (5-10 minutes)

1. **Test Model in Studio**
   - Click **Test** tab in Studio
   - **Upload test document** (not in training set)
   - Click **Analyze**
   - Wait for results (10-30 seconds)

2. **Review Extracted Fields**
   - **Left panel:** Extracted field values
   - **Center panel:** Bounding boxes overlaid on document
   - **Confidence scores:** Check per-field confidence
   - **Field highlighting:** Click field to see bounding box

3. **Evaluate Accuracy**
   - **High confidence (>0.85):** Green indicator, auto-accept
   - **Medium confidence (0.70-0.85):** Yellow indicator, review recommended
   - **Low confidence (<0.70):** Red indicator, manual review required

4. **Iterate if Needed**
   - **Low accuracy?**
     - Add more training samples (especially with similar issues)
     - Re-label ambiguous fields with clearer bounding boxes
     - Check for consistent field naming across documents
     - Retrain model

#### Phase 5: Deployment

1. **Copy Model ID**
   - In Studio, go to **Models** tab
   - Find your trained model
   - **Model ID:** Click copy icon (e.g., `invoice-model-v1-20241204`)

2. **Integrate with API**
   - Use Model ID in `begin_analyze_document()` calls
   - See [API Integration](#5-api-integration) section

3. **Production Checklist**
   - ✅ Tested on diverse document samples
   - ✅ Confidence thresholds defined (e.g., 0.75 for auto-accept)
   - ✅ Error handling implemented (rate limits, timeouts)
   - ✅ Monitoring/logging configured
   - ✅ Fallback to human review for low-confidence extractions

### Advanced Studio Features

#### Auto-Labeling
- **Native in v4.0 GA** (no IP allowlisting required)
- Use prebuilt models or previously trained models
- **Caution:** May create duplicate labels - review and clean up
- Time savings: ~70% reduction in labeling time

#### Incremental Training (v4.0 GA)
- **Custom Classification Models:** Add new samples to existing classes or new classes
- Reference existing classifier, Studio merges training data
- Avoids retraining from scratch

#### Office Document Support (v4.0 GA)
- Classification models now support:
  - DOCX (Word documents)
  - XLSX (Excel spreadsheets)
  - PPTX (PowerPoint presentations)
- Previously limited to PDFs and images

---

## 4. Best Practices

### Document Preparation

#### Pre-Processing Tips ✅

1. **Use Text-Based PDFs**
   - Prefer digital PDFs over scanned images
   - Text-based = native text extraction (faster, more accurate)
   - Scanned PDFs = OCR required (slower, less accurate)

2. **Optimize Scans**
   - **Resolution:** 300 DPI minimum
   - **Color:** Grayscale or color (avoid pure black-and-white)
   - **Orientation:** Correct rotation before upload
   - **Deskew:** Straighten tilted scans

3. **Image Quality**
   - High contrast (dark text, light background)
   - Minimal noise, artifacts, or compression
   - No shadows or glare
   - Crop unnecessary borders

4. **Document Variations**
   - Include all layout variations in training set
   - Examples: Different vendors, form versions, languages
   - At least 5 samples per major variation

#### What to Avoid ❌

- Heavily redacted documents (too much missing context)
- Low-resolution scans (<200 DPI)
- Documents with watermarks obscuring text
- Mixed orientations in same document
- Extremely large files (>500 MB)

### Labeling Accuracy Guidelines

#### Field Naming Conventions

**Good:**
```
VendorName          ✅ (PascalCase)
invoice_total       ✅ (snake_case)
paymentDueDate      ✅ (camelCase)
```

**Bad:**
```
vendor name         ❌ (spaces not recommended)
VENDOR              ❌ (unclear, not descriptive)
field_1             ❌ (meaningless name)
```

#### Labeling Best Practices

1. **Bounding Box Precision**
   - **Tight bounds:** Minimize whitespace around text
   - **Complete capture:** Include all relevant text
   - **Avoid overlap:** Don't overlap unrelated text
   - **Tables:** Draw around entire table, Studio detects cells

2. **Consistency**
   - Same field name across all documents (case-sensitive)
   - Same labeling approach (e.g., always include currency symbol or always exclude)
   - Same table structure (column names, order)

3. **Complex Structures**
   - **Nested objects:** Use object fields for addresses, customer info
   - **Arrays:** Use for repeating items (line items, transactions)
   - **Multi-line fields:** Single bounding box around all lines

4. **Ambiguous Fields**
   - **Multiple addresses:** Label separately (`VendorAddress`, `ShipToAddress`)
   - **Multiple dates:** Distinguish (`InvoiceDate`, `DueDate`, `ShipDate`)
   - **Similar numbers:** Clear naming (`InvoiceNumber`, `PONumber`, `OrderNumber`)

### Confidence Threshold Recommendations

#### General Guidelines

| Use Case | Recommended Threshold | Routing Strategy |
|----------|----------------------|------------------|
| **Financial/Medical** | **>0.95** (95%) | High-risk, near 100% required |
| **General Business** | **0.80-0.90** (80-90%) | Balanced automation |
| **High-Volume/Low-Risk** | **0.70-0.80** (70-80%) | Accept more, review less |

#### Confidence-Based Routing

```python
def route_by_confidence(confidence: float, field_name: str) -> str:
    """Route extraction based on confidence level."""
    if confidence >= 0.95:
        return "auto_accept"  # High confidence → auto-accept
    elif confidence >= 0.75:
        return "human_review"  # Medium confidence → send for review
    else:
        return "reject_reprocess"  # Low confidence → reject or reprocess
```

#### Threshold Calibration Process

1. **Run pilot with diverse documents** (100-500 samples)
2. **Analyze confidence distribution:**
   - What % fall into high/medium/low buckets?
   - Where are false positives/negatives occurring?
3. **Adjust thresholds based on findings:**
   - Lower threshold = more automation, higher error rate
   - Higher threshold = less automation, lower error rate
4. **Monitor ongoing accuracy** (see below)

### Model Training Best Practices

#### Training Data Volume

| Document Complexity | Minimum Samples | Recommended Samples |
|---------------------|----------------|---------------------|
| Simple (< 10 fields) | 5 | 10-15 |
| Medium (10-20 fields) | 10 | 15-25 |
| Complex (> 20 fields, tables) | 15 | 25-50 |

#### Training Data Diversity

- ✅ **Include:** All layout variations, font styles, quality levels
- ✅ **Include:** Edge cases (partially filled forms, handwriting if applicable)
- ✅ **Include:** Different document versions (annual updates)
- ❌ **Avoid:** Duplicate documents (same content, same layout)
- ❌ **Avoid:** Outliers that aren't representative

#### Split Training vs. Test Data

```
Total Documents: 100

Training Set: 80 (80%)
  └── Used for model training

Validation Set: 10 (10%)
  └── Used during training to tune model

Test Set: 10 (10%)
  └── Held out completely, used for final evaluation
```

**Never test on training data** - overfitting risk!

### Handling Low-Confidence Extractions

#### Strategy 1: Human-in-the-Loop

```python
def process_with_human_review(result: dict) -> dict:
    """Route low-confidence fields to human review queue."""
    auto_accepted = {}
    needs_review = {}

    for field, data in result["fields"].items():
        if data["confidence"] >= 0.85:
            auto_accepted[field] = data["value"]
        else:
            needs_review[field] = {
                "value": data["value"],
                "confidence": data["confidence"],
                "needs_review": True
            }

    if needs_review:
        send_to_review_queue(result["document_id"], needs_review)

    return {"auto_accepted": auto_accepted, "needs_review": needs_review}
```

#### Strategy 2: Fallback Models

```python
async def extract_with_fallback(blob_url: str) -> dict:
    """Try custom model, fallback to prebuilt if low confidence."""
    # Try custom model first
    result = await analyze_with_custom_model(blob_url, "custom-invoice-v1")

    if result["confidence"] < 0.70:
        # Fallback to prebuilt model
        result = await analyze_with_prebuilt_model(blob_url, "prebuilt-invoice")

    return result
```

#### Strategy 3: Reprocessing Pipeline

1. **Initial extraction** (custom model)
2. **Confidence check** (< threshold?)
3. **Preprocess and retry:**
   - Enhance image quality (sharpen, contrast)
   - Rotate/deskew if needed
   - Retry extraction
4. **Manual review** if still low confidence

### Model Versioning Strategies

#### Semantic Versioning for Models

```
model-name-vMAJOR.MINOR.PATCH

Examples:
invoice-model-v1.0.0   Initial release
invoice-model-v1.1.0   Added new fields (minor)
invoice-model-v1.0.1   Bug fix (patch)
invoice-model-v2.0.0   Breaking change (different fields, major)
```

#### A/B Testing Strategy

```python
import random

def get_model_for_request(document_type: str) -> str:
    """A/B test: 80% old model, 20% new model."""
    if random.random() < 0.20:
        return f"{document_type}-model-v2"  # New model
    else:
        return f"{document_type}-model-v1"  # Old model (baseline)
```

#### Model Refresh Cadence

- **Monthly:** High-volume use cases, evolving documents
- **Quarterly:** Standard business documents
- **Annually:** Stable forms (government, standardized)
- **Event-driven:** When accuracy drops below threshold

---

## 5. API Integration

### Python SDK Usage Patterns

See [azure_document_intelligence_patterns.md](./azure_document_intelligence_patterns.md) for comprehensive SDK implementation patterns including:

- Sync and async `begin_analyze_document()` usage
- Field extraction from `AnalyzeResult`
- Error handling and retry logic
- Rate limiting and quota management
- SAS URL generation for blob storage
- Production-ready processing patterns

**Quick Example:**

```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

client = DocumentIntelligenceClient(
    endpoint=os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["DOCUMENTINTELLIGENCE_API_KEY"])
)

# Analyze document with custom model
poller = client.begin_analyze_document(
    model_id="custom-invoice-model-v1",
    analyze_request=AnalyzeDocumentRequest(url_source=blob_url_with_sas)
)

result = poller.result()  # Blocks until complete

# Extract fields
for document in result.documents:
    for field_name, field_value in document.fields.items():
        print(f"{field_name}: {field_value.get('content')} "
              f"(confidence: {field_value.get('confidence')})")
```

### Error Handling and Retries

**Common HTTP Status Codes:**

| Code | Meaning | Action |
|------|---------|--------|
| **200** | Success | Process result |
| **400** | Bad Request | Check model ID, blob URL, request format |
| **401** | Unauthorized | Verify API key, check Key Vault |
| **404** | Not Found | Model ID doesn't exist, check model list |
| **408** | Request Timeout | Document too large, increase timeout or split |
| **429** | Rate Limit (TPS) | Implement exponential backoff, check Retry-After header |
| **500** | Internal Server Error | Transient, retry with backoff |
| **503** | Service Unavailable | Azure maintenance, retry with backoff |

**Rate Limiting Pattern:**

```python
from azure.core.exceptions import HttpResponseError
import time

def analyze_with_rate_limit_handling(client, model_id, blob_url, max_retries=5):
    """Handle 429 rate limits with exponential backoff."""
    for attempt in range(max_retries):
        try:
            poller = client.begin_analyze_document(
                model_id=model_id,
                analyze_request=AnalyzeDocumentRequest(url_source=blob_url)
            )
            return poller.result()
        except HttpResponseError as e:
            if e.status_code == 429:
                # Check Retry-After header
                retry_after = e.response.headers.get("Retry-After", 2 ** attempt)
                print(f"Rate limited. Retrying after {retry_after}s...")
                time.sleep(float(retry_after))
            else:
                raise
    raise Exception("Rate limit exceeded after maximum retries")
```

### Long-Running Operations

Document Intelligence operations are **asynchronous**:

1. **POST /analyze** → Returns operation ID
2. **GET /analyze/{operationId}** → Poll for status
3. **Status: succeeded** → Results available

**Polling Best Practices:**
- Don't poll faster than **every 2 seconds** (causes rate limiting)
- Use exponential backoff for polling intervals: 2s → 5s → 10s → 20s
- Recommended: 2-5-13-34 pattern (Fibonacci-like)
- SDK handles this automatically with `poller.result()`

---

## 6. Troubleshooting

### Common Training Issues

#### Issue: Model Training Stuck in "Running" State (>24 hours)

**Causes:**
- Validation errors (invalid blobs, corrupted files)
- Quota exhaustion (neural models: 20 builds/month limit)
- High regional load
- Internal service bugs

**Solutions:**
1. **Check quota:** Neural models limited to 20 builds/month (resets monthly)
2. **Try smaller dataset:** Train with 5 documents first to isolate issue
3. **Check blob access:** Verify SAS token valid, blobs readable
4. **Switch regions:** Deploy and train in different Azure region
5. **Open support ticket:** Provide correlation IDs from failed attempts

#### Issue: Training Fails with "InternalServerError"

**Causes:**
- Heavy service load
- Invalid training data (corrupted PDFs)
- Labeling errors (duplicate bounding boxes, invalid field types)

**Solutions:**
1. **Retry training:** Generic errors often transient
2. **Validate training data:**
   - Check all PDFs open correctly
   - Remove corrupted files
   - Verify no duplicate labels in Studio
3. **Reduce dataset size:** Train with 5 documents to isolate problematic files
4. **Use template mode:** If neural fails, try template build mode (faster, simpler)
5. **Contact support:** If persists, open Azure support ticket

#### Issue: "InvalidRequest" or "InvalidContent"

**Causes:**
- Corrupted files or unsupported formats
- Invalid SAS token or expired URL
- Files exceed size limits (500 MB per file)

**Solutions:**
1. **Verify file format:** Ensure PDF, JPEG, PNG, BMP, TIFF, or HEIF
2. **Check file integrity:** Open files locally to confirm not corrupted
3. **Regenerate SAS token:** Ensure read + list permissions, valid expiry
4. **Check file size:** Max 500 MB per file, split if needed

### Common Analysis Issues

#### Issue: 408 Request Timeout (Large Documents)

**Causes:**
- Documents with 300+ pages
- Complex layouts with many tables
- Service throttling under load

**Solutions:**
1. **Split large PDFs:** Break into smaller chunks (e.g., 50-100 pages each)
2. **Increase function timeout:** Azure Functions default 5 minutes, increase to 10 minutes
3. **Use async polling:** Longer timeout, less blocking
4. **Optimize document:** Reduce file size (compress images, remove unnecessary pages)

```python
# Example: Split large PDF
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(input_path: str, output_dir: str, pages_per_chunk: int = 50):
    """Split large PDF into smaller chunks."""
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    for i in range(0, total_pages, pages_per_chunk):
        writer = PdfWriter()
        for page_num in range(i, min(i + pages_per_chunk, total_pages)):
            writer.add_page(reader.pages[page_num])

        output_path = f"{output_dir}/chunk_{i // pages_per_chunk + 1}.pdf"
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
```

#### Issue: 429 Rate Limit Errors

**Causes:**
- Exceeding 15 TPS default limit
- Polling too aggressively (GET operations count toward TPS)
- Concurrent requests without throttling

**Solutions:**
1. **Implement exponential backoff:** See [API Integration](#5-api-integration)
2. **Enable autoscaling:**
   ```bash
   az resource update \
     --namespace Microsoft.CognitiveServices \
     --resource-type accounts \
     --set properties.dynamicThrottlingEnabled=true \
     --resource-group YOUR_RG \
     --name YOUR_RESOURCE
   ```
3. **Request TPS increase:** Open support ticket for production workloads
4. **Use semaphores for concurrency control:**
   ```python
   semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
   ```
5. **Batch with delays:** Process documents in batches with 2-5 second delays

#### Issue: Low Accuracy / Incorrect Extractions

**Causes:**
- Insufficient training data
- Training data not representative
- Low-quality documents
- Field confusion (similar fields, ambiguous labels)

**Solutions:**
1. **Add more training samples:** 15-25 recommended for complex documents
2. **Diversify training data:** Include all layout variations, quality levels
3. **Improve labeling precision:**
   - Tighter bounding boxes
   - Consistent field naming
   - Clear disambiguation (e.g., `BillToAddress` vs `ShipToAddress`)
4. **Use neural model:** Better generalization than template
5. **Check confidence scores:** Identify patterns in low-confidence fields
6. **Preprocess documents:** Enhance quality (deskew, sharpen, increase contrast)

### Model Management Issues

#### Issue: Model Not Found (404)

**Causes:**
- Incorrect model ID (typo, wrong version)
- Model deleted or expired
- Using model from different resource

**Solutions:**
1. **List models:** Verify model ID exists
   ```python
   from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient

   admin_client = DocumentIntelligenceAdministrationClient(endpoint, credential)
   models = admin_client.list_models()
   for model in models:
       print(f"Model ID: {model.model_id}, Created: {model.created_on}")
   ```
2. **Check resource:** Ensure using correct Document Intelligence resource
3. **Check expiration:** Models expire 2 years after creation
4. **Use correct endpoint:** Classifier vs extraction model endpoints differ

#### Issue: Cannot Delete Model

**Causes:**
- Model in use by composed model
- Model locked by active training operation

**Solutions:**
1. **Check composed models:** Remove from composed model first
2. **Wait for operations:** Cancel or wait for active operations to complete
3. **Use administration client:**
   ```python
   admin_client.delete_model(model_id="model-to-delete")
   ```

### Debugging Tips

#### Enable Logging

```python
import logging
from azure.core.diagnostics import set_logging_level

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)
set_logging_level(logging.DEBUG)

# Analyze with detailed logs
result = client.begin_analyze_document(model_id, analyze_request=request)
```

#### Inspect Request/Response

```python
from azure.core.pipeline.policies import HttpLoggingPolicy

client = DocumentIntelligenceClient(
    endpoint=endpoint,
    credential=credential,
    logging_policy=HttpLoggingPolicy(logger=logging.getLogger("azure"))
)
```

#### Check Service Health

- **Azure Status Page:** https://status.azure.com
- **Service Limits:** https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits
- **Known Issues:** Check Document Intelligence release notes

---

## Resources and References

### Official Documentation

- [Document Intelligence Overview](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/model-overview?view=doc-intel-4.0.0)
- [Custom Document Models](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-model?view=doc-intel-4.0.0)
- [Custom Template Models](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-template?view=doc-intel-4.0.0)
- [Custom Neural Models](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-neural?view=doc-intel-4.0.0)
- [Composed Models](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/composed-models?view=doc-intel-4.0.0)
- [Build and Train Custom Models](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/build-a-custom-model?view=doc-intel-4.0.0)
- [Document Intelligence Studio](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/studio-overview?view=doc-intel-4.0.0)
- [Create Studio Custom Projects](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/quickstarts/studio-custom-project?view=doc-intel-4.0.0)
- [Accuracy and Confidence Interpretation](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/accuracy-confidence?view=doc-intel-4.0.0)
- [Service Limits and Quotas](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0)
- [Resolve Errors Reference](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/resolve-errors?view=doc-intel-4.0.0)
- [What's New in v4.0](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/whats-new?view=doc-intel-4.0.0)

### Python SDK

- [Azure AI Document Intelligence Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-documentintelligence-readme?view=azure-python)
- [Python SDK Samples](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/documentintelligence/azure-ai-documentintelligence/samples)
- [Document Intelligence Code Samples](https://github.com/Azure-Samples/document-intelligence-code-samples)

### Community Resources

- [Microsoft Tech Community - Azure AI](https://techcommunity.microsoft.com/t5/azure-ai-foundry/ct-p/azure-ai-foundry)
- [Stack Overflow - azure-document-intelligence](https://stackoverflow.com/questions/tagged/azure-document-intelligence)
- [GitHub Issues - Azure SDK for Python](https://github.com/Azure/azure-sdk-for-python/issues)

---

## Appendix: Quick Reference Checklists

### Pre-Training Checklist ✅

- [ ] **5+ training documents** prepared (10-15 recommended)
- [ ] **Documents in Azure Blob Storage** (container created)
- [ ] **Document Intelligence resource** provisioned (F0 or S0)
- [ ] **RBAC roles assigned** (Cognitive Services User, Storage Blob Data Contributor)
- [ ] **Documents represent variations** (different layouts, vendors, versions)
- [ ] **Document quality verified** (readable, high resolution, correct orientation)
- [ ] **Field naming convention** decided (camelCase, PascalCase, snake_case)

### Production Deployment Checklist ✅

- [ ] **Model tested** on diverse documents (not in training set)
- [ ] **Confidence thresholds** defined (e.g., 0.75 auto-accept, <0.75 review)
- [ ] **Error handling** implemented (rate limits, timeouts, retries)
- [ ] **SAS token generation** configured (2+ hour expiry)
- [ ] **Monitoring/logging** enabled (track accuracy, latency, errors)
- [ ] **Human review queue** set up for low-confidence extractions
- [ ] **Rate limiting** handled (exponential backoff, semaphores)
- [ ] **Model versioning** strategy defined (semantic versioning, A/B testing)
- [ ] **Fallback strategy** planned (prebuilt models, manual review)
- [ ] **Auto-scaling** enabled for production load
- [ ] **Cost monitoring** configured (track page counts, training hours)

### Troubleshooting Checklist 🔧

**Training Issues:**
- [ ] Check quota (neural models: 20 builds/month)
- [ ] Verify blob access (valid SAS token, readable files)
- [ ] Validate training data (no corrupted files, duplicate labels)
- [ ] Try smaller dataset (5 documents first)
- [ ] Switch regions if persistent failures

**Analysis Issues:**
- [ ] Verify model ID exists (list models)
- [ ] Check SAS token expiry (regenerate if needed)
- [ ] Confirm file format supported (PDF, JPEG, PNG, etc.)
- [ ] Split large documents (>300 pages)
- [ ] Implement rate limit handling (429 errors)

**Low Accuracy:**
- [ ] Add more training samples (15-25 for complex docs)
- [ ] Diversify training data (all variations)
- [ ] Improve labeling precision (tighter bounding boxes)
- [ ] Use neural model (better generalization)
- [ ] Check confidence score patterns (identify weak fields)

---

**Document Version:** 1.0
**Last Reviewed:** 2025-12-04
**Next Review:** 2025-03-04 (quarterly)
