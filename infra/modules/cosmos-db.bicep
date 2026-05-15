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

// =============================================================================
// SECURITY HARDENING PARAMETERS
// =============================================================================

@description('Enable network hardening (restrict public access). For production, set to true and use Private Endpoints.')
param enableNetworkHardening bool = environment == 'prod'

@description('Allowed IP addresses when network hardening is enabled (CIDR notation). Empty means Private Endpoint only.')
param allowedIpRanges array = []

@description('Allowed subnet resource IDs for VNet service endpoints')
param allowedSubnetIds array = []

// =============================================================================
// BACKUP & DISASTER RECOVERY PARAMETERS
// =============================================================================

@description('Backup policy type: Periodic (default) or Continuous (enables point-in-time restore)')
@allowed([
  'Periodic'
  'Continuous'
])
param backupPolicyType string = environment == 'prod' ? 'Continuous' : 'Periodic'

@description('For Periodic backup: interval between backups in minutes (60-1440, default 240 = 4 hours)')
@minValue(60)
@maxValue(1440)
param backupIntervalInMinutes int = 240

@description('For Periodic backup: retention period in hours (8-720, default 8)')
@minValue(8)
@maxValue(720)
param backupRetentionIntervalInHours int = environment == 'prod' ? 168 : 8  // 1 week for prod, 8 hours for dev

@description('For Periodic backup: storage redundancy (Geo, Local, Zone)')
@allowed([
  'Geo'
  'Local'
  'Zone'
])
param backupStorageRedundancy string = environment == 'prod' ? 'Geo' : 'Local'

@description('For Continuous backup: tier (Continuous7Days for free tier, Continuous30Days for standard)')
@allowed([
  'Continuous7Days'
  'Continuous30Days'
])
param continuousBackupTier string = environment == 'prod' ? 'Continuous30Days' : 'Continuous7Days'

@description('Enable geo-replication with secondary region for high availability (production only)')
param enableGeoReplication bool = false

@description('Secondary region for geo-replication (if enabled)')
param secondaryLocation string = ''

@description('Enable availability zones for zone redundancy')
param enableZoneRedundancy bool = environment == 'prod'

// Cosmos DB account name
var cosmosAccountName = '${prefix}-cosmos-${environment}'

// Build IP rules array from allowed IP ranges (Cosmos DB uses different format than Storage/Key Vault)
var ipRules = [for ip in allowedIpRanges: {
  ipAddressOrRange: ip
}]

// Build virtual network rules array from subnet IDs
var virtualNetworkRules = [for subnetId in allowedSubnetIds: {
  id: subnetId
  ignoreMissingVNetServiceEndpoint: false
}]

// Build locations array for geo-replication
var primaryLocation = {
  locationName: location
  failoverPriority: 0
  isZoneRedundant: enableZoneRedundancy
}

var secondaryLocationConfig = enableGeoReplication && secondaryLocation != '' ? [{
  locationName: secondaryLocation
  failoverPriority: 1
  isZoneRedundant: enableZoneRedundancy
}] : []

var allLocations = concat([primaryLocation], secondaryLocationConfig)

// Build backup policy based on type
var periodicBackupPolicy = {
  type: 'Periodic'
  periodicModeProperties: {
    backupIntervalInMinutes: backupIntervalInMinutes
    backupRetentionIntervalInHours: backupRetentionIntervalInHours
    backupStorageRedundancy: backupStorageRedundancy
  }
}

var continuousBackupPolicy = {
  type: 'Continuous'
  continuousModeProperties: {
    tier: continuousBackupTier
  }
}

var backupPolicy = backupPolicyType == 'Continuous' ? continuousBackupPolicy : periodicBackupPolicy

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
    locations: allLocations
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    // Backup policy configuration
    backupPolicy: backupPolicy
    // Network hardening: Disable public access in prod, enable in dev
    publicNetworkAccess: enableNetworkHardening ? 'Disabled' : 'Enabled'
    // IP filter rules
    ipRules: enableNetworkHardening ? ipRules : []
    // VNet service endpoint rules
    virtualNetworkRules: enableNetworkHardening ? virtualNetworkRules : []
    isVirtualNetworkFilterEnabled: enableNetworkHardening
    // Enable automatic failover when geo-replication is configured
    enableAutomaticFailover: enableGeoReplication
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

@description('Backup policy type configured')
output backupPolicyType string = backupPolicyType

@description('Geo-replication enabled status')
output geoReplicationEnabled bool = enableGeoReplication

@description('Zone redundancy enabled status')
output zoneRedundancyEnabled bool = enableZoneRedundancy

@description('Secondary region (if geo-replication enabled)')
output secondaryRegion string = enableGeoReplication ? secondaryLocation : ''
