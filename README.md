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
│   ├── routes/                  # Flask blueprints (webhook, UI, health)
│   ├── services/                # Business logic (chart, data transform)
│   ├── storage/                 # Storage backends (local CSV, Azure Table)
│   └── templates/               # Jinja2 HTML templates
├── tests/                       # Pytest test suite
├── scripts/
│   └── seed_data.py            # Seed local storage from historical CSV
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
| `/health` | GET | Health check |

### SmartThings Lifecycle Events

The webhook handler processes these event types:

- **PING**: Responds with challenge for app verification
- **CONFIRMATION**: Confirms webhook URL registration
- **INSTALL/UPDATE**: Creates device subscriptions
- **EVENT**: Processes sensor readings (temperature/humidity)
- **UNINSTALL**: Cleanup when app is removed

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

1. Azure account with Web App and Storage Account
2. Azure CLI installed and logged in

### Deploy Steps

1. Create Azure Table Storage and get connection string
2. Create Azure Web App (Free tier works)
3. Configure environment variables in Azure
4. Deploy code via Git, ZIP, or GitHub Actions

### Environment Variables (Azure)

```
STORAGE_TYPE=azure
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_TABLE_NAME=sensorreadings
SECRET_KEY=<generate-secure-key>
```

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
