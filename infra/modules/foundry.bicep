@description('Name of the Microsoft Foundry (AI Services) account')
param accountName string

@description('Name of the Foundry project')
param projectName string

@description('Location for the Foundry account')
param location string

@description('Tags to apply')
param tags object = {}

@description('Principal ID granted access to the Foundry project')
param principalId string

@description('Model deployments to create on the account')
param modelDeployments array = []

// Microsoft Foundry ("new Foundry") account. Unlike the hub-based
// Microsoft.MachineLearningServices workspaces, this exposes the
// https://<account>.services.ai.azure.com/api/projects/<project> endpoint that
// the Agents API and the Evaluations pane in the Foundry portal both use.
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    // Agents and evaluation upload authenticate with Entra ID.
    disableLocalAuth: false
    allowProjectManagement: true
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectName
    description: 'Insurance multi-agent claims project'
  }
}

@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for deployment in modelDeployments: {
    parent: account
    name: deployment.name
    sku: {
      name: deployment.skuName
      capacity: deployment.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: deployment.modelName
        version: deployment.modelVersion
      }
    }
  }
]

// Azure AI User lets the backend create agents and evaluation runs in the project.
resource aiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, principalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User for inference against the account's deployments.
resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, principalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output accountName string = account.name
output accountEndpoint string = account.properties.endpoint
output projectName string = project.name
#disable-next-line BCP053
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'
output accountPrincipalId string = account.identity.principalId
output projectPrincipalId string = project.identity.principalId
