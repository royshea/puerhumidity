@description('Name of the shared App Service Plan in rg-shared-platform')
param appServicePlanName string

@description('Name of the shared Storage Account in rg-shared-platform')
param storageAccountName string

@description('Name of the Web App to create')
param webAppName string = 'app-puerhumidity'

@description('Deploy RBAC role assignments (requires User Access Administrator — use for bootstrap only)')
param deployRbac bool = false

@description('Name of the shared Action Group for alert notifications (created in commonAzureInfra)')
param actionGroupName string = ''

@description('Name of the shared Application Insights resource (created in commonAzureInfra)')
param appInsightsName string = ''

param location string = 'westus3'

// Reference shared resources (must already exist in the target resource group)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' existing = {
  name: appServicePlanName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(appInsightsName)) {
  name: appInsightsName
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
    appSettings: concat([
      { name: 'STORAGE_TYPE', value: 'azure' }
      { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
      { name: 'AZURE_TABLE_NAME', value: 'sensorreadings' }
      { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
    ], !empty(appInsightsName) ? [
      #disable-next-line BCP318 // appInsights is guaranteed non-null when appInsightsName is non-empty
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
    ] : [])
  }
}

// Grant the web app's managed identity Table Data Contributor on shared storage.
// Requires User Access Administrator — run manually with deployRbac=true for bootstrap.
module storageRbac 'modules/storage-rbac.bicep' = if (deployRbac) {
  name: 'puerhumidity-storage-rbac'
  params: {
    principalId: webApp.outputs.principalId
    storageAccountId: storageAccount.id
    accessType: 'table'
  }
}

// Metric alerts for the web app, wired to the shared Action Group.
module alerts 'modules/alerts.bicep' = if (!empty(actionGroupName)) {
  name: 'puerhumidity-alerts'
  params: {
    webAppName: webAppName
    webAppResourceId: webApp.outputs.id
    actionGroupName: actionGroupName
    appInsightsId: !empty(appInsightsName) ? appInsights.id : ''
    location: location
  }
}
