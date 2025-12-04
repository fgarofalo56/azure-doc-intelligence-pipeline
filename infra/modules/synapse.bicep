@description('Prefix for resource naming')
param prefix string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, prod)')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Storage account resource ID for Synapse')
param storageAccountId string

@description('Storage account name')
param storageAccountName string

@description('SQL administrator login')
param sqlAdministratorLogin string = 'sqladmin'

@description('SQL administrator password')
@secure()
param sqlAdministratorPassword string

@description('Log Analytics workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

// =============================================================================
// GITHUB INTEGRATION PARAMETERS
// =============================================================================
@description('Enable GitHub integration for Synapse workspace')
param enableGitHubIntegration bool = false

@description('GitHub account name (organization or user)')
param gitHubAccountName string = ''

@description('GitHub repository name')
param gitHubRepositoryName string = ''

@description('GitHub collaboration branch (default: main)')
param gitHubCollaborationBranch string = 'main'

@description('Root folder in repository for Synapse artifacts')
param gitHubRootFolder string = '/src/synapse'

@description('Automatically create GitHub repo if it does not exist (requires appropriate permissions)')
param gitHubAutoCreateRepo bool = false

@description('GitHub type (GitHub or GitHubEnterprise)')
@allowed(['GitHub', 'GitHubEnterprise'])
param gitHubType string = 'GitHub'

@description('GitHub Enterprise host URL (only for GitHubEnterprise type)')
param gitHubHostName string = ''

// Synapse workspace name
var synapseWorkspaceName = '${prefix}-syn-${environment}'
var defaultDataLakeStorageFilesystemName = 'synapse'

// Create container for Synapse
resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' existing = {
  parent: storageAccount
  name: 'default'
}

resource synapseContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobServices
  name: defaultDataLakeStorageFilesystemName
  properties: {
    publicAccess: 'None'
  }
}

// GitHub configuration object (only populated when GitHub integration is enabled)
var gitHubConfiguration = enableGitHubIntegration ? {
  type: gitHubType
  accountName: gitHubAccountName
  repositoryName: gitHubRepositoryName
  collaborationBranch: gitHubCollaborationBranch
  rootFolder: gitHubRootFolder
  hostName: gitHubType == 'GitHubEnterprise' ? gitHubHostName : ''
} : null

// NOTE: Synapse API version 2021-06-01 is the latest stable version
resource synapseWorkspace 'Microsoft.Synapse/workspaces@2021-06-01' = {
  name: synapseWorkspaceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    defaultDataLakeStorage: {
      resourceId: storageAccountId
      accountUrl: 'https://${storageAccountName}.dfs.${az.environment().suffixes.storage}'
      filesystem: defaultDataLakeStorageFilesystemName
    }
    sqlAdministratorLogin: sqlAdministratorLogin
    sqlAdministratorLoginPassword: sqlAdministratorPassword
    managedVirtualNetwork: 'default'
    managedResourceGroupName: '${prefix}-syn-managed-${environment}'
    publicNetworkAccess: 'Enabled'
    azureADOnlyAuthentication: false
    // GitHub repository configuration (optional)
    workspaceRepositoryConfiguration: enableGitHubIntegration ? {
      type: 'WorkspaceGitHubConfiguration'
      accountName: gitHubAccountName
      repositoryName: gitHubRepositoryName
      collaborationBranch: gitHubCollaborationBranch
      rootFolder: gitHubRootFolder
      hostName: gitHubType == 'GitHubEnterprise' ? gitHubHostName : ''
    } : null
  }
}

// Firewall rule to allow Azure services
resource allowAzureServices 'Microsoft.Synapse/workspaces/firewallRules@2021-06-01' = {
  parent: synapseWorkspace
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Firewall rule to allow all (for development)
resource allowAll 'Microsoft.Synapse/workspaces/firewallRules@2021-06-01' = if (environment == 'dev') {
  parent: synapseWorkspace
  name: 'AllowAll'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

// Diagnostic settings for Synapse workspace
resource synapseDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && logAnalyticsWorkspaceId != '') {
  name: '${synapseWorkspace.name}-diagnostics'
  scope: synapseWorkspace
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'SynapseRbacOperations'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'GatewayApiRequests'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'BuiltinSqlReqsEnded'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'IntegrationPipelineRuns'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'IntegrationActivityRuns'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'IntegrationTriggerRuns'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

@description('Synapse workspace name')
output name string = synapseWorkspace.name

@description('Synapse workspace resource ID')
output resourceId string = synapseWorkspace.id

@description('Synapse workspace development endpoint')
output devEndpoint string = synapseWorkspace.properties.connectivityEndpoints.dev

@description('Synapse workspace SQL on-demand endpoint')
output sqlOnDemandEndpoint string = synapseWorkspace.properties.connectivityEndpoints.sqlOnDemand

@description('Synapse workspace principal ID for managed identity')
output principalId string = synapseWorkspace.identity.principalId

@description('GitHub integration enabled')
output gitHubIntegrationEnabled bool = enableGitHubIntegration

@description('GitHub repository URL (if GitHub integration is enabled)')
output gitHubRepositoryUrl string = enableGitHubIntegration ? 'https://github.com/${gitHubAccountName}/${gitHubRepositoryName}' : ''

@description('GitHub collaboration branch')
output gitHubCollaborationBranch string = enableGitHubIntegration ? gitHubCollaborationBranch : ''

@description('Synapse artifacts root folder in GitHub')
output gitHubRootFolder string = enableGitHubIntegration ? gitHubRootFolder : ''
