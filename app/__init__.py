"""Flask application factory for PuerHumidity webhook server."""

from flask import Flask

from app.config import Config, DevelopmentConfig, ProductionConfig


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: Configuration to use ('development', 'production', or None for default).

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Load configuration
    if config_name == "production":
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Register blueprints
    from app.routes import register_blueprints

    register_blueprints(app)

    return app
