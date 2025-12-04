@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Log Analytics workspace retention in days')
@minValue(30)
@maxValue(730)
param retentionInDays int = 30

@description('Log Analytics workspace SKU')
@allowed([
  'Free'
  'PerGB2018'
  'PerNode'
  'Premium'
  'Standalone'
  'Standard'
])
param sku string = 'PerGB2018'

// Log Analytics workspace name
var workspaceName = '${prefix}-law-${environment}'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: sku
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: environment == 'dev' ? 1 : -1 // 1GB daily cap for dev, unlimited for prod
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

@description('Log Analytics workspace name')
output name string = logAnalyticsWorkspace.name

@description('Log Analytics workspace resource ID')
output resourceId string = logAnalyticsWorkspace.id

@description('Log Analytics workspace ID (for diagnostic settings)')
output workspaceId string = logAnalyticsWorkspace.id

@description('Log Analytics workspace customer ID (workspace GUID)')
output customerId string = logAnalyticsWorkspace.properties.customerId

@description('Log Analytics workspace primary shared key')
#disable-next-line outputs-should-not-contain-secrets
output primarySharedKey string = logAnalyticsWorkspace.listKeys().primarySharedKey
