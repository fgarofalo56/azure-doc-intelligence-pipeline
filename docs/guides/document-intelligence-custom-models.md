# 🤖 Azure Document Intelligence Custom Models Guide

> **Complete guide to building, training, and deploying custom extraction models**

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Model Types Comparison](#-model-types-comparison)
- [When to Use Custom Models](#-when-to-use-custom-models)
- [Training Requirements](#-training-requirements)
- [Document Intelligence Studio Walkthrough](#-document-intelligence-studio-walkthrough)
- [API Integration](#-api-integration)
- [Best Practices](#-best-practices)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Overview

Azure Document Intelligence (formerly Form Recognizer) provides AI-powered document processing capabilities. Custom models allow you to extract specific fields from your unique document types.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Prebuilt Models** | Ready-to-use models for common documents (invoices, receipts, IDs) |
| **Custom Models** | Models trained on your specific document types |
| **Composed Models** | Combine multiple custom models with automatic routing |
| **Document Intelligence Studio** | Web UI for labeling, training, and testing models |

### API Versions

| Version | Status | Used In This Project |
|---------|--------|---------------------|
| `2024-11-30` | GA (v4.0) | ❌ |
| `2024-02-29-preview` | Preview | ✅ |
| `2023-07-31` | GA (v3.1) | ❌ |

---

## 📊 Model Types Comparison

### Custom Template vs Custom Neural

| Feature | Custom Template | Custom Neural |
|---------|-----------------|---------------|
| **Best For** | Fixed-layout forms | Variable layouts |
| **Training Time** | Minutes | 30+ minutes |
| **Min Documents** | 5 | 5 |
| **Recommended Docs** | 5-10 | 10-15 |
| **Max Training Data** | 50 MB / 500 pages | 1 GB / 50,000 pages |
| **Training Cost** | Free | $3/hour (first 10 hrs free) |
| **Accuracy** | High (fixed layouts) | High (varying layouts) |
| **Tables Support** | ✅ | ✅ |
| **Signatures** | ✅ | ✅ (with confidence) |
| **Overlapping Fields** | ❌ | ✅ (v4.0+) |

### Decision Matrix

```
┌─────────────────────────────────────────────────────────────┐
│                    Which Model to Use?                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Are your documents identical in layout?                     │
│  (Same positions, same formatting)                           │
│                                                              │
│         YES                              NO                  │
│          │                                │                  │
│          ▼                                ▼                  │
│  ┌───────────────┐              ┌─────────────────┐         │
│  │   TEMPLATE    │              │     NEURAL      │         │
│  │    MODEL      │              │     MODEL       │         │
│  └───────────────┘              └─────────────────┘         │
│                                                              │
│  Examples:                       Examples:                   │
│  • Government forms              • Invoices (various vendors)│
│  • Tax forms (W-2, 1040)        • Contracts                 │
│  • Applications                  • Letters                   │
│  • Surveys                       • Mixed-format documents    │
└─────────────────────────────────────────────────────────────┘
```

### Composed Models

Combine up to **200 custom models** into a single endpoint:

```
┌─────────────────────────────────────────────┐
│            Composed Model                    │
├─────────────────────────────────────────────┤
│                                             │
│    Document → [Auto Router] → Model A       │
│                            → Model B        │
│                            → Model C        │
│                                             │
│    Returns: Best matching model's results   │
└─────────────────────────────────────────────┘
```

**Use Cases:**
- Multiple form types to single endpoint
- A/B testing between model versions
- Gradual model rollouts

---

## 🎯 When to Use Custom Models

### ✅ Use Custom Models When:

1. **Prebuilt models don't cover your document type**
   - Agricultural surveys, medical forms, custom applications

2. **You need specific field extraction**
   - Extract exact fields by name (e.g., "OperatorName", "FarmAddress")

3. **High accuracy is required**
   - Financial documents, legal contracts, compliance forms

4. **Document layout is consistent**
   - Even with variations, neural models handle this well

### ❌ Use Prebuilt Models When:

1. **Standard document types**
   - Invoices, receipts, business cards, IDs

2. **Quick prototyping**
   - Get started without training data

3. **General layout analysis**
   - Use `prebuilt-layout` for tables, text, structure

### This Project's Approach

This pipeline uses **custom models** because:
- Agricultural survey forms have unique field layouts
- Specific fields need extraction (operator info, crop data, etc.)
- Forms are 2-page documents with consistent structure
- High confidence thresholds required for data quality

---

## 📚 Training Requirements

### Document Preparation

| Requirement | Specification |
|-------------|---------------|
| **Format** | PDF, JPEG, PNG, BMP, TIFF, HEIF |
| **File Size** | Max 500 MB per file |
| **Resolution** | Minimum 50x50 pixels, recommended 300 DPI |
| **Quality** | Clear, readable, minimal skew |
| **Orientation** | Auto-detected, but consistent is better |

### Labeling Requirements

| Field Type | Description | Example |
|------------|-------------|---------|
| **String** | Text values | "John Smith" |
| **Number** | Numeric values | "1500.50" |
| **Date** | Date values | "2024-01-15" |
| **Time** | Time values | "14:30:00" |
| **Integer** | Whole numbers | "42" |
| **Selection Mark** | Checkboxes, radio buttons | ☑ / ☐ |
| **Signature** | Signature detection | ✍️ |
| **Currency** | Money amounts | "$1,500.00" |
| **Country/Region** | Country codes | "US" |
| **Array** | Repeated fields | Multiple line items |
| **Object** | Nested structure | Address with subfields |

### Sample Size Guidelines

| Document Complexity | Minimum | Recommended | Notes |
|--------------------|---------|-------------|-------|
| Simple (5-10 fields) | 5 | 10 | Template model |
| Medium (10-30 fields) | 5 | 15 | Neural recommended |
| Complex (30+ fields) | 10 | 20+ | Neural required |
| Tables | 5 | 15 | Include varied row counts |
| Handwritten | 10 | 25+ | More variation needed |

---

## 🖥️ Document Intelligence Studio Walkthrough

### Access the Studio

**URL:** https://documentintelligence.ai.azure.com/studio

### Phase 1: Project Setup (5-10 minutes)

#### Step 1: Create Custom Extraction Project

1. Navigate to **Custom extraction model**
2. Click **+ Create a project**
3. Enter project details:
   - **Project name:** `ag-survey-model-v1`
   - **Description:** `Agricultural survey form extraction`

#### Step 2: Configure Azure Resources

```
┌─────────────────────────────────────────────────────────────┐
│                   Resource Configuration                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Document Intelligence Resource:                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Subscription: [Your Subscription]                    │    │
│  │ Resource:     docproc-docintel-dev                  │    │
│  │ API Version:  2024-02-29-preview                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Storage Account (for training data):                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Subscription: [Your Subscription]                    │    │
│  │ Storage:      docprocstorage                        │    │
│  │ Container:    training-data                         │    │
│  │ Folder:       ag-surveys/                           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Step 3: Required RBAC Permissions

Ensure your account has:
- `Cognitive Services User` on Document Intelligence resource
- `Storage Blob Data Contributor` on storage account

### Phase 2: Document Labeling (15-30 min per document)

#### Step 1: Upload Training Documents

1. Upload 10-15 sample PDFs to storage container
2. Studio auto-discovers documents in configured folder
3. Documents appear in left panel

#### Step 2: Create Field Schema

Define fields to extract:

```yaml
Fields:
  - name: operatorName
    type: string
    description: "Farm operator's full name"

  - name: operationAddress
    type: object
    subfields:
      - street: string
      - city: string
      - state: string
      - zip: string

  - name: totalAcres
    type: number
    description: "Total farm acreage"

  - name: certificationDate
    type: date
    description: "Date form was certified"

  - name: signaturePresent
    type: signature
    description: "Operator signature"

  - name: organicCertified
    type: selectionMark
    description: "Organic certification checkbox"
```

#### Step 3: Label Documents

For each document:

1. **Select field** from right panel
2. **Draw bounding box** around the value
3. **Verify extracted text** is correct
4. **Repeat** for all fields

**Labeling Tips:**
- Be consistent with bounding box placement
- Include some margin around text
- Label same field in same location across documents
- Use auto-label feature (v4.0) to speed up

#### Step 4: Auto-Labeling (v4.0 Feature)

1. Label 5 documents manually
2. Click **Auto-label** button
3. Review and correct auto-labeled documents
4. Saves ~70% labeling time

### Phase 3: Model Training (5-30 minutes)

#### Step 1: Start Training

1. Click **Train** button
2. Enter model details:
   - **Model ID:** `ag-survey-v1`
   - **Description:** `Agricultural survey extraction model v1`
3. Select **Build mode:**
   - `Template` for fixed layouts
   - `Neural` for variable layouts

#### Step 2: Monitor Training

```
┌─────────────────────────────────────────────────────────────┐
│                    Training Progress                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Status: Training...                                         │
│  ████████████░░░░░░░░░░░░░░░░░░░░  45%                      │
│                                                              │
│  Estimated time remaining: 12 minutes                        │
│                                                              │
│  Training metrics will appear after completion               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Training Limits

| Limit | Value |
|-------|-------|
| Neural builds per month | 20 |
| Template builds | Unlimited |
| Concurrent training | 1 |
| Model expiration | 2 years |

### Phase 4: Model Testing (5-10 minutes)

#### Step 1: Test with New Documents

1. Click **Test** tab
2. Upload document not in training set
3. Click **Analyze**
4. Review extracted fields and confidence

#### Step 2: Evaluate Results

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Results                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Field              Value                    Confidence      │
│  ─────────────────────────────────────────────────────────  │
│  operatorName       "John Smith"             0.98           │
│  operationAddress   "123 Farm Rd..."         0.95           │
│  totalAcres         "450"                    0.97           │
│  certificationDate  "2024-01-15"             0.92           │
│  signaturePresent   true                     0.89           │
│  organicCertified   selected                 0.96           │
│                                                              │
│  Overall Accuracy: 94.5%                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Phase 5: Deployment

#### Step 1: Copy Model ID

After successful testing:

1. Go to **Models** tab
2. Find your model
3. Copy the **Model ID** (e.g., `ag-survey-v1`)

#### Step 2: Use in Pipeline

Update your pipeline configuration:

```python
# In function parameters or environment
MODEL_ID = "ag-survey-v1"

# Or via Synapse pipeline parameter
{
    "modelId": "ag-survey-v1"
}
```

---

## 🔌 API Integration

### Python SDK Usage

```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

# Initialize client
client = DocumentIntelligenceClient(
    endpoint="https://your-resource.cognitiveservices.azure.com",
    credential=AzureKeyCredential("your-api-key")
)

# Analyze document with custom model
async def analyze_document(blob_url: str, model_id: str):
    poller = await client.begin_analyze_document(
        model_id=model_id,
        analyze_request={"urlSource": blob_url},
        pages="1-"  # All pages
    )
    result = await poller.result()
    return result
```

### Extracting Results

```python
def extract_fields(result) -> dict:
    extracted = {}

    for document in result.documents:
        for field_name, field in document.fields.items():
            extracted[field_name] = {
                "value": field.value,
                "confidence": field.confidence,
                "type": field.type
            }

    return extracted
```

### Error Handling

```python
from azure.core.exceptions import HttpResponseError

try:
    result = await analyze_document(url, model_id)
except HttpResponseError as e:
    if e.status_code == 429:
        # Rate limited - implement backoff
        await asyncio.sleep(60)
        retry...
    elif e.status_code == 400:
        # Bad request - check document format
        log_error(f"Invalid document: {e.message}")
    else:
        raise
```

---

## 🏆 Best Practices

### Document Preparation

| ✅ Do | ❌ Don't |
|-------|---------|
| Use 300 DPI scans | Use low-resolution images |
| Keep documents straight | Use heavily skewed documents |
| Ensure good contrast | Use faded or washed out copies |
| Remove backgrounds | Include busy backgrounds |
| Use PDF format | Use compressed JPEGs |

### Labeling Accuracy

| Best Practice | Reason |
|---------------|--------|
| Consistent bounding boxes | Model learns field locations |
| Include margins around text | Handles slight variations |
| Label all instances of repeating fields | Teaches pattern recognition |
| Use exact field names | Matches API response keys |
| Document edge cases | Improves model robustness |

### Confidence Thresholds

| Use Case | Minimum Confidence | Action Below Threshold |
|----------|-------------------|------------------------|
| Financial/Medical | 0.95 | Human review required |
| Legal Documents | 0.90 | Human review required |
| General Business | 0.80 | Flag for review |
| High-Volume Processing | 0.70 | Auto-accept with audit |

### Model Versioning

```
Model Naming Convention:
  {document-type}-v{major}.{minor}

Examples:
  ag-survey-v1.0      # Initial production model
  ag-survey-v1.1      # Minor improvements
  ag-survey-v2.0      # Major changes (new fields)
```

**Version Strategy:**
1. Keep previous version active during rollout
2. Use composed models for A/B testing
3. Document changes in version notes
4. Set model expiration reminders (2-year limit)

---

## 🔧 Troubleshooting

### Common Training Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Training stuck | Large dataset | Wait longer, check status |
| Low accuracy | Insufficient samples | Add more training documents |
| Missing fields | Inconsistent labeling | Re-label with consistency |
| Training failed | Invalid documents | Check document format/quality |

### Common Analysis Issues

| Error | Cause | Solution |
|-------|-------|----------|
| 429 Rate Limit | Too many requests | Implement exponential backoff |
| 400 Bad Request | Invalid document | Check URL, format, size |
| Low confidence | Poor document quality | Improve source documents |
| Missing values | Field not found | Verify field exists in model |

### Debugging Tips

1. **Enable logging:**
   ```python
   import logging
   logging.getLogger("azure").setLevel(logging.DEBUG)
   ```

2. **Check model status:**
   ```python
   model_info = client.get_model(model_id)
   print(f"Status: {model_info.status}")
   print(f"Created: {model_info.created_date_time}")
   ```

3. **Validate documents:**
   - Test with `prebuilt-layout` first
   - Check if text is being extracted
   - Verify bounding regions are correct

---

## 📚 Resources

- [Document Intelligence Documentation](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/)
- [Custom Model Overview](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-model)
- [Python SDK Reference](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-documentintelligence-readme)
- [Studio Guide](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/studio-overview)
- [Pricing](https://azure.microsoft.com/en-us/pricing/details/ai-document-intelligence/)

---

*Last Updated: December 2024*
*API Version: 2024-02-29-preview*
