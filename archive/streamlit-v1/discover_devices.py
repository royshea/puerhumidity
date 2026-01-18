#!/usr/bin/env python3
"""
SmartThings Device Discovery Script
Helps identify devices with humidity and temperature capabilities
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SMARTTHINGS_TOKEN = os.getenv("SMARTTHINGS_TOKEN")
API_BASE = "https://api.smartthings.com/v1"

def fetch_devices():
    """Fetch all devices from SmartThings API"""
    if not SMARTTHINGS_TOKEN:
        print("ERROR: SMARTTHINGS_TOKEN not found in .env file")
        print("Please create a .env file with your SmartThings Personal Access Token")
        return None
    
    headers = {
        "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE}/devices", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR fetching devices: {e}")
        return None

def display_devices(data):
    """Display devices with humidity or temperature capabilities"""
    if not data or "items" not in data:
        print("No devices found")
        return
    
    devices = data["items"]
    
    # Filter for devices with humidity or temperature capabilities
    relevant_devices = []
    for device in devices:
        capabilities = [comp.get("capabilities", []) for comp in device.get("components", [])]
        flat_caps = [cap.get("id") for comp in capabilities for cap in comp]
        
        has_temp = any("temperature" in cap.lower() for cap in flat_caps)
        has_humidity = any("humidity" in cap.lower() for cap in flat_caps)
        
        if has_temp or has_humidity:
            relevant_devices.append({
                "name": device.get("label", device.get("name", "Unnamed")),
                "id": device.get("deviceId"),
                "location": device.get("locationId"),
                "capabilities": flat_caps,
                "has_temp": has_temp,
                "has_humidity": has_humidity
            })
    
    if not relevant_devices:
        print("No devices found with temperature or humidity capabilities")
        print("\nAll devices:")
        for device in devices:
            print(f"  - {device.get('label', device.get('name'))}")
        return
    
    print("\n" + "=" * 80)
    print("DEVICES WITH TEMPERATURE/HUMIDITY CAPABILITIES")
    print("=" * 80)
    
    for i, device in enumerate(relevant_devices, 1):
        print(f"\n[{i}] {device['name']}")
        print(f"    ID: {device['id']}")
        print(f"    Temperature: {'✓' if device['has_temp'] else '✗'}")
        print(f"    Humidity: {'✓' if device['has_humidity'] else '✗'}")
        print(f"    Capabilities: {', '.join(device['capabilities'][:5])}")
        if len(device['capabilities']) > 5:
            print(f"                  ... and {len(device['capabilities']) - 5} more")
    
    print("\n" + "=" * 80)
    print("\nTo use these devices in the app, add to your .env file:")
    print("\nDEVICE_1_ID=<device-id-here>")
    print("DEVICE_1_LABEL=<friendly-name-here>")
    print("DEVICE_2_ID=<device-id-here>")
    print("DEVICE_2_LABEL=<friendly-name-here>")
    print("\n" + "=" * 80)

def main():
    print("\nSmartThings Device Discovery")
    print("=" * 80)
    
    data = fetch_devices()
    if data:
        display_devices(data)

if __name__ == "__main__":
    main()
