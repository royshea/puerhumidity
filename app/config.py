"""Configuration classes for different environments."""

import os
from typing import Any


class Config:
    """Base configuration with defaults."""

    # Flask settings
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG: bool = False
    TESTING: bool = False

    # Storage settings
    STORAGE_TYPE: str = os.environ.get("STORAGE_TYPE", "local")
    LOCAL_DATA_PATH: str = os.environ.get("LOCAL_DATA_PATH", "data/readings.csv")

    # Azure Table Storage settings
    AZURE_STORAGE_ACCOUNT_NAME: str | None = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    AZURE_TABLE_NAME: str = os.environ.get("AZURE_TABLE_NAME", "sensorreadings")

    # SmartThings settings
    SMARTTHINGS_API_BASE: str = "https://api.smartthings.com/v1"

    # Device label mapping (JSON string from env, or default)
    DEVICE_LABELS: dict[str, str] = {
        "9a52da52-a841-4883-b91e-8d29b9a6d01d": "PuerHumidity",
        "baee9df0-5635-4205-8e58-7de7eb5d88d4": "ChestHumidity",
    }

    @classmethod
    def init_app(cls, app: Any) -> None:
        """Initialize application-specific configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG: bool = True
    STORAGE_TYPE: str = os.environ.get("STORAGE_TYPE", "local")


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG: bool = False
    STORAGE_TYPE: str = os.environ.get("STORAGE_TYPE", "azure")

    @classmethod
    def init_app(cls, app: Any) -> None:
        """Validate production configuration."""
        if cls.STORAGE_TYPE == "azure" and not cls.AZURE_STORAGE_ACCOUNT_NAME:
            raise ValueError(
                "AZURE_STORAGE_ACCOUNT_NAME must be set in production with azure storage"
            )
        if not os.environ.get("SECRET_KEY"):
            raise ValueError(
                "SECRET_KEY environment variable must be set in production"
            )


class TestingConfig(Config):
    """Testing configuration."""

    TESTING: bool = True
    DEBUG: bool = True
    STORAGE_TYPE: str = "local"
    LOCAL_DATA_PATH: str = "tests/data/test_humidity_data.csv"
