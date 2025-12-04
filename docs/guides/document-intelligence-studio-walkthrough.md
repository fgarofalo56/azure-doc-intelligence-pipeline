# 🖥️ Document Intelligence Studio Walkthrough

> **Step-by-step guide to creating custom extraction models using Azure Document Intelligence Studio**

---

## 📑 Table of Contents

- [Prerequisites](#-prerequisites)
- [Phase 1: Access the Studio](#-phase-1-access-the-studio)
- [Phase 2: Create a Project](#-phase-2-create-a-project)
- [Phase 3: Upload Documents](#-phase-3-upload-documents)
- [Phase 4: Label Documents](#-phase-4-label-documents)
- [Phase 5: Train the Model](#-phase-5-train-the-model)
- [Phase 6: Test the Model](#-phase-6-test-the-model)
- [Phase 7: Deploy to Pipeline](#-phase-7-deploy-to-pipeline)
- [Tips for Best Results](#-tips-for-best-results)

---

## 📋 Prerequisites

Before starting, ensure you have:

- [ ] **Azure Subscription** with appropriate permissions
- [ ] **Document Intelligence Resource** deployed (S0 tier recommended for custom models)
- [ ] **Storage Account** with a container for training data
- [ ] **Training Documents** - 10-15 sample PDFs of your form type
- [ ] **RBAC Roles:**
  - `Cognitive Services User` on Document Intelligence resource
  - `Storage Blob Data Contributor` on storage account

---

## 🌐 Phase 1: Access the Studio

### Step 1.1: Open Document Intelligence Studio

Navigate to: **https://documentintelligence.ai.azure.com/studio**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Document Intelligence Studio                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│   │   Read          │  │   Layout         │  │   Prebuilt       │ │
│   │   Extract text  │  │   Tables/struct  │  │   Invoice/Receipt│ │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│   │   Custom        │  │   Custom         │  │   Composed       │ │
│   │   extraction ◀──│  │   classification │  │   models         │ │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                      │
│   Click "Custom extraction model" to start                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 1.2: Sign In

1. Click **Sign in** in the top right
2. Use your Azure AD credentials
3. Select your Azure subscription if prompted

---

## 📁 Phase 2: Create a Project

### Step 2.1: Start New Project

1. Click **+ Create a project**
2. Fill in project details:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Create a new project                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Project name:     [ag-survey-extraction-v1        ]               │
│                                                                      │
│   Description:      [Agricultural survey form                        │
│                      extraction for yield data     ]                │
│                                                                      │
│                                            [Cancel]  [Continue →]   │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 2.2: Connect Azure Resources

**Document Intelligence Resource:**

| Field | Value | Example |
|-------|-------|---------|
| Subscription | Your subscription | `Visual Studio Enterprise` |
| Resource group | RG with Doc Intel | `rg-docproc-dev` |
| Resource | Doc Intel resource | `docproc-docintel-dev` |

**Storage Account:**

| Field | Value | Example |
|-------|-------|---------|
| Subscription | Your subscription | `Visual Studio Enterprise` |
| Resource group | RG with storage | `rg-docproc-dev` |
| Storage account | Training data storage | `docprocstorage` |
| Blob container | Container with PDFs | `training-data` |
| Folder path | Folder with samples | `ag-surveys/` |

### Step 2.3: Review and Create

1. Review settings summary
2. Click **Create project**
3. Wait for project initialization (~30 seconds)

---

## 📤 Phase 3: Upload Documents

### Step 3.1: Prepare Training Documents

**Recommended Document Set:**

| Document Type | Quantity | Notes |
|---------------|----------|-------|
| Clean samples | 8-10 | Best quality examples |
| Edge cases | 2-3 | Variations, handwritten |
| Different layouts | 2-3 | If form changed over time |
| **Total** | **12-15** | More is better |

### Step 3.2: Upload to Storage

**Option A: Azure Portal**

1. Navigate to Storage Account → Containers → `training-data`
2. Create folder `ag-surveys/`
3. Upload PDF files

**Option B: Azure CLI**

```bash
# Upload all PDFs in a folder
az storage blob upload-batch \
  --account-name docprocstorage \
  --destination training-data/ag-surveys \
  --source ./training-samples/ \
  --pattern "*.pdf"
```

**Option C: Storage Explorer**

1. Open Azure Storage Explorer
2. Navigate to container
3. Create folder and upload files

### Step 3.3: Verify in Studio

After upload, documents appear in the left panel:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Documents (15)                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  📄 survey_001.pdf                                    ○ Not labeled │
│  📄 survey_002.pdf                                    ○ Not labeled │
│  📄 survey_003.pdf                                    ○ Not labeled │
│  📄 survey_004.pdf                                    ○ Not labeled │
│  ...                                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏷️ Phase 4: Label Documents

### Step 4.1: Define Field Schema

Click **+ Add field** for each field to extract:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Fields (12)                                      [+ Add field]     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  📝 operatorName          string                                    │
│  📝 operationAddress      object                                    │
│     ├─ street             string                                    │
│     ├─ city               string                                    │
│     ├─ state              string                                    │
│     └─ zip                string                                    │
│  🔢 totalAcres            number                                    │
│  📅 certificationDate     date                                      │
│  ☑️ organicCertified      selectionMark                             │
│  ✍️ operatorSignature     signature                                 │
│  📝 countyCode            string                                    │
│  🔢 yieldPerAcre          number                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Field Types Reference:**

| Type | Icon | Use For | Example |
|------|------|---------|---------|
| `string` | 📝 | Text values | Names, addresses |
| `number` | 🔢 | Numeric values | Quantities, totals |
| `date` | 📅 | Date values | 2024-01-15 |
| `selectionMark` | ☑️ | Checkboxes | Yes/No selections |
| `signature` | ✍️ | Signatures | Signature presence |
| `object` | 📦 | Nested fields | Address with parts |
| `array` | 📋 | Repeated items | Table rows |

### Step 4.2: Label First Document

1. **Select document** from left panel
2. **Select field** from right panel
3. **Draw bounding box** around the value on the document
4. **Verify** the extracted text is correct

```
┌─────────────────────────────────────────────────────────────────────┐
│  Document Viewer                           │  Fields                │
├────────────────────────────────────────────┼────────────────────────┤
│                                            │                        │
│  ┌────────────────────────────────────┐   │  operatorName: ●       │
│  │  AGRICULTURAL SURVEY               │   │  [John Smith     ]     │
│  │                                    │   │  Confidence: 0.98      │
│  │  Operator: ┌──────────────┐       │   │                        │
│  │           │ John Smith   │◀──────│───│─ Click to label        │
│  │            └──────────────┘       │   │                        │
│  │                                    │   │  operationAddress: ○   │
│  │  Address: 123 Farm Road           │   │  [Not labeled    ]     │
│  │           Springfield, IL 62701   │   │                        │
│  │                                    │   │  totalAcres: ○         │
│  │  Total Acres: 450                 │   │  [Not labeled    ]     │
│  │                                    │   │                        │
│  └────────────────────────────────────┘   │                        │
│                                            │                        │
└────────────────────────────────────────────┴────────────────────────┘
```

### Step 4.3: Labeling Best Practices

| ✅ Do | ❌ Don't |
|-------|---------|
| Include small margin around text | Draw box too tight |
| Be consistent across documents | Label differently each time |
| Label all instances of field | Skip some occurrences |
| Match field type to content | Use wrong type (string for number) |

### Step 4.4: Use Auto-Label (v4.0 Feature)

After labeling 5 documents manually:

1. Click **Auto-label** button
2. Review auto-labeled documents
3. Correct any mistakes
4. Saves ~70% labeling time

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Auto-label Results                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ✅ survey_006.pdf - 12/12 fields auto-labeled                      │
│  ⚠️ survey_007.pdf - 11/12 fields (review operatorName)             │
│  ✅ survey_008.pdf - 12/12 fields auto-labeled                      │
│  ⚠️ survey_009.pdf - 10/12 fields (review 2 fields)                 │
│                                                                      │
│  Documents requiring review: 2                                       │
│                                         [Review Now]  [Accept All]  │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 4.5: Verify All Labels

Before training, verify:

- [ ] All documents are labeled (green checkmark)
- [ ] All fields have at least 5 labels
- [ ] No obvious mistakes in bounding boxes
- [ ] Extracted text matches actual values

---

## 🏋️ Phase 5: Train the Model

### Step 5.1: Start Training

1. Click **Train** button (top right)
2. Enter model details:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Train Model                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Model ID:        [ag-survey-v1                    ]                │
│                   (lowercase letters, numbers, hyphens only)        │
│                                                                      │
│  Description:     [Agricultural survey extraction                    │
│                    model version 1.0              ]                 │
│                                                                      │
│  Build mode:      ○ Template (fixed layouts)                        │
│                   ● Neural (variable layouts) ◀── Recommended       │
│                                                                      │
│                                            [Cancel]  [Train →]      │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 5.2: Monitor Training Progress

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Training in Progress                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Model: ag-survey-v1                                                │
│  Status: Training                                                    │
│                                                                      │
│  ████████████████░░░░░░░░░░░░░░░░░░░░░░  45%                       │
│                                                                      │
│  Started: 2024-01-15 10:30:00                                       │
│  Estimated completion: ~15 minutes                                   │
│                                                                      │
│  Training steps:                                                     │
│  ✅ Validating documents                                            │
│  ✅ Extracting features                                             │
│  🔄 Training neural network                                         │
│  ○ Evaluating model                                                 │
│  ○ Finalizing                                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Training Time Estimates:**

| Build Mode | Documents | Estimated Time |
|------------|-----------|----------------|
| Template | 5-15 | 2-5 minutes |
| Neural | 5-15 | 15-30 minutes |
| Neural | 50+ | 1-2 hours |

### Step 5.3: Review Training Results

After training completes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Training Complete ✅                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Model: ag-survey-v1                                                │
│  Status: Ready                                                       │
│                                                                      │
│  Training Metrics:                                                   │
│  ─────────────────────────────────────────────────────────────────  │
│  Field                 Accuracy    Samples                          │
│  ─────────────────────────────────────────────────────────────────  │
│  operatorName          98.5%       15/15                            │
│  operationAddress      96.2%       15/15                            │
│  totalAcres            99.1%       15/15                            │
│  certificationDate     97.8%       15/15                            │
│  organicCertified      99.5%       15/15                            │
│  operatorSignature     94.2%       15/15                            │
│  ─────────────────────────────────────────────────────────────────  │
│  Overall:              97.5%                                         │
│                                                                      │
│                                    [View Details]  [Test Model →]   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Phase 6: Test the Model

### Step 6.1: Upload Test Document

1. Click **Test** tab
2. Click **+ Add** to upload a test document
3. Use a document **NOT** in the training set

### Step 6.2: Run Analysis

1. Select the uploaded document
2. Click **Analyze**
3. Wait for results (~10-30 seconds)

### Step 6.3: Review Results

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Analysis Results                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Document: test_survey_new.pdf                                      │
│  Model: ag-survey-v1                                                │
│  Processing time: 12.3s                                             │
│                                                                      │
│  Extracted Fields:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Field                Value                    Confidence     │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ operatorName        "Jane Doe"               0.98 ✅        │   │
│  │ operationAddress    "456 Rural Rd..."        0.95 ✅        │   │
│  │ totalAcres          "320"                    0.97 ✅        │   │
│  │ certificationDate   "2024-02-01"             0.93 ✅        │   │
│  │ organicCertified    "selected"               0.96 ✅        │   │
│  │ operatorSignature   "signed"                 0.87 ⚠️        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Legend: ✅ High confidence (>0.90)  ⚠️ Review (<0.90)              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 6.4: Iterate if Needed

If accuracy is too low:

1. **Add more training documents** (especially edge cases)
2. **Review and fix labels** (incorrect bounding boxes)
3. **Re-train the model**

---

## 🚀 Phase 7: Deploy to Pipeline

### Step 7.1: Copy Model ID

1. Go to **Models** tab in Studio
2. Find your trained model
3. Copy the **Model ID**: `ag-survey-v1`

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Models                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Model ID          Status    Created           Actions               │
│  ─────────────────────────────────────────────────────────────────  │
│  ag-survey-v1      Ready     2024-01-15        [📋 Copy ID] [Test]  │
│  ag-survey-v0      Ready     2024-01-10        [📋 Copy ID] [Test]  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 7.2: Update Pipeline Configuration

**Option A: Synapse Pipeline Parameter**

In Azure Synapse, update the pipeline parameter:

```json
{
  "modelId": "ag-survey-v1"
}
```

**Option B: Environment Variable**

Update your Function App configuration:

```bash
az functionapp config appsettings set \
  --name docproc-func-dev \
  --resource-group rg-docproc-dev \
  --settings "DEFAULT_MODEL_ID=ag-survey-v1"
```

### Step 7.3: Test End-to-End

1. Upload a test PDF to `incoming/` folder
2. Trigger the Synapse pipeline
3. Verify results in Cosmos DB

---

## 💡 Tips for Best Results

### Document Quality

| ✅ Best Practices | Impact |
|-------------------|--------|
| 300 DPI scans | Higher text recognition accuracy |
| Straight alignment | Better field detection |
| Good contrast | Clearer text extraction |
| Consistent formatting | More reliable model |

### Labeling Tips

| Tip | Why It Matters |
|-----|----------------|
| Label at least 5 samples per field | Model needs examples |
| Include edge cases | Handles real-world variation |
| Be consistent with boxes | Model learns patterns |
| Review auto-labels carefully | Prevents training errors |

### Model Selection

| Scenario | Recommended Model |
|----------|-------------------|
| Forms are identical every time | Template |
| Different vendors/layouts | Neural |
| Mix of both | Start with Neural |

### Confidence Thresholds

```python
# Recommended thresholds for this pipeline
THRESHOLDS = {
    "high_confidence": 0.95,    # Auto-accept
    "medium_confidence": 0.80,  # Review queue
    "low_confidence": 0.60,     # Manual entry
}
```

---

## 🔧 Common Issues

| Issue | Solution |
|-------|----------|
| "No fields detected" | Check document quality, orientation |
| Low confidence on all fields | Add more training samples |
| Training takes too long | Neural models need 20-30 min |
| Model stuck at "Running" | Wait up to 2 hours, then contact support |
| 429 Rate limit errors | Implement retry with backoff |

---

## 📚 Resources

- [Document Intelligence Studio](https://documentintelligence.ai.azure.com/studio)
- [Custom Model Documentation](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-model)
- [Labeling Best Practices](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/build-a-custom-model)
- [Troubleshooting Guide](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/resolve-errors)

---

*Last Updated: December 2024*
*Studio Version: 2024*
