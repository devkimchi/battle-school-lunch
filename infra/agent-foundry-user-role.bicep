targetScope = 'resourceGroup'

@description('Object ID of the agent managed identity.')
param principalId string

@description('Name of the Microsoft Foundry account.')
param foundryAccountName string

@description('Name of the Microsoft Foundry project.')
param foundryProjectName string

var foundryUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d'
)

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource agentFoundryUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, principalId, foundryUserRoleDefinitionId)
  scope: foundryProject
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: foundryUserRoleDefinitionId
  }
}
