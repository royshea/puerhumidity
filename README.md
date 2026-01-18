# SmartThings Humidity & Temperature Monitor

A minimal Python application for monitoring and visualizing humidity and temperature data from SmartThings sensors.

## Overview

This application connects to the SmartThings API to capture sensor readings from two devices, stores them in a CSV file for historical tracking, and provides an interactive time-series visualization using Streamlit and Plotly.

## Features

- **Real-time Data Collection**: Fetch current temperature and humidity readings from SmartThings devices
- **Historical Data Import**: Import past readings from SmartThings Activities API (backfills data from recent days/weeks)
- **Persistent Storage**: All readings are stored in a CSV file for long-term tracking
- **Interactive Visualization**: Dual-axis chart with temperature (°F) and humidity (%) plotted over time
- **Statistics Dashboard**: View total readings, last update time, and average values
- **21-Day Data Window**: Automatically filters display to the most recent 21 days

## Technology Stack

- **Python 3.13+**
- **Streamlit**: Web UI framework
- **Pandas**: Data manipulation and CSV handling
- **Plotly**: Interactive charting
- **SmartThings REST API**: Device data source

## Prerequisites

- Python 3.13 or higher
- SmartThings account with configured temperature/humidity sensors
- SmartThings OAuth 2.0 credentials (recommended) or Personal Access Token

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd puerHumidity
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
SMARTTHINGS_TOKEN=your-token-here

DEVICE_1_ID=device-uuid-1
DEVICE_1_LABEL=DeviceName1
DEVICE_2_ID=device-uuid-2
DEVICE_2_LABEL=DeviceName2
```

1. Go to https://account.smartthings.com/tokens
2. Create a new token with at least `r:devices:*` permission
3. Copy the token to your `.env` file

#### Finding Your Device IDs

Run the discovery script:

```bash
python discover_devices.py
```

This will list all your SmartThings devices with temperature/humidity capabilities. Copy the device IDs and labels to your `.env` file.

## Running the Application

```bash
streamlit run app.py
```

The application will open in your browser at http://localhost:8501

## Usage

### Fetch New Data
Click the **"🔄 Fetch New Data"** button to pull current temperature and humidity readings from your devices and append them to the CSV.

### Import Historical Data
Click the **"📥 Import History"** button to import historical readings from the SmartThings Activities API. This retrieves past events and automatically:
- Fetches multiple pages of historical activities
- Filters for your configured devices
- Removes duplicates
- Merges with existing CSV data

> **Note**: The Activities API typically stores several days to weeks of historical data depending on SmartThings retention policies.

## Project Structure

```
puerHumidity/
├── app.py                      # Main Streamlit application
├── webhook_handler.py          # SmartThings webhook server for app registration
├── discover_devices.py         # Device discovery utility
├── test_activities.py          # Activities API testing script
├── requirements.txt            # Python dependencies
├── .env                        # Configuration (not in git)
├── .env.example               # Configuration template
├── .gitignore                 # Git ignore rules
├── data/
│   ├── humidity_data.csv      # Historical readings (CSV format)
│   └── .smartapp_tokens.json  # SmartApp tokens (after installation)
└── README.md                  # This file
```

## Registering as a SmartThings SmartApp

If you want to register this as a SmartApp (for OAuth tokens that don't expire), follow these steps:

### 1. Start the Webhook Handler

```bash
# Terminal 1: Start the webhook server
python webhook_handler.py
```

### 2. Create a Tunnel with LocalTunnel

```bash
# Terminal 2: Expose the webhook server
lt --port 8501 -s lovely-candies-dream

```

Copy the HTTPS URL provided (e.g., `https://random-name.loca.lt`)

### 3. Register in SmartThings Developer Workspace

1. Go to https://developer.smartthings.com/workspace/projects
2. Create a new **Automation** project
3. Click **"Register App"**
4. Enter your LocalTunnel URL as the **Target URL**
5. SmartThings will send a CONFIRMATION request to your webhook
6. The webhook handler will automatically confirm it

### 4. Deploy and Install

1. Click **"Deploy to Test"** in the Developer Workspace
2. Open the SmartThings mobile app
3. Go to **Menu → SmartApps → + → My SmartApps**
4. Install your app - this will trigger the INSTALL lifecycle
5. Tokens will be saved to `data/.smartapp_tokens.json`

## CSV Data Schema

The application stores data with the following structure:

| Column       | Type     | Description                                    |
|-------------|----------|------------------------------------------------|
| sensor_name | string   | Device label + sensor type (e.g., "Device1-Temperature") |
| datetime    | datetime | Timestamp of the reading (ISO 8601 format)    |
| value       | float    | Sensor value (°F for temperature, % for humidity) |

## SmartThings API Endpoints Used

- **GET /v1/devices/{deviceId}**: Retrieve device details and location ID
- **GET /v1/devices/{deviceId}/status**: Fetch current device status
- **GET /activities?location={locationId}**: Retrieve historical device activities

## Data Retention

- **Display**: Last 21 days of data are shown in charts and statistics
- **Storage**: All historical data remains in the CSV file
- **Filtering**: Automatic filtering is applied only at load time for visualization

## Automated Data Collection

For continuous monitoring, consider setting up automated polling:

### Windows Task Scheduler
Schedule a task to run `streamlit run app.py` or create a script that calls the fetch functions periodically.

### Cron (Linux/Mac)
```bash
*/15 * * * * cd /path/to/puerHumidity && .venv/bin/python -c "from app import *; fetch_and_append()"
```

## Troubleshooting

**No data appears after import**: Check that your SmartThings token has the correct permissions and that your device IDs are correct.

**Activities API returns 401**: Verify your SmartThings token is valid and hasn't expired.

**OAuth login fails**: Ensure your redirect URI matches exactly what's configured in the SmartThings Developer Workspace. The default is `http://localhost:8501`.

**Token refresh fails**: Delete `data/.tokens.json` and re-authenticate. If the issue persists, verify your OAuth client is still active in the Developer Workspace.

**"No valid access token" error**: Either authenticate via OAuth (click "Login with SmartThings") or add a valid SMARTTHINGS_TOKEN to your .env file.

**Chart not displaying**: Ensure you have at least one reading in the CSV file. Click "Fetch New Data" or "Import History".

## Using LocalTunnel for HTTPS Testing

SmartThings OAuth registration may require an HTTPS redirect URI. You can use [LocalTunnel](https://theboroer.github.io/localtunnel-www/) to create a secure tunnel to your local development server.

### Setup LocalTunnel

1. Install LocalTunnel globally:
   ```bash
   npm install -g localtunnel
   ```

2. Start your Streamlit app:
   ```bash
   streamlit run app.py
   ```

3. In a separate terminal, create a tunnel:
   ```bash
   lt --port 8501
   ```

4. LocalTunnel will provide a public HTTPS URL like:
   ```
   https://random-name.loca.lt
   ```

### Configure OAuth with LocalTunnel URL

1. Go to [SmartThings Developer Workspace](https://developer.smartthings.com/workspace/projects)
2. Set your **Redirect URI** to the LocalTunnel URL (e.g., `https://random-name.loca.lt`)
3. Update your `.env` file:
   ```env
   SMARTTHINGS_REDIRECT_URI=https://random-name.loca.lt
   ```

### Important Notes

- LocalTunnel URLs are temporary and change each time you restart the tunnel
- For a consistent subdomain, use: `lt --port 8501 --subdomain myapp`
- When accessing through LocalTunnel, you may need to click through a reminder page on first visit
- For production use, consider a proper HTTPS hosting solution

## License

This project is provided as-is for personal use.

## Contributing

This is a minimal implementation designed for specific use cases. Feel free to fork and adapt to your needs.
