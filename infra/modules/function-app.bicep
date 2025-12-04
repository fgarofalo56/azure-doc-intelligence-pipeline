@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Storage account connection string for Function App')
param storageConnectionString string

@description('Document Intelligence endpoint')
param docIntelEndpoint string

@description('Document Intelligence API key')
@secure()
param docIntelApiKey string

@description('Cosmos DB endpoint')
param cosmosEndpoint string

@description('Cosmos DB database name')
param cosmosDatabase string

@description('Cosmos DB container name')
param cosmosContainer string

@description('Key Vault name for secret references')
param keyVaultName string

@description('Log Analytics workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

@description('App Service Plan SKU. Use Y1 for Consumption (requires Dynamic VM quota), B1 for Basic, S1 for Standard, EP1 for Premium.')
@allowed([
  'Y1'   // Consumption (Dynamic) - cheapest, pay-per-execution, requires Dynamic VM quota
  'B1'   // Basic - ~$55/month, always-on capable
  'B2'   // Basic - ~$110/month
  'S1'   // Standard - ~$73/month, auto-scale capable
  'P1v2' // Premium v2 - ~$146/month, better performance
  'EP1'  // Elastic Premium - ~$150/month, premium functions features
])
param appServicePlanSku string = 'Y1'

// Determine SKU tier based on SKU name
var skuTiers = {
  Y1: 'Dynamic'
  B1: 'Basic'
  B2: 'Basic'
  S1: 'Standard'
  P1v2: 'PremiumV2'
  EP1: 'ElasticPremium'
}
var skuTier = skuTiers[appServicePlanSku]

// Determine if this is a consumption plan
var isConsumptionPlan = appServicePlanSku == 'Y1'
var isElasticPremium = appServicePlanSku == 'EP1'

// Function App name
var functionAppName = '${prefix}-func-${environment}'
var appServicePlanName = '${prefix}-asp-${environment}'
var appInsightsName = '${prefix}-ai-${environment}'

// Application Insights (linked to Log Analytics workspace if provided)
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Request_Source: 'rest'
    WorkspaceResourceId: logAnalyticsWorkspaceId != '' ? logAnalyticsWorkspaceId : null
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// App Service Plan (configurable SKU)
resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: isElasticPremium ? 'elastic' : 'functionapp'
  sku: {
    name: appServicePlanSku
    tier: skuTier
  }
  properties: {
    reserved: true // Required for Linux
    maximumElasticWorkerCount: isElasticPremium ? 20 : null
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.10'
      pythonVersion: '3.10'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      functionAppScaleLimit: 200
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: functionAppName
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'DOC_INTEL_ENDPOINT'
          value: docIntelEndpoint
        }
        {
          name: 'DOC_INTEL_API_KEY'
          // Use direct value - for production, consider storing in Key Vault and using:
          // '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=doc-intel-api-key)'
          value: docIntelApiKey
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_DATABASE'
          value: cosmosDatabase
        }
        {
          name: 'COSMOS_CONTAINER'
          value: cosmosContainer
        }
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
      ]
    }
  }
}

// Diagnostic settings for Function App
resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${functionApp.name}-diagnostics'
  scope: functionApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'FunctionAppLogs'
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

// Diagnostic settings for App Service Plan
resource appServicePlanDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${appServicePlan.name}-diagnostics'
  scope: appServicePlan
  properties: {
    workspaceId: logAnalyticsWorkspaceId
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

@description('Function App name')
output name string = functionApp.name

@description('Function App resource ID')
output resourceId string = functionApp.id

@description('Function App default hostname')
output defaultHostname string = functionApp.properties.defaultHostName

@description('Function App URL')
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'

@description('Function App principal ID for managed identity')
output principalId string = functionApp.identity.principalId

@description('Application Insights instrumentation key')
output appInsightsKey string = appInsights.properties.InstrumentationKey
