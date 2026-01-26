#!/usr/bin/env python3
"""
Migrate historical data from local CSV to Azure Table Storage.

This script reads readings from the local CSV file and writes them to
Azure Table Storage using batch operations for efficiency.

Usage:
    python scripts/migrate_csv.py

Environment variables required:
    AZURE_STORAGE_CONNECTION_STRING - Azure Storage connection string
    
Or set in .env file.
"""

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

from app.models import SensorReading
from app.storage.table_storage import TableStorage


def load_readings_from_csv(csv_path: Path) -> list[SensorReading]:
    """Load sensor readings from a CSV file.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        List of SensorReading objects.
    """
    readings: list[SensorReading] = []

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse timestamp - add UTC timezone if missing
            timestamp_str = row["timestamp"]
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except ValueError as e:
                print(f"Skipping row with invalid timestamp: {timestamp_str} - {e}")
                continue

            # Validate reading_type
            reading_type = row["reading_type"]
            if reading_type not in ("temperature", "humidity"):
                print(f"Skipping row with invalid reading_type: {reading_type}")
                continue

            reading = SensorReading(
                device_id=row["device_id"],
                device_label=row["device_label"],
                reading_type=reading_type,  # type: ignore
                value=float(row["value"]),
                timestamp=timestamp,
            )
            readings.append(reading)

    return readings


def main() -> int:
    """Main entry point for the migration script."""
    # Load environment variables
    load_dotenv()

    # Check for required environment variable
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("ERROR: AZURE_STORAGE_CONNECTION_STRING environment variable not set.")
        print("Set it in your .env file or environment.")
        return 1

    # Determine CSV path
    csv_path = project_root / "data" / "readings.csv"
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return 1

    print(f"Loading readings from: {csv_path}")
    readings = load_readings_from_csv(csv_path)
    print(f"Loaded {len(readings)} readings from CSV")

    if not readings:
        print("No readings to migrate.")
        return 0

    # Show date range
    timestamps = [r.timestamp for r in readings]
    earliest = min(timestamps)
    latest = max(timestamps)
    print(f"Date range: {earliest.isoformat()} to {latest.isoformat()}")

    # Confirm before proceeding
    table_name = os.getenv("AZURE_TABLE_NAME", "sensorreadings")
    print(f"\nTarget table: {table_name}")
    response = input("Proceed with migration? (y/N): ").strip().lower()
    if response != "y":
        print("Migration cancelled.")
        return 0

    # Initialize storage and write
    print("\nInitializing Azure Table Storage...")
    storage = TableStorage(connection_string, table_name)

    print("Writing readings to Azure Table Storage...")
    written_count = storage.write_readings(readings)

    print(f"\nMigration complete!")
    print(f"  Total readings in CSV: {len(readings)}")
    print(f"  Successfully written:  {written_count}")

    if written_count < len(readings):
        print(f"  Failed: {len(readings) - written_count}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
