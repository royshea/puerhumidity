"""Azure Table Storage backend implementation."""

from datetime import datetime, timedelta, timezone

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, TableServiceClient

from app.models import SensorReading
from app.storage.base import StorageBase


class TableStorage(StorageBase):
    """Azure Table Storage backend for production use.

    Uses reverse timestamps in RowKey for efficient "most recent first" queries.
    Schema:
        - PartitionKey: sensor_name (e.g., "PuerHumidity-Humidity")
        - RowKey: reverse timestamp (9999999999 - unix_timestamp)
        - value: float
        - timestamp: ISO format string
        - device_id: str
        - device_label: str
        - reading_type: str
    """

    # Max timestamp for reverse calculation (year 2286)
    MAX_TIMESTAMP = 9999999999

    def __init__(self, connection_string: str, table_name: str = "sensorreadings") -> None:
        """Initialize Azure Table Storage.

        Args:
            connection_string: Azure Storage connection string.
            table_name: Name of the table to use.
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self._table_client: TableClient | None = None
        self._ensure_table_exists()

    def _get_table_client(self) -> TableClient:
        """Get or create the table client.

        Returns:
            TableClient instance.
        """
        if self._table_client is None:
            service_client = TableServiceClient.from_connection_string(self.connection_string)
            self._table_client = service_client.get_table_client(self.table_name)
        return self._table_client

    def _ensure_table_exists(self) -> None:
        """Create the table if it doesn't exist."""
        service_client = TableServiceClient.from_connection_string(self.connection_string)
        try:
            service_client.create_table(self.table_name)
        except ResourceNotFoundError:
            # Table already exists, which is fine
            pass
        except Exception as e:
            # For Azurite or if table exists, we might get a different error
            if "TableAlreadyExists" not in str(e):
                raise

    def _make_row_key(self, timestamp: datetime) -> str:
        """Create a reverse timestamp row key for descending sort order.

        Args:
            timestamp: The reading timestamp.

        Returns:
            Reverse timestamp string for RowKey.
        """
        # Ensure timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        unix_ts = int(timestamp.timestamp())
        reverse_ts = self.MAX_TIMESTAMP - unix_ts
        return f"{reverse_ts:010d}"

    def _parse_row_key(self, row_key: str) -> datetime:
        """Parse a reverse timestamp row key back to datetime.

        Args:
            row_key: The RowKey string.

        Returns:
            Original datetime.
        """
        reverse_ts = int(row_key)
        unix_ts = self.MAX_TIMESTAMP - reverse_ts
        return datetime.fromtimestamp(unix_ts, tz=timezone.utc)

    def write_reading(self, reading: SensorReading) -> None:
        """Write a single sensor reading to Table Storage.

        Args:
            reading: The sensor reading to store.
        """
        entity = {
            "PartitionKey": reading.sensor_name,
            "RowKey": self._make_row_key(reading.timestamp),
            "value": reading.value,
            "timestamp": reading.timestamp.isoformat(),
            "device_id": reading.device_id,
            "device_label": reading.device_label,
            "reading_type": reading.reading_type,
        }
        self._get_table_client().upsert_entity(entity)

    def write_readings(self, readings: list[SensorReading]) -> int:
        """Write multiple sensor readings to Table Storage using batch operations.

        Azure Table Storage batches require all entities to share the same PartitionKey,
        so we group readings by sensor_name (which is the PartitionKey) and batch within
        each group. Max 100 entities per batch.

        Args:
            readings: List of sensor readings to store.

        Returns:
            Number of readings successfully written.
        """
        if not readings:
            return 0

        # Group readings by PartitionKey (sensor_name)
        from collections import defaultdict
        partitions: dict[str, list[SensorReading]] = defaultdict(list)
        for reading in readings:
            partitions[reading.sensor_name].append(reading)

        written_count = 0
        table_client = self._get_table_client()

        for partition_key, partition_readings in partitions.items():
            # Process in batches of 100 (Azure Table Storage limit)
            batch_size = 100
            for i in range(0, len(partition_readings), batch_size):
                batch_readings = partition_readings[i : i + batch_size]
                
                # Build batch operations
                operations = []
                for reading in batch_readings:
                    entity = {
                        "PartitionKey": reading.sensor_name,
                        "RowKey": self._make_row_key(reading.timestamp),
                        "value": reading.value,
                        "timestamp": reading.timestamp.isoformat(),
                        "device_id": reading.device_id,
                        "device_label": reading.device_label,
                        "reading_type": reading.reading_type,
                    }
                    operations.append(("upsert", entity))

                # Submit batch
                try:
                    table_client.submit_transaction(operations)
                    written_count += len(batch_readings)
                except Exception as e:
                    # If batch fails, fall back to individual writes
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        "Batch write failed for partition %s, falling back to individual writes: %s",
                        partition_key,
                        e,
                    )
                    for reading in batch_readings:
                        try:
                            self.write_reading(reading)
                            written_count += 1
                        except Exception:
                            pass

        return written_count

    def get_readings(self, sensor_name: str, hours: int = 504) -> list[SensorReading]:
        """Get readings for a specific sensor within the time window.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of sensor readings, sorted by timestamp ascending.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_row_key = self._make_row_key(cutoff)

        # RowKey < cutoff_row_key means timestamp > cutoff (due to reverse)
        filter_query = f"PartitionKey eq '{sensor_name}' and RowKey lt '{cutoff_row_key}'"

        readings = []
        for entity in self._get_table_client().query_entities(filter_query):
            reading = self._entity_to_reading(entity)
            readings.append(reading)

        # Sort by timestamp ascending (Table Storage returns by RowKey ascending = newest first)
        return sorted(readings, key=lambda r: r.timestamp)

    def get_all_readings(self, hours: int = 504) -> list[SensorReading]:
        """Get all readings within the time window.

        Args:
            hours: Number of hours to look back (default 504 = 3 weeks).

        Returns:
            List of all sensor readings, sorted by timestamp ascending.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_row_key = self._make_row_key(cutoff)

        # Query all partitions where RowKey is within the time window
        filter_query = f"RowKey lt '{cutoff_row_key}'"

        readings = []
        for entity in self._get_table_client().query_entities(filter_query):
            reading = self._entity_to_reading(entity)
            readings.append(reading)

        return sorted(readings, key=lambda r: r.timestamp)

    def get_latest_reading(self, sensor_name: str) -> SensorReading | None:
        """Get the most recent reading for a specific sensor.

        Args:
            sensor_name: The composite sensor name (e.g., "PuerHumidity-Humidity").

        Returns:
            The most recent reading, or None if no readings exist.
        """
        # Query with top=1, sorted by RowKey ascending (which is newest first due to reverse)
        filter_query = f"PartitionKey eq '{sensor_name}'"

        for entity in self._get_table_client().query_entities(
            filter_query, results_per_page=1
        ):
            return self._entity_to_reading(entity)

        return None

    def _entity_to_reading(self, entity: dict[str, object]) -> SensorReading:
        """Convert a Table Storage entity to a SensorReading.

        Args:
            entity: The entity dictionary from Table Storage.

        Returns:
            SensorReading instance.
        """
        timestamp_str = entity["timestamp"]
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str)
        elif isinstance(timestamp_str, datetime):
            timestamp = timestamp_str
        else:
            raise ValueError(f"Invalid timestamp type: {type(timestamp_str)}")

        # Ensure timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        reading_type = entity["reading_type"]
        if reading_type not in ("temperature", "humidity"):
            raise ValueError(f"Invalid reading_type: {reading_type}")

        return SensorReading(
            device_id=str(entity["device_id"]),
            device_label=str(entity["device_label"]),
            reading_type=reading_type,  # type: ignore[arg-type]
            value=float(entity["value"]),  # type: ignore[arg-type]
            timestamp=timestamp,
        )
