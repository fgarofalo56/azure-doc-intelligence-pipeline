# Azure Synapse Pipeline Patterns for Document Processing

This document provides implementation-critical patterns for orchestrating PDF document processing through Azure Document Intelligence using Azure Synapse Analytics pipelines and Azure Functions.

## Table of Contents

- [Overview](#overview)
- [GetMetadata Activity](#getmetadata-activity)
- [Filter Activity](#filter-activity)
- [ForEach Activity](#foreach-activity)
- [Azure Function Activity](#azure-function-activity)
- [Error Handling and Retry](#error-handling-and-retry)
- [Complete Pipeline Pattern](#complete-pipeline-pattern)
- [Common Gotchas](#common-gotchas)

---

## Overview

**Typical Document Processing Flow:**
1. **GetMetadata** - List all files from blob storage
2. **Filter** - Keep only PDF files
3. **ForEach** - Process each PDF in parallel (with batch control)
4. **Azure Function** - Call Document Intelligence via HTTP-triggered function
5. **Error Handling** - Retry on transient failures, log errors

---

## GetMetadata Activity

### Purpose
Retrieve file lists from Azure Blob Storage for processing.

### JSON Configuration

```json
{
  "name": "GetPDFFileList",
  "type": "GetMetadata",
  "dependsOn": [],
  "policy": {
    "timeout": "0.12:00:00",
    "retry": 0,
    "retryIntervalInSeconds": 30,
    "secureOutput": false,
    "secureInput": false
  },
  "userProperties": [],
  "typeProperties": {
    "dataset": {
      "referenceName": "DS_BlobStorage_Binary",
      "type": "DatasetReference",
      "parameters": {
        "folderPath": "@pipeline().parameters.sourceFolderPath",
        "container": "@pipeline().parameters.containerName"
      }
    },
    "fieldList": [
      "childItems",
      "itemName",
      "lastModified"
    ],
    "storeSettings": {
      "type": "AzureBlobStorageReadSettings",
      "recursive": true,
      "enablePartitionDiscovery": false
    }
  }
}
```

### Dataset Definition (Binary)

```json
{
  "name": "DS_BlobStorage_Binary",
  "properties": {
    "linkedServiceName": {
      "referenceName": "LS_AzureBlobStorage",
      "type": "LinkedServiceReference"
    },
    "parameters": {
      "folderPath": {
        "type": "string"
      },
      "container": {
        "type": "string"
      }
    },
    "type": "Binary",
    "typeProperties": {
      "location": {
        "type": "AzureBlobStorageLocation",
        "folderPath": {
          "value": "@dataset().folderPath",
          "type": "Expression"
        },
        "container": {
          "value": "@dataset().container",
          "type": "Expression"
        }
      }
    }
  }
}
```

### Output Structure

```json
{
  "exists": true,
  "itemName": "incoming",
  "itemType": "Folder",
  "lastModified": "2025-01-15T10:30:00Z",
  "childItems": [
    {
      "name": "invoice_001.pdf",
      "type": "File"
    },
    {
      "name": "receipt_002.pdf",
      "type": "File"
    },
    {
      "name": "subfolder",
      "type": "Folder"
    }
  ]
}
```

### Key Points

- **fieldList Options**: `childItems`, `itemName`, `itemType`, `size`, `lastModified`, `structure`, `columnCount`
- **Recursive**: Use `"recursive": true` in storeSettings to scan subfolders
- **Performance**: Avoid pointing to folders with thousands of files when using `lastModified` filters
- **Output Access**: `@activity('GetPDFFileList').output.childItems`

---

## Filter Activity

### Purpose
Filter file lists by extension (e.g., keep only .pdf files) or other criteria.

### JSON Configuration

```json
{
  "name": "FilterPDFFiles",
  "type": "Filter",
  "dependsOn": [
    {
      "activity": "GetPDFFileList",
      "dependencyConditions": [
        "Succeeded"
      ]
    }
  ],
  "userProperties": [],
  "typeProperties": {
    "items": {
      "value": "@activity('GetPDFFileList').output.childItems",
      "type": "Expression"
    },
    "condition": {
      "value": "@and(equals(item().type, 'File'), endswith(item().name, '.pdf'))",
      "type": "Expression"
    }
  }
}
```

### Common Filter Expressions

**Filter by extension:**
```json
"condition": "@endswith(item().name, '.pdf')"
```

**Filter files only (exclude folders):**
```json
"condition": "@equals(item().type, 'File')"
```

**Filter by name pattern:**
```json
"condition": "@startswith(item().name, 'invoice_')"
```

**Multiple conditions:**
```json
"condition": "@and(equals(item().type, 'File'), contains(item().name, '2025'))"
```

**Exclude specific files:**
```json
"condition": "@not(contains(item().name, '_processed'))"
```

### Output Access

```json
{
  "value": "@activity('FilterPDFFiles').output.value",
  "type": "Expression"
}
```

Result is an array of objects that matched the condition.

### Key Points

- Use `item()` to reference current array element
- Output is accessible via `.output.value`
- Supports standard expression functions: `equals`, `startswith`, `endswith`, `contains`, `and`, `or`, `not`
- **Limitation**: Cannot use wildcards for nested JSON arrays

---

## ForEach Activity

### Purpose
Iterate over file lists and execute processing activities (e.g., call Azure Functions) for each file.

### JSON Configuration (Parallel Processing)

```json
{
  "name": "ForEachPDF",
  "type": "ForEach",
  "dependsOn": [
    {
      "activity": "FilterPDFFiles",
      "dependencyConditions": [
        "Succeeded"
      ]
    }
  ],
  "userProperties": [],
  "typeProperties": {
    "items": {
      "value": "@activity('FilterPDFFiles').output.value",
      "type": "Expression"
    },
    "isSequential": false,
    "batchCount": 10,
    "activities": [
      {
        "name": "ProcessDocumentFunction",
        "type": "AzureFunctionActivity",
        "dependsOn": [],
        "policy": {
          "timeout": "0:10:00",
          "retry": 2,
          "retryIntervalInSeconds": 30,
          "secureOutput": false,
          "secureInput": false
        },
        "userProperties": [],
        "typeProperties": {
          "functionName": "process_document",
          "method": "POST",
          "headers": {
            "Content-Type": "application/json"
          },
          "body": {
            "value": "@json(concat('{\"blobUrl\":\"', pipeline().parameters.storageAccountUrl, '/', pipeline().parameters.containerName, '/', pipeline().parameters.sourceFolderPath, '/', item().name, '\",\"blobName\":\"', pipeline().parameters.sourceFolderPath, '/', item().name, '\",\"modelId\":\"', pipeline().parameters.modelId, '\"}'))",
            "type": "Expression"
          }
        },
        "linkedServiceName": {
          "referenceName": "LS_AzureFunction",
          "type": "LinkedServiceReference"
        }
      }
    ]
  }
}
```

### Sequential Processing

```json
{
  "name": "ForEachPDF_Sequential",
  "type": "ForEach",
  "typeProperties": {
    "items": {
      "value": "@activity('FilterPDFFiles').output.value",
      "type": "Expression"
    },
    "isSequential": true,
    "activities": [
      {
        "name": "ProcessDocument",
        "type": "AzureFunctionActivity"
      }
    ]
  }
}
```

### Key Configuration Options

| Property | Description | Default | Max |
|----------|-------------|---------|-----|
| `isSequential` | Run items one at a time | true | - |
| `batchCount` | Parallel execution count | 20 | 50 |
| `items` | Array to iterate | Required | 100,000 |

### Accessing Current Item

Use `@item()` expression to reference the current iteration's object:

```json
"blobName": "@item().name"
```

For nested properties:
```json
"fileSize": "@item().metadata.size"
```

### Iteration Patterns

**From array parameter:**
```json
"items": "@pipeline().parameters.fileList"
```

**From activity output:**
```json
"items": "@activity('FilterPDFFiles').output.value"
```

**From numeric range:**
```json
"items": "@range(0, 10)"
```

### Key Points

- **Parallel Max**: 50 concurrent iterations
- **Default Batch**: 20 parallel by default
- **Nesting Limitation**: Cannot nest ForEach inside ForEach (use Execute Pipeline activity for multi-level)
- **SetVariable**: Cannot use in parallel ForEach
- **Timeout**: No direct timeout on ForEach itself, set on child activities

---

## Azure Function Activity

### Purpose
Call HTTP-triggered Azure Functions to process documents with Document Intelligence.

### Linked Service Configuration

```json
{
  "name": "LS_AzureFunction",
  "type": "Microsoft.Synapse/workspaces/linkedservices",
  "properties": {
    "annotations": [],
    "type": "AzureFunction",
    "typeProperties": {
      "functionAppUrl": "https://func-docprocessing-dev.azurewebsites.net",
      "authentication": "SystemAssignedManagedIdentity",
      "resourceId": "/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{functionAppName}"
    }
  }
}
```

**Alternative with Function Key:**
```json
{
  "type": "AzureFunction",
  "typeProperties": {
    "functionAppUrl": "https://func-docprocessing-dev.azurewebsites.net",
    "functionKey": {
      "type": "AzureKeyVaultSecret",
      "store": {
        "referenceName": "LS_AzureKeyVault",
        "type": "LinkedServiceReference"
      },
      "secretName": "FunctionAppKey"
    }
  }
}
```

### Activity Configuration

```json
{
  "name": "ProcessDocument",
  "type": "AzureFunctionActivity",
  "dependsOn": [],
  "policy": {
    "timeout": "0:10:00",
    "retry": 3,
    "retryIntervalInSeconds": 30,
    "secureOutput": false,
    "secureInput": false
  },
  "userProperties": [],
  "typeProperties": {
    "functionName": "process_document",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "x-correlation-id": "@{pipeline().RunId}"
    },
    "body": {
      "blobUrl": "https://storageaccount.blob.core.windows.net/container/file.pdf",
      "blobName": "folder/file.pdf",
      "modelId": "custom-model-v1"
    }
  },
  "linkedServiceName": {
    "referenceName": "LS_AzureFunction",
    "type": "LinkedServiceReference"
  }
}
```

### Dynamic Body Construction

```json
{
  "body": {
    "value": "@json(concat('{\"blobUrl\":\"', variables('blobUrl'), '\",\"blobName\":\"', item().name, '\"}'))",
    "type": "Expression"
  }
}
```

Or cleaner with object syntax (supported in newer versions):
```json
{
  "body": {
    "value": "@json(concat('{',
      '\"blobUrl\":\"', variables('blobUrl'), '\",',
      '\"blobName\":\"', item().name, '\",',
      '\"modelId\":\"', pipeline().parameters.modelId, '\"',
      '}'))",
    "type": "Expression"
  }
}
```

### HTTP Methods

- **POST** - Most common for document processing
- **GET** - Status checks
- **PUT** - Updates

### Query Parameters

Include in `functionName`:
```json
{
  "functionName": "process_document?timeout=300&priority=high"
}
```

### Routing Parameters

```json
{
  "functionName": "documents/process/{documentId}"
}
```

### Output Access

```json
{
  "cosmosDocumentId": "@activity('ProcessDocument').output.documentId",
  "status": "@activity('ProcessDocument').output.status"
}
```

### Key Points

- **230-Second Limit**: HTTP functions MUST respond within 230 seconds (Azure Load Balancer timeout)
- **Return Type**: Must return valid `JObject`, not `JArray`
- **Long Operations**: Use Durable Functions with status polling for operations >230s
- **Default Timeout**: 1 minute (00:01:00) if not specified
- **Max Timeout**: 10 minutes (but see 230-second HTTP limit above)
- **Retry**: Configure at activity policy level, not in linked service

### Durable Functions Pattern (for long operations)

```json
{
  "name": "StartDurableFunction",
  "type": "AzureFunctionActivity",
  "typeProperties": {
    "functionName": "StartDocumentProcessing",
    "method": "POST"
  }
},
{
  "name": "PollDurableStatus",
  "type": "WebActivity",
  "dependsOn": [
    {
      "activity": "StartDurableFunction",
      "dependencyConditions": ["Succeeded"]
    }
  ],
  "typeProperties": {
    "url": "@activity('StartDurableFunction').output.statusQueryGetUri",
    "method": "GET"
  }
}
```

---

## Error Handling and Retry

### Activity-Level Retry Policy

```json
{
  "name": "ProcessDocument",
  "type": "AzureFunctionActivity",
  "policy": {
    "timeout": "0:10:00",
    "retry": 3,
    "retryIntervalInSeconds": 30,
    "secureOutput": false,
    "secureInput": false
  }
}
```

**Policy Properties:**
- `timeout` - Max time for activity (format: `d.hh:mm:ss`)
- `retry` - Number of retry attempts (0-3 recommended)
- `retryIntervalInSeconds` - Wait between retries (30-300 recommended)

### Conditional Paths

```json
{
  "name": "ProcessDocument",
  "type": "AzureFunctionActivity"
},
{
  "name": "LogSuccess",
  "type": "WebActivity",
  "dependsOn": [
    {
      "activity": "ProcessDocument",
      "dependencyConditions": ["Succeeded"]
    }
  ]
},
{
  "name": "LogFailure",
  "type": "WebActivity",
  "dependsOn": [
    {
      "activity": "ProcessDocument",
      "dependencyConditions": ["Failed"]
    }
  ]
}
```

**Available Dependency Conditions:**
- `Succeeded`
- `Failed`
- `Skipped`
- `Completed` (any outcome)

### Error Handling Pattern with ForEach

```json
{
  "name": "ForEachPDF",
  "type": "ForEach",
  "typeProperties": {
    "activities": [
      {
        "name": "ProcessDocument",
        "type": "AzureFunctionActivity",
        "policy": {
          "retry": 2,
          "retryIntervalInSeconds": 30
        }
      },
      {
        "name": "LogError",
        "type": "WebActivity",
        "dependsOn": [
          {
            "activity": "ProcessDocument",
            "dependencyConditions": ["Failed"]
          }
        ],
        "typeProperties": {
          "url": "@pipeline().parameters.errorLoggingEndpoint",
          "method": "POST",
          "body": {
            "fileName": "@item().name",
            "error": "@activity('ProcessDocument').error.message"
          }
        }
      }
    ]
  }
}
```

### Pipeline-Level Error Handling

```json
{
  "activities": [
    {
      "name": "MainProcessing",
      "type": "ForEach"
    },
    {
      "name": "FinalizeSuccess",
      "type": "WebActivity",
      "dependsOn": [
        {
          "activity": "MainProcessing",
          "dependencyConditions": ["Succeeded"]
        }
      ]
    },
    {
      "name": "CleanupOnFailure",
      "type": "WebActivity",
      "dependsOn": [
        {
          "activity": "MainProcessing",
          "dependencyConditions": ["Failed"]
        }
      ]
    }
  ]
}
```

### Retry with Exponential Backoff

Not directly supported in Synapse. Implement in Azure Function:

```python
import time
from azure.core.exceptions import ServiceRequestError

def process_with_retry(max_retries=3, base_delay=2):
    for attempt in range(max_retries):
        try:
            return call_document_intelligence()
        except ServiceRequestError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            time.sleep(delay)
```

### Transient Error Handling

Configure retry for these common transient errors:
- 429 (Too Many Requests) - Document Intelligence rate limiting
- 503 (Service Unavailable) - Temporary service issues
- 504 (Gateway Timeout) - Network issues
- Connection timeouts

**Best Practice:**
```json
{
  "policy": {
    "timeout": "0:10:00",
    "retry": 3,
    "retryIntervalInSeconds": 60
  }
}
```

---

## Complete Pipeline Pattern

### Full Pipeline JSON

```json
{
  "name": "ProcessPDFsWithDocIntelligence",
  "properties": {
    "description": "Orchestrate PDF processing through Document Intelligence",
    "activities": [
      {
        "name": "GetPDFFileList",
        "type": "GetMetadata",
        "policy": {
          "timeout": "0:10:00",
          "retry": 0,
          "retryIntervalInSeconds": 30
        },
        "typeProperties": {
          "dataset": {
            "referenceName": "DS_BlobStorage_Binary",
            "type": "DatasetReference",
            "parameters": {
              "folderPath": "@pipeline().parameters.sourceFolderPath",
              "container": "@pipeline().parameters.containerName"
            }
          },
          "fieldList": ["childItems"],
          "storeSettings": {
            "type": "AzureBlobStorageReadSettings",
            "recursive": false
          }
        }
      },
      {
        "name": "FilterPDFFiles",
        "type": "Filter",
        "dependsOn": [
          {
            "activity": "GetPDFFileList",
            "dependencyConditions": ["Succeeded"]
          }
        ],
        "typeProperties": {
          "items": {
            "value": "@activity('GetPDFFileList').output.childItems",
            "type": "Expression"
          },
          "condition": {
            "value": "@and(equals(item().type, 'File'), endswith(item().name, '.pdf'))",
            "type": "Expression"
          }
        }
      },
      {
        "name": "ForEachPDF",
        "type": "ForEach",
        "dependsOn": [
          {
            "activity": "FilterPDFFiles",
            "dependencyConditions": ["Succeeded"]
          }
        ],
        "typeProperties": {
          "items": {
            "value": "@activity('FilterPDFFiles').output.value",
            "type": "Expression"
          },
          "isSequential": false,
          "batchCount": 10,
          "activities": [
            {
              "name": "ProcessDocument",
              "type": "AzureFunctionActivity",
              "policy": {
                "timeout": "0:10:00",
                "retry": 2,
                "retryIntervalInSeconds": 30
              },
              "typeProperties": {
                "functionName": "process_document",
                "method": "POST",
                "headers": {
                  "Content-Type": "application/json",
                  "x-correlation-id": "@{pipeline().RunId}"
                },
                "body": {
                  "value": "@json(concat('{\"blobUrl\":\"', pipeline().parameters.storageAccountUrl, '/', pipeline().parameters.containerName, '/', pipeline().parameters.sourceFolderPath, '/', item().name, '\",\"blobName\":\"', pipeline().parameters.sourceFolderPath, '/', item().name, '\",\"modelId\":\"', pipeline().parameters.modelId, '\"}'))",
                  "type": "Expression"
                }
              },
              "linkedServiceName": {
                "referenceName": "LS_AzureFunction",
                "type": "LinkedServiceReference"
              }
            }
          ]
        }
      }
    ],
    "parameters": {
      "containerName": {
        "type": "string",
        "defaultValue": "documents"
      },
      "sourceFolderPath": {
        "type": "string",
        "defaultValue": "incoming"
      },
      "storageAccountUrl": {
        "type": "string",
        "defaultValue": "https://storageaccount.blob.core.windows.net"
      },
      "modelId": {
        "type": "string",
        "defaultValue": "custom-model-v1"
      }
    },
    "folder": {
      "name": "DocumentProcessing"
    }
  }
}
```

### Pipeline Parameters

```json
{
  "parameters": {
    "containerName": {
      "type": "string",
      "defaultValue": "documents"
    },
    "sourceFolderPath": {
      "type": "string",
      "defaultValue": "incoming"
    },
    "storageAccountUrl": {
      "type": "string"
    },
    "modelId": {
      "type": "string",
      "defaultValue": "prebuilt-invoice"
    }
  }
}
```

### Triggering the Pipeline

**Manual trigger via Azure CLI:**
```bash
az synapse pipeline create-run \
  --workspace-name synapse-workspace-name \
  --name ProcessPDFsWithDocIntelligence \
  --parameters sourceFolderPath=incoming/2025-01
```

**Scheduled trigger:**
```json
{
  "name": "DailyDocumentProcessing",
  "properties": {
    "type": "ScheduleTrigger",
    "typeProperties": {
      "recurrence": {
        "frequency": "Day",
        "interval": 1,
        "startTime": "2025-01-01T02:00:00Z",
        "timeZone": "UTC"
      }
    },
    "pipelines": [
      {
        "pipelineReference": {
          "referenceName": "ProcessPDFsWithDocIntelligence",
          "type": "PipelineReference"
        },
        "parameters": {
          "sourceFolderPath": "incoming"
        }
      }
    ]
  }
}
```

---

## Common Gotchas

### 1. Web Activity / Azure Function Timeout

**Issue**: Default timeout is only 1 minute.

**Solution**: Always explicitly set timeout to 10 minutes max:
```json
{
  "policy": {
    "timeout": "0:10:00"
  }
}
```

**Critical Limitation**: HTTP-triggered Azure Functions have a hard 230-second limit due to Azure Load Balancer. For longer operations, use Durable Functions.

### 2. ForEach Parallel Limits

**Issue**: Too many parallel requests overwhelm Document Intelligence (15 TPS default).

**Solution**: Set appropriate `batchCount`:
```json
{
  "batchCount": 10  // Process 10 PDFs concurrently
}
```

### 3. GetMetadata Performance

**Issue**: Using `lastModified` filter on folders with thousands of files causes timeouts.

**Solution**:
- Keep processing folders small
- Use folder structure to partition data (e.g., by date)
- Filter at the blob storage level when possible

### 4. Filter Activity Output

**Issue**: Forgetting to use `.output.value` instead of just `.output`.

**Incorrect:**
```json
"items": "@activity('FilterPDFFiles').output"
```

**Correct:**
```json
"items": "@activity('FilterPDFFiles').output.value"
```

### 5. Item() Expression Scope

**Issue**: Using `@item()` outside of ForEach context.

**Solution**: `@item()` only works inside ForEach activities. Use `@activity()` elsewhere.

### 6. Nested ForEach Limitation

**Issue**: Cannot nest ForEach loops directly.

**Solution**: Use Execute Pipeline activity to call child pipeline with ForEach:
```json
{
  "name": "ForEachFolder",
  "type": "ForEach",
  "activities": [
    {
      "name": "ExecuteChildPipeline",
      "type": "ExecutePipeline",
      "typeProperties": {
        "pipeline": {
          "referenceName": "ProcessFilesInFolder",
          "type": "PipelineReference"
        }
      }
    }
  ]
}
```

### 7. JSON Body Construction

**Issue**: Complex JSON bodies with dynamic values are error-prone.

**Solution**: Use `concat()` with proper escaping or consider passing simple parameters:

```json
{
  "body": {
    "value": "@json(concat('{\"blobName\":\"', item().name, '\"}'))",
    "type": "Expression"
  }
}
```

### 8. Managed Identity Permissions

**Issue**: Azure Function activity fails with 403 when using Managed Identity.

**Solution**: Grant Synapse workspace managed identity appropriate roles:
```bash
az role assignment create \
  --role "Website Contributor" \
  --assignee-object-id <synapse-managed-identity-id> \
  --scope /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{function-app}
```

### 9. Document Intelligence Rate Limiting

**Issue**: 429 errors when processing many documents in parallel.

**Solution**:
- Implement exponential backoff in Azure Function
- Configure retry policy with appropriate intervals
- Adjust `batchCount` to stay within rate limits

```json
{
  "policy": {
    "timeout": "0:10:00",
    "retry": 3,
    "retryIntervalInSeconds": 60
  }
}
```

### 10. Large File Processing

**Issue**: PDFs larger than 10MB take >30 seconds to process.

**Solution**:
- Set generous timeouts (10 minutes)
- Use async Document Intelligence operations with polling
- Consider Durable Functions for very large documents

---

## Additional Resources

### Microsoft Learn Documentation
- [Get Metadata activity - Azure Data Factory & Azure Synapse](https://learn.microsoft.com/en-us/azure/data-factory/control-flow-get-metadata-activity)
- [ForEach activity - Azure Data Factory & Azure Synapse](https://learn.microsoft.com/bs-latn-ba/Azure/data-factory/control-flow-for-each-activity)
- [Azure Function Activity - Azure Data Factory & Azure Synapse](https://learn.microsoft.com/en-us/azure/data-factory/control-flow-azure-function-activity)
- [Filter activity - Azure Data Factory & Azure Synapse](https://learn.microsoft.com/en-us/azure/data-factory/control-flow-filter-activity)
- [Pipeline failure and error handling - Azure Data Factory](https://learn.microsoft.com/en-us/azure/data-factory/tutorial-pipeline-failure-error-handling)

### Community Resources
- [How To Retry Pipelines in Azure Data Factory and Synapse Analytics](https://segunakinyemi.com/blog/adf-synapse-pipeline-retries/)
- [Get Metadata vs Lookup activity in Azure Data Factory & Azure Synapse Analytics](https://medium.com/@rganesh0203/get-metadata-vs-lookup-activity-in-azure-data-factory-azure-synapse-analytics-9eacd6d2e843)
- [Azure Synapse get metadata - Stack Overflow](https://stackoverflow.com/questions/70418638/azure-synapse-get-metadata)
- [Request Timeout on ADF Web Activity to Synapse - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2115728/request-timeout-on-adf-web-activity-to-synapse)

### GitHub Examples
- [MicrosoftDocs/azure-docs - GetMetadata Activity](https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/data-factory/control-flow-get-metadata-activity.md)
- [MicrosoftDocs/azure-docs - Filter Activity](https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/data-factory/control-flow-filter-activity.md)

---

## Version History

- **v1.0** (2025-12-02): Initial documentation covering GetMetadata, Filter, ForEach, Azure Function activities, error handling, and retry patterns
