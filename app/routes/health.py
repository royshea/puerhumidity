"""Health check endpoint."""

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check() -> ResponseReturnValue:
    """Return health status of the application.

    Returns:
        JSON response with status "ok".
    """
    return jsonify({"status": "ok"})
