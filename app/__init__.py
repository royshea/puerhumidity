"""Flask application factory for PuerHumidity webhook server."""

import os

# Configure Azure Monitor telemetry before importing Flask (required by OpenTelemetry).
# Only activates when APPLICATIONINSIGHTS_CONNECTION_STRING is set (production).
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()

import logging
import sys

from flask import Flask

from app.config import DevelopmentConfig, ProductionConfig
from app.storage import init_storage
from app.storage.base import StorageBase


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: Configuration to use ('development', 'production', or None for default).

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Configure logging to stdout for Azure App Service
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    # Also ensure Flask's logger outputs to stdout
    app.logger.setLevel(logging.INFO)
    if not app.logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        app.logger.addHandler(handler)

    # Load configuration
    if config_name == "production":
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Initialize storage based on configuration
    storage = _create_storage(app)
    init_storage(storage)

    # Register blueprints
    from app.routes import register_blueprints

    register_blueprints(app)

    return app


def _create_storage(app: Flask) -> StorageBase:
    """Create the appropriate storage backend based on configuration.

    Args:
        app: Flask application with configuration loaded.

    Returns:
        Configured storage backend.
    """
    storage_type = app.config.get("STORAGE_TYPE", "local")

    if storage_type == "azure":
        from app.storage.table_storage import TableStorage

        account_name = app.config.get("AZURE_STORAGE_ACCOUNT_NAME")
        if not account_name:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME required for azure storage")
        account_url = f"https://{account_name}.table.core.windows.net"
        table_name = app.config.get("AZURE_TABLE_NAME", "sensorreadings")
        return TableStorage(account_url=account_url, table_name=table_name)
    else:
        from app.storage.local_storage import LocalStorage

        data_path = app.config.get("LOCAL_DATA_PATH", "data/humidity_data.csv")
        return LocalStorage(data_path)


# Create app instance for WSGI servers (gunicorn, etc.)
# Usage: gunicorn "app:application"
application = create_app()
