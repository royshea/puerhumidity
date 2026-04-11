@description('Name of the shared App Service Plan in rg-shared-platform')
param appServicePlanName string

@description('Name of the shared Storage Account in rg-shared-platform')
param storageAccountName string

@description('Name of the Web App to create')
param webAppName string = 'app-puerhumidity-v2'

param location string = 'westus3'

// Reference shared resources (must already exist in the target resource group)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' existing = {
  name: appServicePlanName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

module webApp 'modules/web-app.bicep' = {
  name: 'puerhumidity-web-app'
  params: {
    name: webAppName
    location: location
    appServicePlanId: appServicePlan.id
    linuxFxVersion: 'PYTHON|3.13'
    startupCommand: 'gunicorn --bind=0.0.0.0 --timeout 600 app:application'
    projectName: 'puerhumidity'
    alwaysOn: true
    healthCheckPath: '/health'
    appSettings: [
      { name: 'STORAGE_TYPE', value: 'azure' }
      { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
      { name: 'AZURE_TABLE_NAME', value: 'sensorreadings' }
      { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
    ]
  }
}

// Grant the web app's managed identity Table Data Contributor on shared storage
module storageRbac 'modules/storage-rbac.bicep' = {
  name: 'puerhumidity-storage-rbac'
  params: {
    principalId: webApp.outputs.principalId
    storageAccountId: storageAccount.id
    accessType: 'table'
  }
}
