// =============================================================================
// AZURE MONITOR ALERT RULES
// =============================================================================
// Provides comprehensive alerting for document processing pipeline monitoring
// Includes alerts for: errors, latency, CPU/memory, dead letter queue, restarts

@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Application Insights resource ID')
param appInsightsResourceId string

@description('Function App resource ID')
param functionAppResourceId string

@description('Action group resource ID for alert notifications')
param actionGroupId string = ''

@description('Enable alert rules')
param enableAlerts bool = true

@description('Cosmos DB account resource ID (for DLQ monitoring)')
param cosmosDbResourceId string = ''

// =============================================================================
// ALERT CONFIGURATION THRESHOLDS
// =============================================================================

@description('Error rate threshold percentage (default: 5%)')
param errorRateThreshold int = 5

@description('Response time threshold in seconds (default: 30s)')
param responseTimeThreshold int = 30

@description('CPU usage threshold percentage (default: 80%)')
param cpuThreshold int = 80

@description('Memory usage threshold percentage (default: 85%)')
param memoryThreshold int = 85

@description('Dead letter queue depth threshold (default: 10)')
param dlqDepthThreshold int = 10

@description('Function app restart threshold count in 1 hour (default: 3)')
param restartThreshold int = 3

// =============================================================================
// ALERT ACTION GROUP (creates one if not provided)
// =============================================================================

resource alertActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableAlerts && actionGroupId == '') {
  name: '${prefix}-alerts-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    groupShortName: '${prefix}alerts'
    enabled: true
    emailReceivers: []
    smsReceivers: []
    webhookReceivers: []
    // Add receivers as needed - can be updated post-deployment
  }
}

var effectiveActionGroupId = actionGroupId != '' ? actionGroupId : alertActionGroup.id

// =============================================================================
// ERROR RATE ALERT
// =============================================================================
// Triggers when HTTP 5xx error rate exceeds threshold

resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-error-rate-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert when error rate exceeds ${errorRateThreshold}%'
    severity: 1 // Critical
    enabled: true
    scopes: [
      appInsightsResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighErrorRate'
          metricName: 'requests/failed'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: errorRateThreshold
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// RESPONSE TIME ALERT
// =============================================================================
// Triggers when average response time exceeds threshold

resource responseTimeAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-response-time-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert when response time exceeds ${responseTimeThreshold} seconds'
    severity: 2 // Warning
    enabled: true
    scopes: [
      appInsightsResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'SlowResponseTime'
          metricName: 'requests/duration'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: responseTimeThreshold * 1000 // Convert to milliseconds
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// CPU USAGE ALERT
// =============================================================================
// Triggers when CPU usage exceeds threshold

resource cpuAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-cpu-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert when CPU usage exceeds ${cpuThreshold}%'
    severity: 2 // Warning
    enabled: true
    scopes: [
      functionAppResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighCPU'
          metricName: 'CpuPercentage'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: cpuThreshold
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// MEMORY USAGE ALERT
// =============================================================================
// Triggers when memory usage exceeds threshold

resource memoryAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-memory-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert when memory usage exceeds ${memoryThreshold}%'
    severity: 2 // Warning
    enabled: true
    scopes: [
      functionAppResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighMemory'
          metricName: 'MemoryWorkingSet'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: memoryThreshold * 1024 * 1024 * 10 // Convert % to approximate bytes for 1GB plan
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// HTTP 5XX ERRORS ALERT
// =============================================================================
// Triggers on any HTTP 5xx server errors

resource http5xxAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-http5xx-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert on HTTP 5xx server errors'
    severity: 1 // Critical
    enabled: true
    scopes: [
      functionAppResourceId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Http5xxErrors'
          metricName: 'Http5xx'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: 0
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// FUNCTION EXECUTION FAILURES ALERT
// =============================================================================
// Triggers when function executions fail

resource functionFailureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-func-failures-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert on function execution failures'
    severity: 1 // Critical
    enabled: true
    scopes: [
      functionAppResourceId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FunctionFailures'
          metricName: 'FunctionExecutionCount'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: 5 // Allow some failures before alerting
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
          dimensions: [
            {
              name: 'FunctionName'
              operator: 'Include'
              values: ['*']
            }
          ]
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// AVAILABILITY ALERT (Health Check)
// =============================================================================
// Triggers when health endpoint returns failures

resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: '${prefix}-alert-availability-${environment}'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Alert when service availability drops'
    severity: 1 // Critical
    enabled: true
    scopes: [
      appInsightsResourceId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'LowAvailability'
          metricName: 'availabilityResults/availabilityPercentage'
          metricNamespace: 'microsoft.insights/components'
          operator: 'LessThan'
          threshold: 99 // Alert if availability drops below 99%
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: actionGroupId != '' || !enableAlerts ? [
      {
        actionGroupId: effectiveActionGroupId
        webHookProperties: {}
      }
    ] : []
  }
}

// =============================================================================
// LOG-BASED ALERTS (using scheduled query rules)
// =============================================================================

// Dead Letter Queue Depth Alert
resource dlqDepthAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = if (enableAlerts && cosmosDbResourceId != '') {
  name: '${prefix}-alert-dlq-depth-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: 'Dead Letter Queue Depth Alert'
    description: 'Alert when dead letter queue exceeds ${dlqDepthThreshold} items'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT15M'
    scopes: [
      appInsightsResourceId
    ]
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
            customMetrics
            | where name == "dlq_depth" or name == "dead_letter_queue_depth"
            | summarize DLQDepth = max(value) by bin(timestamp, 5m)
            | where DLQDepth > ${dlqDepthThreshold}
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupId != '' || !enableAlerts ? [effectiveActionGroupId] : []
    }
  }
}

// Function App Restart Alert
resource restartAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = if (enableAlerts) {
  name: '${prefix}-alert-restarts-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: 'Function App Restart Alert'
    description: 'Alert when function app restarts more than ${restartThreshold} times in 1 hour'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT15M'
    scopes: [
      appInsightsResourceId
    ]
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: '''
            traces
            | where message contains "Host started" or message contains "Host initialized"
            | summarize RestartCount = count() by bin(timestamp, 1h)
            | where RestartCount > ${restartThreshold}
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupId != '' || !enableAlerts ? [effectiveActionGroupId] : []
    }
  }
}

// Circuit Breaker Open Alert
resource circuitBreakerAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = if (enableAlerts) {
  name: '${prefix}-alert-circuit-breaker-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: 'Circuit Breaker Open Alert'
    description: 'Alert when circuit breaker opens'
    severity: 1 // Critical
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [
      appInsightsResourceId
    ]
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          query: '''
            traces
            | where message contains "circuit breaker" and (message contains "opened" or message contains "OPEN")
            | summarize OpenCount = count() by bin(timestamp, 5m)
            | where OpenCount > 0
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupId != '' || !enableAlerts ? [effectiveActionGroupId] : []
    }
  }
}

// Document Processing Error Rate Alert
resource docProcessingErrorAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = if (enableAlerts) {
  name: '${prefix}-alert-doc-processing-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: 'Document Processing Error Alert'
    description: 'Alert on document processing failures'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [
      appInsightsResourceId
    ]
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
            customEvents
            | where name == "DocumentProcessingFailed" or name == "document_processing_failed"
            | summarize FailureCount = count() by bin(timestamp, 15m)
            | where FailureCount > 5
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupId != '' || !enableAlerts ? [effectiveActionGroupId] : []
    }
  }
}

// =============================================================================
// OUTPUTS
// =============================================================================

@description('Action group resource ID')
output actionGroupId string = effectiveActionGroupId

@description('Error rate alert resource ID')
output errorRateAlertId string = enableAlerts ? errorRateAlert.id : ''

@description('Response time alert resource ID')
output responseTimeAlertId string = enableAlerts ? responseTimeAlert.id : ''

@description('CPU alert resource ID')
output cpuAlertId string = enableAlerts ? cpuAlert.id : ''

@description('Memory alert resource ID')
output memoryAlertId string = enableAlerts ? memoryAlert.id : ''

@description('HTTP 5xx alert resource ID')
output http5xxAlertId string = enableAlerts ? http5xxAlert.id : ''

@description('Availability alert resource ID')
output availabilityAlertId string = enableAlerts ? availabilityAlert.id : ''

@description('DLQ depth alert resource ID')
output dlqDepthAlertId string = enableAlerts && cosmosDbResourceId != '' ? dlqDepthAlert.id : ''

@description('Restart alert resource ID')
output restartAlertId string = enableAlerts ? restartAlert.id : ''

@description('Circuit breaker alert resource ID')
output circuitBreakerAlertId string = enableAlerts ? circuitBreakerAlert.id : ''

@description('Document processing error alert resource ID')
output docProcessingErrorAlertId string = enableAlerts ? docProcessingErrorAlert.id : ''
