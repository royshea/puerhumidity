"""Route blueprints for PuerHumidity."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask app.

    Args:
        app: Flask application instance.
    """
    from app.routes.health import health_bp
    from app.routes.import_data import import_bp
    from app.routes.ui import ui_bp
    from app.routes.webhook import webhook_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(webhook_bp)
