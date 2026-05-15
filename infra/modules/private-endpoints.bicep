@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

// =============================================================================
// PRIVATE ENDPOINT TARGET RESOURCES
// =============================================================================

@description('Storage account resource ID (optional - provide to create storage private endpoint)')
param storageAccountId string = ''

@description('Storage account name (required if storageAccountId is provided)')
param storageAccountName string = ''

@description('Cosmos DB account resource ID (optional - provide to create Cosmos DB private endpoint)')
param cosmosAccountId string = ''

@description('Cosmos DB account name (required if cosmosAccountId is provided)')
param cosmosAccountName string = ''

@description('Key Vault resource ID (optional - provide to create Key Vault private endpoint)')
param keyVaultId string = ''

@description('Key Vault name (required if keyVaultId is provided)')
param keyVaultName string = ''

// =============================================================================
// VNET CONFIGURATION
// =============================================================================

@description('Virtual Network resource ID where private endpoints will be created')
param vnetId string

@description('Subnet resource ID for private endpoints')
param privateEndpointSubnetId string

@description('Create private DNS zones (set to false if using centralized DNS zones)')
param createPrivateDnsZones bool = true

@description('Existing Private DNS Zone resource ID for blob storage (required if createPrivateDnsZones is false)')
param existingBlobDnsZoneId string = ''

@description('Existing Private DNS Zone resource ID for Cosmos DB (required if createPrivateDnsZones is false)')
param existingCosmosDnsZoneId string = ''

@description('Existing Private DNS Zone resource ID for Key Vault (required if createPrivateDnsZones is false)')
param existingKeyVaultDnsZoneId string = ''

// =============================================================================
// VARIABLES
// =============================================================================

var createStorageEndpoint = storageAccountId != '' && storageAccountName != ''
var createCosmosEndpoint = cosmosAccountId != '' && cosmosAccountName != ''
var createKeyVaultEndpoint = keyVaultId != '' && keyVaultName != ''

// Private DNS zone names (Azure standard names)
var blobDnsZoneName = 'privatelink.blob.${az.environment().suffixes.storage}'
var cosmosDnsZoneName = 'privatelink.documents.azure.com'
var keyVaultDnsZoneName = 'privatelink.vaultcore.azure.net'

// =============================================================================
// PRIVATE DNS ZONES (Optional - for organizations without centralized DNS)
// =============================================================================

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones && createStorageEndpoint) {
  name: blobDnsZoneName
  location: 'global'
  tags: tags
}

resource cosmosPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones && createCosmosEndpoint) {
  name: cosmosDnsZoneName
  location: 'global'
  tags: tags
}

resource keyVaultPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones && createKeyVaultEndpoint) {
  name: keyVaultDnsZoneName
  location: 'global'
  tags: tags
}

// =============================================================================
// VNET LINKS (Link DNS zones to VNet for resolution)
// =============================================================================

resource blobDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones && createStorageEndpoint) {
  parent: blobPrivateDnsZone
  name: '${prefix}-blob-vnet-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource cosmosDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones && createCosmosEndpoint) {
  parent: cosmosPrivateDnsZone
  name: '${prefix}-cosmos-vnet-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource keyVaultDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones && createKeyVaultEndpoint) {
  parent: keyVaultPrivateDnsZone
  name: '${prefix}-kv-vnet-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// =============================================================================
// PRIVATE ENDPOINTS
// =============================================================================

// Storage Account Private Endpoint (for blob storage)
resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (createStorageEndpoint) {
  name: '${prefix}-pe-storage-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${prefix}-plsc-storage'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

// Storage Private DNS Zone Group
resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (createStorageEndpoint) {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-storage'
        properties: {
          privateDnsZoneId: createPrivateDnsZones ? blobPrivateDnsZone.id : existingBlobDnsZoneId
        }
      }
    ]
  }
}

// Cosmos DB Private Endpoint
resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (createCosmosEndpoint) {
  name: '${prefix}-pe-cosmos-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${prefix}-plsc-cosmos'
        properties: {
          privateLinkServiceId: cosmosAccountId
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
}

// Cosmos DB Private DNS Zone Group
resource cosmosPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (createCosmosEndpoint) {
  parent: cosmosPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-cosmos-documents'
        properties: {
          privateDnsZoneId: createPrivateDnsZones ? cosmosPrivateDnsZone.id : existingCosmosDnsZoneId
        }
      }
    ]
  }
}

// Key Vault Private Endpoint
resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (createKeyVaultEndpoint) {
  name: '${prefix}-pe-kv-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${prefix}-plsc-keyvault'
        properties: {
          privateLinkServiceId: keyVaultId
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

// Key Vault Private DNS Zone Group
resource keyVaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (createKeyVaultEndpoint) {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-keyvault'
        properties: {
          privateDnsZoneId: createPrivateDnsZones ? keyVaultPrivateDnsZone.id : existingKeyVaultDnsZoneId
        }
      }
    ]
  }
}

// =============================================================================
// OUTPUTS
// =============================================================================

@description('Storage private endpoint resource ID')
output storagePrivateEndpointId string = createStorageEndpoint ? storagePrivateEndpoint.id : ''

@description('Storage private endpoint name')
output storagePrivateEndpointName string = createStorageEndpoint ? storagePrivateEndpoint.name : ''

@description('Cosmos DB private endpoint resource ID')
output cosmosPrivateEndpointId string = createCosmosEndpoint ? cosmosPrivateEndpoint.id : ''

@description('Cosmos DB private endpoint name')
output cosmosPrivateEndpointName string = createCosmosEndpoint ? cosmosPrivateEndpoint.name : ''

@description('Key Vault private endpoint resource ID')
output keyVaultPrivateEndpointId string = createKeyVaultEndpoint ? keyVaultPrivateEndpoint.id : ''

@description('Key Vault private endpoint name')
output keyVaultPrivateEndpointName string = createKeyVaultEndpoint ? keyVaultPrivateEndpoint.name : ''

@description('Blob Private DNS Zone resource ID')
output blobDnsZoneId string = createPrivateDnsZones && createStorageEndpoint ? blobPrivateDnsZone.id : existingBlobDnsZoneId

@description('Cosmos DB Private DNS Zone resource ID')
output cosmosDnsZoneId string = createPrivateDnsZones && createCosmosEndpoint ? cosmosPrivateDnsZone.id : existingCosmosDnsZoneId

@description('Key Vault Private DNS Zone resource ID')
output keyVaultDnsZoneId string = createPrivateDnsZones && createKeyVaultEndpoint ? keyVaultPrivateDnsZone.id : existingKeyVaultDnsZoneId
