@description('Name of the existing Cosmos DB account')
param cosmosAccountName string

@description('Database name to create')
param databaseName string = 'DocumentsDB'

@description('Container name to create')
param containerName string = 'ExtractedDocuments'

@description('Enable analytical store for Synapse Link')
param enableAnalyticalStore bool = false

@description('Analytical store TTL in seconds (-1 for infinite, 0 to disable)')
param analyticalStorageTtl int = -1

// Reference existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

// Create database in existing account
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Create container in database
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
      // NOTE: Synapse Link must already be enabled at the account level for this to work
      analyticalStorageTtl: enableAnalyticalStore ? analyticalStorageTtl : 0
    }
  }
}

@description('Database name')
output databaseName string = database.name

@description('Container name')
output containerName string = container.name

@description('Cosmos DB account endpoint')
output endpoint string = cosmosAccount.properties.documentEndpoint
