// module-version: 2.0

@description('Name of the Web App')
param name string

@description('Azure region')
param location string

@description('Resource ID of the App Service Plan to host this app')
param appServicePlanId string

@description('Runtime stack (e.g., PYTHON|3.13, NODE|22-lts, DOTNETCORE|8.0)')
param linuxFxVersion string

@description('Startup command (e.g., "gunicorn --bind=0.0.0.0 app:app")')
param startupCommand string = ''

@description('App settings (environment variables)')
param appSettings array = []

@description('Project name for tagging (used to identify which project owns this resource)')
param projectName string

@description('Additional tags to apply to the resource')
param tags object = {}

@description('Always On setting (set to false for static sites to conserve memory on shared plans)')
param alwaysOn bool = true

@description('CORS allowed origins (e.g., ["https://myapp.ambleramble.org", "http://localhost:5173"])')
param corsAllowedOrigins array = []

@description('Health check path (e.g., "/health")')
param healthCheckPath string = ''

var resourceTags = union(tags, {
  project: projectName
  managedBy: 'bicep'
})

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: resourceTags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: linuxFxVersion
      appCommandLine: startupCommand
      alwaysOn: alwaysOn
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      healthCheckPath: !empty(healthCheckPath) ? healthCheckPath : null
      cors: !empty(corsAllowedOrigins) ? {
        allowedOrigins: corsAllowedOrigins
      } : null
      appSettings: appSettings
    }
  }
}

@description('Default hostname of the web app')
output defaultHostname string = webApp.properties.defaultHostName

@description('Resource ID of the web app')
output id string = webApp.id

@description('Name of the web app')
output webAppName string = webApp.name

@description('Principal ID of the system-assigned managed identity')
output principalId string = webApp.identity.principalId
