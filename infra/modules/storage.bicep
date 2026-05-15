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

// =============================================================================
// SECURITY HARDENING PARAMETERS
// =============================================================================

@description('Enable network hardening (restrict public access). For production, consider setting to true.')
param enableNetworkHardening bool = environment == 'prod'

@description('Allowed IP addresses when network hardening is enabled (CIDR notation). Empty list means only VNet/Private Endpoint access.')
param allowedIpRanges array = []

@description('Allowed subnet resource IDs for VNet service endpoints')
param allowedSubnetIds array = []

// Storage account name: lowercase, no hyphens, 3-24 chars
var storageAccountName = toLower('${prefix}st${uniqueString(resourceGroup().id)}')

// Build IP rules array from allowed IP ranges
var ipRules = [for ip in allowedIpRanges: {
  value: ip
  action: 'Allow'
}]

// Build virtual network rules array from subnet IDs
var virtualNetworkRules = [for subnetId in allowedSubnetIds: {
  id: subnetId
  action: 'Allow'
}]

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Network hardening: Deny by default in prod, Allow in dev
    networkAcls: {
      defaultAction: enableNetworkHardening ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
      ipRules: enableNetworkHardening ? ipRules : []
      virtualNetworkRules: enableNetworkHardening ? virtualNetworkRules : []
    }
    // Allow shared key access only if network hardening is disabled (for Function App compatibility)
    allowSharedKeyAccess: true
    encryption: {
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// Container for PDF documents to process
resource pdfsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobServices
  name: 'pdfs'
  properties: {
    publicAccess: 'None'
  }
}

// Container for staging/temporary files
resource stagingContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobServices
  name: 'staging'
  properties: {
    publicAccess: 'None'
  }
}

// Container for processed documents archive
resource processedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobServices
  name: 'processed'
  properties: {
    publicAccess: 'None'
  }
}

// Diagnostic settings for storage account
resource storageAccountDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${storageAccount.name}-diagnostics'
  scope: storageAccount
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [
      {
        category: 'Transaction'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'Capacity'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

// Diagnostic settings for blob service
resource blobServiceDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${storageAccount.name}-blob-diagnostics'
  scope: blobServices
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'StorageRead'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'StorageWrite'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'StorageDelete'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'Transaction'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'Capacity'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

@description('Storage account name')
output name string = storageAccount.name

@description('Storage account resource ID')
output resourceId string = storageAccount.id

@description('Storage account primary blob endpoint')
output primaryBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob

// WARNING: Connection strings should be stored in Key Vault for production
// Consider using managed identity authentication instead
// This output is used for module chaining to Key Vault secret storage
@description('Storage account connection string')
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
