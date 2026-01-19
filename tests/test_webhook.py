"""Tests for webhook routes."""

from flask.testing import FlaskClient


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
