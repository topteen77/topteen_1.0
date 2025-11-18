#!/usr/bin/env python3
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to your service account key file
KEY_FILE_LOCATION = '/home/manish/Public/demo-topteens/demoproject.json'
VIEW_ID = '493379109'  # Your GA View ID

def test_analytics_connection():
    print("Testing Google Analytics API connection...")
    
    # Print debug info about the key file
    if os.path.exists(KEY_FILE_LOCATION):
        with open(KEY_FILE_LOCATION, 'r') as f:
            key_data = json.load(f)
            print(f"Service account email: {key_data.get('client_email')}")
            print(f"Project ID: {key_data.get('project_id')}")
    else:
        print(f"Key file not found at: {KEY_FILE_LOCATION}")
        return
    
    try:
        # Create credentials
        print("Creating credentials...")
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        
        # Build the service
        print("Building analytics service...")
        analytics = build('analyticsreporting', 'v4', credentials=credentials)
        
        # Create a simple request
        print(f"Making API request with View ID: {VIEW_ID}...")
        body = {
            'reportRequests': [
                {
                    'viewId': VIEW_ID,
                    'dateRanges': [{'startDate': '7daysAgo', 'endDate': 'today'}],
                    'metrics': [{'expression': 'ga:sessions'}]
                }
            ]
        }
        
        # Make the API request
        print("Executing API request...")
        response = analytics.reports().batchGet(body=body).execute()
        
        print("API request successful!")
        print("Response data:")
        print(json.dumps(response, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_analytics_connection()