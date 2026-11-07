targetScope = 'resourceGroup'

@description('Azure region supplied by Aspire.')
#disable-next-line no-unused-params
param location string = resourceGroup().location

@description('Name of the agent managed identity supplied by Aspire.')
param identityName string

@description('Principal ID of the agent managed identity supplied by Aspire.')
param identityPrincipalId string

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
  name: last(split(foundryProjectName, '/'))
}

resource agentFoundryUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, identityName, foundryUserRoleDefinitionId)
  scope: foundryProject
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: foundryUserRoleDefinitionId
  }
}
