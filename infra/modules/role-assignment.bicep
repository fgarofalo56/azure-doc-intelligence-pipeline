// =============================================================================
// ROLE ASSIGNMENT MODULE
// =============================================================================
// Creates a role assignment for a principal (e.g., managed identity) at the
// resource group scope. Used for granting cross-resource-group access.
//
// Common role definition IDs:
// - Key Vault Secrets User: 4633458b-17de-408a-b874-0445c86b69e6
// - Cosmos DB Built-in Data Contributor: 00000000-0000-0000-c000-000000000002
// - Storage Blob Data Contributor: ba92f5b4-2d11-453d-a403-e96b0029c9fe
// - Storage Blob Data Reader: 2a2b9908-6ea1-4ae2-8e65-a410df84e7d1
// =============================================================================

@description('Principal ID to assign the role to')
param principalId string

@description('Role definition ID (GUID)')
param roleDefinitionId string

@description('Principal type')
@allowed([
  'Device'
  'ForeignGroup'
  'Group'
  'ServicePrincipal'
  'User'
])
param principalType string = 'ServicePrincipal'

@description('Description for the role assignment')
param roleAssignmentDescription string = ''

// Create a unique name for the role assignment based on inputs
var roleAssignmentName = guid(resourceGroup().id, principalId, roleDefinitionId)

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: principalId
    principalType: principalType
    description: !empty(roleAssignmentDescription) ? roleAssignmentDescription : null
  }
}

@description('Role assignment resource ID')
output id string = roleAssignment.id

@description('Role assignment name')
output name string = roleAssignment.name
