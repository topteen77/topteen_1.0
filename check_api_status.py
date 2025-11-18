#!/usr/bin/env python3
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to your service account key file
KEY_FILE_LOCATION = '/home/manish/Public/demo-topteens/demoproject.json'

def check_api_status():
    print("Checking Google API status...")
    
    # Print debug info about the key file
    if os.path.exists(KEY_FILE_LOCATION):
        with open(KEY_FILE_LOCATION, 'r') as f:
            key_data = json.load(f)
            print(f"Service account email: {key_data.get('client_email')}")
            print(f"Project ID: {key_data.get('project_id')}")
            project_id = key_data.get('project_id')
    else:
        print(f"Key file not found at: {KEY_FILE_LOCATION}")
        return
    
    try:
        # Create credentials
        print("Creating credentials...")
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Build the service discovery API
        print("Building service management API...")
        service = build('servicemanagement', 'v1', credentials=credentials)
        
        # Check if Analytics API is enabled
        print(f"Checking if Analytics APIs are enabled for project {project_id}...")
        
        # List of APIs to check
        apis_to_check = [
            'analytics.googleapis.com',
            'analyticsreporting.googleapis.com',
            'analyticsdata.googleapis.com'
        ]
        
        for api in apis_to_check:
            try:
                # Get the service configuration
                request = service.services().get(serviceName=api)
                response = request.execute()
                print(f"✓ API {api} is available")
            except Exception as e:
                print(f"✗ API {api} check failed: {str(e)}")
        
        print("\nTo enable these APIs, go to:")
        print(f"https://console.cloud.google.com/apis/library?project={project_id}")
        print("And search for and enable:")
        print("1. Google Analytics API")
        print("2. Analytics Reporting API")
        print("3. Analytics Data API (for GA4)")
        
    except Exception as e:
        print(f"Error checking API status: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_api_status()