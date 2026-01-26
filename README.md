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
├── scripts/
│   ├── seed_data.py            # Seed local storage from historical CSV
│   ├── migrate_csv.py          # Migrate CSV to Azure Table Storage
│   └── deploy.ps1              # Azure deployment script
├── archive/                     # Legacy Streamlit app (preserved)
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

# Azure Table Storage (production)
AZURE_STORAGE_CONNECTION_STRING=...   # Azure connection string
AZURE_TABLE_NAME=sensorreadings       # Table name

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
    --resource-group rg-puerhumidity `
    --settings ENABLE_IMPORT=true

# Perform your import at /import

# Disable import again
az webapp config appsettings delete `
    --name app-puerhumidity `
    --resource-group rg-puerhumidity `
    --setting-names ENABLE_IMPORT
```

### CSV Migration

For larger historical datasets, use the migration script:

```powershell
# Set connection string and run
$env:AZURE_STORAGE_CONNECTION_STRING = (az storage account show-connection-string `
    --name stpuerhumidity --resource-group rg-puerhumidity --query connectionString -o tsv)
python scripts/migrate_csv.py
```

The script uses batch operations (100 entities per transaction) for efficient bulk loading.

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

### Prerequisites

1. Azure account with subscription
2. Azure CLI installed and logged in (`az login`)

### Initial Setup (One-time)

```bash
# Create resource group
az group create --name rg-puerhumidity --location centralus

# Create storage account
az storage account create --name stpuerhumidity --resource-group rg-puerhumidity --sku Standard_LRS

# Create table
az storage table create --name sensorreadings --account-name stpuerhumidity

# Get connection string (save this)
az storage account show-connection-string --name stpuerhumidity --resource-group rg-puerhumidity --query connectionString -o tsv

# Create App Service Plan (Free tier)
az appservice plan create --name asp-puerhumidity --resource-group rg-puerhumidity --sku F1 --is-linux --location centralus

# Create Web App
az webapp create --name app-puerhumidity --resource-group rg-puerhumidity --plan asp-puerhumidity --runtime "PYTHON:3.11"

# Configure app settings
az webapp config appsettings set --name app-puerhumidity --resource-group rg-puerhumidity --settings \
    STORAGE_TYPE=azure \
    "AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>" \
    AZURE_TABLE_NAME=sensorreadings \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true

# Set startup command (use app:app, not app:create_app())
az webapp config set --name app-puerhumidity --resource-group rg-puerhumidity \
    --startup-file "antenv/bin/gunicorn --bind=0.0.0.0 --timeout 600 app:app"
```

> **Important**: See [Azure App Service Notes](#azure-app-service-notes) below for details on why this specific startup command format is required.

### Deploy Code

Use the deployment script to create a clean package and deploy:

```powershell
# From project root
.\scripts\deploy.ps1
```

The script:
- Creates a clean deployment package (excludes `__pycache__`, tests, etc.)
- Deploys via ZIP to Azure Web App
- Cleans up temporary files

**Manual deployment** (if needed):
```powershell
# Create ZIP manually
Compress-Archive -Path app, requirements.txt -DestinationPath deploy.zip -Force

# Deploy
az webapp deploy --name app-puerhumidity --resource-group rg-puerhumidity --src-path deploy.zip --type zip
```

### Verify Deployment

```bash
# Health check
curl https://app-puerhumidity.azurewebsites.net/health

# Test webhook
curl -X POST https://app-puerhumidity.azurewebsites.net/webhook \
    -H "Content-Type: application/json" \
    -d '{"lifecycle": "PING", "pingData": {"challenge": "test"}}'
```

### Environment Variables (Azure)

| Variable | Description |
|----------|-------------|
| `STORAGE_TYPE` | `azure` for production |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Table Storage connection string |
| `AZURE_TABLE_NAME` | Table name (default: `sensorreadings`) |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` to install dependencies |

## Azure App Service Notes

### How Oryx Builds Python Apps

When you deploy to Azure App Service (Linux), the **Oryx** build system handles your app:

1. **Build Phase**: Oryx detects `requirements.txt` and creates a virtualenv at `/home/site/wwwroot/antenv`
2. **Compression**: The built app is compressed into `output.tar.gz`
3. **Startup Phase**: On container start, Oryx extracts to `/tmp/<hash>/` and sets up `PYTHONPATH`
4. **Execution**: Your startup command runs with the extracted virtualenv

**Key Insight**: The virtualenv is at `antenv/` relative to the app root, NOT in `PATH`. You must reference `antenv/bin/gunicorn` explicitly in the startup command.

### Gunicorn App Reference

Gunicorn expects a WSGI application object, not a factory function. The app exports an instance at module level:

```python
# In app/__init__.py
def create_app(config_name: str | None = None) -> Flask:
    ...
    return app

# Export for gunicorn - MUST be at module level
app = create_app()
```

The startup command uses `app:app` (module:variable):
```
antenv/bin/gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

⚠️ **Warning**: Using `app:create_app()` with parentheses fails on Azure due to shell quoting issues, causing `syntax error near unexpected token '('`.

### F1 (Free) Tier Quotas

The F1 tier has strict quotas that can block deployments and restarts:

| Quota | Limit | Reset |
|-------|-------|-------|
| WPStopRequests | 15/hour | Top of each hour |
| CPU | 60 min/day | Daily at 00:00 UTC |

If you hit quota limits during debugging, temporarily upgrade to B1:
```bash
# Upgrade (~$0.02/hour)
az appservice plan update --name asp-puerhumidity --resource-group rg-puerhumidity --sku B1

# Scale back down when done
az appservice plan update --name asp-puerhumidity --resource-group rg-puerhumidity --sku F1
```

### Viewing Logs

```bash
# Deployment logs
az webapp log deployment list --name app-puerhumidity --resource-group rg-puerhumidity -o table

# Runtime logs (live tail)
az webapp log tail --name app-puerhumidity --resource-group rg-puerhumidity
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Exit code 127` | Command not found | Use `antenv/bin/gunicorn` not just `gunicorn` |
| `syntax error near unexpected token '('` | Shell quoting issue | Use `app:app` not `app:create_app()` |
| `TypeError: create_app() takes 0 arguments but 2 were given` | Gunicorn passing WSGI args to factory | Export `app = create_app()` at module level |
| `504 Gateway Timeout` on deploy | App is stopped | Start the app before deploying |

## Legacy Streamlit App

The original Streamlit polling app is preserved in `archive/`. It used:
- Polling-based data collection (vs webhooks)
- Direct SmartThings API calls
- Single CSV storage format

## Troubleshooting

**Webhook not receiving events**: Ensure your webhook URL is publicly accessible (HTTPS required for production). Use LocalTunnel for development.

**Timezone comparison errors**: All timestamps should be UTC. The app normalizes naive datetimes to UTC.

**No data in chart**: Run the seed script or wait for SmartThings events. Check that `data/readings.csv` exists and has data.

**Azure connection fails**: Verify your connection string and that the storage account allows your IP.

## Development

### Type Checking

```bash
mypy app/ tests/
```

### Code Style

The project uses standard Python conventions. Consider using `ruff` or `black` for formatting.

## License

This project is provided as-is for personal use.
