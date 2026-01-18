#!/usr/bin/env python3
"""
Test script to explore the SmartThings Activities API
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SMARTTHINGS_TOKEN = os.getenv("SMARTTHINGS_TOKEN")
DEVICE_1_ID = os.getenv("DEVICE_1_ID")
DEVICE_2_ID = os.getenv("DEVICE_2_ID")

# First, get the device details to find the locationId
print("Fetching device details to get location ID...")
headers = {
    "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
    "Accept": "application/json"
}

response = requests.get(
    f"https://api.smartthings.com/v1/devices/{DEVICE_1_ID}",
    headers=headers
)

if response.status_code == 200:
    device_info = response.json()
    location_id = device_info.get("locationId")
    print(f"\nDevice Location ID: {location_id}")
    print(f"Device Name: {device_info.get('label')}")
    
    # Now try the activities endpoint
    print("\n" + "="*60)
    print("Testing Activities API...")
    print("="*60)
    
    activities_headers = {
        "Authorization": f"Bearer {SMARTTHINGS_TOKEN}",
        "Accept": "application/vnd.smartthings+json;v=20180919"
    }
    
    # Try getting activities for this location
    activities_url = f"https://api.smartthings.com/activities?location={location_id}"
    print(f"\nRequest URL: {activities_url}")
    
    activities_response = requests.get(activities_url, headers=activities_headers)
    
    print(f"Status Code: {activities_response.status_code}")
    
    if activities_response.status_code == 200:
        activities_data = activities_response.json()
        print(f"\nSuccess! Found activities data")
        print(f"Response structure: {json.dumps(activities_data, indent=2)[:500]}...")
        
        # Save full response to file for inspection
        with open("activities_response.json", "w") as f:
            json.dump(activities_data, f, indent=2)
        print(f"\nFull response saved to: activities_response.json")
        
        # Try to analyze the structure
        if isinstance(activities_data, dict):
            print(f"\nTop-level keys: {list(activities_data.keys())}")
            if 'items' in activities_data:
                print(f"Number of items: {len(activities_data['items'])}")
                if activities_data['items']:
                    print(f"\nFirst item structure:")
                    print(json.dumps(activities_data['items'][0], indent=2))
    else:
        print(f"\nError: {activities_response.status_code}")
        print(f"Response: {activities_response.text}")
        
    # Try with additional query parameters
    print("\n" + "="*60)
    print("Testing with device filter...")
    print("="*60)
    
    activities_url_device = f"https://api.smartthings.com/activities?location={location_id}&deviceId={DEVICE_1_ID}"
    print(f"\nRequest URL: {activities_url_device}")
    
    activities_response_device = requests.get(activities_url_device, headers=activities_headers)
    print(f"Status Code: {activities_response_device.status_code}")
    
    if activities_response_device.status_code == 200:
        print("Success with device filter!")
        device_activities = activities_response_device.json()
        with open("activities_device_response.json", "w") as f:
            json.dump(device_activities, f, indent=2)
        print("Response saved to: activities_device_response.json")
    else:
        print(f"Response: {activities_response_device.text}")
        
else:
    print(f"Failed to get device info: {response.status_code}")
    print(response.text)
