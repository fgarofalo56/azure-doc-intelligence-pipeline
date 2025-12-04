@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Database name')
param databaseName string = 'DocumentsDB'

@description('Container name')
param containerName string = 'ExtractedDocuments'

@description('Log Analytics workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

@description('Enable Azure Synapse Link for analytical queries')
param enableSynapseLink bool = true

@description('Analytical store TTL in seconds (-1 for infinite, 0 to disable)')
param analyticalStorageTtl int = -1

// Cosmos DB account name
var cosmosAccountName = '${prefix}-cosmos-${environment}'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: cosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: environment == 'dev'
    // Enable Azure Synapse Link for analytical queries
    enableAnalyticalStorage: enableSynapseLink
    analyticalStorageConfiguration: enableSynapseLink ? {
      schemaType: 'FullFidelity'
    } : null
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    publicNetworkAccess: 'Enabled'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    disableLocalAuth: false
    minimalTlsVersion: 'Tls12'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/sourceFile'
        ]
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
      defaultTtl: -1
      // Enable analytical store for Synapse Link (TTL: -1 = infinite, 0 = disabled)
      analyticalStorageTtl: enableSynapseLink ? analyticalStorageTtl : 0
    }
  }
}

// Diagnostic settings for Cosmos DB
resource cosmosDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${cosmosAccount.name}-diagnostics'
  scope: cosmosAccount
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'DataPlaneRequests'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'QueryRuntimeStatistics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'PartitionKeyStatistics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'PartitionKeyRUConsumption'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'ControlPlaneRequests'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'Requests'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

@description('Cosmos DB account endpoint')
output endpoint string = cosmosAccount.properties.documentEndpoint

@description('Cosmos DB account resource ID')
output resourceId string = cosmosAccount.id

@description('Cosmos DB account name')
output name string = cosmosAccount.name

@description('Cosmos DB database name')
output databaseName string = database.name

@description('Cosmos DB container name')
output containerName string = container.name

@description('Cosmos DB principal ID for managed identity')
output principalId string = cosmosAccount.identity.principalId

// WARNING: Connection strings should be stored in Key Vault for production
// Consider using managed identity authentication instead
// This output is used for module chaining to Key Vault secret storage
@description('Cosmos DB primary connection string')
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = cosmosAccount.listConnectionStrings().connectionStrings[0].connectionString

@description('Synapse Link enabled status')
output synapseLinkEnabled bool = enableSynapseLink

@description('Cosmos DB account key for Synapse Link connection')
#disable-next-line outputs-should-not-contain-secrets
output accountKey string = cosmosAccount.listKeys().primaryMasterKey
