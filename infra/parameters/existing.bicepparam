using '../main.bicep'

// =============================================================================
// EXISTING RESOURCES DEPLOYMENT
// =============================================================================
// Use this when you have existing Azure resources and want to:
//   - Option B: Deploy function CODE only to existing Function App
//   - Option C: Deploy new Function App with existing backend resources
//
// Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/existing.bicepparam
// =============================================================================

// -----------------------------------------------------------------------------
// CORE SETTINGS
// -----------------------------------------------------------------------------
// The resource group will be created if it doesn't exist
param resourceGroupName = 'rg-docprocessing-functions-dev'
param location = 'eastus'
param deploymentMode = 'existing'
param prefix = 'docproc'
param environment = 'dev'

param tags = {
  project: 'document-processing'
  environment: 'dev'
  deployedBy: 'bicep'
  deploymentType: 'existing-backend'
}

// -----------------------------------------------------------------------------
// EXISTING STORAGE ACCOUNT (Required)
// -----------------------------------------------------------------------------
param existingStorageAccountName = 'yourstorageaccount'
param existingStorageAccountResourceGroup = 'rg-your-storage-rg'

// -----------------------------------------------------------------------------
// EXISTING DOCUMENT INTELLIGENCE (Required)
// -----------------------------------------------------------------------------
param existingDocIntelName = 'your-doc-intel'
param existingDocIntelResourceGroup = 'rg-your-docintel-rg'

// -----------------------------------------------------------------------------
// EXISTING COSMOS DB (Required)
// -----------------------------------------------------------------------------
param existingCosmosAccountName = 'your-cosmos-account'
param existingCosmosAccountResourceGroup = 'rg-your-cosmos-rg'

// Database and container will be created automatically if they don't exist
param cosmosDatabase = 'DocumentsDB'
param cosmosContainer = 'ExtractedDocuments'

// -----------------------------------------------------------------------------
// COSMOS DB SYNAPSE LINK (Optional)
// -----------------------------------------------------------------------------
// To enable Synapse Link on an existing Cosmos DB account:
// 1. First enable at account level via Azure Portal:
//    Cosmos DB Account > Azure Synapse Link > Enable
// 2. Then set this parameter to true to enable analytical store on the container:
param enableExistingCosmosAnalyticalStore = false

// NOTE: Once Synapse Link is enabled on an account, it CANNOT be disabled.
// The container's analytical store will be configured with TTL=-1 (infinite retention).

// -----------------------------------------------------------------------------
// EXISTING KEY VAULT (Required)
// -----------------------------------------------------------------------------
param existingKeyVaultName = 'your-keyvault'
param existingKeyVaultResourceGroup = 'rg-your-keyvault-rg'

// -----------------------------------------------------------------------------
// FUNCTION APP CONFIGURATION
// -----------------------------------------------------------------------------
// Option B: Use existing Function App (set name, deployFunctionApp = false)
// Option C: Deploy new Function App (leave name empty, deployFunctionApp = true)

param existingFunctionAppName = ''  // Leave empty to deploy new Function App
param deployFunctionApp = true
param appServicePlanSku = 'S1'      // Use S1 for production, B1 for dev

// -----------------------------------------------------------------------------
// EXISTING SYNAPSE WORKSPACE (Optional)
// -----------------------------------------------------------------------------
// Leave empty if not using existing Synapse workspace
// If your existing Synapse workspace has GitHub integration configured,
// artifacts must be deployed to that external repository (not via Bicep)
param existingSynapseWorkspaceName = ''
param existingSynapseResourceGroup = ''

// =============================================================================
// SYNAPSE ARTIFACT DEPLOYMENT (for existing Synapse with GitHub integration)
// =============================================================================
// If your existing Synapse workspace is configured with GitHub integration
// pointing to a DIFFERENT repository, use the deployment script:
//
// Direct deployment (no GitHub integration):
//   .\scripts\Deploy-SynapseArtifacts.ps1 `
//     -WorkspaceName "your-synapse-workspace" `
//     -ResourceGroup "rg-your-synapse-rg" `
//     -DeploymentMode direct `
//     -StorageAccountUrl "https://yourstorageaccount.blob.core.windows.net" `
//     -FunctionAppUrl "https://your-func-app.azurewebsites.net"
//
// External GitHub repo deployment (Synapse configured with external repo):
//   .\scripts\Deploy-SynapseArtifacts.ps1 `
//     -WorkspaceName "your-synapse-workspace" `
//     -ResourceGroup "rg-your-synapse-rg" `
//     -DeploymentMode external-github `
//     -ExternalRepoUrl "https://github.com/your-org/synapse-artifacts.git" `
//     -ExternalRepoRootFolder "/synapse" `
//     -GitHubBranch "main" `
//     -StorageAccountUrl "https://yourstorageaccount.blob.core.windows.net" `
//     -FunctionAppUrl "https://your-func-app.azurewebsites.net"
// =============================================================================

// -----------------------------------------------------------------------------
// LOGGING AND DIAGNOSTICS
// -----------------------------------------------------------------------------
param enableDiagnostics = true

// Use existing Log Analytics workspace (recommended for enterprise)
param existingLogAnalyticsWorkspaceName = 'your-log-analytics-workspace'
param existingLogAnalyticsResourceGroup = 'rg-your-monitoring-rg'
// For cross-subscription Log Analytics:
// param existingLogAnalyticsSubscriptionId = '12345678-1234-1234-1234-123456789012'

// Or deploy a new Log Analytics workspace:
// param existingLogAnalyticsWorkspaceName = ''
// param logAnalyticsRetentionDays = 30
// param logAnalyticsSku = 'PerGB2018'

// -----------------------------------------------------------------------------
// SYNAPSE GITHUB INTEGRATION (Not applicable for existing mode)
// -----------------------------------------------------------------------------
param enableSynapseGitHubIntegration = false
