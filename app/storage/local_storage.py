"""Local CSV-backed storage implementation for development and testing."""

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from app.models import SensorReading
from app.storage.base import StorageBase


class LocalStorage(StorageBase):
    """CSV file-backed storage for local development and testing.

    Thread-safe implementation that stores readings in a CSV file.
    Suitable for development but not for production use.
    """

    def __init__(self, file_path: str | Path) -> None:
        """Initialize local storage.

        Args:
            file_path: Path to the CSV file for storing readings.
        """
        self.file_path = Path(file_path)
        self._lock = Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create the CSV file with headers if it doesn't exist or is empty."""
        needs_header = False
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            needs_header = True
        elif self.file_path.stat().st_size == 0:
            needs_header = True

        if needs_header:
            with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["device_id", "device_label", "reading_type", "value", "timestamp"]
                )

    def write_reading(self, reading: SensorReading) -> None:
        """Write a single sensor reading to the CSV file.

        Args:
            reading: The sensor reading to store.
        """
        with self._lock:
            with open(self.file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        reading.device_id,
                        reading.device_label,
                        reading.reading_type,
                        reading.value,
                        reading.timestamp.isoformat(),
                    ]
                )

    def write_readings(self, readings: list[SensorReading]) -> None:
        """Write multiple sensor readings to the CSV file.

        Args:
            readings: List of sensor readings to store.
        """
        with self._lock:
            with open(self.file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for reading in readings:
                    writer.writerow(
                        [
                            reading.device_id,
                            reading.device_label,
                            reading.reading_type,
                            reading.value,
                            reading.timestamp.isoformat(),
                        ]
                    )

    def _read_all_from_file(self) -> list[SensorReading]:
        """Read all readings from the CSV file.

        Returns:
            List of all sensor readings in the file.
        """
        readings: list[SensorReading] = []

        with self._lock:
            with open(self.file_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reading = SensorReading.from_dict(row)
                    readings.append(reading)

        return readings

    def get_readings(self, sensor_name: str, hours: int = 504) -> list[SensorReading]:
        """Get readings for a specific sensor within the time window.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of sensor readings, sorted by timestamp ascending.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_readings = self._read_all_from_file()

        filtered = [
            r
            for r in all_readings
            if r.sensor_name == sensor_name and self._is_after_cutoff(r.timestamp, cutoff)
        ]

        return sorted(filtered, key=lambda r: r.timestamp)

    def get_all_readings(self, hours: int = 504) -> list[SensorReading]:
        """Get all readings within the time window.

        Args:
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of all sensor readings, sorted by timestamp ascending.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_readings = self._read_all_from_file()

        filtered = [r for r in all_readings if self._is_after_cutoff(r.timestamp, cutoff)]

        return sorted(filtered, key=lambda r: r.timestamp)

    def get_latest_reading(self, sensor_name: str) -> SensorReading | None:
        """Get the most recent reading for a specific sensor.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").

        Returns:
            The most recent reading, or None if no readings exist.
        """
        all_readings = self._read_all_from_file()
        sensor_readings = [r for r in all_readings if r.sensor_name == sensor_name]

        if not sensor_readings:
            return None

        return max(sensor_readings, key=lambda r: r.timestamp)

    @staticmethod
    def _is_after_cutoff(timestamp: datetime, cutoff: datetime) -> bool:
        """Check if a timestamp is after the cutoff, handling timezone awareness.

        Args:
            timestamp: The timestamp to check.
            cutoff: The cutoff datetime (timezone-aware).

        Returns:
            True if timestamp is after cutoff.
        """
        # Make timestamp timezone-aware if it isn't
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp >= cutoff
