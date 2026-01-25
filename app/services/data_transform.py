"""Data transformation utilities for sensor readings.

Provides two-stage transformation pipeline:
1. Forward-fill: Convert irregular readings to regular time intervals
2. Sliding average: Optional smoothing with configurable lookback window
"""

from datetime import datetime, timedelta
from typing import Literal

from app.models import SensorReading


def forward_fill_to_timeseries(
    readings: list[SensorReading],
    resolution_minutes: int = 10,
) -> list[SensorReading]:
    """Convert irregular readings to regular time intervals using forward-fill.

    Sensors only report when values change, so the last known value holds until
    a new reading arrives. This function creates evenly-spaced time slots and
    carries forward the most recent value for each slot.

    Args:
        readings: List of raw sensor readings (irregular timestamps).
        resolution_minutes: Interval size in minutes (default 10).

    Returns:
        List of readings at regular intervals. Time slots before the first
        reading for each sensor will be omitted (no backfill).
    """
    if not readings:
        return []

    # Group readings by sensor_name
    readings_by_sensor: dict[str, list[SensorReading]] = {}
    for reading in readings:
        key = reading.sensor_name
        if key not in readings_by_sensor:
            readings_by_sensor[key] = []
        readings_by_sensor[key].append(reading)

    # Sort each group by timestamp
    for sensor_readings in readings_by_sensor.values():
        sensor_readings.sort(key=lambda r: r.timestamp)

    # Get time range across all readings
    all_timestamps = [r.timestamp for r in readings]
    min_time = min(all_timestamps)
    max_time = max(all_timestamps)

    # Create aligned time slots
    resolution = timedelta(minutes=resolution_minutes)
    start_time = _floor_to_resolution(min_time, resolution_minutes)
    end_time = _ceil_to_resolution(max_time, resolution_minutes)

    # Generate time slots
    time_slots: list[datetime] = []
    current = start_time
    while current <= end_time:
        time_slots.append(current)
        current += resolution

    # Process each sensor with forward-fill
    result: list[SensorReading] = []

    for sensor_readings in readings_by_sensor.values():
        if not sensor_readings:
            continue

        device_id = sensor_readings[0].device_id
        device_label = sensor_readings[0].device_label
        reading_type = sensor_readings[0].reading_type

        # Forward-fill: for each time slot, use the most recent reading <= slot time
        reading_idx = 0
        current_value: float | None = None

        for slot_time in time_slots:
            # Advance to the latest reading that is <= slot_time
            while (
                reading_idx < len(sensor_readings)
                and sensor_readings[reading_idx].timestamp <= slot_time
            ):
                current_value = sensor_readings[reading_idx].value
                reading_idx += 1

            # Only emit if we have a value (no backfill before first reading)
            if current_value is not None:
                result.append(
                    SensorReading(
                        device_id=device_id,
                        device_label=device_label,
                        reading_type=reading_type,
                        value=current_value,
                        timestamp=slot_time,
                    )
                )

    return result


def sliding_average(
    readings: list[SensorReading],
    window_minutes: int = 60,
    resolution_minutes: int = 10,
) -> list[SensorReading]:
    """Apply sliding window average to a regular time series.

    This is an O(n) algorithm using a running sum. Assumes input is already
    a regular time series (e.g., from forward_fill_to_timeseries).

    Args:
        readings: List of readings at regular intervals.
        window_minutes: Lookback window size in minutes (default 60).
        resolution_minutes: Expected interval between readings (default 10).

    Returns:
        List of smoothed readings. The first (window_size - 1) readings will
        use a smaller window (partial average).
    """
    if not readings:
        return []

    # Group readings by sensor_name
    readings_by_sensor: dict[str, list[SensorReading]] = {}
    for reading in readings:
        key = reading.sensor_name
        if key not in readings_by_sensor:
            readings_by_sensor[key] = []
        readings_by_sensor[key].append(reading)

    # Sort each group by timestamp
    for sensor_readings in readings_by_sensor.values():
        sensor_readings.sort(key=lambda r: r.timestamp)

    # Calculate window size in number of readings
    window_size = max(1, window_minutes // resolution_minutes)

    result: list[SensorReading] = []

    for sensor_readings in readings_by_sensor.values():
        if not sensor_readings:
            continue

        device_id = sensor_readings[0].device_id
        device_label = sensor_readings[0].device_label
        reading_type = sensor_readings[0].reading_type

        # O(n) sliding window using running sum
        values = [r.value for r in sensor_readings]
        n = len(values)

        running_sum = 0.0
        for i in range(n):
            running_sum += values[i]

            # Remove the value that's falling out of the window
            if i >= window_size:
                running_sum -= values[i - window_size]

            # Calculate average over available window
            window_count = min(i + 1, window_size)
            avg_value = running_sum / window_count

            result.append(
                SensorReading(
                    device_id=device_id,
                    device_label=device_label,
                    reading_type=reading_type,
                    value=round(avg_value, 2),
                    timestamp=sensor_readings[i].timestamp,
                )
            )

    return result


def get_default_window_minutes(
    reading_type: Literal["humidity", "temperature"],
) -> int:
    """Get the default smoothing window size for a reading type.

    Temperature changes more quickly, so uses a smaller window.

    Args:
        reading_type: Either "humidity" or "temperature".

    Returns:
        Window size in minutes.
    """
    return 30 if reading_type == "temperature" else 60


def _floor_to_resolution(dt: datetime, minutes: int) -> datetime:
    """Floor datetime to the nearest resolution boundary."""
    return dt.replace(
        minute=(dt.minute // minutes) * minutes,
        second=0,
        microsecond=0,
    )


def _ceil_to_resolution(dt: datetime, minutes: int) -> datetime:
    """Ceil datetime to the nearest resolution boundary."""
    floored = _floor_to_resolution(dt, minutes)
    if floored < dt:
        return floored + timedelta(minutes=minutes)
    return floored
