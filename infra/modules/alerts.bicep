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
// Severity 2 (Warning) — fires after sustained zero successful POST /webhook requests.
// Uses a scheduled query rule against Application Insights request telemetry, which
// allows filtering to just the /webhook endpoint (platform metrics are aggregate only).
//
// CONTEXT: SmartThings subscriptions use stateChangeOnly:True (app/services/smartthings.py:66),
// so EVENT webhooks arrive only when sensor values CHANGE. In a stable humidity-controlled
// environment, legitimate multi-hour gaps can occur (especially overnight). The original 1-hour
// window false-positived frequently.
//
// CONSERVATIVE FIX: 6-hour lookback + 2-consecutive-failure gating. Evaluation runs hourly; requires
// zero webhook traffic for 2 consecutive evaluations (≈6-7 hours of silence) before firing. This
// stops firing on normal stateChangeOnly gaps while catching genuinely dead sensors within ~7 hours.
//
// PROVISIONAL THRESHOLDS: App Insights telemetry only covers ~1 hour of data as of 2026-06-21 (the
// 65+ days of *sensor readings* live in Azure Table Storage, not App Insights). These parameters
// should be revisited once several weeks of actual webhook request telemetry accumulates (see Issue #2).
resource noWebhookDataAlert 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = if (!empty(appInsightsId)) {
  name: 'alert-${webAppName}-no-webhook-data'
  location: location
  properties: {
    displayName: 'No webhook data flowing'
    description: 'No successful POST /webhook requests in 6+ hours (2 consecutive hourly checks) — sensor data flow may have stopped. Thresholds are provisional pending accumulated App Insights telemetry (Issue #2).'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    targetResourceTypes: ['Microsoft.Insights/components']
    evaluationFrequency: 'PT1H'
    windowSize: 'PT6H'
    criteria: {
      allOf: [
        {
          query: 'requests | where name == "POST /webhook" and success == true'
          timeAggregation: 'Count'
          operator: 'LessThanOrEqual'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 2
            minFailingPeriodsToAlert: 2
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
