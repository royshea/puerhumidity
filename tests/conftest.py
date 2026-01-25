"""Pytest fixtures for PuerHumidity tests."""

from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.config import TestingConfig
from app.models import SensorReading


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Create application for testing.

    Yields:
        Flask application configured for testing.
    """
    app = create_app("development")
    app.config.from_object(TestingConfig)
    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create test client.

    Args:
        app: Flask application fixture.

    Returns:
        Flask test client.
    """
    return app.test_client()


@pytest.fixture
def sample_reading() -> SensorReading:
    """Create a sample sensor reading.

    Returns:
        SensorReading with sample data.
    """
    return SensorReading(
        device_id="9a52da52-a841-4883-b91e-8d29b9a6d01d",
        device_label="PuerHumidity",
        reading_type="humidity",
        value=65.0,
        timestamp=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_readings() -> list[SensorReading]:
    """Create a list of sample sensor readings.

    Returns:
        List of SensorReading objects spanning 24 hours.
    """
    base_time = datetime(2026, 1, 17, 0, 0, 0)
    readings = []

    for i in range(24):
        # Humidity reading
        readings.append(
            SensorReading(
                device_id="9a52da52-a841-4883-b91e-8d29b9a6d01d",
                device_label="PuerHumidity",
                reading_type="humidity",
                value=60.0 + (i % 10),
                timestamp=base_time + timedelta(hours=i),
            )
        )
        # Temperature reading
        readings.append(
            SensorReading(
                device_id="9a52da52-a841-4883-b91e-8d29b9a6d01d",
                device_label="PuerHumidity",
                reading_type="temperature",
                value=68.0 + (i % 5),
                timestamp=base_time + timedelta(hours=i),
            )
        )

    return readings


@pytest.fixture
def ping_payload() -> dict:
    """Create a sample PING lifecycle payload.

    Returns:
        Dictionary representing a PING webhook payload.
    """
    return {"lifecycle": "PING", "pingData": {"challenge": "test-challenge-12345"}}


@pytest.fixture
def event_payload() -> dict:
    """Create a sample EVENT lifecycle payload.

    Returns:
        Dictionary representing an EVENT webhook payload with a humidity reading.
    """
    return {
        "lifecycle": "EVENT",
        "eventData": {
            "authToken": "test-token",
            "installedApp": {
                "installedAppId": "55713660-1f57-4338-81e0-3c45479b2279",
                "locationId": "9ec8c9fc-3af2-464f-b917-d0403ab0c4bb",
            },
            "events": [
                {
                    "eventType": "DEVICE_EVENT",
                    "deviceEvent": {
                        "subscriptionName": "humidity_sensors",
                        "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
                        "componentId": "main",
                        "capability": "relativeHumidityMeasurement",
                        "attribute": "humidity",
                        "value": 65,
                        "stateChange": True,
                    },
                }
            ],
        },
    }
