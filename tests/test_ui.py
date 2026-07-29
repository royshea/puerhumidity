"""Tests for UI route helpers."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

from app.models import SensorReading
from app.routes.ui import _build_latest_summary


class TestBuildLatestSummary:
    """Tests for latest readings summary generation."""

    def _make_reading(
        self,
        device_label: str,
        reading_type: Literal["temperature", "humidity"],
        value: float,
        timestamp: datetime,
    ) -> SensorReading:
        """Create a sensor reading for summary tests."""
        return SensorReading(
            device_id=f"{device_label}-{reading_type}",
            device_label=device_label,
            reading_type=reading_type,
            value=value,
            timestamp=timestamp,
        )

    def test_empty_readings_returns_empty(self) -> None:
        """Test that empty input returns an empty summary."""
        assert _build_latest_summary([]) == []

    def test_latest_reading_per_sensor_wins(self) -> None:
        """Test that the newest reading is selected for each composite sensor."""
        older_time = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)
        newer_time = older_time + timedelta(minutes=15)
        readings = [
            self._make_reading("PuerHumidity", "humidity", 60.0, older_time),
            self._make_reading("PuerHumidity", "humidity", 66.0, newer_time),
            self._make_reading("PuerHumidity", "humidity", 62.0, older_time),
        ]

        summary = _build_latest_summary(readings)

        assert summary == [
            {
                "sensor_name": "PuerHumidity-Humidity",
                "device_label": "PuerHumidity",
                "reading_type": "Humidity",
                "value": "66%",
                "timestamp": "2026-01-20 12:15 UTC",
            }
        ]

    def test_all_sensors_units_and_stable_order(self) -> None:
        """Test all composite sensors are distinct, formatted, and sorted."""
        timestamp = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)
        readings = [
            self._make_reading("PuerHumidity", "temperature", 72.5, timestamp),
            self._make_reading("ChestHumidity", "temperature", 68.0, timestamp),
            self._make_reading("PuerHumidity", "humidity", 65.0, timestamp),
            self._make_reading("ChestHumidity", "humidity", 55.0, timestamp),
        ]

        summary = _build_latest_summary(readings)

        assert [entry["sensor_name"] for entry in summary] == [
            "ChestHumidity-Humidity",
            "ChestHumidity-Temperature",
            "PuerHumidity-Humidity",
            "PuerHumidity-Temperature",
        ]
        assert [entry["device_label"] for entry in summary] == [
            "ChestHumidity",
            "ChestHumidity",
            "PuerHumidity",
            "PuerHumidity",
        ]
        assert [entry["reading_type"] for entry in summary] == [
            "Humidity",
            "Temperature",
            "Humidity",
            "Temperature",
        ]
        assert [entry["value"] for entry in summary] == ["55%", "68°F", "65%", "72.5°F"]

    def test_timestamp_converts_to_utc_before_formatting(self) -> None:
        """Test that non-UTC timestamps are displayed as UTC wall-clock time."""
        pacific_time = timezone(timedelta(hours=-7))
        reading = self._make_reading(
            "PuerHumidity",
            "temperature",
            72.0,
            datetime(2026, 7, 28, 18, 3, tzinfo=pacific_time),
        )

        summary = _build_latest_summary([reading])

        assert summary[0]["timestamp"] == "2026-07-29 01:03 UTC"
