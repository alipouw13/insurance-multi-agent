targetScope = 'resourceGroup'

@description('The environment name')
param environmentName string

@description('The location for all resources')
param location string = resourceGroup().location

@description('The backend container image to deploy')
param backendContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('The frontend container image to deploy')
param frontendContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('The project name for resource naming')
param projectName string = 'insurance-multi-agent'

@description('Azure OpenAI deployment name')
param azureOpenAIDeploymentName string = 'gpt-4o-mini'

@description('Azure OpenAI embedding model')
param azureOpenAIEmbeddingModel string = 'text-embedding-3-large'

// Generate a short unique suffix for resource naming
var uniqueSuffix = take(uniqueString(resourceGroup().id), 6)

// Common tags for all resources
var commonTags = {
  Environment: environmentName
  Project: projectName
  Location: location
  ManagedBy: 'Bicep'
}

// Simple, short resource names that stay within limits
var containerAppsEnvironmentName = 'env-${uniqueSuffix}'
var containerRegistryName = 'cr${uniqueSuffix}'
var managedIdentityName = 'id-${uniqueSuffix}'
var backendContainerAppName = 'backend-${uniqueSuffix}'
var frontendContainerAppName = 'frontend-${uniqueSuffix}'
var storageAccountName = 'st${uniqueSuffix}'
var cosmosAccountName = 'cosmos-${uniqueSuffix}'
var searchServiceName = 'search-${uniqueSuffix}'
var openAIAccountName = 'openai-${uniqueSuffix}'
var appInsightsName = 'ai-${uniqueSuffix}'
var logAnalyticsName = 'log-${uniqueSuffix}'
var aiHubName = 'hub-${uniqueSuffix}'
var aiProjectName = 'proj-${uniqueSuffix}'

// Create managed identity for container registry and Azure services access
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
  tags: commonTags
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  tags: commonTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: commonTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// Azure Storage Account (for document storage)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: commonTags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// Blob container for documents
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'insurance-documents'
  properties: {
    publicAccess: 'None'
  }
}

// Azure Cosmos DB (for agent data storage)
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  tags: commonTags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: 'insurance-agents'
  properties: {
    resource: {
      id: 'insurance-agents'
    }
  }
}

resource agentDefinitionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'agent-definitions'
  properties: {
    resource: {
      id: 'agent-definitions'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
    }
  }
}

resource agentExecutionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'agent-executions'
  properties: {
    resource: {
      id: 'agent-executions'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
    }
  }
}

resource tokenUsageContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'token-usage'
  properties: {
    resource: {
      id: 'token-usage'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
    }
  }
}

resource evaluationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'evaluations'
  properties: {
    resource: {
      id: 'evaluations'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
    }
  }
}

// Azure AI Search
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  tags: commonTags
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
  }
}

// Azure OpenAI
resource openAIAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: openAIAccountName
  location: location
  tags: commonTags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAIAccountName
    publicNetworkAccess: 'Enabled'
  }
}

resource openAIDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAIAccount
  name: azureOpenAIDeploymentName
  properties: {
    model: {
      format: 'OpenAI'
      name: azureOpenAIDeploymentName
      version: '2024-08-06'
    }
  }
  sku: {
    name: 'Standard'
    capacity: 10
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAIAccount
  name: azureOpenAIEmbeddingModel
  properties: {
    model: {
      format: 'OpenAI'
      name: azureOpenAIEmbeddingModel
      version: '1'
    }
  }
  sku: {
    name: 'Standard'
    capacity: 10
  }
  dependsOn: [
    openAIDeployment
  ]
}

// Azure AI Hub
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: aiHubName
  location: location
  tags: commonTags
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'Insurance Multi-Agent AI Hub'
    description: 'AI Hub for insurance multi-agent system'
    storageAccount: storageAccount.id
    applicationInsights: appInsights.id
  }
}

// Azure AI Project
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: aiProjectName
  location: location
  tags: commonTags
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'Insurance Multi-Agent Project'
    description: 'AI Project for insurance claims processing'
    hubResourceId: aiHub.id
  }
}

// Deploy container apps stack (environment + registry)
module containerAppsStack 'modules/container-apps-stack.bicep' = {
  name: 'container-apps-stack'
  params: {
    containerAppsEnvironmentName: containerAppsEnvironmentName
    containerRegistryName: containerRegistryName
    location: location
    tags: commonTags
    projectName: projectName
    environmentName: environmentName
  }
}

// Assign AcrPull role to managed identity
module roleAssignment 'modules/role-assignment.bicep' = {
  name: 'role-assignment'
  params: {
    registryId: containerAppsStack.outputs.containerRegistryId
    managedIdentityPrincipalId: managedIdentity.properties.principalId
    resourcePrefix: uniqueSuffix
  }
}

// Storage Blob Data Contributor role for managed identity
resource storageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentity.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Data Contributor role for managed identity
resource cosmosDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosAccount.id, managedIdentity.id, '00000000-0000-0000-0000-000000000002')
  scope: cosmosAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor role for managed identity
resource searchIndexDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, managedIdentity.id, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User role for managed identity
resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAIAccount.id, managedIdentity.id, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openAIAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Deploy backend container app
module backendContainerApp 'modules/containerapp.bicep' = {
  name: 'backend-container-app'
  params: {
    name: backendContainerAppName
    location: location
    environmentId: containerAppsStack.outputs.containerAppsEnvironmentId
    containerImage: backendContainerImage
    containerPort: 8000
    registryServer: containerAppsStack.outputs.containerRegistryLoginServer
    managedIdentityResourceId: managedIdentity.id
    managedIdentityClientId: managedIdentity.properties.clientId
    tags: commonTags
    resourcePrefix: uniqueSuffix
    environmentVariables: [
      {
        name: 'ENVIRONMENT'
        value: 'production'
      }
      {
        name: 'FRONTEND_ORIGIN'
        value: 'https://${frontendContainerAppName}.${containerAppsStack.outputs.containerAppsEnvironmentDefaultDomain}'
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: openAIAccount.properties.endpoint
      }
      {
        name: 'AZURE_OPENAI_API_KEY'
        value: openAIAccount.listKeys().key1
      }
      {
        name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
        value: azureOpenAIDeploymentName
      }
      {
        name: 'AZURE_OPENAI_EMBEDDING_MODEL'
        value: azureOpenAIEmbeddingModel
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: '2024-08-01-preview'
      }
      {
        name: 'PROJECT_ENDPOINT'
        value: '${aiProject.properties.discoveryUrl}/api/projects/${aiProjectName}'
      }
      {
        name: 'AZURE_SUBSCRIPTION_ID'
        value: subscription().subscriptionId
      }
      {
        name: 'AZURE_RESOURCE_GROUP'
        value: resourceGroup().name
      }
      {
        name: 'AZURE_AI_PROJECT_NAME'
        value: aiProjectName
      }
      {
        name: 'AZURE_STORAGE_ACCOUNT_NAME'
        value: storageAccount.name
      }
      {
        name: 'AZURE_STORAGE_CONTAINER_NAME'
        value: 'insurance-documents'
      }
      {
        name: 'AZURE_SEARCH_ENDPOINT'
        value: 'https://${searchService.name}.search.windows.net'
      }
      {
        name: 'AZURE_SEARCH_INDEX_NAME'
        value: 'insurance-policies'
      }
      {
        name: 'AZURE_COSMOS_ENDPOINT'
        value: cosmosAccount.properties.documentEndpoint
      }
      {
        name: 'AZURE_COSMOS_DATABASE_NAME'
        value: 'insurance-agents'
      }
      {
        name: 'AZURE_COSMOS_AGENT_DEFINITIONS_CONTAINER'
        value: 'agent-definitions'
      }
      {
        name: 'AZURE_COSMOS_AGENT_EXECUTIONS_CONTAINER'
        value: 'agent-executions'
      }
      {
        name: 'AZURE_COSMOS_TOKEN_USAGE_CONTAINER'
        value: 'token-usage'
      }
      {
        name: 'AZURE_COSMOS_EVALUATIONS_CONTAINER'
        value: 'evaluations'
      }
      {
        name: 'APPLICATION_INSIGHTS_CONNECTION_STRING'
        value: appInsights.properties.ConnectionString
      }
      {
        name: 'ENABLE_TELEMETRY'
        value: 'true'
      }
    ]
  }
  dependsOn: [
    roleAssignment
  ]
}

// Deploy frontend container app
module frontendContainerApp 'modules/containerapp.bicep' = {
  name: 'frontend-container-app'
  params: {
    name: frontendContainerAppName
    location: location
    environmentId: containerAppsStack.outputs.containerAppsEnvironmentId
    containerImage: frontendContainerImage
    containerPort: 3000
    registryServer: containerAppsStack.outputs.containerRegistryLoginServer
    managedIdentityResourceId: managedIdentity.id
    managedIdentityClientId: managedIdentity.properties.clientId
    tags: commonTags
    resourcePrefix: uniqueSuffix
    environmentVariables: [
      {
        name: 'API_URL'
        value: 'https://${backendContainerApp.outputs.fqdn}'
      }
    ]
  }
  dependsOn: [
    roleAssignment
  ]
}

// Outputs
output backendContainerAppFqdn string = backendContainerApp.outputs.fqdn
output frontendContainerAppFqdn string = frontendContainerApp.outputs.fqdn
output containerRegistryLoginServer string = containerAppsStack.outputs.containerRegistryLoginServer
output managedIdentityClientId string = managedIdentity.properties.clientId
output resourceGroupName string = resourceGroup().name

// Azure service outputs
output storageAccountName string = storageAccount.name
output cosmosAccountEndpoint string = cosmosAccount.properties.documentEndpoint
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output openAIEndpoint string = openAIAccount.properties.endpoint
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
output aiProjectName string = aiProjectName
output aiHubName string = aiHubName

