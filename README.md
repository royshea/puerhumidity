# SmartThings Humidity & Temperature Monitor

A Python Flask application that receives real-time sensor events from SmartThings via webhooks, stores readings in Azure Table Storage, and provides an interactive time-series visualization with Plotly.

Live at: https://app-puerhumidity.azurewebsites.net

## Architecture

```
SmartThings Cloud                      Azure (rg-shared-platform, westus3)
┌──────────────┐    HTTPS POST     ┌──────────────────────────────────────┐
│  Hub/Sensors ├──── webhook ─────►│  app-puerhumidity (App Service, B1)  │
└──────────────┘    /webhook       │  Python 3.13 · Flask · Gunicorn      │
                                   │  Managed Identity (DefaultAzureCredential)
                                   └──────────────┬───────────────────────┘
                                                   │ Table Data Contributor (RBAC)
                                                   ▼
                                   ┌──────────────────────────────────────┐
                                   │  sthobbyshared (Storage Account)     │
                                   │  Table: sensorreadings               │
                                   └──────────────────────────────────────┘
```

Infrastructure is defined as code in [`infra/`](infra/) using Bicep modules from [commonAzureInfra](https://github.com/royshea/commonAzureInfra). Deployment is fully automated via GitHub Actions with OIDC federation — no stored credentials.

## Features

- **Real-time webhooks** — SmartThings pushes device events instantly (no polling)
- **Managed Identity auth** — `DefaultAzureCredential` for storage access; no connection strings
- **Interactive visualization** — dual-axis chart (temperature °F / humidity %) with Plotly
- **Multiple display modes** — raw data, resampled (forward-fill), or smoothed (sliding average)
- **Configurable time windows** — view from last few hours to 3 weeks
- **Infrastructure as Code** — Bicep templates with CI/CD guard rails
- **Dual storage backends** — Azure Table Storage in production, local CSV for development

## Project Structure

```
puerHumidity/
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── config.py                # Configuration classes (Dev/Prod/Test)
│   ├── models/                  # Data models (SensorReading)
│   ├── routes/                  # Flask blueprints
│   │   ├── webhook.py           #   SmartThings lifecycle handler
│   │   ├── ui.py                #   Chart UI
│   │   ├── health.py            #   Health check
│   │   └── import_data.py       #   Historical data import (disabled by default)
│   ├── services/                # Business logic
│   │   ├── chart.py             #   Plotly chart generation
│   │   ├── data_transform.py    #   Resampling and smoothing
│   │   └── smartthings.py       #   SmartThings API client (subscriptions)
│   ├── storage/                 # Storage backends
│   │   ├── base.py              #   Abstract interface
│   │   ├── local_storage.py     #   CSV backend (development)
│   │   └── table_storage.py     #   Azure Table Storage (production)
│   └── templates/               # Jinja2 HTML templates
├── infra/                       # Bicep infrastructure-as-code
│   ├── main.bicep               #   Orchestrator (web app + conditional RBAC)
│   ├── main.bicepparam          #   Parameter values for shared platform
│   └── modules/                 #   Reusable modules (from commonAzureInfra v2.0)
├── .github/workflows/
│   ├── deploy-infra.yml         # Deploys Bicep on infra/ changes (with RBAC guard)
│   └── deploy-app.yml           # Deploys app code on push to main
├── scripts/
│   ├── seed_data.py             # Seed local CSV from historical data
│   └── migrate_csv.py           # Batch-migrate CSV → Azure Table Storage
├── tests/                       # Pytest test suite (80 tests)
├── docs/
│   └── plan.deprecated.md       # Historical migration plan (Streamlit → Flask/Azure)
├── data/
│   ├── humidity_data.csv        # Original historical data (3-column format)
│   └── readings.csv             # Local dev storage (5-column format)
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies (testing, linting)
└── pyproject.toml               # Project configuration (black, mypy, ruff, pytest)
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.13, Flask 3.0, Gunicorn |
| Visualization | Plotly, Pandas |
| Storage | Azure Table Storage (`azure-data-tables`) |
| Auth | Managed Identity (`azure-identity`, `DefaultAzureCredential`) |
| Monitoring | Application Insights, Azure Monitor (metric + log-based alerts) |
| Infrastructure | Bicep, Azure App Service (B1), Azure Storage Account |
| CI/CD | GitHub Actions, OIDC federation |
| Testing | Pytest, mypy, ruff |

## Local Development

### Prerequisites

- Python 3.13+
- (Optional) [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) for local Azure Table Storage emulation

### Setup

```bash
git clone https://github.com/royshea/puerhumidity.git
cd puerHumidity
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### Environment Variables

Create a `.env` file (see `.env.example`):

```env
STORAGE_TYPE=local                    # 'local' for dev, 'azure' for production
LOCAL_DATA_PATH=data/readings.csv     # Path for local CSV storage
SECRET_KEY=dev-secret-key             # Any value for local dev
```

For local Azure Table Storage testing with Azurite:

```env
STORAGE_TYPE=azure
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=...;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;
AZURE_TABLE_NAME=sensorreadings
```

### Seed Data

```bash
python -m scripts.seed_data
```

Converts historical 3-column data (`data/humidity_data.csv`) to the 5-column format used by the app.

### Run

```bash
flask run --debug
```

Visit http://localhost:5000 for the chart UI.

### Testing

```bash
pytest                  # Run all tests (80 tests)
pytest --cov=app        # With coverage
pytest tests/test_webhook.py -v   # Specific file
mypy app/ tests/        # Type checking
```

## SmartThings Integration

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook` | POST | Receive SmartThings lifecycle events |
| `/` | GET | Interactive chart UI |
| `/health` | GET | Health check |
| `/import` | GET/POST | Import historical data via PAT (disabled by default) |

### Lifecycle Events

The webhook handler (`app/routes/webhook.py`) processes:

| Lifecycle | Purpose |
|-----------|---------|
| **PING** | Echo challenge back for app verification |
| **CONFIRMATION** | Fetch confirmation URL to register webhook |
| **CONFIGURATION** | Return app metadata and UI pages for mobile app |
| **INSTALL** | Store tokens, create device subscriptions |
| **UPDATE** | Re-create subscriptions on config changes |
| **EVENT** | Parse sensor readings, write to storage |
| **UNINSTALL** | Cleanup |

> **Important**: The CONFIGURATION lifecycle must return `permissions: ["r:devices:*", "r:locations:*"]` or the INSTALL lifecycle will never fire. See `docs/plan.deprecated.md` for detailed notes on this gotcha.

### Registered SmartApp

| Field | Value |
|-------|-------|
| App ID | `4060b8f2-4ade-4c99-8e71-01306215b942` |
| Devices | PuerHumidity, ChestHumidity |
| Target URL | `https://app-puerhumidity.azurewebsites.net/webhook` |

### Chart UI Controls

- **Display Mode**: `raw` (markers), `resampled` (forward-fill stepped line), `smoothed` (sliding average)
- **Hours**: Time window — default 504 (3 weeks)
- **Resolution**: Resampling interval in minutes
- **Smoothing Window**: Sliding average window in minutes

## Data Schema

### Azure Table Storage

| Field | Description |
|-------|-------------|
| PartitionKey | `{DeviceLabel}-{ReadingType}` (e.g., `PuerHumidity-Humidity`) |
| RowKey | Reverse timestamp + reading type (newest first) |
| device_id | SmartThings device UUID |
| device_label | Human-readable name |
| reading_type | `temperature` or `humidity` |
| value | Sensor value (°F or %) |
| timestamp | ISO 8601 UTC |

### Local CSV (5-column)

`device_id, device_label, reading_type, value, timestamp`

## Azure Deployment

### Infrastructure

| Resource | Value |
|----------|-------|
| Resource Group | `rg-shared-platform` (westus3) |
| App Service Plan | `asp-hobby` (B1 shared with other hobby projects) |
| Web App | `app-puerhumidity` (`alwaysOn: true` — webhook receiver) |
| Storage Account | `sthobbyshared` (shared) |
| Application Insights | `appi-hobby` (shared, daily cap 100 MB) |
| Auth | Managed Identity → Table Data Contributor RBAC |
| IaC | Bicep in `infra/` (modules from [commonAzureInfra](https://github.com/royshea/commonAzureInfra) v2.0) |

### CI/CD Pipelines

Pushing to `main` triggers automatic deployment:

- **`deploy-infra.yml`** — Runs when `infra/**` files change. Includes an RBAC change guard that fails the pipeline if any RBAC-related files are modified (RBAC must be bootstrapped manually).
- **`deploy-app.yml`** — Runs when app code changes (ignores `infra/`, `docs/`, `*.md`). Zips and deploys to Azure App Service.

Both workflows authenticate via OIDC federation — no stored credentials.

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | App registration client ID for OIDC |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

### App Settings

Managed via Bicep (`infra/main.bicep`):

| Variable | Value | Description |
|----------|-------|-------------|
| `STORAGE_TYPE` | `azure` | Use Azure Table Storage |
| `AZURE_STORAGE_ACCOUNT_NAME` | `sthobbyshared` | Shared storage account |
| `AZURE_TABLE_NAME` | `sensorreadings` | Table name |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Install pip dependencies on deploy |

| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (from `appi-hobby`) | Application Insights telemetry |

`SECRET_KEY` is set manually (not in Bicep — it's a secret):

```bash
az webapp config appsettings set \
    --name app-puerhumidity \
    --resource-group rg-shared-platform \
    --settings SECRET_KEY='<random-secret>'
```

### Monitoring & Alerting

Connected to the shared **Application Insights** (`appi-hobby`) for per-request telemetry. Four alert rules are defined in `infra/modules/alerts.bicep`, all wired to the shared Action Group (`ag-hobby-email`) from commonAzureInfra:

| Alert | Type | Fires when |
|-------|------|-----------|
| Health check (Sev 1) | Metric | Health probes drop below 100% |
| HTTP 5xx (Sev 2) | Metric | > 3 server errors in 5 minutes |
| No webhook data (Sev 2) | Log query | Zero successful POST /webhook requests in 1 hour |
| Slow response (Sev 3) | Metric | Average response > 5 seconds |

The "no webhook data" alert uses a **scheduled query rule** against Application Insights rather than a platform metric — this allows filtering to just the `/webhook` endpoint, excluding health check probes that would mask a real data flow interruption.

### RBAC Bootstrap

The CI/CD service principal has Contributor but not User Access Administrator. RBAC role assignments must be deployed manually when the web app's managed identity changes:

```bash
az deployment group create \
    --resource-group rg-shared-platform \
    --template-file infra/main.bicep \
    --parameters infra/main.bicepparam \
    --parameters deployRbac=true
```

The `deployRbac` parameter (default `false`) gates the RBAC module. The pipeline includes a guard step that fails if RBAC files are modified, preventing accidental attempts to deploy RBAC through CI.

### Verify Deployment

```bash
# Health check
curl https://app-puerhumidity.azurewebsites.net/health

# Test webhook
curl -X POST https://app-puerhumidity.azurewebsites.net/webhook \
    -H "Content-Type: application/json" \
    -d '{"lifecycle": "PING", "pingData": {"challenge": "test"}}'
```

### View Logs

```bash
az webapp log tail --name app-puerhumidity --resource-group rg-shared-platform
```

## Historical Data Import

Web-based import is disabled by default in production. To temporarily enable:

```bash
# Enable
az webapp config appsettings set \
    --name app-puerhumidity \
    --resource-group rg-shared-platform \
    --settings ENABLE_IMPORT=true

# Import at https://app-puerhumidity.azurewebsites.net/import
# Uses a SmartThings PAT (get one at https://account.smartthings.com/tokens)
# The Activities API provides ~7 days of history

# Disable
az webapp config appsettings delete \
    --name app-puerhumidity \
    --resource-group rg-shared-platform \
    --setting-names ENABLE_IMPORT
```

For bulk CSV migration, use `python scripts/migrate_csv.py` (batch upserts, 100 entities per transaction).

## Troubleshooting

**Webhook not receiving events**: Check the SmartThings Developer Workspace — verify the target URL is `https://app-puerhumidity.azurewebsites.net/webhook`. If the SmartApp was reinstalled, the INSTALL lifecycle must succeed to create subscriptions (check app logs for "Subscriptions created").

**App returns 500**: Likely a storage auth issue. Verify the web app's managed identity has Table Data Contributor on `sthobbyshared`. Run `az role assignment list --scope /subscriptions/.../storageAccounts/sthobbyshared --role "Storage Table Data Contributor"`.

**No data in chart**: In production, wait for SmartThings sensor events (typically every 5–15 minutes). For local dev, run `python -m scripts.seed_data` to populate `data/readings.csv`.

**Timezone errors**: All timestamps should be UTC. The app normalizes naive datetimes to UTC.

**RBAC deploy fails in CI**: By design — the pipeline guards against RBAC changes. Deploy RBAC manually with `deployRbac=true` (see [RBAC Bootstrap](#rbac-bootstrap)).

## License

This project is provided as-is for personal use.
