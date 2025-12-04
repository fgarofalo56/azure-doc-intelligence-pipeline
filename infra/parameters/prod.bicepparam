using '../main.bicep'

// =============================================================================
// PRODUCTION ENVIRONMENT - NEW DEPLOYMENT
// =============================================================================
// Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/prod.bicepparam \
//     --parameters sqlAdministratorPassword='YourSecurePassword123!'
// =============================================================================

// -----------------------------------------------------------------------------
// CORE SETTINGS
// -----------------------------------------------------------------------------
param resourceGroupName = 'rg-docprocessing-prod'
param location = 'eastus'
param deploymentMode = 'new'
param prefix = 'docproc'
param environment = 'prod'

param tags = {
  project: 'document-processing'
  environment: 'prod'
  deployedBy: 'bicep'
  costCenter: 'production'
}

// -----------------------------------------------------------------------------
// COSMOS DB SETTINGS
// -----------------------------------------------------------------------------
param cosmosDatabase = 'DocumentsDB'
param cosmosContainer = 'ExtractedDocuments'

// -----------------------------------------------------------------------------
// FUNCTION APP CONFIGURATION
// -----------------------------------------------------------------------------
param deployFunctionApp = true
param appServicePlanSku = 'S1'   // Standard plan for production (auto-scale capable)

// -----------------------------------------------------------------------------
// LOGGING AND DIAGNOSTICS
// -----------------------------------------------------------------------------
param enableDiagnostics = true

// RECOMMENDED: Use existing centralized Log Analytics workspace for production
// param existingLogAnalyticsWorkspaceName = 'law-prod-central'
// param existingLogAnalyticsResourceGroup = 'rg-shared-monitoring-prod'

// Or deploy a new Log Analytics workspace
param existingLogAnalyticsWorkspaceName = ''
param logAnalyticsRetentionDays = 90   // 90 days for production
param logAnalyticsSku = 'PerGB2018'

// -----------------------------------------------------------------------------
// SYNAPSE GITHUB INTEGRATION
// -----------------------------------------------------------------------------
// RECOMMENDED for production: Enable GitHub integration for version control
param enableSynapseGitHubIntegration = false

// Uncomment and configure for GitHub integration:
// param synapseGitHubAccountName = 'your-github-org'
// param synapseGitHubRepositoryName = 'your-repo-name'
// param synapseGitHubCollaborationBranch = 'main'
// param synapseGitHubRootFolder = '/src/synapse'

// -----------------------------------------------------------------------------
// NOTE: sqlAdministratorPassword must be provided at deployment time
// Example: --parameters sqlAdministratorPassword='YourSecurePassword123!'
// -----------------------------------------------------------------------------
