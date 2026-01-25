"""Chart generation service using Plotly.

Generates dual-axis charts for temperature and humidity visualization.
"""

from typing import Literal

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.models import SensorReading
from app.services.data_transform import forward_fill_to_timeseries, sliding_average


# Color scheme for chart traces
COLORS = {
    "temperature": {
        "raw": "rgba(255, 99, 71, 0.3)",        # Tomato, semi-transparent
        "resampled": "rgba(255, 99, 71, 0.6)",  # Tomato, medium
        "smoothed": "rgb(255, 99, 71)",          # Tomato, solid
    },
    "humidity": {
        "raw": "rgba(54, 162, 235, 0.3)",        # Blue, semi-transparent
        "resampled": "rgba(54, 162, 235, 0.6)",  # Blue, medium
        "smoothed": "rgb(54, 162, 235)",          # Blue, solid
    },
}


DisplayMode = Literal["raw", "resampled", "smoothed"]


def generate_chart(
    readings: list[SensorReading],
    display_mode: DisplayMode = "smoothed",
    height: int = 500,
    resolution_minutes: int = 10,
    smoothing_window_minutes: int = 60,
) -> str:
    """Generate a dual-axis Plotly chart as HTML.

    Creates an interactive chart with temperature on the left y-axis and
    humidity on the right y-axis.

    Display modes:
    - "raw": Original sparse readings as markers
    - "resampled": Forward-filled regular time series (stepped line)
    - "smoothed": Sliding average applied to resampled data (smooth line)

    Args:
        readings: List of raw sensor readings.
        display_mode: What data to display - "raw", "resampled", or "smoothed".
        height: Chart height in pixels.
        resolution_minutes: Time series interval for resampled/smoothed modes.
        smoothing_window_minutes: Lookback window for smoothed mode.

    Returns:
        HTML string containing the Plotly chart (div + script).
    """
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not readings:
        # Return empty chart with message
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20),
        )
    else:
        if display_mode == "raw":
            _add_traces(fig, readings, trace_type="raw")
        elif display_mode == "resampled":
            resampled = forward_fill_to_timeseries(readings, resolution_minutes)
            _add_traces(fig, resampled, trace_type="resampled")
        else:  # smoothed
            resampled = forward_fill_to_timeseries(readings, resolution_minutes)
            smoothed = sliding_average(
                resampled,
                window_minutes=smoothing_window_minutes,
                resolution_minutes=resolution_minutes,
            )
            _add_traces(fig, smoothed, trace_type="smoothed")

    # Update axes
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Temperature (°F)", secondary_y=False)
    fig.update_yaxes(title_text="Humidity (%)", secondary_y=True)

    # Update layout
    fig.update_layout(
        height=height,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=50, t=50, b=50),
    )

    # Return as HTML div
    html: str = fig.to_html(full_html=False, include_plotlyjs="cdn")
    return html


def _add_traces(
    fig: go.Figure,
    readings: list[SensorReading],
    trace_type: Literal["raw", "resampled", "smoothed"],
) -> None:
    """Add traces to the figure for each sensor.

    Args:
        fig: Plotly figure to add traces to.
        readings: List of sensor readings.
        trace_type: Style selection - "raw", "resampled", or "smoothed".
    """
    # Group readings by sensor_name
    readings_by_sensor: dict[str, list[SensorReading]] = {}
    for reading in readings:
        key = reading.sensor_name
        if key not in readings_by_sensor:
            readings_by_sensor[key] = []
        readings_by_sensor[key].append(reading)

    # Sort each group and add traces
    for sensor_name, sensor_readings in readings_by_sensor.items():
        sensor_readings.sort(key=lambda r: r.timestamp)

        if not sensor_readings:
            continue

        reading_type = sensor_readings[0].reading_type
        x_values = [r.timestamp for r in sensor_readings]
        y_values = [r.value for r in sensor_readings]

        color = COLORS[reading_type][trace_type]
        name = f"{sensor_name} ({trace_type})"

        # Determine display style based on trace type
        if trace_type == "raw":
            mode = "markers"
            line_config = None
            marker_config = dict(size=4, color=color)
        elif trace_type == "resampled":
            # Step line for forward-filled data (shows holds)
            mode = "lines"
            line_config = dict(color=color, width=1, shape="hv")  # horizontal-vertical steps
            marker_config = None
        else:  # smoothed
            mode = "lines"
            line_config = dict(color=color, width=2)
            marker_config = None

        # Temperature on primary y-axis, humidity on secondary
        secondary_y = reading_type == "humidity"

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                name=name,
                mode=mode,
                line=line_config,
                marker=marker_config,
                showlegend=True,
            ),
            secondary_y=secondary_y,
        )
