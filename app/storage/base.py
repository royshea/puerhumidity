"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod

from app.models import SensorReading


class StorageBase(ABC):
    """Abstract interface for sensor reading storage.

    All storage backends (local CSV, Azure Table Storage) must implement
    this interface to ensure consistent behavior across environments.
    """

    @abstractmethod
    def write_reading(self, reading: SensorReading) -> None:
        """Write a single sensor reading to storage.

        Args:
            reading: The sensor reading to store.
        """
        ...

    @abstractmethod
    def write_readings(self, readings: list[SensorReading]) -> int:
        """Write multiple sensor readings to storage.

        Args:
            readings: List of sensor readings to store.

        Returns:
            Number of readings successfully written.
        """
        ...

    @abstractmethod
    def get_readings(self, sensor_name: str, hours: int = 504) -> list[SensorReading]:
        """Get readings for a specific sensor within the time window.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of sensor readings, sorted by timestamp ascending.
        """
        ...

    @abstractmethod
    def get_all_readings(self, hours: int = 504) -> list[SensorReading]:
        """Get all readings within the time window.

        Args:
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of all sensor readings, sorted by timestamp ascending.
        """
        ...

    @abstractmethod
    def get_latest_reading(self, sensor_name: str) -> SensorReading | None:
        """Get the most recent reading for a specific sensor.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").

        Returns:
            The most recent reading, or None if no readings exist.
        """
        ...
