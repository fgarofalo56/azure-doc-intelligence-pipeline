@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

// Generate unique workbook ID
var workbookName = '${prefix}-workbook-${environment}'
var workbookId = guid(subscription().subscriptionId, resourceGroup().id, workbookName)

// Workbook definition with dashboard panels
var workbookContent = {
  version: 'Notebook/1.0'
  items: [
    // Header section
    {
      type: 1
      content: {
        json: '# Document Processing Pipeline Dashboard\n\nReal-time monitoring for the Document Intelligence PDF processing pipeline.'
      }
      name: 'header'
    }
    // Time range parameter
    {
      type: 9
      content: {
        version: 'KqlParameterItem/1.0'
        parameters: [
          {
            id: 'timeRange'
            version: 'KqlParameterItem/1.0'
            name: 'TimeRange'
            type: 4
            isRequired: true
            value: {
              durationMs: 86400000
            }
            typeSettings: {
              selectableValues: [
                { durationMs: 3600000 }
                { durationMs: 14400000 }
                { durationMs: 43200000 }
                { durationMs: 86400000 }
                { durationMs: 172800000 }
                { durationMs: 604800000 }
              ]
            }
          }
        ]
      }
      name: 'parameters'
    }
    // Processing Throughput panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          FunctionAppLogs
          | where TimeGenerated >= ago(24h)
          | where Message contains "processed" or Message contains "completed"
          | summarize DocumentsProcessed = count() by bin(TimeGenerated, 1h)
          | render timechart
        '''
        size: 0
        title: 'Documents Processed Over Time'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
      }
      name: 'processingThroughput'
    }
    // Error Rates panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          FunctionAppLogs
          | where TimeGenerated >= ago(24h)
          | where Level == "Error" or Level == "Warning"
          | summarize Errors = countif(Level == "Error"), Warnings = countif(Level == "Warning") by bin(TimeGenerated, 1h)
          | render timechart
        '''
        size: 0
        title: 'Error and Warning Rates'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'Errors', color: 'redBright' }
            { seriesName: 'Warnings', color: 'yellow' }
          ]
        }
      }
      name: 'errorRates'
    }
    // Document Intelligence Latency panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where Message contains "Document Intelligence" or Message contains "analyze_document"
          | extend Duration = extract("duration[=:]\\s*(\\d+)", 1, Message)
          | where isnotempty(Duration)
          | summarize AvgLatencyMs = avg(todouble(Duration)), P95LatencyMs = percentile(todouble(Duration), 95) by bin(TimeGenerated, 1h)
          | render timechart
        '''
        size: 0
        title: 'Document Intelligence Latency (ms)'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
      }
      name: 'docIntelLatency'
    }
    // Cosmos DB RU Consumption panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AzureDiagnostics
          | where TimeGenerated >= ago(24h)
          | where ResourceProvider == "MICROSOFT.DOCUMENTDB"
          | where Category == "DataPlaneRequests"
          | summarize TotalRUs = sum(todouble(requestCharge_s)) by bin(TimeGenerated, 1h)
          | render timechart
        '''
        size: 0
        title: 'Cosmos DB RU Consumption'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
      }
      name: 'cosmosRuConsumption'
    }
    // Function Execution Summary panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          FunctionAppLogs
          | where TimeGenerated >= ago(24h)
          | summarize
              TotalExecutions = count(),
              SuccessfulExecutions = countif(Level != "Error"),
              FailedExecutions = countif(Level == "Error")
          | extend SuccessRate = round(100.0 * SuccessfulExecutions / TotalExecutions, 2)
        '''
        size: 4
        title: 'Function Execution Summary (24h)'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'tiles'
        tileSettings: {
          showBorder: false
          titleContent: {
            columnMatch: 'Column1'
            formatter: 1
          }
          leftContent: {
            columnMatch: 'TotalExecutions'
            formatter: 12
            numberFormat: {
              unit: 17
              options: {
                style: 'decimal'
              }
            }
          }
        }
      }
      name: 'executionSummary'
    }
    // Processing Status by Source panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          FunctionAppLogs
          | where TimeGenerated >= ago(24h)
          | where Message contains "sourceFile" or Message contains "blob"
          | extend Status = case(
              Level == "Error", "Failed",
              Message contains "completed", "Completed",
              Message contains "processing", "Processing",
              "Unknown"
          )
          | summarize Count = count() by Status
          | render piechart
        '''
        size: 3
        title: 'Processing Status Distribution'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'piechart'
      }
      name: 'processingStatus'
    }
    // Recent Errors panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          FunctionAppLogs
          | where TimeGenerated >= ago(24h)
          | where Level == "Error"
          | project TimeGenerated, FunctionName, Message
          | top 20 by TimeGenerated desc
        '''
        size: 0
        title: 'Recent Errors'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'table'
        gridSettings: {
          formatters: [
            {
              columnMatch: 'TimeGenerated'
              formatter: 6
            }
            {
              columnMatch: 'Message'
              formatter: 1
            }
          ]
        }
      }
      name: 'recentErrors'
    }
    // Cache Hit Rate panel (for new cache service)
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where Message contains "Cache hit" or Message contains "Cache miss"
          | extend CacheResult = iff(Message contains "Cache hit", "Hit", "Miss")
          | summarize Count = count() by CacheResult
          | render piechart
        '''
        size: 3
        title: 'Cache Hit Rate'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'piechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'Hit', color: 'green' }
            { seriesName: 'Miss', color: 'orange' }
          ]
        }
      }
      name: 'cacheHitRate'
    }
    // Dead Letter Queue Depth panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where Message contains "dead_letter" or Message contains "DLQ"
          | extend Action = case(
              Message contains "added to dead letter", "Added",
              Message contains "retry", "Retry Attempted",
              Message contains "resolved", "Resolved",
              "Other"
          )
          | summarize Count = count() by bin(TimeGenerated, 1h), Action
          | render timechart
        '''
        size: 0
        title: 'Dead Letter Queue Activity'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'Added', color: 'redBright' }
            { seriesName: 'Retry Attempted', color: 'yellow' }
            { seriesName: 'Resolved', color: 'green' }
          ]
        }
      }
      name: 'dlqActivity'
    }
    // Circuit Breaker States panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where Message contains "circuit" or Message contains "Circuit"
          | extend State = case(
              Message contains "OPEN" or Message contains "opened", "Open",
              Message contains "HALF_OPEN" or Message contains "half-open", "Half-Open",
              Message contains "CLOSED" or Message contains "closed", "Closed",
              "Unknown"
          )
          | summarize StateChanges = count() by bin(TimeGenerated, 15m), State
          | render timechart
        '''
        size: 0
        title: 'Circuit Breaker State Changes'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'Open', color: 'redBright' }
            { seriesName: 'Half-Open', color: 'yellow' }
            { seriesName: 'Closed', color: 'green' }
          ]
        }
      }
      name: 'circuitBreakerStates'
    }
    // Latency Percentiles panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppRequests
          | where TimeGenerated >= ago(24h)
          | summarize
              P50 = percentile(DurationMs, 50),
              P90 = percentile(DurationMs, 90),
              P95 = percentile(DurationMs, 95),
              P99 = percentile(DurationMs, 99)
            by bin(TimeGenerated, 15m)
          | render timechart
        '''
        size: 0
        title: 'Request Latency Percentiles (ms)'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'timechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'P50', color: 'green' }
            { seriesName: 'P90', color: 'blue' }
            { seriesName: 'P95', color: 'yellow' }
            { seriesName: 'P99', color: 'redBright' }
          ]
        }
      }
      name: 'latencyPercentiles'
    }
    // DLQ Depth Summary panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where Message contains "dead_letter" or Message contains "DLQ"
          | where Message contains "added"
          | summarize
              TotalAdded = count(),
              Last1Hour = countif(TimeGenerated >= ago(1h)),
              Last4Hours = countif(TimeGenerated >= ago(4h))
        '''
        size: 4
        title: 'Dead Letter Queue Summary (24h)'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'tiles'
        tileSettings: {
          showBorder: true
        }
      }
      name: 'dlqSummary'
    }
    // Error Types Breakdown panel
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
          AppTraces
          | where TimeGenerated >= ago(24h)
          | where SeverityLevel >= 3
          | extend ErrorType = case(
              Message contains "rate limit" or Message contains "429", "Rate Limit",
              Message contains "timeout" or Message contains "timed out", "Timeout",
              Message contains "authentication" or Message contains "401", "Auth Error",
              Message contains "not found" or Message contains "404", "Not Found",
              Message contains "circuit breaker", "Circuit Breaker",
              Message contains "cosmos" or Message contains "CosmosDB", "Cosmos DB",
              Message contains "blob" or Message contains "storage", "Storage",
              Message contains "document intelligence", "Doc Intelligence",
              "Other"
          )
          | summarize Count = count() by ErrorType
          | order by Count desc
          | render piechart
        '''
        size: 3
        title: 'Error Types Distribution'
        timeContext: {
          durationMs: 86400000
        }
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [
          logAnalyticsWorkspaceId
        ]
        visualization: 'piechart'
      }
      name: 'errorTypesBreakdown'
    }
  ]
  isLocked: false
  fallbackResourceIds: [
    logAnalyticsWorkspaceId
  ]
}

// Azure Workbook resource
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookId
  location: location
  tags: union(tags, {
    'hidden-title': 'Document Processing Pipeline Dashboard'
  })
  kind: 'shared'
  properties: {
    displayName: 'Document Processing Pipeline Dashboard - ${environment}'
    category: 'workbook'
    version: '1.0'
    serializedData: string(workbookContent)
    sourceId: logAnalyticsWorkspaceId
  }
}

@description('Workbook name')
output name string = workbook.name

@description('Workbook resource ID')
output resourceId string = workbook.id

@description('Workbook display name')
output displayName string = workbook.properties.displayName
