// =============================================================================
// COSMOS DB SQL ROLE ASSIGNMENT MODULE
// =============================================================================
// Creates a Cosmos DB data plane role assignment for a principal.
// This is different from Azure RBAC - these are Cosmos DB's built-in data roles.
//
// Cosmos DB Built-in Role Definition IDs:
// - Cosmos DB Built-in Data Reader: 00000000-0000-0000-0000-000000000001
// - Cosmos DB Built-in Data Contributor: 00000000-0000-0000-0000-000000000002
//
// Note: The roleDefinitionId in sqlRoleAssignments must be the FULL resource ID,
// not just the GUID. This module constructs the full ID automatically.
// =============================================================================

@description('Name of the Cosmos DB account')
param cosmosAccountName string

@description('Principal ID (Object ID) of the identity to assign the role to')
param principalId string

@description('Cosmos DB built-in role definition ID (just the GUID part)')
@allowed([
  '00000000-0000-0000-0000-000000000001' // Cosmos DB Built-in Data Reader
  '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
])
param roleDefinitionId string = '00000000-0000-0000-0000-000000000002'

@description('Scope for the role assignment. Defaults to the account level. Can be more specific like /dbs/{db} or /dbs/{db}/colls/{container}')
param scope string = ''

// Reference existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

// Construct the full role definition resource ID
var fullRoleDefinitionId = '${cosmosAccount.id}/sqlRoleDefinitions/${roleDefinitionId}'

// Determine the scope (default to account level if not specified)
var effectiveScope = scope != '' ? '${cosmosAccount.id}${scope}' : cosmosAccount.id

// Create a unique name for the role assignment
var roleAssignmentName = guid(cosmosAccount.id, principalId, roleDefinitionId)

resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmosAccount
  name: roleAssignmentName
  properties: {
    principalId: principalId
    roleDefinitionId: fullRoleDefinitionId
    scope: effectiveScope
  }
}

@description('Role assignment resource ID')
output id string = sqlRoleAssignment.id

@description('Role assignment name')
output name string = sqlRoleAssignment.name
