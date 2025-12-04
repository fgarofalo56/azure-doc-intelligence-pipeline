@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Log Analytics workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

// Document Intelligence resource name
var documentIntelligenceName = '${prefix}-di-${environment}'

// CRITICAL: Kind is 'FormRecognizer' despite service rename to Document Intelligence
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: documentIntelligenceName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: {
    name: environment == 'prod' ? 'S0' : 'F0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: documentIntelligenceName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false
  }
}

// Diagnostic settings for Document Intelligence
resource docIntelDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${documentIntelligence.name}-diagnostics'
  scope: documentIntelligence
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'Audit'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'RequestResponse'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'Trace'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

@description('Document Intelligence endpoint')
output endpoint string = documentIntelligence.properties.endpoint

@description('Document Intelligence resource ID')
output resourceId string = documentIntelligence.id

@description('Document Intelligence resource name')
output name string = documentIntelligence.name

@description('Document Intelligence principal ID for managed identity')
output principalId string = documentIntelligence.identity.principalId

// WARNING: API keys should be stored in Key Vault for production
// Consider using managed identity authentication instead
// This output is used for module chaining to Key Vault secret storage
@description('Document Intelligence API key')
#disable-next-line outputs-should-not-contain-secrets
output apiKey string = documentIntelligence.listKeys().key1
