# SmartThings Humidity & Temperature Monitor

A Python application for monitoring and visualizing humidity and temperature data from SmartThings sensors using real-time webhooks.

## Overview

This application receives real-time sensor events from SmartThings via webhooks, stores readings in persistent storage (local CSV or Azure Table Storage), and provides an interactive time-series visualization using Flask and Plotly.

## Features

- **Real-time Webhooks**: SmartThings pushes device events instantly (no polling)
- **Dual Storage Backends**: Local CSV for development, Azure Table Storage for production
- **Interactive Visualization**: Dual-axis chart with temperature (°F) and humidity (%) 
- **Multiple Display Modes**: Raw data, resampled (forward-fill), or smoothed (sliding average)
- **Configurable Time Windows**: View data from last few hours to 3 weeks
- **21-Day Data Window**: Automatically filters display to the most recent 21 days

## Technology Stack

- **Python 3.13+**
- **Flask 3.0**: Web framework for webhook handling and UI
- **Plotly**: Interactive charting
- **Azure Table Storage**: Production data storage (optional)
- **SmartThings Webhook API**: Real-time device event delivery

## Project Structure

```
puerHumidity/
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── config.py                # Configuration classes
│   ├── models/                  # Data models (SensorReading)
│   ├── routes/                  # Flask blueprints (webhook, UI, health, import)
│   ├── services/                # Business logic (chart, data transform)
│   ├── storage/                 # Storage backends (local CSV, Azure Table)
│   └── templates/               # Jinja2 HTML templates
├── tests/                       # Pytest test suite
├── infra/                       # Bicep infrastructure-as-code
│   ├── main.bicep               # Project infrastructure orchestrator
│   ├── main.bicepparam          # Parameter values for shared platform
│   └── modules/                 # Reusable Bicep modules (from commonAzureInfra)
├── .github/workflows/           # CI/CD pipelines
│   ├── deploy-infra.yml         # Deploy Bicep on infra/ changes
│   └── deploy-app.yml           # Deploy app code on push to main
├── scripts/
│   ├── seed_data.py            # Seed local storage from historical CSV
│   └── migrate_csv.py          # Migrate CSV to Azure Table Storage
├── docs/
│   └── plan.md                 # Migration plan and architecture docs
├── data/
│   ├── humidity_data.csv       # Original historical data (3-column format)
│   └── readings.csv            # Active storage (5-column format)
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
└── pyproject.toml              # Project configuration
```

## Prerequisites

- Python 3.13 or higher
- SmartThings account with configured temperature/humidity sensors
- SmartThings SmartApp registration (for webhook delivery)
- Azure account (optional, for production deployment)

## Setup

### 1. Clone and Create Virtual Environment

```bash
git clone <repository-url>
cd puerHumidity
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Production only
pip install -r requirements.txt

# Development (includes testing tools)
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Storage configuration
STORAGE_TYPE=local                    # 'local' or 'azure'
LOCAL_DATA_PATH=data/readings.csv     # For local storage

# Azure Table Storage (production — uses Managed Identity, not connection strings)
AZURE_STORAGE_ACCOUNT_NAME=sthobbyshared  # Storage account name
AZURE_TABLE_NAME=sensorreadings            # Table name

# Flask settings
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

### 4. Seed Local Data (Development)

If you have historical data in `data/humidity_data.csv`, seed the local storage:

```bash
python -m scripts.seed_data
```

This converts the 3-column format to the 5-column format used by the app.

## Running the Application

### Development Server

```bash
flask run --debug
```

The application will be available at http://localhost:5000

### Using the Chart UI

Visit http://localhost:5000 to see the interactive chart. Controls include:

- **Display Mode**: 
  - `raw` - Show original data points as markers
  - `resampled` - Forward-fill to regular intervals (stepped line)
  - `smoothed` - Apply sliding average smoothing
- **Hours**: Time window to display (default: 504 = 3 weeks)
- **Resolution**: Resampling interval in minutes (for resampled/smoothed modes)
- **Smoothing Window**: Sliding average window in minutes (for smoothed mode)

## SmartThings Integration

### Webhook Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook` | POST | Receive SmartThings lifecycle events |
| `/` | GET | Chart UI |
| `/import` | GET/POST | Import historical data with PAT |
| `/health` | GET | Health check |

### SmartThings Lifecycle Events

The webhook handler processes these event types:

- **PING**: Responds with challenge for app verification
- **CONFIRMATION**: Confirms webhook URL registration
- **CONFIGURATION**: Returns app metadata and UI pages (required for mobile app)
- **INSTALL/UPDATE**: Creates device subscriptions
- **EVENT**: Processes sensor readings (temperature/humidity)
- **UNINSTALL**: Cleanup when app is removed

> **Important**: The CONFIGURATION lifecycle must return proper `permissions` (`["r:devices:*", "r:locations:*"]`) or the INSTALL lifecycle will never fire.

### Registered SmartApp

- **App ID**: `4060b8f2-4ade-4c99-8e71-01306215b942`
- **Devices**: PuerHumidity, ChestHumidity

## Data Schema

### CSV Storage (5-column format)

| Column | Type | Description |
|--------|------|-------------|
| device_id | string | SmartThings device UUID |
| device_label | string | Human-readable device name |
| reading_type | string | `temperature` or `humidity` |
| value | float | Sensor value (°F or %) |
| timestamp | datetime | ISO 8601 timestamp (UTC) |

### Azure Table Storage

- **Partition Key**: Device label (e.g., "PuerHumidity")
- **Row Key**: Timestamp + reading type (for uniqueness)

## Historical Data Import

> **Note**: Web-based import is disabled by default in production for security. 
> See [Enabling Web Import](#enabling-web-import) below.

### Web Import (SmartThings Activities API)

1. Visit `/import` on your deployed app
2. Generate a PAT at [account.smartthings.com/tokens](https://account.smartthings.com/tokens)
3. Enter the PAT and submit
4. The app fetches all available history with pagination

The Activities API provides ~7 days of history.

### Enabling Web Import

Import is disabled by default to prevent unauthorized data writes. To temporarily enable:

```powershell
# Enable import
az webapp config appsettings set `
    --name app-puerhumidity `
    --resource-group rg-shared-platform `
    --settings ENABLE_IMPORT=true

# Perform your import at /import

# Disable import again
az webapp config appsettings delete `
    --name app-puerhumidity `
    --resource-group rg-shared-platform `
    --setting-names ENABLE_IMPORT
```

### CSV Migration

For larger historical datasets, use the migration script:

```bash
python scripts/migrate_csv.py
```

The script uses batch operations (100 entities per transaction) for efficient bulk loading.
See `docs/shared-infra-migration.md` for details on migrating data between storage accounts.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_chart.py -v
```

## Azure Deployment

This project runs on the shared hobby platform (`rg-shared-platform`, westus3) using infrastructure defined in [commonAzureInfra](https://github.com/royshea/commonAzureInfra). Deployment is fully automated via GitHub Actions.

### Architecture

| Resource | Value |
|----------|-------|
| Resource Group | `rg-shared-platform` (westus3) |
| App Service Plan | `asp-hobby` (B1 shared) |
| Web App | `app-puerhumidity` |
| Storage Account | `sthobbyshared` (shared) |
| Auth to storage | Managed Identity + RBAC (Table Data Contributor) |
| Deployment | GitHub Actions CI/CD |
| IaC | Bicep in `infra/` directory |

### CI/CD Workflows

Pushing to `main` triggers automatic deployment:

- **`deploy-infra.yml`** — Runs when `infra/**` files change. Previews changes (what-if) then deploys Bicep templates to `rg-shared-platform`.
- **`deploy-app.yml`** — Runs when application code changes (ignores `infra/`, `docs/`, `*.md`). Builds and deploys the Python app to Azure App Service.

Both workflows authenticate via OIDC federation — no stored credentials.

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | App registration client ID for OIDC |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

### Environment Variables (Azure)

Configured via Bicep in `infra/main.bicep`:

| Variable | Description |
|----------|-------------|
| `STORAGE_TYPE` | `azure` for production |
| `AZURE_STORAGE_ACCOUNT_NAME` | Shared storage account name |
| `AZURE_TABLE_NAME` | Table name (default: `sensorreadings`) |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` to install dependencies |

`SECRET_KEY` is set manually via `az webapp config appsettings set` (not in Bicep, since it's a secret).

### Verify Deployment

```bash
# Health check
curl https://app-puerhumidity.azurewebsites.net/health

# Test webhook
curl -X POST https://app-puerhumidity.azurewebsites.net/webhook \
    -H "Content-Type: application/json" \
    -d '{"lifecycle": "PING", "pingData": {"challenge": "test"}}'
```

### Viewing Logs

```bash
# Runtime logs (live tail)
az webapp log tail --name app-puerhumidity --resource-group rg-shared-platform
```

## Troubleshooting

**Webhook not receiving events**: Ensure your webhook URL is publicly accessible (HTTPS required for production). Use LocalTunnel for development.

**Timezone comparison errors**: All timestamps should be UTC. The app normalizes naive datetimes to UTC.

**No data in chart**: Run the seed script or wait for SmartThings events. Check that `data/readings.csv` exists and has data.

## Development

### Type Checking

```bash
mypy app/ tests/
```

### Code Style

The project uses standard Python conventions. Consider using `ruff` or `black` for formatting.

## License

This project is provided as-is for personal use.
