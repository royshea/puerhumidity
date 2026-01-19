"""SmartThings webhook lifecycle handlers."""

from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/webhook", methods=["POST"])
def handle_webhook() -> ResponseReturnValue:
    """Handle SmartThings lifecycle events.

    Supports: PING, CONFIRMATION, INSTALL, UPDATE, EVENT, UNINSTALL

    Returns:
        Appropriate JSON response for each lifecycle type.
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    lifecycle = data.get("lifecycle")

    if lifecycle == "PING":
        return _handle_ping(data)
    elif lifecycle == "CONFIRMATION":
        return _handle_confirmation(data)
    elif lifecycle == "INSTALL":
        return _handle_install(data)
    elif lifecycle == "UPDATE":
        return _handle_update(data)
    elif lifecycle == "EVENT":
        return _handle_event(data)
    elif lifecycle == "UNINSTALL":
        return _handle_uninstall(data)
    else:
        return jsonify({"error": f"Unknown lifecycle: {lifecycle}"}), 400


def _handle_ping(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle PING lifecycle - echo back the challenge.

    Args:
        data: The webhook payload containing pingData.challenge.

    Returns:
        JSON response with the challenge echoed back.
    """
    challenge = data.get("pingData", {}).get("challenge")
    return jsonify({"pingData": {"challenge": challenge}})


def _handle_confirmation(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle CONFIRMATION lifecycle - fetch the confirmation URL.

    Args:
        data: The webhook payload containing confirmationData.confirmationUrl.

    Returns:
        Empty 200 response after fetching confirmation URL.
    """
    import requests

    confirmation_url = data.get("confirmationData", {}).get("confirmationUrl")
    if confirmation_url:
        requests.get(confirmation_url, timeout=10)
    return jsonify({}), 200


def _handle_install(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle INSTALL lifecycle - store tokens and create subscriptions.

    Args:
        data: The webhook payload containing installData with auth tokens.

    Returns:
        JSON response with installData echoed back.

    TODO: Implement subscription creation in Phase 5.
    """
    # Placeholder - subscription creation will be implemented in Phase 5
    return jsonify({"installData": {}})


def _handle_update(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle UPDATE lifecycle - re-create subscriptions.

    Args:
        data: The webhook payload containing updateData.

    Returns:
        JSON response with updateData echoed back.

    TODO: Implement subscription update in Phase 5.
    """
    # Placeholder - subscription update will be implemented in Phase 5
    return jsonify({"updateData": {}})


def _handle_event(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle EVENT lifecycle - process device events.

    Args:
        data: The webhook payload containing eventData with device events.

    Returns:
        JSON response with eventData echoed back.

    TODO: Implement event processing in Phase 4.
    """
    # Placeholder - event processing will be implemented in Phase 4
    return jsonify({"eventData": {}})


def _handle_uninstall(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle UNINSTALL lifecycle - cleanup if needed.

    Args:
        data: The webhook payload containing uninstallData.

    Returns:
        JSON response with uninstallData echoed back.
    """
    return jsonify({"uninstallData": {}})
