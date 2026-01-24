"""Tests for storage backends."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import SensorReading
from app.storage.base import StorageBase
from app.storage.local_storage import LocalStorage


class TestLocalStorage:
    """Tests for LocalStorage CSV-backed implementation."""

    @pytest.fixture
    def temp_csv(self) -> Path:
        """Create a temporary CSV file path."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def storage(self, temp_csv: Path) -> LocalStorage:
        """Create a LocalStorage instance with a temp file."""
        return LocalStorage(temp_csv)

    @pytest.fixture
    def sample_reading(self) -> SensorReading:
        """Create a sample sensor reading."""
        return SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.0,
            timestamp=datetime.now(timezone.utc),
        )

    def test_implements_storage_base(self, storage: LocalStorage) -> None:
        """Test that LocalStorage implements StorageBase interface."""
        assert isinstance(storage, StorageBase)

    def test_creates_file_on_init(self, temp_csv: Path) -> None:
        """Test that storage creates CSV file if it doesn't exist."""
        # Delete the temp file first
        temp_csv.unlink(missing_ok=True)
        assert not temp_csv.exists()

        # Create storage - should create the file
        LocalStorage(temp_csv)
        assert temp_csv.exists()

    def test_creates_parent_directories(self) -> None:
        """Test that storage creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "subdir" / "nested" / "data.csv"
            LocalStorage(nested_path)
            assert nested_path.exists()

    def test_write_reading(self, storage: LocalStorage, sample_reading: SensorReading) -> None:
        """Test writing a single reading."""
        storage.write_reading(sample_reading)

        readings = storage.get_all_readings()
        assert len(readings) == 1
        assert readings[0].device_id == sample_reading.device_id
        assert readings[0].value == sample_reading.value

    def test_write_readings_batch(self, storage: LocalStorage) -> None:
        """Test writing multiple readings at once."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="Sensor1",
                reading_type="humidity",
                value=60.0 + i,
                timestamp=now + timedelta(hours=i),
            )
            for i in range(5)
        ]

        storage.write_readings(readings)

        result = storage.get_all_readings()
        assert len(result) == 5

    def test_get_readings_filters_by_sensor_name(self, storage: LocalStorage) -> None:
        """Test that get_readings filters by sensor name."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="PuerHumidity",
                reading_type="humidity",
                value=65.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-1",
                device_label="PuerHumidity",
                reading_type="temperature",
                value=72.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-2",
                device_label="ChestHumidity",
                reading_type="humidity",
                value=55.0,
                timestamp=now,
            ),
        ]
        storage.write_readings(readings)

        humidity_readings = storage.get_readings("PuerHumidity-Humidity")
        assert len(humidity_readings) == 1
        assert humidity_readings[0].value == 65.0

        temp_readings = storage.get_readings("PuerHumidity-Temperature")
        assert len(temp_readings) == 1
        assert temp_readings[0].value == 72.0

    def test_get_readings_filters_by_time(self, storage: LocalStorage) -> None:
        """Test that get_readings respects the hours parameter."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now - timedelta(hours=2),  # 2 hours ago
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=66.0,
                timestamp=now - timedelta(hours=48),  # 48 hours ago
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=100),  # 100 hours ago
            ),
        ]
        storage.write_readings(readings)

        # Get last 24 hours
        recent = storage.get_readings("TestSensor-Humidity", hours=24)
        assert len(recent) == 1
        assert recent[0].value == 65.0

        # Get last 72 hours
        more = storage.get_readings("TestSensor-Humidity", hours=72)
        assert len(more) == 2

        # Get all (504 hours default)
        all_readings = storage.get_readings("TestSensor-Humidity")
        assert len(all_readings) == 3

    def test_get_readings_sorted_by_timestamp(self, storage: LocalStorage) -> None:
        """Test that readings are returned sorted by timestamp ascending."""
        now = datetime.now(timezone.utc)
        # Write in random order
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=66.0,
                timestamp=now - timedelta(hours=1),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=3),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now,
            ),
        ]
        storage.write_readings(readings)

        result = storage.get_readings("TestSensor-Humidity")
        assert result[0].value == 67.0  # Oldest first
        assert result[1].value == 66.0
        assert result[2].value == 65.0  # Newest last

    def test_get_all_readings(self, storage: LocalStorage) -> None:
        """Test getting all readings across sensors."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="Sensor1",
                reading_type="humidity",
                value=65.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-2",
                device_label="Sensor2",
                reading_type="temperature",
                value=72.0,
                timestamp=now,
            ),
        ]
        storage.write_readings(readings)

        result = storage.get_all_readings()
        assert len(result) == 2

    def test_get_latest_reading(self, storage: LocalStorage) -> None:
        """Test getting the most recent reading for a sensor."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now - timedelta(hours=2),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=70.0,
                timestamp=now,  # Most recent
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=1),
            ),
        ]
        storage.write_readings(readings)

        latest = storage.get_latest_reading("TestSensor-Humidity")
        assert latest is not None
        assert latest.value == 70.0

    def test_get_latest_reading_returns_none_for_empty(self, storage: LocalStorage) -> None:
        """Test that get_latest_reading returns None when no readings exist."""
        result = storage.get_latest_reading("NonExistent-Humidity")
        assert result is None

    def test_get_readings_empty_result(self, storage: LocalStorage) -> None:
        """Test that get_readings returns empty list for non-existent sensor."""
        result = storage.get_readings("NonExistent-Humidity")
        assert result == []

    def test_raises_error_on_malformed_rows(self, temp_csv: Path) -> None:
        """Test that malformed CSV rows raise an error."""
        # Write valid header and some invalid data
        with open(temp_csv, "w", newline="", encoding="utf-8") as f:
            f.write("device_id,device_label,reading_type,value,timestamp\n")
            f.write("device-1,TestSensor,humidity,65.0,2026-01-17T12:00:00\n")
            f.write("bad,data,invalid\n")  # Malformed row

        storage = LocalStorage(temp_csv)

        with pytest.raises((KeyError, ValueError)):
            storage.get_all_readings()


class TestTableStorage:
    """Tests for TableStorage Azure Table Storage implementation.

    These tests require Azurite (Azure Storage Emulator) to be running:
        azurite --silent --location .azurite

    Tests are skipped if Azurite is not available.
    """

    AZURITE_CONNECTION_STRING = (
        "DefaultEndpointsProtocol=http;"
        "AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
    )

    @pytest.fixture
    def table_storage(self) -> "TableStorage | None":
        """Create a TableStorage instance connected to Azurite.

        Returns None if Azurite is not available.
        """
        from app.storage.table_storage import TableStorage

        # Use a unique table name for each test run to avoid conflicts
        import uuid

        table_name = f"test{uuid.uuid4().hex[:8]}"

        try:
            storage = TableStorage(self.AZURITE_CONNECTION_STRING, table_name)
            return storage
        except Exception:
            pytest.skip("Azurite not available - skipping Table Storage tests")
            return None

    @pytest.fixture
    def cleanup_table(self, table_storage: "TableStorage | None"):
        """Cleanup fixture to delete test table after test."""
        yield table_storage
        if table_storage is not None:
            try:
                from azure.data.tables import TableServiceClient

                service = TableServiceClient.from_connection_string(
                    self.AZURITE_CONNECTION_STRING
                )
                service.delete_table(table_storage.table_name)
            except Exception:
                pass  # Best effort cleanup

    def test_implements_storage_base(self, table_storage: "TableStorage", cleanup_table) -> None:
        """Test that TableStorage implements StorageBase interface."""
        from app.storage.base import StorageBase

        assert isinstance(table_storage, StorageBase)

    def test_write_and_read_reading(self, table_storage: "TableStorage", cleanup_table) -> None:
        """Test writing and reading a single reading."""
        now = datetime.now(timezone.utc)
        reading = SensorReading(
            device_id="device-123",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.0,
            timestamp=now,
        )

        table_storage.write_reading(reading)

        readings = table_storage.get_all_readings()
        assert len(readings) == 1
        assert readings[0].device_id == reading.device_id
        assert readings[0].value == reading.value

    def test_write_readings_batch(self, table_storage: "TableStorage", cleanup_table) -> None:
        """Test writing multiple readings at once."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="Sensor1",
                reading_type="humidity",
                value=60.0 + i,
                timestamp=now + timedelta(hours=i),
            )
            for i in range(5)
        ]

        table_storage.write_readings(readings)

        result = table_storage.get_all_readings()
        assert len(result) == 5

    def test_get_readings_filters_by_sensor_name(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that get_readings filters by sensor name."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="PuerHumidity",
                reading_type="humidity",
                value=65.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-1",
                device_label="PuerHumidity",
                reading_type="temperature",
                value=72.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-2",
                device_label="ChestHumidity",
                reading_type="humidity",
                value=55.0,
                timestamp=now,
            ),
        ]
        table_storage.write_readings(readings)

        humidity_readings = table_storage.get_readings("PuerHumidity-Humidity")
        assert len(humidity_readings) == 1
        assert humidity_readings[0].value == 65.0

    def test_get_readings_filters_by_time(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that get_readings respects the hours parameter."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now - timedelta(hours=2),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=66.0,
                timestamp=now - timedelta(hours=48),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=100),
            ),
        ]
        table_storage.write_readings(readings)

        # Get last 24 hours
        recent = table_storage.get_readings("TestSensor-Humidity", hours=24)
        assert len(recent) == 1
        assert recent[0].value == 65.0

        # Get last 72 hours
        more = table_storage.get_readings("TestSensor-Humidity", hours=72)
        assert len(more) == 2

    def test_get_readings_sorted_by_timestamp(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that readings are returned sorted by timestamp ascending."""
        now = datetime.now(timezone.utc)
        # Write in random order
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=66.0,
                timestamp=now - timedelta(hours=1),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=3),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now,
            ),
        ]
        table_storage.write_readings(readings)

        result = table_storage.get_readings("TestSensor-Humidity")
        assert result[0].value == 67.0  # Oldest first
        assert result[1].value == 66.0
        assert result[2].value == 65.0  # Newest last

    def test_get_latest_reading(self, table_storage: "TableStorage", cleanup_table) -> None:
        """Test getting the most recent reading for a sensor."""
        now = datetime.now(timezone.utc)
        readings = [
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=65.0,
                timestamp=now - timedelta(hours=2),
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=70.0,
                timestamp=now,
            ),
            SensorReading(
                device_id="device-1",
                device_label="TestSensor",
                reading_type="humidity",
                value=67.0,
                timestamp=now - timedelta(hours=1),
            ),
        ]
        table_storage.write_readings(readings)

        latest = table_storage.get_latest_reading("TestSensor-Humidity")
        assert latest is not None
        assert latest.value == 70.0

    def test_get_latest_reading_returns_none_for_empty(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that get_latest_reading returns None when no readings exist."""
        result = table_storage.get_latest_reading("NonExistent-Humidity")
        assert result is None

    def test_reverse_timestamp_ordering(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that reverse timestamp produces correct ordering."""
        # Verify the row key calculation
        earlier = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        later = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

        earlier_key = table_storage._make_row_key(earlier)
        later_key = table_storage._make_row_key(later)

        # Earlier time should have LARGER row key (for descending sort)
        assert earlier_key > later_key

    def test_upsert_overwrites_duplicate_timestamps(
        self, table_storage: "TableStorage", cleanup_table
    ) -> None:
        """Test that writing same timestamp twice overwrites the value."""
        now = datetime.now(timezone.utc)

        reading1 = SensorReading(
            device_id="device-1",
            device_label="TestSensor",
            reading_type="humidity",
            value=65.0,
            timestamp=now,
        )
        reading2 = SensorReading(
            device_id="device-1",
            device_label="TestSensor",
            reading_type="humidity",
            value=70.0,
            timestamp=now,  # Same timestamp
        )

        table_storage.write_reading(reading1)
        table_storage.write_reading(reading2)

        readings = table_storage.get_all_readings()
        assert len(readings) == 1
        assert readings[0].value == 70.0  # Second value wins