"""Sensor reading data model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class SensorReading:
    """Represents a single sensor reading from a SmartThings device.

    Attributes:
        device_id: The SmartThings device ID.
        device_label: Human-readable device name (e.g., "PuerHumidity").
        reading_type: Type of reading - either "temperature" or "humidity".
        value: The sensor value (temperature in °F, humidity in %).
        timestamp: When the reading was recorded.
    """

    device_id: str
    device_label: str
    reading_type: Literal["temperature", "humidity"]
    value: float
    timestamp: datetime

    @property
    def sensor_name(self) -> str:
        """Get the composite sensor name for storage partitioning.

        Returns:
            String like "PuerHumidity-Temperature" or "ChestHumidity-Humidity".
        """
        type_suffix = self.reading_type.capitalize()
        return f"{self.device_label}-{type_suffix}"

    def to_dict(self) -> dict[str, str | float]:
        """Convert reading to dictionary for storage.

        Returns:
            Dictionary with string keys suitable for CSV or Table Storage.
        """
        return {
            "device_id": self.device_id,
            "device_label": self.device_label,
            "reading_type": self.reading_type,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | float]) -> "SensorReading":
        """Create a SensorReading from a dictionary.

        Args:
            data: Dictionary with keys matching the dataclass fields.

        Returns:
            New SensorReading instance.
        """
        raw_timestamp = data["timestamp"]
        if isinstance(raw_timestamp, str):
            parsed_timestamp = datetime.fromisoformat(raw_timestamp)
        else:
            raise ValueError(f"timestamp must be a string, got {type(raw_timestamp)}")

        reading_type = data["reading_type"]
        if reading_type not in ("temperature", "humidity"):
            raise ValueError(f"Invalid reading_type: {reading_type}")

        return cls(
            device_id=str(data["device_id"]),
            device_label=str(data["device_label"]),
            reading_type=reading_type,  # type: ignore[arg-type]
            value=float(data["value"]),
            timestamp=parsed_timestamp,
        )
