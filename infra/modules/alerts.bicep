// Metric alerts for the puerHumidity web app.
// Requires a shared Action Group (created in commonAzureInfra) to exist.

@description('Name of the web app (used for alert naming)')
param webAppName string

@description('Resource ID of the web app to monitor')
param webAppResourceId string

@description('Name of the shared Action Group in rg-shared-platform')
param actionGroupName string

@description('Resource ID of the shared Application Insights (empty string to skip log-based alerts)')
param appInsightsId string = ''

@description('Azure region for scheduled query rules (must match resource group region)')
param location string

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' existing = {
  name: actionGroupName
}

// Alert: HTTP server errors (5xx)
// Severity 2 (Warning) — fires when more than 3 server errors in a 5-minute window.
resource http5xxAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${webAppName}-http5xx'
  location: 'global'
  properties: {
    description: 'More than 3 HTTP 5xx errors in a 5-minute window'
    severity: 2
    enabled: true
    scopes: [webAppResourceId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'Http5xx'
          metricName: 'Http5xx'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: 3
          timeAggregation: 'Total'
        }
      ]
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
    }
    autoMitigate: true
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

// Alert: Slow response time
// Severity 3 (Informational) — fires when average response exceeds 5 seconds.
resource responseTimeAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${webAppName}-slow-response'
  location: 'global'
  properties: {
    description: 'Average response time exceeds 5 seconds over a 5-minute window'
    severity: 3
    enabled: true
    scopes: [webAppResourceId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'ResponseTime'
          metricName: 'HttpResponseTime'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Average'
        }
      ]
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
    }
    autoMitigate: true
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

// Alert: Health check degradation
// Severity 1 (Error) — fires when health probes report below 100%.
resource healthCheckAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${webAppName}-health'
  location: 'global'
  properties: {
    description: 'Health check status has degraded below 100%'
    severity: 1
    enabled: true
    scopes: [webAppResourceId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'HealthCheck'
          metricName: 'HealthCheckStatus'
          metricNamespace: 'Microsoft.Web/sites'
          operator: 'LessThan'
          threshold: 100
          timeAggregation: 'Average'
        }
      ]
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
    }
    autoMitigate: true
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

// Alert: No webhook data flowing (log-based, requires Application Insights)
// Severity 2 (Warning) — fires when zero successful POST /webhook requests in 1 hour.
// Uses a scheduled query rule against Application Insights request telemetry, which
// allows filtering to just the /webhook endpoint (platform metrics are aggregate only).
// Historic analysis: post-migration data shows zero hourly gaps across 65+ days (~10
// readings/hour), so any full hour without webhook traffic is a genuine anomaly.
resource noWebhookDataAlert 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = if (!empty(appInsightsId)) {
  name: 'alert-${webAppName}-no-webhook-data'
  location: location
  properties: {
    displayName: 'No webhook data flowing'
    description: 'No successful POST /webhook requests in the past hour — sensor data flow may have stopped. Requires Application Insights telemetry to be flowing (verify after first deploy).'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    targetResourceTypes: ['Microsoft.Insights/components']
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: 'requests | where name == "POST /webhook" and success == true'
          timeAggregation: 'Count'
          operator: 'LessThanOrEqual'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}
