#!/usr/bin/env python3
"""
SmartThings Humidity & Temperature Monitor
Fetches data from two SmartThings sensors and visualizes trends
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from dotenv import load_dotenv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load environment variables
load_dotenv()

# Configuration
SMARTTHINGS_TOKEN = os.getenv("SMARTTHINGS_TOKEN")
API_BASE = "https://api.smartthings.com/v1"
CSV_FILE = "data/humidity_data.csv"
LOCATION_ID = None  # Will be fetched from device

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

# Page configuration
st.set_page_config(
    page_title="SmartThings Humidity Monitor",
    page_icon="🌡️",
    layout="wide"
)

st.title("🌡️ Humidity & Temperature Monitor")
st.caption("Real-time tracking of SmartThings sensors")


def get_location_id():
    """Get location ID from the first configured device"""
    global LOCATION_ID
    if LOCATION_ID:
        return LOCATION_ID

    headers = {
        "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
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
    if not SMARTTHINGS_TOKEN:
        raise ValueError("SMARTTHINGS_TOKEN not configured")

    headers = {
        "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
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


def fetch_historical_activities(max_pages=50):
    """Fetch historical device activities from SmartThings"""
    location_id = get_location_id()

    headers = {
        "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
        "Accept": "application/vnd.smartthings+json;v=20180919"
    }

    all_readings = []
    url = f"https://api.smartthings.com/activities?location={location_id}"
    pages_fetched = 0

    while url and pages_fetched < max_pages:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

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

                if capability == "temperatureMeasurement" and attribute_value:
                    all_readings.append({
                        "sensor_name": f"{device_label}-Temperature",
                        "datetime": pd.to_datetime(timestamp).tz_localize(None),
                        "value": float(attribute_value)
                    })
                elif capability == "relativeHumidityMeasurement" and attribute_value:
                    all_readings.append({
                        "sensor_name": f"{device_label}-Humidity",
                        "datetime": pd.to_datetime(timestamp).tz_localize(None),
                        "value": float(attribute_value)
                    })

        # Check for next page
        pages_fetched += 1
        links = data.get("_links", {})
        next_link = links.get("next", {})
        url = next_link.get("href") if next_link else None

    return all_readings


def import_historical_data():
    """Import historical activities and merge with existing CSV"""
    # Fetch historical activities
    activities = fetch_historical_activities()

    if not activities:
        return 0, 0

    # Convert to DataFrame
    new_df = pd.DataFrame(activities)

    # Load existing data
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
