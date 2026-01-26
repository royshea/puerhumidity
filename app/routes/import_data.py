"""Routes for importing historical data via SmartThings Activities API.

NOTE: Import functionality is disabled in production for security.
To enable, set ENABLE_IMPORT=true in environment variables and redeploy.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.models import SensorReading
from app.storage import get_storage

import_bp = Blueprint("import", __name__)
logger = logging.getLogger(__name__)

# SmartThings Activities API requires this specific Accept header
ACTIVITIES_ACCEPT_HEADER = "application/vnd.smartthings+json;v=20180919"

# Import is disabled by default for security
IMPORT_ENABLED = os.environ.get("ENABLE_IMPORT", "").lower() == "true"


@import_bp.route("/import", methods=["GET"])
def import_form() -> str:
    """Render the import form page.

    Returns:
        Rendered import form HTML.
    """
    return render_template("import.html", import_enabled=IMPORT_ENABLED)


@import_bp.route("/import", methods=["POST"])
def import_data() -> str:
    """Import historical data from SmartThings Activities API.

    Uses a Personal Access Token (PAT) provided by the user.
    The PAT is NOT stored - it's used once for the import.

    Returns:
        Redirect to chart page on success, or import form with error.
    """
    # Check if import is enabled
    if not IMPORT_ENABLED:
        flash("Import functionality is disabled. Set ENABLE_IMPORT=true to enable.", "error")
        return render_template("import.html", import_enabled=IMPORT_ENABLED)

    pat = request.form.get("pat", "").strip()
    if not pat:
        flash("Please enter a Personal Access Token", "error")
        return render_template("import.html", import_enabled=IMPORT_ENABLED)

    # Get location ID from config or use the known one
    location_id = current_app.config.get(
        "SMARTTHINGS_LOCATION_ID", "9ec8c9fc-3af2-464f-b917-d0403ab0c4bb"
    )

    try:
        # Fetch activities from SmartThings
        readings = _fetch_activities(pat, location_id)

        if not readings:
            flash("No humidity/temperature data found in activities", "warning")
            return render_template("import.html", import_enabled=IMPORT_ENABLED)

        # Write to storage using batch operations
        storage = get_storage()
        written_count = storage.write_readings(readings)

        logger.info("Imported %d readings from Activities API", written_count)
        flash(f"Successfully imported {written_count} readings!", "success")
        return redirect(url_for("ui.chart"))

    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            flash("Invalid or expired token. Please generate a new PAT.", "error")
        else:
            flash(f"API error: {e}", "error")
        logger.error("Activities API error: %s", e)
        return render_template("import.html", import_enabled=IMPORT_ENABLED)

    except Exception as e:
        flash(f"Import failed: {e}", "error")
        logger.error("Import failed: %s", e)
        return render_template("import.html", import_enabled=IMPORT_ENABLED)


def _fetch_activities(pat: str, location_id: str) -> list[SensorReading]:
    """Fetch activities from SmartThings and parse into readings.

    Handles pagination to fetch all available history.

    Args:
        pat: Personal Access Token for SmartThings API.
        location_id: SmartThings location ID to fetch activities for.

    Returns:
        List of SensorReading objects parsed from activities.

    Raises:
        requests.HTTPError: If API call fails.
    """
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": ACTIVITIES_ACCEPT_HEADER,
    }

    device_labels = current_app.config.get("DEVICE_LABELS", {})
    all_items: list[dict] = []
    
    # Start with base URL, then follow pagination
    url: str | None = f"https://api.smartthings.com/activities?location={location_id}&limit=100"
    page_count = 0
    max_pages = 100  # Safety limit to prevent infinite loops
    
    while url and page_count < max_pages:
        page_count += 1
        logger.info("Fetching activities page %d from %s", page_count, url[:80])

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])
        all_items.extend(items)
        logger.info("Page %d: fetched %d items (total: %d)", page_count, len(items), len(all_items))
        
        # Check for next page - SmartThings uses _links.next.href
        links = data.get("_links", {})
        next_link = links.get("next", {})
        url = next_link.get("href") if next_link else None
        
        # If no more items, stop
        if not items:
            break

    logger.info("Fetched %d total activity items across %d pages", len(all_items), page_count)

    # Parse activities into readings
    readings = []

    for item in all_items:
        reading = _parse_activity(item, device_labels)
        if reading:
            readings.append(reading)

    logger.info("Parsed %d sensor readings from activities", len(readings))
    return readings


def _parse_activity(item: dict[str, Any], device_labels: dict[str, str]) -> SensorReading | None:
    """Parse a single activity item into a SensorReading.

    Args:
        item: Activity item from the API response.
        device_labels: Mapping of device IDs to human-readable labels.

    Returns:
        SensorReading if the activity is humidity/temperature, else None.
    """
    # Only process DEVICE activities
    if item.get("activityType") != "DEVICE":
        return None

    device_activity = item.get("deviceActivity", {})
    if not device_activity:
        return None

    # Extract fields
    device_id = device_activity.get("deviceId")
    capability = device_activity.get("capability")
    attribute = device_activity.get("attributeName")
    value_str = device_activity.get("attributeValue")
    timestamp_str = item.get("timestamp")

    if not all([device_id, capability, value_str, timestamp_str]):
        return None

    # Determine reading type
    reading_type: str
    if capability == "relativeHumidityMeasurement" and attribute == "humidity":
        reading_type = "humidity"
    elif capability == "temperatureMeasurement" and attribute == "temperature":
        reading_type = "temperature"
    else:
        return None

    # Parse value
    try:
        value = float(value_str)
    except (ValueError, TypeError):
        return None

    # Parse timestamp (format: "2026-01-17T23:07:44.000+00:00")
    try:
        # Handle the timezone format
        timestamp = datetime.fromisoformat(timestamp_str.replace("+00:00", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

    # Get device label
    device_label = device_labels.get(device_id, device_activity.get("deviceName", device_id))

    return SensorReading(
        device_id=device_id,
        device_label=device_label,
        reading_type=reading_type,  # type: ignore[arg-type]
        value=value,
        timestamp=timestamp,
    )
