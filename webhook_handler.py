"""
SmartThings Webhook Handler

This server handles SmartThings lifecycle events for app registration and confirmation.
Run this alongside your Streamlit app when registering with SmartThings.

Usage:
    1. Start the webhook server: python webhook_handler.py
    2. Use localtunnel to expose it: lt --port 5000
    3. Register your app in SmartThings Developer Workspace with the tunnel URL
    4. SmartThings will send a CONFIRMATION request
    5. The server will automatically confirm by fetching the confirmation URL
"""

import os
import json
import hashlib
import base64
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Store for app credentials (populated after registration)
APP_ID = os.getenv("SMARTTHINGS_APP_ID", "")
CLIENT_ID = os.getenv("SMARTTHINGS_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SMARTTHINGS_CLIENT_SECRET", "")


def log_event(lifecycle: str, data: dict):
    """Log lifecycle events with timestamp"""
    timestamp = datetime.now().isoformat()
    print(f"\n{'='*60}")
    print(f"[{timestamp}] Lifecycle: {lifecycle}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2))
    print(f"{'='*60}\n")


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "message": "SmartThings Webhook Handler is running",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/", methods=["POST"])
def webhook():
    """Main webhook endpoint for SmartThings lifecycle events"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        lifecycle = data.get("lifecycle", "UNKNOWN")
        log_event(lifecycle, data)
        
        # Handle different lifecycle events
        if lifecycle == "CONFIRMATION":
            return handle_confirmation(data)
        elif lifecycle == "PING":
            return handle_ping(data)
        elif lifecycle == "CONFIGURATION":
            return handle_configuration(data)
        elif lifecycle == "INSTALL":
            return handle_install(data)
        elif lifecycle == "UPDATE":
            return handle_update(data)
        elif lifecycle == "UNINSTALL":
            return handle_uninstall(data)
        elif lifecycle == "EVENT":
            return handle_event(data)
        else:
            print(f"Unknown lifecycle: {lifecycle}")
            return jsonify({"error": f"Unknown lifecycle: {lifecycle}"}), 400
            
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500


def handle_confirmation(data: dict):
    """
    Handle CONFIRMATION lifecycle - verify domain ownership
    SmartThings sends a confirmationUrl that we need to GET to confirm
    """
    confirmation_data = data.get("confirmationData", {})
    app_id = confirmation_data.get("appId", "")
    confirmation_url = confirmation_data.get("confirmationUrl", "")
    
    print(f"\n*** CONFIRMATION REQUEST ***")
    print(f"App ID: {app_id}")
    print(f"Confirmation URL: {confirmation_url}")
    
    if confirmation_url:
        try:
            # Automatically fetch the confirmation URL to complete verification
            print(f"Fetching confirmation URL...")
            response = requests.get(confirmation_url, timeout=10)
            print(f"Confirmation response: {response.status_code}")
            print(f"Response body: {response.text[:500] if response.text else '(empty)'}")
            
            if response.ok:
                print("\n✓ APP CONFIRMED SUCCESSFULLY!")
                print(f"Save this App ID to your .env: SMARTTHINGS_APP_ID={app_id}")
            else:
                print(f"\n✗ Confirmation failed: {response.status_code}")
                
        except Exception as e:
            print(f"Error fetching confirmation URL: {str(e)}")
            print(f"You can manually confirm by visiting: {confirmation_url}")
    
    # Return 200 OK to acknowledge receipt
    return jsonify({"status": "confirmed"}), 200


def handle_ping(data: dict):
    """
    Handle PING lifecycle (deprecated but may still be used)
    Must echo back the challenge
    """
    ping_data = data.get("pingData", {})
    challenge = ping_data.get("challenge", "")
    
    print(f"PING challenge: {challenge}")
    
    return jsonify({
        "pingData": {
            "challenge": challenge
        }
    }), 200


def handle_configuration(data: dict):
    """
    Handle CONFIGURATION lifecycle - define app settings pages
    For our simple use case, we just need a minimal configuration
    """
    config_data = data.get("configurationData", {})
    phase = config_data.get("phase", "")
    
    print(f"Configuration phase: {phase}")
    
    if phase == "INITIALIZE":
        # Return app initialization info
        response = {
            "configurationData": {
                "initialize": {
                    "id": "humidity-monitor",
                    "name": "Humidity Monitor",
                    "description": "Monitor humidity and temperature sensors",
                    "permissions": [
                        "r:devices:*",
                        "r:locations:*"
                    ],
                    "firstPageId": "1"
                }
            }
        }
        print(f"INITIALIZE response: {json.dumps(response, indent=2)}")
        return jsonify(response), 200
        
    elif phase == "PAGE":
        # Return a simple single-page configuration - mark as complete immediately
        page_id = config_data.get("pageId", "1")
        response = {
            "configurationData": {
                "page": {
                    "pageId": page_id,
                    "name": "Humidity Monitor Setup",
                    "nextPageId": None,
                    "previousPageId": None,
                    "complete": True,
                    "sections": []
                }
            }
        }
        print(f"PAGE response: {json.dumps(response, indent=2)}")
        return jsonify(response), 200
    
    # Unknown phase - return empty config
    print(f"Unknown configuration phase: {phase}")
    return jsonify({"configurationData": {}}), 200


def handle_install(data: dict):
    """Handle INSTALL lifecycle - app was installed by user"""
    install_data = data.get("installData", {})
    auth_token = install_data.get("authToken", "")
    refresh_token = install_data.get("refreshToken", "")
    installed_app = install_data.get("installedApp", {})
    
    installed_app_id = installed_app.get("installedAppId", "")
    location_id = installed_app.get("locationId", "")
    
    print(f"\n*** APP INSTALLED ***")
    print(f"Installed App ID: {installed_app_id}")
    print(f"Location ID: {location_id}")
    
    if auth_token:
        print(f"\n*** SAVE THESE TOKENS TO YOUR .env FILE ***")
        print(f"SMARTTHINGS_AUTH_TOKEN={auth_token[:50]}...")
        print(f"SMARTTHINGS_REFRESH_TOKEN={refresh_token[:50]}...")
        print(f"SMARTTHINGS_INSTALLED_APP_ID={installed_app_id}")
        print(f"SMARTTHINGS_LOCATION_ID={location_id}")
        
        # Optionally save to a file
        tokens_file = os.path.join("data", ".smartapp_tokens.json")
        os.makedirs("data", exist_ok=True)
        with open(tokens_file, "w") as f:
            json.dump({
                "authToken": auth_token,
                "refreshToken": refresh_token,
                "installedAppId": installed_app_id,
                "locationId": location_id,
                "installedAt": datetime.now().isoformat()
            }, f, indent=2)
        print(f"\nTokens saved to: {tokens_file}")
    
    return jsonify({
        "installData": {}
    }), 200


def handle_update(data: dict):
    """Handle UPDATE lifecycle - app configuration was updated"""
    update_data = data.get("updateData", {})
    auth_token = update_data.get("authToken", "")
    refresh_token = update_data.get("refreshToken", "")
    
    print(f"App configuration updated")
    
    if auth_token:
        # Save updated tokens
        tokens_file = os.path.join("data", ".smartapp_tokens.json")
        os.makedirs("data", exist_ok=True)
        
        existing = {}
        if os.path.exists(tokens_file):
            with open(tokens_file, "r") as f:
                existing = json.load(f)
        
        existing.update({
            "authToken": auth_token,
            "refreshToken": refresh_token,
            "updatedAt": datetime.now().isoformat()
        })
        
        with open(tokens_file, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"Tokens updated in: {tokens_file}")
    
    return jsonify({
        "updateData": {}
    }), 200


def handle_uninstall(data: dict):
    """Handle UNINSTALL lifecycle - app was uninstalled"""
    print("App was uninstalled")
    
    return jsonify({
        "uninstallData": {}
    }), 200


def handle_event(data: dict):
    """Handle EVENT lifecycle - device events (subscriptions)"""
    event_data = data.get("eventData", {})
    events = event_data.get("events", [])
    
    print(f"Received {len(events)} event(s)")
    for event in events:
        print(f"  - {event.get('eventType', 'unknown')}: {event}")
    
    return jsonify({
        "eventData": {}
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", 5000))
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           SmartThings Webhook Handler                       ║
╠══════════════════════════════════════════════════════════════╣
║  Server starting on port {port}                               ║
║                                                              ║
║  Next steps:                                                 ║
║  1. Open a new terminal and run:                            ║
║     lt --port {port}                                          ║
║                                                              ║
║  2. Copy the HTTPS URL (e.g., https://xxx.loca.lt)          ║
║                                                              ║
║  3. Go to SmartThings Developer Workspace:                  ║
║     https://developer.smartthings.com/workspace/projects    ║
║                                                              ║
║  4. Click "Register App" and enter the tunnel URL           ║
║                                                              ║
║  5. SmartThings will send a CONFIRMATION request here       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host="0.0.0.0", port=port, debug=True)
