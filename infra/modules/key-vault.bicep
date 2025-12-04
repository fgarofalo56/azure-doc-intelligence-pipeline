@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

// Optional secrets to store in Key Vault
@description('Storage account connection string to store as secret')
@secure()
param storageConnectionString string = ''

@description('Document Intelligence API key to store as secret')
@secure()
param docIntelApiKey string = ''

@description('Cosmos DB connection string to store as secret')
@secure()
param cosmosConnectionString string = ''

@description('Log Analytics workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

// Key Vault name (3-24 chars, alphanumeric and hyphens)
var keyVaultName = '${prefix}-kv-${environment}'

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: environment == 'prod'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Store secrets in Key Vault if provided
resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = if (storageConnectionString != '') {
  parent: keyVault
  name: 'storage-connection-string'
  properties: {
    value: storageConnectionString
  }
}

resource docIntelApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = if (docIntelApiKey != '') {
  parent: keyVault
  name: 'doc-intel-api-key'
  properties: {
    value: docIntelApiKey
  }
}

resource cosmosConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = if (cosmosConnectionString != '') {
  parent: keyVault
  name: 'cosmos-connection-string'
  properties: {
    value: cosmosConnectionString
  }
}

// Diagnostic settings for Key Vault
resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${keyVault.name}-diagnostics'
  scope: keyVault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AuditEvent'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'AzurePolicyEvaluationDetails'
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

// Variables for Key Vault references (avoid linter false positives)
var hasStorageSecret = storageConnectionString != ''
var hasDocIntelSecret = docIntelApiKey != ''
var hasCosmosSecret = cosmosConnectionString != ''

@description('Key Vault URI')
output vaultUri string = keyVault.properties.vaultUri

@description('Key Vault resource ID')
output resourceId string = keyVault.id

@description('Key Vault name')
output name string = keyVault.name

// Key Vault reference URIs for App Settings (format: @Microsoft.KeyVault(SecretUri=...))
#disable-next-line outputs-should-not-contain-secrets
@description('Key Vault reference for storage connection string')
output storageConnectionStringRef string = hasStorageSecret
  ? '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=storage-connection-string)'
  : ''

#disable-next-line outputs-should-not-contain-secrets
@description('Key Vault reference for Document Intelligence API key')
output docIntelApiKeyRef string = hasDocIntelSecret
  ? '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=doc-intel-api-key)'
  : ''

#disable-next-line outputs-should-not-contain-secrets
@description('Key Vault reference for Cosmos DB connection string')
output cosmosConnectionStringRef string = hasCosmosSecret
  ? '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=cosmos-connection-string)'
  : ''
