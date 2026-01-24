"""Tests for webhook routes."""

import tempfile
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.config import TestingConfig


@pytest.fixture
def temp_storage_app() -> Flask:
    """Create app with temporary storage for testing EVENT processing."""
    app = create_app()
    app.config.from_object(TestingConfig)

    # Use a temp file for storage
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        app.config["LOCAL_DATA_PATH"] = f.name

    # Re-initialize storage with temp path
    from app.storage import init_storage
    from app.storage.local_storage import LocalStorage

    init_storage(LocalStorage(app.config["LOCAL_DATA_PATH"]))

    return app


@pytest.fixture
def storage_client(temp_storage_app: Flask) -> FlaskClient:
    """Create test client with storage enabled."""
    return temp_storage_app.test_client()


class TestWebhookRoutes:
    """Tests for SmartThings webhook lifecycle handlers."""

    def test_ping_lifecycle(self, client: FlaskClient, ping_payload: dict) -> None:
        """Test PING lifecycle returns challenge."""
        response = client.post("/webhook", json=ping_payload)

        assert response.status_code == 200
        assert response.json == {"pingData": {"challenge": "test-challenge-12345"}}

    def test_ping_with_different_challenge(self, client: FlaskClient) -> None:
        """Test PING returns the exact challenge provided."""
        payload = {"lifecycle": "PING", "pingData": {"challenge": "unique-challenge-abc"}}

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        assert response.json["pingData"]["challenge"] == "unique-challenge-abc"

    def test_event_lifecycle(self, client: FlaskClient, event_payload: dict) -> None:
        """Test EVENT lifecycle is accepted."""
        response = client.post("/webhook", json=event_payload)

        assert response.status_code == 200
        assert "eventData" in response.json

    def test_install_lifecycle(self, client: FlaskClient) -> None:
        """Test INSTALL lifecycle is accepted."""
        payload = {
            "lifecycle": "INSTALL",
            "installData": {
                "authToken": "test-token",
                "refreshToken": "test-refresh",
                "installedApp": {
                    "installedAppId": "test-app-id",
                    "locationId": "test-location-id",
                },
            },
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        assert "installData" in response.json

    def test_update_lifecycle(self, client: FlaskClient) -> None:
        """Test UPDATE lifecycle is accepted."""
        payload = {
            "lifecycle": "UPDATE",
            "updateData": {
                "authToken": "test-token",
                "refreshToken": "test-refresh",
            },
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        assert "updateData" in response.json

    def test_uninstall_lifecycle(self, client: FlaskClient) -> None:
        """Test UNINSTALL lifecycle is accepted."""
        payload = {"lifecycle": "UNINSTALL", "uninstallData": {}}

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        assert "uninstallData" in response.json

    def test_unknown_lifecycle(self, client: FlaskClient) -> None:
        """Test unknown lifecycle returns 400."""
        payload = {"lifecycle": "UNKNOWN"}

        response = client.post("/webhook", json=payload)

        assert response.status_code == 400
        assert "error" in response.json

    def test_missing_json_payload(self, client: FlaskClient) -> None:
        """Test request without JSON returns 415 (Unsupported Media Type)."""
        response = client.post("/webhook", data="not json", content_type="text/plain")

        assert response.status_code == 415

    def test_empty_json_payload(self, client: FlaskClient) -> None:
        """Test request with empty JSON returns 400."""
        response = client.post("/webhook", json={})

        assert response.status_code == 400


class TestEventProcessing:
    """Tests for EVENT lifecycle processing and storage."""

    def test_event_writes_humidity_reading(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that humidity events are written to storage."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
                            "capability": "relativeHumidityMeasurement",
                            "attribute": "humidity",
                            "value": 65,
                        },
                    }
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        # Verify reading was written
        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 1
            assert readings[0].reading_type == "humidity"
            assert readings[0].value == 65.0
            assert readings[0].device_label == "PuerHumidity"

    def test_event_writes_temperature_reading(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that temperature events are written to storage."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
                            "capability": "temperatureMeasurement",
                            "attribute": "temperature",
                            "value": 72.5,
                        },
                    }
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 1
            assert readings[0].reading_type == "temperature"
            assert readings[0].value == 72.5

    def test_event_handles_multiple_events(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that multiple events in one payload are all processed."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
                            "capability": "relativeHumidityMeasurement",
                            "attribute": "humidity",
                            "value": 65,
                        },
                    },
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "9a52da52-a841-4883-b91e-8d29b9a6d01d",
                            "capability": "temperatureMeasurement",
                            "attribute": "temperature",
                            "value": 72,
                        },
                    },
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 2

    def test_event_ignores_non_device_events(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that non-DEVICE_EVENT events are ignored."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "TIMER_EVENT",
                        "timerEvent": {"name": "some-timer"},
                    }
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 0

    def test_event_ignores_unknown_capabilities(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that unknown capabilities are ignored."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "device-123",
                            "capability": "switch",
                            "attribute": "switch",
                            "value": "on",
                        },
                    }
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 0

    def test_event_uses_device_id_as_fallback_label(
        self, storage_client: FlaskClient, temp_storage_app: Flask
    ) -> None:
        """Test that unknown device IDs use the ID as the label."""
        payload = {
            "lifecycle": "EVENT",
            "eventData": {
                "events": [
                    {
                        "eventType": "DEVICE_EVENT",
                        "deviceEvent": {
                            "deviceId": "unknown-device-xyz",
                            "capability": "relativeHumidityMeasurement",
                            "attribute": "humidity",
                            "value": 50,
                        },
                    }
                ]
            },
        }

        response = storage_client.post("/webhook", json=payload)

        assert response.status_code == 200

        with temp_storage_app.app_context():
            from app.storage import get_storage

            storage = get_storage()
            readings = storage.get_all_readings()
            assert len(readings) == 1
            assert readings[0].device_label == "unknown-device-xyz"