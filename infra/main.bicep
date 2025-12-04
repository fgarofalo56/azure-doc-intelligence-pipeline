// =============================================================================
// UNIFIED DEPLOYMENT TEMPLATE
// =============================================================================
// This subscription-level template handles all deployment scenarios:
//   - Option A: New deployment (all resources in a new or existing RG)
//   - Option B: Existing resources with existing Function App (code deploy only)
//   - Option C: Existing backend resources with new Function App (same RG)
//   - Option C+: Existing backend resources with new Function App (new RG)
//
// DEPLOY WITH:
//   az deployment sub create \
//     --location <location> \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/<env>.bicepparam
//
// =============================================================================

targetScope = 'subscription'

// =============================================================================
// USER-DEFINED TYPES
// =============================================================================

@description('Tags type definition for consistent tagging across resources')
type tagsType = {
  @description('Project name for resource organization')
  project: string?
  @description('Environment identifier (dev, prod)')
  environment: string?
  @description('Deployment method identifier')
  deployedBy: string?
  @description('Cost center for billing allocation')
  costCenter: string?
  @description('Additional custom tags')
  *: string
}

// =============================================================================
// CORE PARAMETERS
// =============================================================================

@description('Resource group name for deployment')
param resourceGroupName string

@description('Azure region for deployment')
param location string = 'eastus'

@description('Deployment mode: "new" deploys all resources, "existing" references pre-deployed resources')
@allowed(['new', 'existing'])
param deploymentMode string = 'new'

@description('Prefix for resource naming (3-10 lowercase chars)')
@minLength(3)
@maxLength(10)
param prefix string

@description('Environment name')
@allowed(['dev', 'prod'])
param environment string = 'dev'

@description('Tags to apply to all resources')
param tags tagsType = {
  project: 'document-processing'
  environment: environment
  deployedBy: 'bicep'
}

// SQL administrator password for Synapse (required for new deployment)
@description('SQL administrator password for Synapse workspace')
@secure()
param sqlAdministratorPassword string = ''

// =============================================================================
// EXISTING RESOURCES PARAMETERS
// =============================================================================
// Required when deploymentMode = 'existing'
// Resources can be in different resource groups - specify RG for each

// Storage Account
@description('Name of existing storage account (required for existing mode)')
param existingStorageAccountName string = ''

@description('Resource group of existing storage account')
param existingStorageAccountResourceGroup string = ''

// Document Intelligence
@description('Name of existing Document Intelligence resource (required for existing mode)')
param existingDocIntelName string = ''

@description('Resource group of existing Document Intelligence')
param existingDocIntelResourceGroup string = ''

// Cosmos DB
@description('Name of existing Cosmos DB account (required for existing mode)')
param existingCosmosAccountName string = ''

@description('Resource group of existing Cosmos DB account')
param existingCosmosAccountResourceGroup string = ''

// Key Vault
@description('Name of existing Key Vault (required for existing mode)')
param existingKeyVaultName string = ''

@description('Resource group of existing Key Vault')
param existingKeyVaultResourceGroup string = ''

// Function App (optional - leave empty to deploy new)
@description('Name of existing Function App (leave empty to deploy new)')
param existingFunctionAppName string = ''

@description('Resource group of existing Function App')
param existingFunctionAppResourceGroup string = ''

// Synapse Workspace (optional)
@description('Name of existing Synapse workspace (leave empty to deploy new or skip)')
param existingSynapseWorkspaceName string = ''

@description('Resource group of existing Synapse workspace')
param existingSynapseResourceGroup string = ''

// =============================================================================
// FUNCTION APP CONFIGURATION
// =============================================================================

@description('Deploy new Function App (set false if using existing or code-only deployment)')
param deployFunctionApp bool = true

@description('App Service Plan SKU. Use B1/S1 if you get Dynamic VM quota errors.')
@allowed([
  'Y1'   // Consumption (Dynamic) - pay-per-execution, requires quota
  'B1'   // Basic - ~$55/month
  'B2'   // Basic - ~$110/month
  'S1'   // Standard - ~$73/month, auto-scale
  'P1v2' // Premium v2 - ~$146/month
  'EP1'  // Elastic Premium - ~$150/month
])
param appServicePlanSku string = 'Y1'

// =============================================================================
// COSMOS DB SETTINGS
// =============================================================================

@description('Cosmos DB database name')
param cosmosDatabase string = 'DocumentsDB'

@description('Cosmos DB container name')
param cosmosContainer string = 'ExtractedDocuments'

@description('Enable Azure Synapse Link for Cosmos DB analytical queries (new deployments)')
param enableCosmosSynapseLink bool = true

@description('Enable analytical store on container for existing Cosmos DB account. Requires Synapse Link to be enabled at account level first.')
param enableExistingCosmosAnalyticalStore bool = false

// =============================================================================
// LOGGING AND DIAGNOSTICS
// =============================================================================

@description('Enable diagnostic settings for all resources')
param enableDiagnostics bool = true

@description('Name of existing Log Analytics workspace (leave empty to deploy new)')
param existingLogAnalyticsWorkspaceName string = ''

@description('Resource group of existing Log Analytics workspace')
param existingLogAnalyticsResourceGroup string = ''

@description('Subscription ID of existing Log Analytics workspace (for cross-subscription)')
param existingLogAnalyticsSubscriptionId string = ''

@description('Log Analytics workspace retention in days (for new workspace)')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionDays int = 30

@description('Log Analytics workspace SKU (for new workspace)')
@allowed(['Free', 'PerGB2018', 'PerNode', 'Premium', 'Standalone', 'Standard'])
param logAnalyticsSku string = 'PerGB2018'

// =============================================================================
// SYNAPSE GITHUB INTEGRATION
// =============================================================================

@description('Enable GitHub integration for Synapse workspace')
param enableSynapseGitHubIntegration bool = false

@description('GitHub account name (organization or user)')
param synapseGitHubAccountName string = ''

@description('GitHub repository name for Synapse artifacts')
param synapseGitHubRepositoryName string = ''

@description('GitHub collaboration branch')
param synapseGitHubCollaborationBranch string = 'main'

@description('Root folder in repository for Synapse artifacts')
param synapseGitHubRootFolder string = '/src/synapse'

@description('GitHub type')
@allowed(['GitHub', 'GitHubEnterprise'])
param synapseGitHubType string = 'GitHub'

@description('GitHub Enterprise host URL (only for GitHubEnterprise)')
param synapseGitHubHostName string = ''

// =============================================================================
// COMPUTED VARIABLES
// =============================================================================

// Determine if we need to deploy a new Function App
var shouldDeployFunctionApp = deployFunctionApp && existingFunctionAppName == ''

// Determine effective resource groups for existing resources (default to main RG)
var effectiveStorageRg = existingStorageAccountResourceGroup != '' ? existingStorageAccountResourceGroup : resourceGroupName
var effectiveDocIntelRg = existingDocIntelResourceGroup != '' ? existingDocIntelResourceGroup : resourceGroupName
var effectiveCosmosRg = existingCosmosAccountResourceGroup != '' ? existingCosmosAccountResourceGroup : resourceGroupName
var effectiveKeyVaultRg = existingKeyVaultResourceGroup != '' ? existingKeyVaultResourceGroup : resourceGroupName
var effectiveFunctionAppRg = existingFunctionAppResourceGroup != '' ? existingFunctionAppResourceGroup : resourceGroupName
var effectiveSynapseRg = existingSynapseResourceGroup != '' ? existingSynapseResourceGroup : resourceGroupName

// Log Analytics effective values
var effectiveLogAnalyticsRg = existingLogAnalyticsResourceGroup != '' ? existingLogAnalyticsResourceGroup : resourceGroupName
var effectiveLogAnalyticsSubId = existingLogAnalyticsSubscriptionId != '' ? existingLogAnalyticsSubscriptionId : subscription().subscriptionId
var isLogAnalyticsCrossSubscription = existingLogAnalyticsSubscriptionId != '' && existingLogAnalyticsSubscriptionId != subscription().subscriptionId

// =============================================================================
// RESOURCE GROUP
// =============================================================================

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// =============================================================================
// LOG ANALYTICS WORKSPACE
// =============================================================================

// Deploy new Log Analytics workspace if needed
module logAnalyticsNew 'modules/log-analytics.bicep' = if (enableDiagnostics && existingLogAnalyticsWorkspaceName == '') {
  name: 'log-analytics-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    retentionInDays: logAnalyticsRetentionDays
    sku: logAnalyticsSku
  }
}

// Reference existing Log Analytics workspace (same subscription)
resource existingLogAnalyticsSameSub 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (enableDiagnostics && existingLogAnalyticsWorkspaceName != '' && !isLogAnalyticsCrossSubscription) {
  name: existingLogAnalyticsWorkspaceName
  scope: resourceGroup(effectiveLogAnalyticsRg)
}

// Reference existing Log Analytics workspace (cross-subscription)
resource existingLogAnalyticsCrossSub 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (enableDiagnostics && existingLogAnalyticsWorkspaceName != '' && isLogAnalyticsCrossSubscription) {
  name: existingLogAnalyticsWorkspaceName
  scope: resourceGroup(effectiveLogAnalyticsSubId, effectiveLogAnalyticsRg)
}

// Determine Log Analytics workspace ID
var logAnalyticsWorkspaceId = !enableDiagnostics ? '' : (existingLogAnalyticsWorkspaceName == ''
  ? logAnalyticsNew!.outputs.workspaceId
  : (isLogAnalyticsCrossSubscription ? existingLogAnalyticsCrossSub.id : existingLogAnalyticsSameSub.id))

// =============================================================================
// NEW RESOURCES DEPLOYMENT (deploymentMode == 'new')
// =============================================================================

// Storage Account
module storageNew 'modules/storage.bicep' = if (deploymentMode == 'new') {
  name: 'storage-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
  }
}

// Document Intelligence
module docIntelNew 'modules/document-intelligence.bicep' = if (deploymentMode == 'new') {
  name: 'document-intelligence-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
  }
}

// Cosmos DB
module cosmosNew 'modules/cosmos-db.bicep' = if (deploymentMode == 'new') {
  name: 'cosmos-db-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    databaseName: cosmosDatabase
    containerName: cosmosContainer
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
    enableSynapseLink: enableCosmosSynapseLink
  }
}

// Key Vault
module keyVaultNew 'modules/key-vault.bicep' = if (deploymentMode == 'new') {
  name: 'key-vault-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
  }
}

// Function App (new deployment)
module functionAppNew 'modules/function-app.bicep' = if (deploymentMode == 'new' && shouldDeployFunctionApp) {
  name: 'function-app-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    storageConnectionString: storageNew!.outputs.connectionString
    docIntelEndpoint: docIntelNew!.outputs.endpoint
    docIntelApiKey: docIntelNew!.outputs.apiKey
    cosmosEndpoint: cosmosNew!.outputs.endpoint
    cosmosDatabase: cosmosDatabase
    cosmosContainer: cosmosContainer
    keyVaultName: keyVaultNew!.outputs.name
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
    appServicePlanSku: appServicePlanSku
  }
}

// Synapse Workspace
module synapseNew 'modules/synapse.bicep' = if (deploymentMode == 'new') {
  name: 'synapse-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    storageAccountId: storageNew!.outputs.resourceId
    storageAccountName: storageNew!.outputs.name
    sqlAdministratorPassword: sqlAdministratorPassword
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
    enableGitHubIntegration: enableSynapseGitHubIntegration
    gitHubAccountName: synapseGitHubAccountName
    gitHubRepositoryName: synapseGitHubRepositoryName
    gitHubCollaborationBranch: synapseGitHubCollaborationBranch
    gitHubRootFolder: synapseGitHubRootFolder
    gitHubType: synapseGitHubType
    gitHubHostName: synapseGitHubHostName
  }
}

// =============================================================================
// EXISTING RESOURCES REFERENCES (deploymentMode == 'existing')
// =============================================================================

// Reference existing Storage Account
resource existingStorage 'Microsoft.Storage/storageAccounts@2024-01-01' existing = if (deploymentMode == 'existing') {
  name: existingStorageAccountName
  scope: resourceGroup(effectiveStorageRg)
}

// Reference existing Document Intelligence
resource existingDocIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deploymentMode == 'existing') {
  name: existingDocIntelName
  scope: resourceGroup(effectiveDocIntelRg)
}

// Reference existing Cosmos DB
resource existingCosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = if (deploymentMode == 'existing') {
  name: existingCosmosAccountName
  scope: resourceGroup(effectiveCosmosRg)
}

// Reference existing Key Vault
resource existingKeyVault 'Microsoft.KeyVault/vaults@2024-11-01' existing = if (deploymentMode == 'existing') {
  name: existingKeyVaultName
  scope: resourceGroup(effectiveKeyVaultRg)
}

// Reference existing Function App (if specified)
resource existingFunctionApp 'Microsoft.Web/sites@2024-04-01' existing = if (deploymentMode == 'existing' && existingFunctionAppName != '') {
  name: existingFunctionAppName
  scope: resourceGroup(effectiveFunctionAppRg)
}

// Reference existing Synapse (if specified)
resource existingSynapse 'Microsoft.Synapse/workspaces@2021-06-01' existing = if (deploymentMode == 'existing' && existingSynapseWorkspaceName != '') {
  name: existingSynapseWorkspaceName
  scope: resourceGroup(effectiveSynapseRg)
}

// =============================================================================
// COSMOS DB DATABASE/CONTAINER FOR EXISTING ACCOUNT
// =============================================================================
// When using existing Cosmos DB account, ensure the required database and container exist
// This is idempotent - will create if not exists, no-op if already exists

module cosmosDbDatabase 'modules/cosmos-db-database.bicep' = if (deploymentMode == 'existing') {
  name: 'cosmos-db-database-deployment'
  scope: resourceGroup(effectiveCosmosRg)
  params: {
    cosmosAccountName: existingCosmosAccountName
    databaseName: cosmosDatabase
    containerName: cosmosContainer
    // NOTE: For Synapse Link on existing accounts, enableAnalyticalStore must be enabled
    // at the account level first via Azure Portal or CLI before this will work
    enableAnalyticalStore: enableExistingCosmosAnalyticalStore
    analyticalStorageTtl: -1
  }
}

// =============================================================================
// FUNCTION APP FOR EXISTING RESOURCES (Option C/C+)
// =============================================================================

// Compute connection strings for existing resources
var existingStorageConnectionString = deploymentMode == 'existing' ? 'DefaultEndpointsProtocol=https;AccountName=${existingStorage.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${existingStorage.listKeys().keys[0].value}' : ''

// Deploy new Function App with existing backend resources
module functionAppExisting 'modules/function-app.bicep' = if (deploymentMode == 'existing' && shouldDeployFunctionApp) {
  name: 'function-app-existing-deployment'
  scope: rg
  params: {
    prefix: prefix
    location: location
    environment: environment
    tags: tags
    storageConnectionString: existingStorageConnectionString
    docIntelEndpoint: existingDocIntel.properties.endpoint
    docIntelApiKey: existingDocIntel.listKeys().key1
    cosmosEndpoint: existingCosmos.properties.documentEndpoint
    cosmosDatabase: cosmosDatabase
    cosmosContainer: cosmosContainer
    keyVaultName: existingKeyVault.name
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableDiagnostics: enableDiagnostics
    appServicePlanSku: appServicePlanSku
  }
}

// =============================================================================
// ROLE ASSIGNMENTS
// =============================================================================

// Key Vault role assignment for NEW deployment
module keyVaultRoleNew 'modules/role-assignment.bicep' = if (deploymentMode == 'new' && shouldDeployFunctionApp) {
  name: 'keyvault-role-new'
  scope: rg
  params: {
    principalId: functionAppNew!.outputs.principalId
    roleDefinitionId: '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB role assignment for NEW deployment
module cosmosRoleNew 'modules/cosmos-role-assignment.bicep' = if (deploymentMode == 'new' && shouldDeployFunctionApp) {
  name: 'cosmos-role-new'
  scope: rg
  params: {
    cosmosAccountName: cosmosNew!.outputs.name
    principalId: functionAppNew!.outputs.principalId
    roleDefinitionId: '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
  }
}

// Synapse Storage role assignment for NEW deployment
module synapseStorageRole 'modules/role-assignment.bicep' = if (deploymentMode == 'new') {
  name: 'synapse-storage-role'
  scope: rg
  params: {
    principalId: synapseNew!.outputs.principalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    principalType: 'ServicePrincipal'
  }
}

// Key Vault role assignment for EXISTING deployment (cross-RG)
module keyVaultRoleExisting 'modules/role-assignment.bicep' = if (deploymentMode == 'existing' && shouldDeployFunctionApp) {
  name: 'keyvault-role-existing'
  scope: resourceGroup(effectiveKeyVaultRg)
  params: {
    principalId: functionAppExisting!.outputs.principalId
    roleDefinitionId: '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB role assignment for EXISTING deployment (cross-RG)
module cosmosRoleExisting 'modules/cosmos-role-assignment.bicep' = if (deploymentMode == 'existing' && shouldDeployFunctionApp) {
  name: 'cosmos-role-existing'
  scope: resourceGroup(effectiveCosmosRg)
  params: {
    cosmosAccountName: existingCosmosAccountName
    principalId: functionAppExisting!.outputs.principalId
    roleDefinitionId: '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
  }
}

// =============================================================================
// OUTPUTS
// =============================================================================

@description('Resource group name')
output resourceGroupName string = rg.name

@description('Storage account name')
output storageAccountName string = deploymentMode == 'new' ? storageNew!.outputs.name : existingStorage.name

@description('Storage account blob endpoint')
output storageBlobEndpoint string = deploymentMode == 'new' ? storageNew!.outputs.primaryBlobEndpoint : existingStorage.properties.primaryEndpoints.blob

@description('Document Intelligence endpoint')
output documentIntelligenceEndpoint string = deploymentMode == 'new' ? docIntelNew!.outputs.endpoint : existingDocIntel.properties.endpoint

@description('Cosmos DB endpoint')
output cosmosDbEndpoint string = deploymentMode == 'new' ? cosmosNew!.outputs.endpoint : existingCosmos.properties.documentEndpoint

@description('Cosmos DB database name')
output cosmosDbDatabaseName string = cosmosDatabase

@description('Cosmos DB container name')
output cosmosDbContainerName string = cosmosContainer

@description('Key Vault name')
output keyVaultName string = deploymentMode == 'new' ? keyVaultNew!.outputs.name : existingKeyVault.name

@description('Function App name')
output functionAppName string = deploymentMode == 'new'
  ? (shouldDeployFunctionApp ? functionAppNew!.outputs.name : 'not-deployed')
  : (shouldDeployFunctionApp ? functionAppExisting!.outputs.name : existingFunctionAppName)

@description('Function App URL')
output functionAppUrl string = deploymentMode == 'new'
  ? (shouldDeployFunctionApp ? functionAppNew!.outputs.functionAppUrl : '')
  : (shouldDeployFunctionApp ? functionAppExisting!.outputs.functionAppUrl : 'https://${existingFunctionApp.properties.defaultHostName}')

@description('Function App principal ID')
output functionAppPrincipalId string = deploymentMode == 'new'
  ? (shouldDeployFunctionApp ? functionAppNew!.outputs.principalId : '')
  : (shouldDeployFunctionApp ? functionAppExisting!.outputs.principalId : '')

@description('Synapse workspace name')
output synapseWorkspaceName string = deploymentMode == 'new' ? synapseNew!.outputs.name : (existingSynapseWorkspaceName != '' ? existingSynapse.name : 'not-deployed')

@description('Synapse dev endpoint')
output synapseDevEndpoint string = deploymentMode == 'new' ? synapseNew!.outputs.devEndpoint : (existingSynapseWorkspaceName != '' ? existingSynapse.properties.connectivityEndpoints.dev : '')

@description('Synapse GitHub integration enabled')
output synapseGitHubEnabled bool = deploymentMode == 'new' ? synapseNew!.outputs.gitHubIntegrationEnabled : false

@description('Log Analytics workspace ID')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspaceId

@description('Diagnostics enabled')
output diagnosticsEnabled bool = enableDiagnostics

@description('App Service Plan SKU')
output appServicePlanSkuOutput string = appServicePlanSku
