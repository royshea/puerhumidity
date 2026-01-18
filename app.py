#!/usr/bin/env python3
"""
SmartThings Humidity & Temperature Monitor
Fetches data from two SmartThings sensors and visualizes trends
"""

import os
import json
import secrets
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from urllib.parse import urlencode

# Load environment variables
load_dotenv()

# API Configuration
API_BASE = "https://api.smartthings.com/v1"
CSV_FILE = "data/humidity_data.csv"
TOKEN_FILE = "data/.tokens.json"  # Encrypted token storage
LOCATION_ID = None  # Will be fetched from device

# OAuth Configuration
OAUTH_CLIENT_ID = os.getenv("SMARTTHINGS_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("SMARTTHINGS_CLIENT_SECRET")
OAUTH_REDIRECT_URI = os.getenv("SMARTTHINGS_REDIRECT_URI", "http://localhost:8501")
OAUTH_AUTH_URL = "https://api.smartthings.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.smartthings.com/oauth/token"
OAUTH_SCOPES = "r:devices:* l:devices r:locations:* l:locations"

# Legacy PAT support (for development/fallback)
LEGACY_PAT = os.getenv("SMARTTHINGS_TOKEN")

# Device configuration
DEVICES = [
    {
        "id": os.getenv("DEVICE_1_ID"),
        "label": os.getenv("DEVICE_1_LABEL", "Device 1")
    },
    {
        "id": os.getenv("DEVICE_2_ID"),
        "label": os.getenv("DEVICE_2_LABEL", "Device 2")
    }
]


# =============================================================================
# OAuth and Token Management
# =============================================================================

def is_oauth_configured():
    """Check if OAuth credentials are configured"""
    return bool(OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)


def build_auth_url():
    """Build the SmartThings OAuth authorization URL"""
    # Generate and store CSRF state token
    state = secrets.token_urlsafe(32)
    st.session_state["oauth_state"] = state
    
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPES,
        "state": state
    }
    return f"{OAUTH_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(authorization_code):
    """Exchange authorization code for access and refresh tokens"""
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "redirect_uri": OAUTH_REDIRECT_URI
    }
    
    response = requests.post(OAUTH_TOKEN_URL, data=data, timeout=10)
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token):
    """Use refresh token to get new access token"""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET
    }
    
    response = requests.post(OAUTH_TOKEN_URL, data=data, timeout=10)
    response.raise_for_status()
    return response.json()


def save_tokens(token_data):
    """Save tokens to session state and persistent storage"""
    # Calculate expiry time
    expires_in = token_data.get("expires_in", 86400)  # Default 24 hours
    expiry_time = datetime.now() + timedelta(seconds=expires_in)
    
    # Store in session state
    st.session_state["access_token"] = token_data["access_token"]
    st.session_state["refresh_token"] = token_data.get("refresh_token")
    st.session_state["token_expiry"] = expiry_time.isoformat()
    
    # Persist to file (for app restarts)
    try:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump({
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "token_expiry": expiry_time.isoformat()
            }, f)
    except Exception as e:
        st.warning(f"Could not persist tokens: {e}")


# SmartApp tokens file (from webhook registration)
SMARTAPP_TOKEN_FILE = os.path.join("data", ".smartapp_tokens.json")


def load_tokens():
    """Load tokens from persistent storage into session state"""
    if "access_token" in st.session_state:
        return True
    
    # Try OAuth token file first
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                st.session_state["access_token"] = data["access_token"]
                st.session_state["refresh_token"] = data.get("refresh_token")
                st.session_state["token_expiry"] = data.get("token_expiry")
                return True
    except Exception:
        pass
    
    # Try SmartApp tokens file (from webhook registration)
    try:
        if os.path.exists(SMARTAPP_TOKEN_FILE):
            with open(SMARTAPP_TOKEN_FILE, "r") as f:
                data = json.load(f)
                if "authToken" in data:
                    st.session_state["access_token"] = data["authToken"]
                    st.session_state["refresh_token"] = data.get("refreshToken")
                    st.session_state["installed_app_id"] = data.get("installedAppId")
                    # SmartApp tokens don't have expiry in the same format
                    return True
    except Exception:
        pass
    
    return False


def clear_tokens():
    """Clear all stored tokens (logout)"""
    for key in ["access_token", "refresh_token", "token_expiry", "oauth_state"]:
        if key in st.session_state:
            del st.session_state[key]
    
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass


def get_access_token():
    """Get a valid access token, refreshing if necessary"""
    # First, try to load from session/storage (OAuth or SmartApp tokens)
    load_tokens()
    
    # If we already have an access token loaded (from SmartApp or OAuth), use it
    if "access_token" in st.session_state:
        # Check if token is expired (with 5 min buffer) - only applies to OAuth tokens
        if "token_expiry" in st.session_state:
            try:
                expiry = datetime.fromisoformat(st.session_state["token_expiry"])
                if datetime.now() >= expiry - timedelta(minutes=5):
                    # Try to refresh
                    if st.session_state.get("refresh_token") and is_oauth_configured():
                        try:
                            token_data = refresh_access_token(st.session_state["refresh_token"])
                            save_tokens(token_data)
                        except Exception as e:
                            st.error(f"Token refresh failed: {e}. Please log in again.")
                            clear_tokens()
                            return None
                    else:
                        # No refresh token or not OAuth, need to re-authenticate
                        clear_tokens()
                        return None
            except Exception:
                pass
        
        return st.session_state.get("access_token")
    
    # Fallback to legacy PAT (for development/fallback)
    if LEGACY_PAT:
        return LEGACY_PAT
    
    return None


def handle_oauth_callback():
    """Handle OAuth callback from SmartThings"""
    params = st.query_params
    
    if "code" in params and "state" in params:
        code = params["code"]
        state = params["state"]
        
        # Verify CSRF state
        expected_state = st.session_state.get("oauth_state")
        if expected_state and state != expected_state:
            st.error("OAuth state mismatch. Please try logging in again.")
            st.query_params.clear()
            return False
        
        try:
            # Exchange code for tokens
            token_data = exchange_code_for_token(code)
            save_tokens(token_data)
            
            # Clear query params and OAuth state
            if "oauth_state" in st.session_state:
                del st.session_state["oauth_state"]
            st.query_params.clear()
            
            st.success("Successfully connected to SmartThings!")
            st.rerun()
            return True
            
        except Exception as e:
            st.error(f"OAuth token exchange failed: {e}")
            st.query_params.clear()
            return False
    
    # Check for OAuth error
    if "error" in params:
        error = params.get("error", "Unknown error")
        error_description = params.get("error_description", "")
        st.error(f"OAuth error: {error}. {error_description}")
        st.query_params.clear()
        return False
    
    return None  # No OAuth callback in progress

# Page configuration
st.set_page_config(
    page_title="SmartThings Humidity Monitor",
    page_icon="🌡️",
    layout="wide"
)

st.title("🌡️ Humidity & Temperature Monitor")
st.caption("Real-time tracking of SmartThings sensors")

# Handle OAuth callback
handle_oauth_callback()

# Authentication UI
if not get_access_token():
    st.warning("⚠️ Not authenticated with SmartThings")
    
    if is_oauth_configured():
        auth_url = build_auth_url()
        if auth_url:
            st.markdown(f"[🔑 Login with SmartThings]({auth_url})")
            st.info("Click the link above to authenticate with your SmartThings account.")
    elif LEGACY_PAT:
        st.info("Using legacy Personal Access Token for authentication.")
    else:
        st.error("No authentication configured. Please set OAuth credentials or SMARTTHINGS_TOKEN in .env")
        st.stop()
else:
    # Show logout option in expander
    with st.expander("🔐 Authentication", expanded=False):
        if is_oauth_configured() and "access_token" in st.session_state:
            if st.button("🚪 Logout"):
                clear_tokens()
                st.rerun()
            # Show token expiry if available
            if "token_expiry" in st.session_state:
                expiry = st.session_state["token_expiry"]
                if isinstance(expiry, str):
                    expiry = datetime.fromisoformat(expiry)
                st.caption(f"Token expires: {expiry.strftime('%Y-%m-%d %H:%M')}")
        elif LEGACY_PAT:
            st.caption("Using legacy Personal Access Token")


def get_location_id():
    """Get location ID from the first configured device"""
    global LOCATION_ID
    if LOCATION_ID:
        return LOCATION_ID

    token = get_access_token()
    if not token:
        st.error("No valid access token available. Please authenticate.")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    device_id = DEVICES[0]["id"]
    response = requests.get(
        f"{API_BASE}/devices/{device_id}",
        headers=headers,
        timeout=10
    )
    response.raise_for_status()
    LOCATION_ID = response.json().get("locationId")
    return LOCATION_ID


def fetch_device_status(device_id):
    """Fetch current status from a SmartThings device"""
    token = get_access_token()
    if not token:
        raise ValueError("No valid access token available")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            f"{API_BASE}/devices/{device_id}/status",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch device {device_id}: {str(e)}")


def extract_sensor_values(status_data, device_label):
    """Extract temperature and humidity values from device status"""
    readings = []

    try:
        components = status_data.get("components", {})
        main_component = components.get("main", {})

        # Extract temperature
        temp_data = main_component.get("temperatureMeasurement", {})
        if "temperature" in temp_data:
            temp_value = temp_data["temperature"].get("value")
            if temp_value is not None:
                readings.append({
                    "sensor_name": f"{device_label}-Temperature",
                    "value": float(temp_value)
                })

        # Extract humidity
        humidity_data = main_component.get("relativeHumidityMeasurement", {})
        if "humidity" in humidity_data:
            humidity_value = humidity_data["humidity"].get("value")
            if humidity_value is not None:
                readings.append({
                    "sensor_name": f"{device_label}-Humidity",
                    "value": float(humidity_value)
                })

    except Exception as e:
        st.warning(f"Error parsing data from {device_label}: {str(e)}")

    return readings


def append_to_csv(readings):
    """Append new readings to CSV file"""
    timestamp = datetime.now()

    # Prepare new rows
    new_rows = []
    for reading in readings:
        new_rows.append({
            "sensor_name": reading["sensor_name"],
            "datetime": timestamp,
            "value": reading["value"]
        })

    new_df = pd.DataFrame(new_rows)

    # Append to CSV
    if os.path.exists(CSV_FILE):
        new_df.to_csv(CSV_FILE, mode='a', header=False, index=False, lineterminator='\n')
    else:
        new_df.to_csv(CSV_FILE, index=False, lineterminator='\n')

    return len(new_rows)


def fetch_historical_activities(max_pages=50, since=None):
    """Fetch historical device activities from SmartThings
    
    Args:
        max_pages: Maximum number of pages to fetch
        since: Optional datetime - only return activities after this time
        
    Note: The Activities API is not available with SmartApp tokens.
    It only works with Personal Access Tokens (PATs).
    """
    location_id = get_location_id()
    if not location_id:
        return []

    token = get_access_token()
    if not token:
        st.error("No valid access token available. Please authenticate.")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.smartthings+json;v=20180919"
    }

    all_readings = []
    url = f"https://api.smartthings.com/activities?location={location_id}"
    pages_fetched = 0
    stop_fetching = False

    while url and pages_fetched < max_pages and not stop_fetching:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            # Handle 403 Forbidden - Activities API not available with SmartApp tokens
            if response.status_code == 403:
                st.warning(
                    "⚠️ The Activities API is not available with SmartApp tokens. "
                    "Historical data import requires a Personal Access Token (PAT). "
                    "Real-time device polling still works normally."
                )
                return []
            
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            st.error(f"Error fetching activities: {e}")
            return []

        # Process activities
        for item in data.get("items", []):
            if item.get("activityType") == "DEVICE":
                device_activity = item.get("deviceActivity", {})
                device_id = device_activity.get("deviceId")

                # Only process our configured devices
                device_label = None
                for device in DEVICES:
                    if device["id"] == device_id:
                        device_label = device["label"]
                        break

                if not device_label:
                    continue

                # Extract sensor type and value
                capability = device_activity.get("capability")
                attribute_value = device_activity.get("attributeValue")
                timestamp = item.get("timestamp")
                activity_time = pd.to_datetime(timestamp).tz_localize(None)

                # Check if we've gone past the cutoff time
                if since is not None and activity_time < since:
                    stop_fetching = True
                    break

                if capability == "temperatureMeasurement" and attribute_value:
                    all_readings.append({
                        "sensor_name": f"{device_label}-Temperature",
                        "datetime": activity_time,
                        "value": float(attribute_value)
                    })
                elif capability == "relativeHumidityMeasurement" and attribute_value:
                    all_readings.append({
                        "sensor_name": f"{device_label}-Humidity",
                        "datetime": activity_time,
                        "value": float(attribute_value)
                    })

        # Check for next page
        pages_fetched += 1
        links = data.get("_links", {})
        next_link = links.get("next", {})
        url = next_link.get("href") if next_link else None

    return all_readings


def import_historical_data():
    """Import historical activities and merge with existing CSV
    
    Only fetches data newer than 1 hour before the most recent existing reading,
    avoiding re-fetching all historical data on each import.
    """
    # Calculate cutoff time from existing data
    since = None
    if os.path.exists(CSV_FILE):
        existing_df = pd.read_csv(CSV_FILE, parse_dates=["datetime"])
        if not existing_df.empty:
            max_time = existing_df["datetime"].max()
            # Go back 1 hour to handle any data that might have been missed
            since = max_time - pd.Timedelta(hours=1)

    # Fetch historical activities (only newer than cutoff if we have existing data)
    activities = fetch_historical_activities(since=since)

    if not activities:
        return 0, 0

    # Convert to DataFrame
    new_df = pd.DataFrame(activities)

    # Load existing data and merge
    if os.path.exists(CSV_FILE):
        existing_df = pd.read_csv(CSV_FILE, parse_dates=["datetime"])

        # Combine and remove duplicates (based on sensor_name and datetime)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=["sensor_name", "datetime"], keep="first")
        combined_df = combined_df.sort_values("datetime")
    else:
        combined_df = new_df.sort_values("datetime")

    # Save to CSV with proper line terminators
    combined_df.to_csv(CSV_FILE, index=False, lineterminator='\n')

    return len(activities), len(combined_df)

# This is a very naive implementation.  Not something you'd want to take
# to a production setting.
def duration_weighted_average(sensor_df, target_time, window_hours):
    """Calculate duration-weighted average for a specific time point"""
    window_delta = pd.Timedelta(hours=window_hours)
    start_time = target_time - window_delta
    end_time = target_time + window_delta

    # Get readings within the window
    window_data = sensor_df[
        (sensor_df["datetime"] >= start_time) &
        (sensor_df["datetime"] <= end_time)
    ].sort_values("datetime").copy()

    if len(window_data) == 0:
        return np.nan

    if len(window_data) == 1:
        return window_data.iloc[0]["value"]

    # Calculate duration weights
    weights = []
    values = []

    for i in range(len(window_data)):
        current_time = window_data.iloc[i]["datetime"]
        current_value = window_data.iloc[i]["value"]

        # Duration is time until next reading (or end of window)
        if i < len(window_data) - 1:
            next_time = window_data.iloc[i + 1]["datetime"]
            duration = (next_time - current_time).total_seconds()
        else:
            duration = (end_time - current_time).total_seconds()

        # Also consider time since previous reading (or start of window)
        if i > 0:
            prev_time = window_data.iloc[i - 1]["datetime"]
            prev_duration = (current_time - prev_time).total_seconds()
            duration = (duration + prev_duration) / 2

        weights.append(duration)
        values.append(current_value)

    # Calculate weighted average
    weights = np.array(weights)
    values = np.array(values)

    if weights.sum() == 0:
        return np.mean(values)

    return np.average(values, weights=weights)


def transform_to_timeseries(df, resolution_minutes=10):
    """Transform data to regular 10-minute intervals with duration-weighted averaging"""
    if df.empty:
        return pd.DataFrame(columns=["sensor_name", "datetime", "value"])

    # Get time range
    min_time = df["datetime"].min()
    max_time = df["datetime"].max()

    # Create 10-minute intervals aligned on the hour
    start_time = min_time.floor(f"{resolution_minutes}min")
    end_time = max_time.ceil(f"{resolution_minutes}min")
    time_slots = pd.date_range(start=start_time, end=end_time, freq=f"{resolution_minutes}min")

    transformed_data = []

    # Process each sensor separately
    for sensor_name in df["sensor_name"].unique():
        sensor_df = df[df["sensor_name"] == sensor_name].sort_values("datetime")

        # Determine window size based on sensor type
        if "Temperature" in sensor_name:
            window_hours = 1.0  # 1 hour on either side
        else:  # Humidity
            window_hours = 2.0  # 2 hours on either side

        # Calculate weighted average for each time slot
        for target_time in time_slots:
            avg_value = duration_weighted_average(sensor_df, target_time, window_hours)

            if not np.isnan(avg_value):
                transformed_data.append({
                    "sensor_name": sensor_name,
                    "datetime": target_time,
                    "value": avg_value
                })

    return pd.DataFrame(transformed_data)


def load_data():
    """Load historical data from CSV (last 21 days max)"""
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=["sensor_name", "datetime", "value"])

    try:
        df = pd.read_csv(CSV_FILE, parse_dates=["datetime"])

        # Ensure required columns exist
        required_columns = ["sensor_name", "datetime", "value"]
        if not all(col in df.columns for col in required_columns):
            st.error(f"CSV file is malformed. Expected columns: {required_columns}. Found: {list(df.columns)}")
            return pd.DataFrame(columns=required_columns)

        # Filter to last 21 days
        if not df.empty:
            cutoff_date = datetime.now() - pd.Timedelta(days=21)
            df = df[df["datetime"] >= cutoff_date]

        return df
    except Exception as e:
        st.error(f"Error loading CSV file: {str(e)}")
        return pd.DataFrame(columns=["sensor_name", "datetime", "value"])


def create_dual_axis_chart(raw_df, filtered_df, display_mode):
    """Create a chart with dual y-axes for temperature and humidity"""
    # Determine which data to display
    show_raw = display_mode in ["Raw Data", "Both"]
    show_filtered = display_mode in ["Filtered Data", "Both"]

    if raw_df.empty and filtered_df.empty:
        st.info("No data available yet. Click 'Fetch New Data' to start collecting readings.")
        return

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Color scheme
    colors = {
        "Temperature": {"raw": "rgba(255, 99, 71, 0.4)", "filtered": "rgb(255, 99, 71)"},
        "Humidity": {"raw": "rgba(54, 162, 235, 0.4)", "filtered": "rgb(54, 162, 235)"}
    }

    # Add raw data traces
    if show_raw and not raw_df.empty:
        sensors = raw_df["sensor_name"].unique()
        for sensor in sensors:
            sensor_data = raw_df[raw_df["sensor_name"] == sensor].sort_values("datetime")

            if "Temperature" in sensor:
                fig.add_trace(
                    go.Scatter(
                        x=sensor_data["datetime"],
                        y=sensor_data["value"],
                        name=f"{sensor} (raw)",
                        mode="markers" if show_filtered else "lines+markers",
                        line=dict(color=colors["Temperature"]["raw"], width=1) if not show_filtered else None,
                        marker=dict(size=3, color=colors["Temperature"]["raw"]),
                        showlegend=True
                    ),
                    secondary_y=False
                )
            elif "Humidity" in sensor:
                fig.add_trace(
                    go.Scatter(
                        x=sensor_data["datetime"],
                        y=sensor_data["value"],
                        name=f"{sensor} (raw)",
                        mode="markers" if show_filtered else "lines+markers",
                        line=dict(color=colors["Humidity"]["raw"], width=1) if not show_filtered else None,
                        marker=dict(size=3, color=colors["Humidity"]["raw"]),
                        showlegend=True
                    ),
                    secondary_y=True
                )

    # Add filtered data traces
    if show_filtered and not filtered_df.empty:
        sensors = filtered_df["sensor_name"].unique()
        for sensor in sensors:
            sensor_data = filtered_df[filtered_df["sensor_name"] == sensor].sort_values("datetime")

            if "Temperature" in sensor:
                fig.add_trace(
                    go.Scatter(
                        x=sensor_data["datetime"],
                        y=sensor_data["value"],
                        name=f"{sensor} (filtered)",
                        mode="lines",
                        line=dict(color=colors["Temperature"]["filtered"], width=2),
                        showlegend=True
                    ),
                    secondary_y=False
                )
            elif "Humidity" in sensor:
                fig.add_trace(
                    go.Scatter(
                        x=sensor_data["datetime"],
                        y=sensor_data["value"],
                        name=f"{sensor} (filtered)",
                        mode="lines",
                        line=dict(color=colors["Humidity"]["filtered"], width=2),
                        showlegend=True
                    ),
                    secondary_y=True
                )

    # Update axes
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Temperature (°F)", secondary_y=False)
    fig.update_yaxes(title_text="Humidity (%)", secondary_y=True)

    # Update layout
    fig.update_layout(
        height=500,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)


# Main UI Layout
col1, col2, col3 = st.columns([3, 1, 1])

with col2:
    if st.button("🔄 Fetch New Data", use_container_width=True, type="primary"):
        with st.spinner("Fetching data from SmartThings..."):
            try:
                all_readings = []

                # Fetch from both devices
                for device in DEVICES:
                    if device["id"]:
                        status = fetch_device_status(device["id"])
                        readings = extract_sensor_values(status, device["label"])
                        all_readings.extend(readings)

                if all_readings:
                    count = append_to_csv(all_readings)
                    st.success(f"✓ Added {count} new readings!")
                    st.rerun()
                else:
                    st.warning("No temperature or humidity data found in devices")

            except Exception as e:
                st.error(f"Error: {str(e)}")

with col3:
    if st.button("📥 Import History", use_container_width=True, help="Import historical data from SmartThings activities"):
        with st.spinner("Importing historical data..."):
            try:
                fetched, total = import_historical_data()
                st.success(f"✓ Imported {fetched} events! Total records: {total}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

with col1:
    st.subheader("Time Series")

# Display mode selector
display_mode = st.radio(
    "Display Mode",
    ["Raw Data", "Filtered Data", "Both"],
    horizontal=True,
    help="Raw: Original readings | Filtered: 10-min intervals with duration-weighted averaging | Both: Show both"
)

# Load and display data
raw_df = load_data()

if not raw_df.empty:
    # Transform data if filtered view is requested
    if display_mode in ["Filtered Data", "Both"]:
        with st.spinner("Transforming data..."):
            filtered_df = transform_to_timeseries(raw_df)
    else:
        filtered_df = pd.DataFrame(columns=["sensor_name", "datetime", "value"])

    # Display chart
    create_dual_axis_chart(raw_df, filtered_df, display_mode)

    # Show statistics (use filtered data if available, otherwise raw)
    stats_df = filtered_df if not filtered_df.empty else raw_df

    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

    with col_stat1:
        st.metric("Total Readings", len(raw_df))

    with col_stat2:
        if not raw_df.empty:
            latest = raw_df.groupby("sensor_name").last()
            st.metric("Last Update", raw_df["datetime"].max().strftime("%m/%d %H:%M"))

    with col_stat3:
        temp_data = stats_df[stats_df["sensor_name"].str.contains("Temperature")]
        if not temp_data.empty:
            st.metric("Avg Temperature", f"{temp_data['value'].mean():.1f}°F")

    with col_stat4:
        humidity_data = stats_df[stats_df["sensor_name"].str.contains("Humidity")]
        if not humidity_data.empty:
            st.metric("Avg Humidity", f"{humidity_data['value'].mean():.1f}%")

    # Recent readings table
    st.subheader("Recent Readings")
    table_df = filtered_df if display_mode == "Filtered Data" and not filtered_df.empty else raw_df
    recent = table_df.tail(20).sort_values("datetime", ascending=False)
    recent["datetime"] = recent["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(recent, use_container_width=True, hide_index=True)

else:
    st.info("👆 Click 'Fetch New Data' to start collecting sensor readings")

# Footer
st.divider()
st.caption(f"Data stored in: {CSV_FILE} | Monitoring: {DEVICES[0]['label']}, {DEVICES[1]['label']}")
