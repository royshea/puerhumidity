// module-version: 2.0

@description('Principal ID of the managed identity to grant access')
param principalId string

@description('Resource ID of the storage account')
param storageAccountId string

@description('Roles to assign (table, blob, queue, both, or all)')
@allowed(['table', 'blob', 'queue', 'both', 'all'])
param accessType string = 'both'

@description('Use Storage Blob Data Owner instead of Contributor (required for Azure Functions runtime)')
param useBlobDataOwner bool = false

// Built-in role definition IDs
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var storageQueueDataContributorRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'

var effectiveBlobRoleId = useBlobDataOwner ? storageBlobDataOwnerRoleId : storageBlobDataContributorRoleId
var needsBlob = accessType == 'blob' || accessType == 'both' || accessType == 'all'
var needsTable = accessType == 'table' || accessType == 'both' || accessType == 'all'
var needsQueue = accessType == 'queue' || accessType == 'all'

resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (needsBlob) {
  name: guid(storageAccountId, principalId, effectiveBlobRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', effectiveBlobRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource tableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (needsTable) {
  name: guid(storageAccountId, principalId, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource queueRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (needsQueue) {
  name: guid(storageAccountId, principalId, storageQueueDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageAccountId, '/'))
}
