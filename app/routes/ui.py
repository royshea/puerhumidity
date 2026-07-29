"""UI routes for chart display."""

from flask import Blueprint, render_template, request

from app.models import SensorReading
from app.services import generate_chart
from app.storage import get_storage

ui_bp = Blueprint("ui", __name__)

# Units to display alongside each reading type.
_READING_UNITS: dict[str, str] = {"temperature": "°F", "humidity": "%"}


def _build_latest_summary(readings: list[SensorReading]) -> list[dict[str, str]]:
    """Compute the latest reading per sensor for the summary section.

    Args:
        readings: Readings within the current time window (sorted ascending).

    Returns:
        One entry per sensor (e.g. "PuerHumidity-Humidity"), each with a
        human-friendly label, formatted value, and reading time. Sorted by
        device label then reading type for a stable display order.
    """
    latest_by_sensor: dict[str, SensorReading] = {}
    for reading in readings:
        current = latest_by_sensor.get(reading.sensor_name)
        if current is None or reading.timestamp > current.timestamp:
            latest_by_sensor[reading.sensor_name] = reading

    summary: list[dict[str, str]] = []
    for reading in latest_by_sensor.values():
        unit = _READING_UNITS.get(reading.reading_type, "")
        summary.append(
            {
                "sensor_name": reading.sensor_name,
                "device_label": reading.device_label,
                "reading_type": reading.reading_type.capitalize(),
                "value": f"{reading.value:g}{unit}",
                "timestamp": reading.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            }
        )

    return sorted(summary, key=lambda s: (s["device_label"], s["reading_type"]))


@ui_bp.route("/")
def chart() -> str:
    """Render the main chart page.

    Query parameters:
        mode: Display mode - "raw", "resampled", or "smoothed" (default: "smoothed")
        hours: Number of hours of data to display (default: 168 = 1 week)
        resolution: Time series resolution in minutes (default: 10)
        window: Smoothing window in minutes (default: 60)

    Returns:
        Rendered chart page HTML.
    """
    # Parse query parameters with defaults
    mode = request.args.get("mode", "smoothed")
    if mode not in ("raw", "resampled", "smoothed"):
        mode = "smoothed"

    hours = request.args.get("hours", "168", type=str)
    try:
        hours_int = int(hours)
        if hours_int < 1:
            hours_int = 168
    except ValueError:
        hours_int = 168

    resolution = request.args.get("resolution", "10", type=str)
    try:
        resolution_int = int(resolution)
        if resolution_int < 1:
            resolution_int = 10
    except ValueError:
        resolution_int = 10

    window = request.args.get("window", "60", type=str)
    try:
        window_int = int(window)
        if window_int < 1:
            window_int = 60
    except ValueError:
        window_int = 60

    # Fetch readings from storage
    storage = get_storage()
    readings = storage.get_all_readings(hours=hours_int)

    # Latest value + time per sensor for the summary section
    latest_readings = _build_latest_summary(readings)

    # Generate chart HTML
    chart_html = generate_chart(
        readings,
        display_mode=mode,  # type: ignore
        resolution_minutes=resolution_int,
        smoothing_window_minutes=window_int,
    )

    return render_template(
        "chart.html",
        chart_html=chart_html,
        latest_readings=latest_readings,
        mode=mode,
        hours=hours_int,
        resolution=resolution_int,
        window=window_int,
        reading_count=len(readings),
    )
