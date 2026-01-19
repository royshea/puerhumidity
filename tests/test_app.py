"""Tests for Flask application factory."""

from flask import Flask

from app import create_app


class TestCreateApp:
    """Tests for create_app factory function."""

    def test_create_app_default(self) -> None:
        """Test creating app with default config (development)."""
        app = create_app()

        assert isinstance(app, Flask)
        assert app.config["DEBUG"] is True

    def test_create_app_development(self) -> None:
        """Test creating app with development config."""
        app = create_app("development")

        assert isinstance(app, Flask)
        assert app.config["DEBUG"] is True

    def test_create_app_production(self) -> None:
        """Test creating app with production config."""
        app = create_app("production")

        assert isinstance(app, Flask)
        assert app.config["DEBUG"] is False

    def test_health_endpoint_registered(self) -> None:
        """Test that health endpoint is registered."""
        app = create_app()
        client = app.test_client()

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json == {"status": "ok"}

    def test_webhook_endpoint_registered(self) -> None:
        """Test that webhook endpoint is registered."""
        app = create_app()
        client = app.test_client()

        response = client.post("/webhook", json={"lifecycle": "PING", "pingData": {"challenge": "test"}})

        assert response.status_code == 200
