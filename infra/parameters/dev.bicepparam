using '../main.bicep'

// =============================================================================
// DEVELOPMENT ENVIRONMENT - NEW DEPLOYMENT
// =============================================================================
// Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/dev.bicepparam \
//     --parameters sqlAdministratorPassword='YourSecurePassword123!'
// =============================================================================

// -----------------------------------------------------------------------------
// CORE SETTINGS
// -----------------------------------------------------------------------------
param resourceGroupName = 'rg-docprocessing-dev'
param location = 'eastus'
param deploymentMode = 'new'
param prefix = 'docproc'
param environment = 'dev'

param tags = {
  project: 'document-processing'
  environment: 'dev'
  deployedBy: 'bicep'
  costCenter: 'development'
}

// -----------------------------------------------------------------------------
// COSMOS DB SETTINGS
// -----------------------------------------------------------------------------
param cosmosDatabase = 'DocumentsDB'
param cosmosContainer = 'ExtractedDocuments'

// Enable Synapse Link for analytical queries (HTAP) - allows querying Cosmos DB
// from Synapse Spark notebooks and SQL serverless without impacting transactions
param enableCosmosSynapseLink = true

// -----------------------------------------------------------------------------
// FUNCTION APP CONFIGURATION
// -----------------------------------------------------------------------------
param deployFunctionApp = true
param appServicePlanSku = 'Y1'   // Consumption plan for dev (pay-per-execution)

// -----------------------------------------------------------------------------
// LOGGING AND DIAGNOSTICS
// -----------------------------------------------------------------------------
param enableDiagnostics = true

// Deploy a new Log Analytics workspace (default for dev)
param existingLogAnalyticsWorkspaceName = ''

// Log Analytics settings for new workspace
param logAnalyticsRetentionDays = 30
param logAnalyticsSku = 'PerGB2018'

// -----------------------------------------------------------------------------
// SYNAPSE GITHUB INTEGRATION (Optional)
// -----------------------------------------------------------------------------
param enableSynapseGitHubIntegration = false

// Uncomment and configure if using GitHub integration:
// param synapseGitHubAccountName = 'your-github-org'
// param synapseGitHubRepositoryName = 'your-repo-name'
// param synapseGitHubCollaborationBranch = 'main'
// param synapseGitHubRootFolder = '/src/synapse'

// -----------------------------------------------------------------------------
// NOTE: sqlAdministratorPassword must be provided at deployment time
// Example: --parameters sqlAdministratorPassword='YourSecurePassword123!'
// -----------------------------------------------------------------------------
