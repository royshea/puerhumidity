"""Tests for data models."""

from datetime import datetime, timezone

import pytest

from app.models import SensorReading


class TestSensorReading:
    """Tests for SensorReading dataclass."""

    def test_create_humidity_reading(self) -> None:
        """Test creating a humidity reading."""
        reading = SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.5,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        assert reading.device_id == "device-123"
        assert reading.device_label == "TestSensor"
        assert reading.reading_type == "humidity"
        assert reading.value == 65.5
        assert reading.timestamp == datetime(2026, 1, 17, 12, 0, 0)

    def test_create_temperature_reading(self) -> None:
        """Test creating a temperature reading."""
        reading = SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="temperature",
            value=72.0,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        assert reading.reading_type == "temperature"
        assert reading.value == 72.0

    def test_sensor_name_humidity(self) -> None:
        """Test sensor_name property for humidity reading."""
        reading = SensorReading(
            device_id="device-123",
            device_label="PuerHumidity",
            reading_type="humidity",
            value=65.0,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        assert reading.sensor_name == "PuerHumidity-Humidity"

    def test_sensor_name_temperature(self) -> None:
        """Test sensor_name property for temperature reading."""
        reading = SensorReading(
            device_id="device-123",
            device_label="ChestHumidity",
            reading_type="temperature",
            value=70.0,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        assert reading.sensor_name == "ChestHumidity-Temperature"

    def test_to_dict(self) -> None:
        """Test converting reading to dictionary."""
        reading = SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.5,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        result = reading.to_dict()

        assert result == {
            "device_id": "device-123",
            "device_label": "TestSensor",
            "reading_type": "humidity",
            "value": 65.5,
            "timestamp": "2026-01-17T12:00:00",
        }

    def test_from_dict(self) -> None:
        """Test creating reading from dictionary."""
        data = {
            "device_id": "device-123",
            "device_label": "TestSensor",
            "reading_type": "humidity",
            "value": 65.5,
            "timestamp": "2026-01-17T12:00:00",
        }

        reading = SensorReading.from_dict(data)

        assert reading.device_id == "device-123"
        assert reading.device_label == "TestSensor"
        assert reading.reading_type == "humidity"
        assert reading.value == 65.5
        assert reading.timestamp == datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_from_dict_invalid_reading_type(self) -> None:
        """Test that invalid reading_type raises ValueError."""
        data = {
            "device_id": "device-123",
            "device_label": "TestSensor",
            "reading_type": "invalid",
            "value": 65.5,
            "timestamp": "2026-01-17T12:00:00",
        }

        with pytest.raises(ValueError, match="Invalid reading_type"):
            SensorReading.from_dict(data)

    def test_reading_is_frozen(self) -> None:
        """Test that readings are immutable."""
        reading = SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.5,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
        )

        with pytest.raises(AttributeError):
            reading.value = 70.0  # type: ignore[misc]

    def test_round_trip_dict_conversion(self, sample_reading: SensorReading) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        data = sample_reading.to_dict()
        restored = SensorReading.from_dict(data)

        assert restored == sample_reading
