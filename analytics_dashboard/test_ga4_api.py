from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

def test_ga4_connection():
    # Path to your service account key file
    # KEY_FILE_LOCATION = '/home/manish/Public/demo-topteens/demoproject.json'  # Your key file path
    KEY_FILE_LOCATION = '/home/manish/Public/demo-topteens/demoproject.json'
    
    # Correct GA4 Property ID format
    PROPERTY_ID = 'properties/493379109'  # Note the "properties/" prefix
    
    try:
        print("Creating credentials...")
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        
        print(f"Using service account: {credentials.service_account_email}")
        
        print("Creating GA4 client...")
        client = BetaAnalyticsDataClient(credentials=credentials)
        
        print(f"Preparing request for property: {PROPERTY_ID}")
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="activeUsers")]
        )
        
        print("Executing request...")
        response = client.run_report(request)
        
        print("Success! Results:")
        for row in response.rows:
            date = row.dimension_values[0].value
            active_users = row.metric_values[0].value
            print(f"Date: {date}, Active Users: {active_users}")
            
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_ga4_connection()
