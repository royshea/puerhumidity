"""SmartThings webhook lifecycle handlers."""

import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from app.models import SensorReading
from app.services import SmartThingsService
from app.storage import get_storage

webhook_bp = Blueprint("webhook", __name__)
logger = logging.getLogger(__name__)


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
    """
    install_data = data.get("installData", {})
    auth_token = install_data.get("authToken")
    installed_app = install_data.get("installedApp", {})
    installed_app_id = installed_app.get("installedAppId")
    location_id = installed_app.get("locationId")

    if auth_token and installed_app_id and location_id:
        try:
            api_base = current_app.config.get(
                "SMARTTHINGS_API_BASE", "https://api.smartthings.com/v1"
            )
            service = SmartThingsService(api_base)
            service.create_subscriptions(installed_app_id, location_id, auth_token)
            logger.info("Subscriptions created for installed app %s", installed_app_id)
        except Exception as e:
            logger.error("Failed to create subscriptions: %s", e)
    else:
        logger.warning(
            "Missing required install data: auth_token=%s, app_id=%s, location_id=%s",
            bool(auth_token),
            bool(installed_app_id),
            bool(location_id),
        )

    return jsonify({"installData": {}})


def _handle_update(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle UPDATE lifecycle - re-create subscriptions.

    Args:
        data: The webhook payload containing updateData.

    Returns:
        JSON response with updateData echoed back.
    """
    update_data = data.get("updateData", {})
    # NOTE: SmartThings docs show authToken at top-level for UPDATE, but the
    # working archive used updateData.authToken. If subscriptions fail during
    # UPDATE, try: auth_token = update_data.get("authToken")
    auth_token = data.get("authToken")
    installed_app = update_data.get("installedApp", {})
    installed_app_id = installed_app.get("installedAppId")
    location_id = installed_app.get("locationId")

    if auth_token and installed_app_id and location_id:
        try:
            api_base = current_app.config.get(
                "SMARTTHINGS_API_BASE", "https://api.smartthings.com/v1"
            )
            service = SmartThingsService(api_base)
            # Delete existing and recreate (handles config changes)
            service.delete_all_subscriptions(installed_app_id, auth_token)
            service.create_subscriptions(installed_app_id, location_id, auth_token)
            logger.info("Subscriptions updated for installed app %s", installed_app_id)
        except Exception as e:
            logger.error("Failed to update subscriptions: %s", e)
    else:
        logger.warning(
            "Missing required update data: auth_token=%s, app_id=%s, location_id=%s",
            bool(auth_token),
            bool(installed_app_id),
            bool(location_id),
        )

    return jsonify({"updateData": {}})


def _handle_event(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle EVENT lifecycle - process device events and write to storage.

    Args:
        data: The webhook payload containing eventData with device events.

    Returns:
        JSON response with eventData echoed back.
    """
    event_data = data.get("eventData", {})
    events = event_data.get("events", [])

    storage = get_storage()
    device_labels = current_app.config.get("DEVICE_LABELS", {})
    processed_count = 0

    for event in events:
        if event.get("eventType") != "DEVICE_EVENT":
            continue

        device_event = event.get("deviceEvent", {})
        reading = _parse_device_event(device_event, device_labels)

        if reading:
            storage.write_reading(reading)
            processed_count += 1
            logger.info(
                f"Wrote reading: {reading.sensor_name} = {reading.value}"
            )

    logger.info(f"EVENT lifecycle: processed {processed_count} readings")
    return jsonify({"eventData": {}})


def _parse_device_event(
    device_event: dict[str, Any], device_labels: dict[str, str]
) -> SensorReading | None:
    """Parse a SmartThings device event into a SensorReading.

    Args:
        device_event: The deviceEvent object from the webhook payload.
        device_labels: Mapping of device IDs to human-readable labels.

    Returns:
        SensorReading if the event is a humidity/temperature reading, else None.
    """
    device_id = device_event.get("deviceId")
    capability = device_event.get("capability")
    attribute = device_event.get("attribute")
    value = device_event.get("value")

    if not all([device_id, capability, value is not None]):
        return None

    # At this point we know device_id and value are not None
    assert device_id is not None
    assert value is not None

    # Map capability to reading type
    reading_type: str
    if capability == "relativeHumidityMeasurement" and attribute == "humidity":
        reading_type = "humidity"
    elif capability == "temperatureMeasurement" and attribute == "temperature":
        reading_type = "temperature"
    else:
        # Not a reading we care about
        return None

    # Get device label (fall back to device ID if not configured)
    device_label = device_labels.get(device_id, device_id)

    return SensorReading(
        device_id=str(device_id),
        device_label=device_label,
        reading_type=reading_type,  # type: ignore[arg-type]
        value=float(value),
        timestamp=datetime.now(timezone.utc),
    )


def _handle_uninstall(data: dict[str, Any]) -> ResponseReturnValue:
    """Handle UNINSTALL lifecycle - cleanup if needed.

    Args:
        data: The webhook payload containing uninstallData.

    Returns:
        JSON response with uninstallData echoed back.
    """
    return jsonify({"uninstallData": {}})
