# PuerHumidity Azure Migration Plan

> **Document Purpose**: Complete implementation plan for migrating from a local Streamlit polling app to an Azure-hosted webhook-based system. Contains enough context to resume work after any break.

## Project Overview

### Current State (Streamlit v1)
- **Streamlit app** (`app.py`) that polls SmartThings devices for temperature/humidity
- **Webhook handler** (`webhook_handler.py`) used for one-time SmartApp registration
- **CSV storage** (`data/humidity_data.csv`) for sensor readings
- **SmartApp registered** with ID `4060b8f2-4ade-4c99-8e71-01306215b942`
- **Installed App ID**: `55713660-1f57-4338-81e0-3c45479b2279`
- **Location ID**: `9ec8c9fc-3af2-464f-b917-d0403ab0c4bb`

### Target State (Azure v2)
- **Azure Web App** (Free tier) running Flask
- **Azure Table Storage** for time-series sensor data
- **Real-time webhooks** - SmartThings pushes device events (no polling)
- **Server-rendered charts** with Plotly (same dual-axis visualization)
- **PAT-based import** for bootstrapping historical data

### Why Migrate?
1. **Real-time updates** - Events pushed instantly vs. polling intervals
2. **Always-on** - Azure hosts 24/7, no local machine needed
3. **Proper architecture** - Clean separation of concerns, testable code
4. **No token expiry issues** - SmartApp tokens auto-refresh

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Azure Web App                            │
├─────────────────────────────────────────────────────────────────┤
│  POST /webhook       ← SmartThings EVENT/INSTALL/PING/etc       │
│  GET  /              → Chart UI (reads from Table Storage)      │
│  POST /import        → One-time PAT import (token not stored)   │
│  GET  /health        → Health check endpoint                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Azure Table Storage │
                    │  - sensorreadings    │
                    │  - devicelabels      │
                    └─────────────────────┘
```

### SmartThings Integration Flow

```
1. INSTALL lifecycle → Create subscriptions for humidity + temperature
2. Device state changes → SmartThings sends EVENT to webhook
3. Webhook receives EVENT → Parse deviceEvent, write to Table Storage
4. User visits / → Query Table Storage, render Plotly chart
```

---

## Device Configuration

| Device | ID | Label |
|--------|-----|-------|
| PuerHumidity | `9a52da52-a841-4883-b91e-8d29b9a6d01d` | PuerHumidity |
| ChestHumidity | `baee9df0-5635-4205-8e58-7de7eb5d88d4` | ChestHumidity |

Each device reports both `temperatureMeasurement` and `relativeHumidityMeasurement` capabilities.

---

## Project Structure (Target)

```
puerHumidity/
├── archive/
│   └── streamlit-v1/           # Preserved original implementation
│       ├── app.py
│       ├── webhook_handler.py
│       ├── discover_devices.py
│       ├── test_activities.py
│       ├── activities_response.json
│       ├── activities_device_response.json
│       └── SignificantPrompts.md
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration classes (dev/prod)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── webhook.py           # SmartThings lifecycle handlers
│   │   ├── ui.py                # Chart UI routes
│   │   └── import_data.py       # PAT-based import endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── smartthings.py       # SmartThings API client
│   │   ├── chart.py             # Plotly chart generation
│   │   └── data_transform.py    # Duration-weighted averaging
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract storage interface
│   │   ├── table_storage.py     # Azure Table Storage implementation
│   │   └── local_storage.py     # Local CSV storage (for dev/testing)
│   ├── models/
│   │   ├── __init__.py
│   │   └── reading.py           # SensorReading dataclass
│   └── templates/
│       ├── base.html
│       ├── chart.html
│       └── import.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_webhook.py
│   ├── test_storage.py
│   ├── test_chart.py
│   └── payloads/                # Sample SmartThings JSON payloads
│       ├── ping.json
│       ├── install.json
│       ├── event_humidity.json
│       └── event_temperature.json
├── scripts/
│   └── migrate_csv.py           # One-time CSV → Table Storage migration
├── docs/
│   └── plan.md                  # This file
├── data/
│   ├── humidity_data.csv        # Historical data (preserved)
│   ├── .smartapp_tokens.json    # SmartApp tokens (preserved)
│   └── .gitignore
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Dev/test dependencies
├── pyproject.toml               # Tool configs (black, mypy, pytest)
├── .env                         # Local environment (not committed)
├── .env.example                 # Template for .env
├── .gitignore
└── README.md
```

---

## Implementation Phases

### Phase 0: Archive Current Implementation

**Goal**: Preserve current Streamlit code for reference, clear root for new implementation.

**Work**:
- Create `archive/streamlit-v1/` directory
- Move `app.py`, `webhook_handler.py`, `discover_devices.py`, `test_activities.py` to archive
- Move `activities_response.json`, `activities_device_response.json` to archive
- Move `SignificantPrompts.md` to archive
- Keep `data/`, `.env`, `.gitignore`, `requirements.txt`, `README.md` in place

**Validation**:
```powershell
Test-Path archive/streamlit-v1/app.py             # True
Test-Path archive/streamlit-v1/webhook_handler.py # True
Test-Path app.py                                   # False
Test-Path data/humidity_data.csv                  # True
git status                                         # Shows moves
```

---

### Phase 1: Project Scaffolding & Models

**Goal**: Set up project structure, configuration, and core data models.

**Work**:
- Create directory structure (`app/`, `tests/`, `scripts/`)
- Implement `SensorReading` dataclass with type hints
- Set up `config.py` with development/production configurations
- Create Flask app factory in `app/__init__.py`
- Set up pytest with fixtures
- Create `pyproject.toml` with tool configurations
- Create new `requirements.txt` and `requirements-dev.txt`

**Files**:
- `app/__init__.py` - Flask app factory with `create_app()`
- `app/config.py` - `Config`, `DevelopmentConfig`, `ProductionConfig` classes
- `app/models/reading.py` - `SensorReading` dataclass
- `tests/conftest.py` - Pytest fixtures (Flask test client, sample data)
- `pyproject.toml` - black, mypy, pytest, isort config
- `requirements.txt` - Flask, azure-data-tables, plotly, requests, python-dotenv
- `requirements-dev.txt` - pytest, black, mypy, isort, ruff

**Validation**:
```bash
pytest tests/ -v                                    # Tests pass
python -c "from app import create_app; create_app()" # App creates
mypy app/                                           # Type checks pass
```

---

### Phase 2: Storage Layer (Local First)

**Goal**: Create abstract storage interface and local CSV implementation.

**Work**:
- Define `StorageBase` abstract class with `write_reading()`, `get_readings()` methods
- Implement `LocalStorage` backed by CSV file
- Write comprehensive unit tests

**Files**:
- `app/storage/base.py` - Abstract base class
- `app/storage/local_storage.py` - CSV-backed implementation
- `tests/test_storage.py` - Storage interface tests

**Key Interface**:
```python
class StorageBase(ABC):
    @abstractmethod
    def write_reading(self, reading: SensorReading) -> None: ...
    
    @abstractmethod
    def get_readings(self, sensor_name: str, hours: int = 504) -> list[SensorReading]: ...
    
    @abstractmethod
    def get_all_readings(self, hours: int = 504) -> list[SensorReading]: ...
```

**Validation**:
```bash
pytest tests/test_storage.py -v
```

---

### Phase 3: Azure Table Storage Implementation

**Goal**: Implement Azure Table Storage backend.

**Work**:
- Implement `TableStorage` class using `azure-data-tables` SDK
- Use Azurite (local emulator) for testing
- Schema: `PartitionKey`=sensor_name, `RowKey`=reverse timestamp

**Files**:
- `app/storage/table_storage.py` - Azure implementation
- `tests/test_storage.py` - Add Azure-specific tests

**Table Schema**:
```
Table: sensorreadings
- PartitionKey: str  (e.g., "PuerHumidity-Temperature")
- RowKey: str        (e.g., "9999999999-2026-01-17T12:00:00" - reverse timestamp)
- value: float       (e.g., 65.5)
- timestamp: str     (ISO format original timestamp)
```

Reverse timestamp = `9999999999 - unix_timestamp` for efficient "most recent first" queries.

**Validation**:
```powershell
# Start Azurite emulator (PowerShell background job)
Start-Job -ScriptBlock { azurite --silent --location .azurite }

# Verify it's running (wait a few seconds first)
Start-Sleep -Seconds 3
netstat -an | Select-String "10002"  # Should show LISTENING

# Run tests
.\.venv\Scripts\pytest tests/test_storage.py -v
```

> **Note**: The tests use the well-known Azurite development credentials which are
> hard-coded and publicly documented (not a secret). Alternatively, run Azurite
> in a separate terminal window: `azurite --silent --location .azurite`

---

### Phase 4: Webhook Routes

**Goal**: Implement SmartThings lifecycle handlers.

**Work**:
- Implement `PING` handler (return challenge)
- Implement `CONFIRMATION` handler (fetch confirmation URL)
- Implement `INSTALL` handler (save tokens, placeholder for subscriptions)
- Implement `UPDATE` handler (re-create subscriptions)
- Implement `EVENT` handler (parse device events, write to storage)

**Files**:
- `app/routes/webhook.py` - Lifecycle handlers
- `tests/payloads/*.json` - Sample payloads
- `tests/test_webhook.py` - Unit tests

**Sample Payloads**:
```json
// tests/payloads/event_humidity.json
{
  "lifecycle": "EVENT",
  "eventData": {
    "events": [{
      "eventType": "DEVICE_EVENT",
      "deviceEvent": {
        "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
        "capability": "relativeHumidityMeasurement",
        "attribute": "humidity",
        "value": 65
      }
    }]
  }
}
```

**Validation**:
```bash
pytest tests/test_webhook.py -v
```

---

### Phase 5: SmartThings Service (Subscription Management)

**Goal**: Create SmartThings API client for subscription management.

**Work**:
- Create `SmartThingsClient` class
- Implement `create_subscriptions()` for humidity + temperature
- Implement `delete_all_subscriptions()`
- Implement `get_device_label()` for mapping device IDs to labels
- Mock external API calls in tests

**Files**:
- `app/services/smartthings.py` - API client
- `tests/test_smartthings.py` - Unit tests

**Subscription Creation**:
```python
def create_subscriptions(self, installed_app_id: str, location_id: str) -> None:
    url = f"{self.base_url}/installedapps/{installed_app_id}/subscriptions"
    
    for capability, attribute, name in [
        ("relativeHumidityMeasurement", "humidity", "humidity_sensors"),
        ("temperatureMeasurement", "temperature", "temperature_sensors"),
    ]:
        self._post(url, {
            "sourceType": "CAPABILITY",
            "capability": {
                "locationId": location_id,
                "capability": capability,
                "attribute": attribute,
                "stateChangeOnly": True,
                "subscriptionName": name,
                "value": "*"
            }
        })
```

**Validation**:
```bash
pytest tests/test_smartthings.py -v
```

---

### Phase 6: Chart Service

**Goal**: Port chart generation from Streamlit app.

**Work**:
- Implement `generate_chart()` returning Plotly HTML
- Port duration-weighted averaging logic
- Support display modes: Raw, Filtered, Both

**Files**:
- `app/services/chart.py` - Chart generation
- `app/services/data_transform.py` - Duration-weighted averaging
- `tests/test_chart.py` - Unit tests

**Reference**: See `archive/streamlit-v1/app.py` lines 536-650 for original logic.

**Validation**:
```bash
pytest tests/test_chart.py -v
```

---

### Phase 7: UI Routes

**Goal**: Implement web UI for charts and data import.

**Work**:
- Implement `/` route serving chart page
- Implement `/import` route with PAT form
- Create Jinja2 templates
- Add display mode selector (Raw/Filtered/Both)
- Add date range selector

**Files**:
- `app/routes/ui.py` - Chart page route
- `app/routes/import_data.py` - Import form + handler
- `app/templates/base.html` - Base template with styling
- `app/templates/chart.html` - Chart page
- `app/templates/import.html` - Import form
- `tests/test_ui.py` - Route tests

**Import Flow**:
1. User visits `/import`
2. Enters PAT token (not stored)
3. Form POSTs to `/import`
4. Server calls Activities API with PAT
5. Writes historical data to Table Storage
6. Redirects to `/` with success message

**Validation**:
```bash
pytest tests/test_ui.py -v
flask run --debug  # Manual verification
```

---

### Phase 8: Local End-to-End Test

**Goal**: Verify complete flow locally before Azure deployment.

**Work**:
- Run app with LocalStorage
- Simulate webhook calls
- Verify data appears in chart

**Validation**:
```bash
# Terminal 1: Run app
STORAGE_TYPE=local flask run --debug

# Terminal 2: Simulate events
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d @tests/payloads/event_humidity.json

# Verify chart
curl http://localhost:5000/ | grep "plotly"
```

---

### Phase 9: Deploy to Azure

**Goal**: Create Azure resources and deploy application.

**Work**:
- Create Resource Group: `rg-puerhumidity`
- Create Storage Account: `stpuerhumidity` (Standard LRS)
- Create App Service Plan: `asp-puerhumidity` (F1 Free)
- Create Web App: `app-puerhumidity` (Python 3.13)
- Configure app settings (connection strings)
- Deploy code via ZIP deploy

**Azure CLI Commands**:
```bash
# Create resources
az group create --name rg-puerhumidity --location eastus

az storage account create \
  --name stpuerhumidity \
  --resource-group rg-puerhumidity \
  --sku Standard_LRS

# Get storage connection string
az storage account show-connection-string \
  --name stpuerhumidity \
  --resource-group rg-puerhumidity \
  --query connectionString -o tsv

# Create Table in storage account
az storage table create \
  --name sensorreadings \
  --connection-string "<connection-string>"

az appservice plan create \
  --name asp-puerhumidity \
  --resource-group rg-puerhumidity \
  --sku F1 \
  --is-linux

az webapp create \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --plan asp-puerhumidity \
  --runtime "PYTHON:3.11"

# Configure settings
az webapp config appsettings set \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --settings \
    STORAGE_TYPE=azure \
    AZURE_STORAGE_CONNECTION_STRING="<connection-string>" \
    AZURE_TABLE_NAME=sensorreadings \
    DEVICE_LABELS='{"9a52da52-a841-4883-b91e-8d29b9a6d01d": "PuerHumidity", "baee9df0-5635-4205-8e58-7de7eb5d88d4": "ChestHumidity"}' \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

**Deployment**:

Option A: ZIP Deploy (simplest)
```powershell
# From project root, create deployment package
Compress-Archive -Path app, requirements.txt -DestinationPath deploy.zip -Force

# Deploy
az webapp deploy \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --src-path deploy.zip \
  --type zip
```

Option B: Git Deploy (for ongoing updates)
```bash
# Configure deployment source
az webapp deployment source config-local-git \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity

# Get deployment URL (will prompt for credentials)
az webapp deployment list-publishing-credentials \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --query scmUri -o tsv

# Add as git remote and push
git remote add azure <deployment-url>
git push azure main
```

**Understanding Oryx Build & Startup**:

When you deploy to Azure App Service (Linux), the **Oryx** build system handles your app:

1. **Build Phase**: Oryx detects `requirements.txt` and creates a virtualenv at `/home/site/wwwroot/antenv`
2. **Compression**: The built app is compressed into `output.tar.gz`
3. **Startup Phase**: On container start, Oryx extracts to `/tmp/<hash>/` and sets up `PYTHONPATH`
4. **Execution**: Your startup command runs with the extracted virtualenv

**Key Insight**: The virtualenv is at `antenv/` relative to the app root, NOT in `PATH`. You must
reference `antenv/bin/gunicorn` explicitly, or Oryx's generated startup script handles this for you.

**Gunicorn App Reference**:

Gunicorn expects a WSGI application object, not a factory function. Two approaches:

**Option A (Recommended)**: Export an `app` instance at module level:
```python
# In app/__init__.py
def create_app(config_name: str | None = None) -> Flask:
    ...
    return app

# Export for gunicorn - MUST be at module level
app = create_app()
```

Then use `app:app` in the startup command.

**Option B**: Use the factory pattern with parentheses:
```
gunicorn "app:create_app()"
```

⚠️ **Warning**: Option B fails on Azure due to shell quoting issues. The parentheses cause
`syntax error near unexpected token '('` when passed through Azure's startup command handling.

**Startup Configuration**:

Configure via CLI (using `app:app` pattern):
```bash
az webapp config set \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --startup-file "antenv/bin/gunicorn --bind=0.0.0.0 --timeout 600 app:app"
```

> **Note**: We use `antenv/bin/gunicorn` because the virtualenv bin directory is not in PATH.
> Oryx extracts the app to a temp directory and the startup command runs from there.

**F1 (Free) Tier Quotas**:

The F1 tier has strict quotas that can block deployments and restarts:

| Quota | Limit | Reset |
|-------|-------|-------|
| WPStopRequests | 15/hour | Top of each hour |
| CPU | 60 min/day | Daily at 00:00 UTC |

If you hit `WPStopRequests` quota during debugging, either:
- Wait for hourly reset
- Temporarily upgrade to B1 (~$0.02/hour): `az appservice plan update --name asp-puerhumidity --resource-group rg-puerhumidity --sku B1`
- Scale back down after: `az appservice plan update --name asp-puerhumidity --resource-group rg-puerhumidity --sku F1`

**Deployment Script**:

Use `scripts/deploy.ps1` for clean deployments (excludes `__pycache__`, tests, etc.):
```powershell
.\scripts\deploy.ps1
```

**Validation**:
```bash
# Health check
curl https://app-puerhumidity.azurewebsites.net/health

# Ping test
curl -X POST https://app-puerhumidity.azurewebsites.net/webhook \
  -H "Content-Type: application/json" \
  -d '{"lifecycle": "PING", "pingData": {"challenge": "test"}}'
```

**Troubleshooting**:

View deployment logs:
```bash
az webapp log deployment list --name app-puerhumidity --resource-group rg-puerhumidity -o table
```

View runtime logs (live tail):
```bash
az webapp log tail --name app-puerhumidity --resource-group rg-puerhumidity
```

Common errors:
- `Exit code 127` = Command not found. Use `antenv/bin/gunicorn` not just `gunicorn`
- `syntax error near unexpected token '('` = Shell quoting issue. Use `app:app` not `app:create_app()`
- `TypeError: create_app() takes 0 arguments but 2 were given` = Gunicorn passing WSGI args to factory. Export `app = create_app()` at module level

---

### Phase 10: SmartThings Integration

**Goal**: Connect SmartApp to Azure webhook.

**Work**:
- Update webhook URL in SmartThings Developer Workspace
- Uninstall existing SmartApp from SmartThings mobile app
- Reinstall to trigger INSTALL lifecycle + subscription creation
- Verify events flow through

**Critical: CONFIGURATION Lifecycle**:

SmartThings apps require a CONFIGURATION lifecycle handler. When a user adds your app:

1. **CONFIGURATION INITIALIZE** - SmartThings asks for app metadata
2. **CONFIGURATION PAGE** - SmartThings asks for UI pages to display
3. **INSTALL** - User confirms, app is installed
4. **EVENT** - Sensor data flows

Without a proper CONFIGURATION handler, the mobile app shows a blank screen.

**CONFIGURATION Handler Example**:
```python
elif lifecycle == "CONFIGURATION":
    phase = data.get("configurationData", {}).get("phase")
    
    if phase == "INITIALIZE":
        return jsonify({
            "configurationData": {
                "initialize": {
                    "id": "app",
                    "name": "PuerHumidity Monitor",
                    "description": "Monitors humidity and temperature",
                    "permissions": ["r:devices:*", "r:locations:*"],  # REQUIRED!
                    "firstPageId": "1"
                }
            }
        })
    
    elif phase == "PAGE":
        return jsonify({
            "configurationData": {
                "page": {
                    "pageId": "1",
                    "name": "Configuration",
                    "complete": True,
                    "nextPageId": None,
                    "previousPageId": None,
                    "sections": []
                }
            }
        })
```

**⚠️ Critical: Permissions Array**:

The `permissions` field in INITIALIZE **must not be empty**. Without permissions:
- CONFIGURATION INITIALIZE/PAGE work fine
- User clicks "Allow" in the mobile app
- **INSTALL lifecycle never fires** - the request hangs and fails

Required permissions for sensor monitoring:
```python
"permissions": ["r:devices:*", "r:locations:*"]
```

**Steps**:
1. Go to https://developer.smartthings.com/workspace/
2. Find app `4060b8f2-4ade-4c99-8e71-01306215b942`
3. Update Target URL to `https://app-puerhumidity.azurewebsites.net/webhook`
4. In SmartThings mobile app, remove installed app
5. Re-add the app (triggers CONFIGURATION → INSTALL)
6. Monitor Azure logs for subscription creation

**Validation**:
```bash
# Monitor logs
az webapp log tail --name app-puerhumidity --resource-group rg-puerhumidity

# Look for:
# - "INSTALL lifecycle received"
# - "Created subscription: humidity_sensors"
# - "Created subscription: temperature_sensors"

# Wait for device event (or trigger manually)
# Look for:
# - "EVENT lifecycle received"
# - "Wrote reading: PuerHumidity-Humidity = 65.0"
```

---

### Phase 11: Historical Data Import

**Goal**: Bootstrap with historical data from multiple sources.

**Work**:
- Create `/import` route with PAT form for SmartThings Activities API
- Implement pagination to fetch all available history
- Optimize storage with batch write operations
- Create `migrate_csv.py` script for local CSV import

**Activities API Import**:

The SmartThings Activities API returns device history with pagination:

```python
# Must use specific Accept header
ACTIVITIES_ACCEPT_HEADER = "application/vnd.smartthings+json;v=20180919"

# Follow pagination via _links.next.href
url = f"https://api.smartthings.com/activities?location={location_id}&limit=100"
while url:
    response = requests.get(url, headers=headers)
    data = response.json()
    items.extend(data.get("items", []))
    url = data.get("_links", {}).get("next", {}).get("href")
```

**Batch Write Optimization**:

Azure Table Storage supports batch transactions (up to 100 entities per batch, same PartitionKey):

```python
# Group readings by PartitionKey (sensor_name)
partitions = defaultdict(list)
for reading in readings:
    partitions[reading.sensor_name].append(reading)

# Batch within each partition
for partition_key, partition_readings in partitions.items():
    for batch in chunks(partition_readings, 100):
        operations = [("upsert", entity) for entity in batch]
        table_client.submit_transaction(operations)
```

This reduces 3,925 individual requests to ~40 batch transactions.

**CSV Migration Script**:

```powershell
# Set connection string inline and run
$env:AZURE_STORAGE_CONNECTION_STRING = (az storage account show-connection-string `
    --name stpuerhumidity --resource-group rg-puerhumidity --query connectionString -o tsv)
.\.\.venv\Scripts\python scripts\migrate_csv.py
```

**Duplicate Prevention**:

Both import methods use `upsert` semantics - same PartitionKey + RowKey overwrites existing entity. Since RowKey is derived from timestamp, duplicate timestamps merge cleanly.

**Validation**:
```bash
# Web-based import
https://app-puerhumidity.azurewebsites.net/import
# Enter PAT, submit
# Verify success message shows reading count

# CSV migration (local)
python scripts/migrate_csv.py
# Confirm with 'y'
```

**Results**:
- Activities API: 1,276 readings (limited to ~7 days of history)
- CSV migration: 3,925 readings (Jan 10-25 historical data)
- Total: 5,201 readings imported with batch optimization

---

### Phase 12: Secure Storage Credentials (Optional)

**Goal**: Rotate exposed storage account key and migrate to more secure authentication.

**Why**: The storage account key was exposed during initial setup. While app settings are 
encrypted, it's best practice to rotate keys and optionally migrate to keyless authentication.

**Step 1: Rotate Storage Account Key**
```bash
# Regenerate the exposed key
az storage account keys renew \
  --account-name stpuerhumidity \
  --resource-group rg-puerhumidity \
  --key key1

# Get the new connection string
az storage account show-connection-string \
  --name stpuerhumidity \
  --resource-group rg-puerhumidity \
  --query connectionString -o tsv

# Update the app setting with new connection string
az webapp config appsettings set \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --settings AZURE_STORAGE_CONNECTION_STRING="<new-connection-string>"
```

**Step 2 (Option A): Use Azure Key Vault**
```bash
# Create Key Vault
az keyvault create \
  --name kv-puerhumidity \
  --resource-group rg-puerhumidity \
  --location centralus

# Store the connection string as a secret
az keyvault secret set \
  --vault-name kv-puerhumidity \
  --name StorageConnectionString \
  --value "<connection-string>"

# Enable managed identity on the web app
az webapp identity assign \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity

# Grant the web app access to Key Vault secrets
az keyvault set-policy \
  --name kv-puerhumidity \
  --object-id <principal-id-from-above> \
  --secret-permissions get list

# Update app setting to reference Key Vault
az webapp config appsettings set \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --settings AZURE_STORAGE_CONNECTION_STRING="@Microsoft.KeyVault(VaultName=kv-puerhumidity;SecretName=StorageConnectionString)"
```

**Step 2 (Option B): Use Managed Identity (No Keys)**

This is the most secure option - no secrets to manage at all.

```bash
# Enable managed identity on the web app
az webapp identity assign \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity

# Get the principal ID
az webapp identity show \
  --name app-puerhumidity \
  --resource-group rg-puerhumidity \
  --query principalId -o tsv

# Grant Storage Table Data Contributor role
az role assignment create \
  --assignee <principal-id> \
  --role "Storage Table Data Contributor" \
  --scope /subscriptions/<subscription-id>/resourceGroups/rg-puerhumidity/providers/Microsoft.Storage/storageAccounts/stpuerhumidity
```

Then update the code to use `DefaultAzureCredential`:
```python
# In app/storage/table_storage.py
from azure.identity import DefaultAzureCredential

# Instead of connection string:
credential = DefaultAzureCredential()
table_service = TableServiceClient(
    endpoint="https://stpuerhumidity.table.core.windows.net",
    credential=credential
)
```

**Validation**:
```bash
# Verify app still works after credential change
curl https://app-puerhumidity.azurewebsites.net/health

# Check logs for any authentication errors
az webapp log tail --name app-puerhumidity --resource-group rg-puerhumidity
```

---

## Code Quality Standards

| Aspect | Tool | Configuration |
|--------|------|---------------|
| Type hints | mypy | `--strict` mode |
| Formatting | black | Line length 100 |
| Import sorting | isort | black-compatible |
| Linting | ruff | Default rules |
| Testing | pytest | Coverage > 80% on services |
| Docstrings | - | Google style |

**pyproject.toml**:
```toml
[tool.black]
line-length = 100

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

---

## Key Technical Details

### SmartThings EVENT Payload Structure

```json
{
  "lifecycle": "EVENT",
  "eventData": {
    "authToken": "...",
    "installedApp": {
      "installedAppId": "55713660-1f57-4338-81e0-3c45479b2279",
      "locationId": "9ec8c9fc-3af2-464f-b917-d0403ab0c4bb"
    },
    "events": [{
      "eventType": "DEVICE_EVENT",
      "deviceEvent": {
        "subscriptionName": "humidity_sensors",
        "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
        "componentId": "main",
        "capability": "relativeHumidityMeasurement",
        "attribute": "humidity",
        "value": 65,
        "stateChange": true
      }
    }]
  }
}
```

### Duration-Weighted Averaging

Algorithm from original app (for Filtered display mode):
1. Create 10-minute time slots over the display period
2. For each slot, find readings within ±window_hours
3. Weight each reading by its duration (time until next reading)
4. Calculate weighted average

Reference: `archive/streamlit-v1/app.py` function `duration_weighted_average()`

### Azure Table Storage Query Pattern

```python
# Query last N hours for a sensor
from datetime import datetime, timedelta

cutoff = datetime.utcnow() - timedelta(hours=hours)
cutoff_rowkey = f"{9999999999 - int(cutoff.timestamp())}"

# RowKey < cutoff_rowkey means timestamp > cutoff (due to reverse)
filter_query = f"PartitionKey eq '{sensor_name}' and RowKey lt '{cutoff_rowkey}'"
```

---

## Azure Resources Summary

| Resource | Name | SKU | Est. Cost |
|----------|------|-----|-----------|
| Resource Group | rg-puerhumidity | - | Free |
| Storage Account | stpuerhumidity | Standard LRS | ~$0.01/mo |
| App Service Plan | asp-puerhumidity | F1 (Free) | Free |
| Web App | app-puerhumidity | Python 3.11 | Free |

---

## Current Progress

- [x] Phase 0: Archive current implementation ✅
- [x] Phase 1: Project scaffolding & models ✅
- [x] Phase 2: Storage layer (local) ✅
- [x] Phase 3: Azure Table Storage ✅
- [x] Phase 4: Webhook routes ✅
- [x] Phase 5: SmartThings service ✅
- [x] Phase 6: Chart service ✅
- [x] Phase 7: UI routes ✅
- [x] Phase 8: Local E2E test ✅
- [x] Phase 9: Deploy to Azure ✅
- [x] Phase 10: SmartThings integration ✅
- [x] Phase 11: Historical data import ✅
- [ ] Phase 12: Secure storage credentials (optional)

---

## Resume Instructions

If starting fresh after a break:

1. Read this document (`docs/plan.md`)
2. Check "Current Progress" section above for last completed phase
3. Review code in the relevant phase's files
4. Run validation commands for the last completed phase
5. Continue with next phase

Key files to understand current state:
- `docs/plan.md` - This plan
- `app/__init__.py` - App factory (if exists)
- `tests/` - What's tested = what's implemented
- `archive/streamlit-v1/` - Original implementation for reference
