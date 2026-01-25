"""Seed local storage with data from the historical CSV file.

This script loads data from data/humidity_data.csv into the storage layer
for local development and testing.
"""

import csv
from datetime import datetime
from pathlib import Path

from app.models import SensorReading
from app.storage import get_storage, init_storage
from app.storage.local_storage import LocalStorage


# Device ID mapping (reverse of the label mapping)
DEVICE_IDS = {
    "PuerHumidity": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
    "ChestHumidity": "baee9df0-5635-4205-8e58-7de7eb5d88d4",
}


def parse_sensor_name(sensor_name: str) -> tuple[str, str]:
    """Parse composite sensor name into device_label and reading_type.

    Args:
        sensor_name: e.g., "PuerHumidity-Temperature"

    Returns:
        Tuple of (device_label, reading_type) e.g., ("PuerHumidity", "temperature")
    """
    parts = sensor_name.rsplit("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid sensor_name format: {sensor_name}")

    device_label = parts[0]
    reading_type = parts[1].lower()

    if reading_type not in ("temperature", "humidity"):
        raise ValueError(f"Unknown reading type: {reading_type}")

    return device_label, reading_type


def load_csv_data(csv_path: Path) -> list[SensorReading]:
    """Load readings from CSV file.

    Handles two CSV formats:
    - 3 columns: sensor_name,datetime,value (original Streamlit format)
    - 5 columns: device_id,device_label,reading_type,value,timestamp (new format)

    Args:
        csv_path: Path to the CSV file.

    Returns:
        List of SensorReading objects.
    """
    readings: list[SensorReading] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        # Read first line to detect format
        first_line = f.readline().strip()
        f.seek(0)  # Reset to beginning

        reader = csv.reader(f)
        header = next(reader)  # Skip header

        for row in reader:
            try:
                if len(row) == 3:
                    # Original format: sensor_name,datetime,value
                    sensor_name, dt_str, value_str = row
                    device_label, reading_type = parse_sensor_name(sensor_name)
                    device_id = DEVICE_IDS.get(device_label, f"unknown-{device_label}")
                    timestamp = datetime.fromisoformat(dt_str.replace(" ", "T"))
                    value = float(value_str)

                elif len(row) == 5:
                    # New format: device_id,device_label,reading_type,value,timestamp
                    device_id, device_label, reading_type, value_str, dt_str = row
                    reading_type = reading_type.lower()
                    if reading_type not in ("temperature", "humidity"):
                        continue  # Skip unknown reading types
                    timestamp = datetime.fromisoformat(dt_str)
                    value = float(value_str)

                else:
                    # Unknown format, skip
                    continue

                readings.append(
                    SensorReading(
                        device_id=device_id,
                        device_label=device_label,
                        reading_type=reading_type,  # type: ignore
                        value=value,
                        timestamp=timestamp,
                    )
                )
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue

    return readings


def seed_storage(csv_path: Path | None = None, target_path: Path | None = None) -> int:
    """Seed storage with data from CSV.

    Args:
        csv_path: Path to source CSV file (default: data/humidity_data.csv)
        target_path: Path for target storage file (default: data/readings.csv)

    Returns:
        Number of readings loaded.
    """
    if csv_path is None:
        csv_path = Path("data/humidity_data.csv")

    if target_path is None:
        target_path = Path("data/readings.csv")  # Use separate file to preserve original

    # Load readings from source CSV
    readings = load_csv_data(csv_path)

    # Delete the target file so LocalStorage creates a fresh one with proper headers
    if target_path.exists():
        target_path.unlink()

    # Initialize storage with target path (creates fresh file with headers)
    storage = LocalStorage(str(target_path))
    init_storage(storage)

    # Write all readings
    storage.write_readings(readings)

    return len(readings)


if __name__ == "__main__":
    import sys

    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    count = seed_storage(csv_path)
    print(f"Seeded {count} readings to storage")
