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
```bash
# Start Azurite emulator
azurite --silent --location .azurite &

# Run tests
STORAGE_TYPE=azure AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true" \
  pytest tests/test_storage.py -v
```

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
- Create Web App: `app-puerhumidity` (Python 3.11)
- Configure app settings (connection strings)
- Deploy via ZIP or GitHub Actions

**Azure CLI Commands**:
```bash
# Create resources
az group create --name rg-puerhumidity --location eastus

az storage account create \
  --name stpuerhumidity \
  --resource-group rg-puerhumidity \
  --sku Standard_LRS

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
    DEVICE_LABELS='{"9a52da52-...": "PuerHumidity", "baee9df0-...": "ChestHumidity"}'
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

---

### Phase 10: SmartThings Integration

**Goal**: Connect SmartApp to Azure webhook.

**Work**:
- Update webhook URL in SmartThings Developer Workspace
- Uninstall existing SmartApp from SmartThings mobile app
- Reinstall to trigger INSTALL lifecycle + subscription creation
- Verify events flow through

**Steps**:
1. Go to https://developer.smartthings.com
2. Find app `4060b8f2-4ade-4c99-8e71-01306215b942`
3. Update Target URL to `https://app-puerhumidity.azurewebsites.net/webhook`
4. In SmartThings mobile app, remove installed app
5. Re-add the app (triggers INSTALL)
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

**Goal**: Bootstrap with historical data.

**Work**:
- Generate fresh PAT at https://account.smartthings.com/tokens
- Use import form to load Activities API data
- Verify chart shows historical + real-time data

**Validation**:
```bash
# Open browser
https://app-puerhumidity.azurewebsites.net/import

# Enter PAT, submit
# Verify success message
# Check chart shows data going back
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
- [ ] Phase 1: Project scaffolding & models
- [ ] Phase 2: Storage layer (local)
- [ ] Phase 3: Azure Table Storage
- [ ] Phase 4: Webhook routes
- [ ] Phase 5: SmartThings service
- [ ] Phase 6: Chart service
- [ ] Phase 7: UI routes
- [ ] Phase 8: Local E2E test
- [ ] Phase 9: Deploy to Azure
- [ ] Phase 10: SmartThings integration
- [ ] Phase 11: Historical data import

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
