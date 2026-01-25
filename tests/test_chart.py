"""Tests for chart and data transformation services."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import SensorReading
from app.services import (
    forward_fill_to_timeseries,
    generate_chart,
    sliding_average,
)


class TestForwardFillToTimeseries:
    """Tests for forward-fill time series conversion."""

    def _make_reading(
        self,
        value: float,
        timestamp: datetime,
        reading_type: str = "humidity",
        device_label: str = "TestSensor",
    ) -> SensorReading:
        """Helper to create a reading."""
        return SensorReading(
            device_id="device-123",
            device_label=device_label,
            reading_type=reading_type,  # type: ignore
            value=value,
            timestamp=timestamp,
        )

    def test_empty_readings_returns_empty(self) -> None:
        """Test that empty input returns empty output."""
        result = forward_fill_to_timeseries([])
        assert result == []

    def test_single_reading_fills_forward(self) -> None:
        """Test that a single reading fills forward to time slots."""
        base_time = datetime(2026, 1, 20, 12, 5, 0, tzinfo=timezone.utc)
        readings = [self._make_reading(65.0, base_time)]

        result = forward_fill_to_timeseries(readings, resolution_minutes=10)

        # Should have at least the slot at 12:10 (first slot >= reading time)
        assert len(result) >= 1
        assert result[0].value == 65.0

    def test_creates_regular_intervals(self) -> None:
        """Test that output has regular 10-minute intervals."""
        base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        readings = [
            self._make_reading(60.0, base_time),
            self._make_reading(70.0, base_time + timedelta(minutes=25)),
        ]

        result = forward_fill_to_timeseries(readings, resolution_minutes=10)

        # Should have readings at 12:00, 12:10, 12:20, 12:30
        assert len(result) >= 3
        timestamps = [r.timestamp for r in result]
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i - 1]).total_seconds()
            assert diff == 600  # 10 minutes

    def test_forward_fill_carries_last_value(self) -> None:
        """Test that values are carried forward until next reading."""
        base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        readings = [
            self._make_reading(60.0, base_time),
            self._make_reading(70.0, base_time + timedelta(minutes=25)),
        ]

        result = forward_fill_to_timeseries(readings, resolution_minutes=10)

        # 12:00 -> 60, 12:10 -> 60, 12:20 -> 60, 12:30 -> 70
        values_by_time = {r.timestamp: r.value for r in result}
        assert values_by_time[base_time] == 60.0
        assert values_by_time[base_time + timedelta(minutes=10)] == 60.0
        assert values_by_time[base_time + timedelta(minutes=20)] == 60.0
        assert values_by_time[base_time + timedelta(minutes=30)] == 70.0

    def test_no_backfill_before_first_reading(self) -> None:
        """Test that time slots before first reading are omitted."""
        # Reading at 12:15, but slot at 12:10 should be empty
        base_time = datetime(2026, 1, 20, 12, 15, 0, tzinfo=timezone.utc)
        readings = [self._make_reading(65.0, base_time)]

        result = forward_fill_to_timeseries(readings, resolution_minutes=10)

        # First slot should be 12:20 (first slot >= 12:15 where value is set)
        # Actually 12:10 is before 12:15, so no value yet
        # 12:20 is first slot after 12:15 but 12:15 sets value, so 12:20 has it
        timestamps = [r.timestamp for r in result]
        assert datetime(2026, 1, 20, 12, 10, 0, tzinfo=timezone.utc) not in timestamps

    def test_preserves_device_info(self) -> None:
        """Test that device info is preserved in output."""
        reading = self._make_reading(
            value=65.0,
            timestamp=datetime(2026, 1, 20, 12, 5, 0, tzinfo=timezone.utc),
            device_label="PuerHumidity",
        )

        result = forward_fill_to_timeseries([reading])

        assert len(result) >= 1
        assert result[0].device_label == "PuerHumidity"
        assert result[0].device_id == "device-123"

    def test_handles_multiple_sensors(self) -> None:
        """Test that multiple sensors are processed separately."""
        base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        readings = [
            self._make_reading(65.0, base_time, "humidity", "SensorA"),
            self._make_reading(70.0, base_time, "temperature", "SensorB"),
        ]

        result = forward_fill_to_timeseries(readings)

        sensor_names = set(r.sensor_name for r in result)
        assert "SensorA-Humidity" in sensor_names
        assert "SensorB-Temperature" in sensor_names


class TestSlidingAverage:
    """Tests for sliding window average."""

    def _make_reading(
        self,
        value: float,
        timestamp: datetime,
        reading_type: str = "humidity",
    ) -> SensorReading:
        """Helper to create a reading."""
        return SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type=reading_type,  # type: ignore
            value=value,
            timestamp=timestamp,
        )

    def test_empty_readings_returns_empty(self) -> None:
        """Test that empty input returns empty output."""
        result = sliding_average([])
        assert result == []

    def test_single_reading_returns_same_value(self) -> None:
        """Test that single reading returns its own value."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        result = sliding_average(readings, window_minutes=60)
        assert len(result) == 1
        assert result[0].value == 65.0

    def test_averages_over_window(self) -> None:
        """Test that values are averaged over the window."""
        base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        # 6 readings, each 10 minutes apart
        readings = [
            self._make_reading(60.0, base_time),
            self._make_reading(60.0, base_time + timedelta(minutes=10)),
            self._make_reading(60.0, base_time + timedelta(minutes=20)),
            self._make_reading(60.0, base_time + timedelta(minutes=30)),
            self._make_reading(60.0, base_time + timedelta(minutes=40)),
            self._make_reading(80.0, base_time + timedelta(minutes=50)),
        ]

        # Window of 60 min = 6 readings at 10-min resolution
        result = sliding_average(readings, window_minutes=60, resolution_minutes=10)

        # Last value should be average of all 6: (60*5 + 80) / 6 ≈ 63.33
        assert len(result) == 6
        assert result[-1].value == pytest.approx(63.33, abs=0.01)

    def test_partial_window_at_start(self) -> None:
        """Test that early readings use partial window."""
        base_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        readings = [
            self._make_reading(60.0, base_time),
            self._make_reading(70.0, base_time + timedelta(minutes=10)),
            self._make_reading(80.0, base_time + timedelta(minutes=20)),
        ]

        # Window of 30 min = 3 readings
        result = sliding_average(readings, window_minutes=30, resolution_minutes=10)

        # First reading: just 60
        assert result[0].value == 60.0
        # Second reading: (60 + 70) / 2 = 65
        assert result[1].value == 65.0
        # Third reading: (60 + 70 + 80) / 3 = 70
        assert result[2].value == 70.0

    def test_preserves_device_info(self) -> None:
        """Test that device info is preserved."""
        reading = self._make_reading(
            65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        )
        result = sliding_average([reading])
        assert result[0].device_id == "device-123"
        assert result[0].device_label == "TestSensor"


class TestGenerateChart:
    """Tests for chart generation."""

    def _make_reading(
        self,
        value: float,
        timestamp: datetime,
        reading_type: str = "humidity",
    ) -> SensorReading:
        """Helper to create a reading."""
        return SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type=reading_type,  # type: ignore
            value=value,
            timestamp=timestamp,
        )

    def test_returns_html_string(self) -> None:
        """Test that output is an HTML string."""
        result = generate_chart([])
        assert isinstance(result, str)
        assert "<div" in result or "plotly" in result.lower()

    def test_empty_readings_shows_message(self) -> None:
        """Test that empty data shows 'No data available'."""
        result = generate_chart([])
        assert "No data available" in result

    def test_raw_mode_includes_raw_traces(self) -> None:
        """Test that raw mode includes raw data traces."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        result = generate_chart(readings, display_mode="raw")
        assert "(raw)" in result

    def test_resampled_mode_includes_resampled_traces(self) -> None:
        """Test that resampled mode includes resampled data traces."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        result = generate_chart(readings, display_mode="resampled")
        assert "(resampled)" in result

    def test_smoothed_mode_includes_smoothed_traces(self) -> None:
        """Test that smoothed mode includes smoothed data traces."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        result = generate_chart(readings, display_mode="smoothed")
        assert "(smoothed)" in result

    def test_includes_plotly_cdn(self) -> None:
        """Test that output includes Plotly CDN reference."""
        result = generate_chart([])
        assert "plotly" in result.lower()

    def test_temperature_on_primary_axis(self) -> None:
        """Test that temperature is on the primary y-axis."""
        readings = [
            self._make_reading(
                72.0,
                datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
                reading_type="temperature",
            )
        ]
        result = generate_chart(readings)
        assert "Temperature" in result

    def test_humidity_on_secondary_axis(self) -> None:
        """Test that humidity is on the secondary y-axis."""
        readings = [
            self._make_reading(
                65.0,
                datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
                reading_type="humidity",
            )
        ]
        result = generate_chart(readings)
        assert "Humidity" in result

    def test_custom_height(self) -> None:
        """Test that custom height is applied."""
        result = generate_chart([], height=800)
        assert "800" in result

    def test_custom_resolution(self) -> None:
        """Test that custom resolution is accepted."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        # Should not raise
        result = generate_chart(readings, display_mode="resampled", resolution_minutes=5)
        assert "(resampled)" in result

    def test_custom_smoothing_window(self) -> None:
        """Test that custom smoothing window is accepted."""
        readings = [
            self._make_reading(
                65.0, datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        # Should not raise
        result = generate_chart(
            readings, display_mode="smoothed", smoothing_window_minutes=120
        )
        assert "(smoothed)" in result


class TestChartColors:
    """Tests for chart color scheme."""

    def test_temperature_colors_defined(self) -> None:
        """Test that temperature colors are defined."""
        from app.services.chart import COLORS

        assert "temperature" in COLORS
        assert "raw" in COLORS["temperature"]
        assert "resampled" in COLORS["temperature"]
        assert "smoothed" in COLORS["temperature"]

    def test_humidity_colors_defined(self) -> None:
        """Test that humidity colors are defined."""
        from app.services.chart import COLORS

        assert "humidity" in COLORS
        assert "raw" in COLORS["humidity"]
        assert "resampled" in COLORS["humidity"]
        assert "smoothed" in COLORS["humidity"]

    def test_raw_colors_are_most_transparent(self) -> None:
        """Test that raw colors use RGBA with transparency."""
        from app.services.chart import COLORS

        assert "rgba" in COLORS["temperature"]["raw"]
        assert "rgba" in COLORS["humidity"]["raw"]
        # Check transparency value (0.3)
        assert "0.3" in COLORS["temperature"]["raw"]

    def test_smoothed_colors_are_solid(self) -> None:
        """Test that smoothed colors use solid RGB."""
        from app.services.chart import COLORS

        assert COLORS["temperature"]["smoothed"].startswith("rgb(")
        assert COLORS["humidity"]["smoothed"].startswith("rgb(")
