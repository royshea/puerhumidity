"""SmartThings API client for subscription management."""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class SmartThingsService:
    """Client for SmartThings Subscriptions API.

    Creates CAPABILITY subscriptions for humidity and temperature sensors
    during INSTALL/UPDATE lifecycles.
    """

    # Capabilities we want to subscribe to
    CAPABILITIES = [
        ("relativeHumidityMeasurement", "humidity"),
        ("temperatureMeasurement", "temperature"),
    ]

    def __init__(self, api_base: str = "https://api.smartthings.com/v1") -> None:
        """Initialize the SmartThings service.

        Args:
            api_base: Base URL for SmartThings API.
        """
        self.api_base = api_base.rstrip("/")

    def create_subscriptions(
        self,
        installed_app_id: str,
        location_id: str,
        auth_token: str,
    ) -> list[dict[str, Any]]:
        """Create CAPABILITY subscriptions for humidity and temperature.

        Args:
            installed_app_id: The installed SmartApp instance ID.
            location_id: The SmartThings location ID.
            auth_token: OAuth token for API authorization.

        Returns:
            List of created subscription responses.

        Raises:
            requests.RequestException: If API call fails.
        """
        url = f"{self.api_base}/installedapps/{installed_app_id}/subscriptions"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

        results = []
        for capability, attribute in self.CAPABILITIES:
            subscription_request = {
                "sourceType": "CAPABILITY",
                "capability": {
                    "locationId": location_id,
                    "capability": capability,
                    "attribute": attribute,
                    "value": "*",
                    "stateChangeOnly": True,
                    "subscriptionName": f"{capability}_sub",
                },
            }

            logger.info(
                "Creating subscription for %s on installed app %s",
                capability,
                installed_app_id,
            )

            response = requests.post(
                url,
                json=subscription_request,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            result = response.json()
            results.append(result)
            logger.info("Subscription created: %s", result.get("id", "unknown"))

        return results

    def delete_all_subscriptions(
        self,
        installed_app_id: str,
        auth_token: str,
    ) -> None:
        """Delete all subscriptions for an installed app.

        Args:
            installed_app_id: The installed SmartApp instance ID.
            auth_token: OAuth token for API authorization.

        Raises:
            requests.RequestException: If API call fails.
        """
        url = f"{self.api_base}/installedapps/{installed_app_id}/subscriptions"
        headers = {"Authorization": f"Bearer {auth_token}"}

        logger.info("Deleting all subscriptions for installed app %s", installed_app_id)

        response = requests.delete(url, headers=headers, timeout=10)
        response.raise_for_status()

        logger.info("All subscriptions deleted for %s", installed_app_id)
