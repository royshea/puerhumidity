"""Tests for SmartThings service."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services import SmartThingsService


class TestSmartThingsService:
    """Tests for SmartThingsService subscription management."""

    @pytest.fixture
    def service(self) -> SmartThingsService:
        """Create a SmartThingsService instance."""
        return SmartThingsService(api_base="https://api.smartthings.com/v1")

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create a mock successful response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "sub-123", "sourceType": "CAPABILITY"}
        return response

    def test_init_default_api_base(self) -> None:
        """Test service initializes with default API base."""
        service = SmartThingsService()
        assert service.api_base == "https://api.smartthings.com/v1"

    def test_init_custom_api_base(self) -> None:
        """Test service accepts custom API base."""
        service = SmartThingsService(api_base="https://custom.api.com/v2/")
        assert service.api_base == "https://custom.api.com/v2"  # trailing slash stripped

    def test_capabilities_defined(self, service: SmartThingsService) -> None:
        """Test that required capabilities are defined."""
        capabilities = dict(service.CAPABILITIES)
        assert "relativeHumidityMeasurement" in capabilities
        assert "temperatureMeasurement" in capabilities
        assert capabilities["relativeHumidityMeasurement"] == "humidity"
        assert capabilities["temperatureMeasurement"] == "temperature"

    @patch("app.services.smartthings.requests.post")
    def test_create_subscriptions_success(
        self, mock_post: MagicMock, service: SmartThingsService, mock_response: MagicMock
    ) -> None:
        """Test successful subscription creation."""
        mock_post.return_value = mock_response

        results = service.create_subscriptions(
            installed_app_id="app-123",
            location_id="loc-456",
            auth_token="token-789",
        )

        # Should create subscriptions for both capabilities
        assert len(results) == 2
        assert mock_post.call_count == 2

        # Verify API calls
        calls = mock_post.call_args_list
        for call in calls:
            assert call.kwargs["headers"]["Authorization"] == "Bearer token-789"
            assert "installedapps/app-123/subscriptions" in call.args[0]

    @patch("app.services.smartthings.requests.post")
    def test_create_subscriptions_request_body(
        self, mock_post: MagicMock, service: SmartThingsService, mock_response: MagicMock
    ) -> None:
        """Test subscription request body format."""
        mock_post.return_value = mock_response

        service.create_subscriptions(
            installed_app_id="app-123",
            location_id="loc-456",
            auth_token="token-789",
        )

        # Check first call (humidity)
        first_call = mock_post.call_args_list[0]
        body = first_call.kwargs["json"]
        assert body["sourceType"] == "CAPABILITY"
        assert body["capability"]["locationId"] == "loc-456"
        assert body["capability"]["capability"] == "relativeHumidityMeasurement"
        assert body["capability"]["attribute"] == "humidity"
        assert body["capability"]["value"] == "*"
        assert body["capability"]["stateChangeOnly"] is True

        # Check second call (temperature)
        second_call = mock_post.call_args_list[1]
        body = second_call.kwargs["json"]
        assert body["capability"]["capability"] == "temperatureMeasurement"
        assert body["capability"]["attribute"] == "temperature"

    @patch("app.services.smartthings.requests.post")
    def test_create_subscriptions_api_error(
        self, mock_post: MagicMock, service: SmartThingsService
    ) -> None:
        """Test subscription creation handles API errors."""
        mock_post.side_effect = requests.RequestException("API Error")

        with pytest.raises(requests.RequestException):
            service.create_subscriptions(
                installed_app_id="app-123",
                location_id="loc-456",
                auth_token="token-789",
            )

    @patch("app.services.smartthings.requests.delete")
    def test_delete_all_subscriptions_success(
        self, mock_delete: MagicMock, service: SmartThingsService
    ) -> None:
        """Test successful deletion of all subscriptions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        service.delete_all_subscriptions(
            installed_app_id="app-123",
            auth_token="token-789",
        )

        mock_delete.assert_called_once()
        call = mock_delete.call_args
        assert "installedapps/app-123/subscriptions" in call.args[0]
        assert call.kwargs["headers"]["Authorization"] == "Bearer token-789"

    @patch("app.services.smartthings.requests.delete")
    def test_delete_all_subscriptions_api_error(
        self, mock_delete: MagicMock, service: SmartThingsService
    ) -> None:
        """Test subscription deletion handles API errors."""
        mock_delete.side_effect = requests.RequestException("API Error")

        with pytest.raises(requests.RequestException):
            service.delete_all_subscriptions(
                installed_app_id="app-123",
                auth_token="token-789",
            )


class TestWebhookInstallHandler:
    """Tests for INSTALL lifecycle handler with subscription creation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import create_app

        app = create_app()
        return app.test_client()

    @patch("app.routes.webhook.SmartThingsService")
    def test_install_creates_subscriptions(
        self, mock_service_class: MagicMock, client
    ) -> None:
        """Test INSTALL lifecycle creates subscriptions."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        payload = {
            "lifecycle": "INSTALL",
            "installData": {
                "authToken": "install-token-123",
                "installedApp": {
                    "installedAppId": "app-abc",
                    "locationId": "loc-xyz",
                },
            },
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        mock_service.create_subscriptions.assert_called_once_with(
            "app-abc", "loc-xyz", "install-token-123"
        )

    @patch("app.routes.webhook.SmartThingsService")
    def test_install_missing_auth_token(
        self, mock_service_class: MagicMock, client
    ) -> None:
        """Test INSTALL handles missing auth token gracefully."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        payload = {
            "lifecycle": "INSTALL",
            "installData": {
                "installedApp": {
                    "installedAppId": "app-abc",
                    "locationId": "loc-xyz",
                },
            },
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        mock_service.create_subscriptions.assert_not_called()


class TestWebhookUpdateHandler:
    """Tests for UPDATE lifecycle handler with subscription recreation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import create_app

        app = create_app()
        return app.test_client()

    @patch("app.routes.webhook.SmartThingsService")
    def test_update_recreates_subscriptions(
        self, mock_service_class: MagicMock, client
    ) -> None:
        """Test UPDATE lifecycle deletes and recreates subscriptions."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        payload = {
            "lifecycle": "UPDATE",
            "authToken": "update-token-456",
            "updateData": {
                "installedApp": {
                    "installedAppId": "app-abc",
                    "locationId": "loc-xyz",
                },
            },
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        mock_service.delete_all_subscriptions.assert_called_once_with(
            "app-abc", "update-token-456"
        )
        mock_service.create_subscriptions.assert_called_once_with(
            "app-abc", "loc-xyz", "update-token-456"
        )

    @patch("app.routes.webhook.SmartThingsService")
    def test_update_handles_service_error(
        self, mock_service_class: MagicMock, client
    ) -> None:
        """Test UPDATE handles service errors gracefully."""
        mock_service = MagicMock()
        mock_service.delete_all_subscriptions.side_effect = Exception("API Error")
        mock_service_class.return_value = mock_service

        payload = {
            "lifecycle": "UPDATE",
            "authToken": "update-token-456",
            "updateData": {
                "installedApp": {
                    "installedAppId": "app-abc",
                    "locationId": "loc-xyz",
                },
            },
        }

        response = client.post("/webhook", json=payload)

        # Should still return 200 - don't fail the webhook
        assert response.status_code == 200
