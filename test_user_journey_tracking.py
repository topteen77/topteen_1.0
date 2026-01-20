"""
Test script to simulate user journey tracking and verify it appears on the user-journey page.
This script simulates browser requests to test the analytics middleware.
"""
import os
import sys
import django
import time
import requests
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from user_analytics.models import UserJourney, UserActivity
from django.utils import timezone

User = get_user_model()

def test_user_journey_tracking():
    """Simulate a user journey by making requests to different pages"""
    print("=" * 80)
    print("Testing User Journey Tracking")
    print("=" * 80)
    
    # Create a test client
    client = Client()
    
    # Get or create a test user (optional - for registered user tracking)
    test_user = None
    try:
        test_user = User.objects.filter(is_staff=True).first()
        if test_user:
            print(f"Using test user: {test_user.email}")
            client.force_login(test_user)
    except Exception as e:
        print(f"Note: Testing as anonymous user (no login): {e}")
    
    # Simulate a user journey - visit multiple pages
    pages_to_visit = [
        '/',
        '/careers/',
        '/careers/engineer/',
        '/blog/',
        '/about-us/',
    ]
    
    print(f"\n📊 Simulating user journey with {len(pages_to_visit)} page views...")
    print("-" * 80)
    
    session_id = None
    for i, page_path in enumerate(pages_to_visit, 1):
        print(f"{i}. Visiting: {page_path}")
        try:
            response = client.get(page_path, follow=True)
            print(f"   Status: {response.status_code}")
            
            # Extract session ID from cookies if available
            if 'sessionid' in client.cookies:
                session_id = client.cookies['sessionid'].value
                print(f"   Session ID: {session_id[:20]}...")
            
            # Small delay between requests to simulate real user behavior
            time.sleep(0.5)
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "-" * 80)
    print("✅ Page views completed!")
    print("\n⏳ Waiting 3 seconds for Celery tasks to process...")
    time.sleep(3)
    
    # Check if journeys were created
    print("\n" + "=" * 80)
    print("Checking User Journey Records")
    print("=" * 80)
    
    # Get recent journeys (last 1 minute)
    recent_time = timezone.now() - timezone.timedelta(minutes=1)
    recent_journeys = UserJourney.objects.filter(start_time__gte=recent_time).order_by('-start_time')
    
    print(f"\n📈 Found {recent_journeys.count()} journey(s) in the last minute:")
    print("-" * 80)
    
    if recent_journeys.exists():
        for journey in recent_journeys[:5]:  # Show first 5
            user_type = "Registered" if journey.user else "Organic/Anonymous"
            user_email = journey.user.email if journey.user else "Anonymous"
            
            print(f"\n🔍 Journey #{journey.id}:")
            print(f"   User: {user_email} ({user_type})")
            print(f"   Session ID: {journey.session_id[:30]}...")
            print(f"   Start Time: {journey.start_time}")
            print(f"   Entry Page: {journey.entry_page}")
            print(f"   Exit Page: {journey.exit_page or 'N/A'}")
            print(f"   Total Pages: {journey.total_pages}")
            print(f"   Journey Path: {journey.journey_path}")
            print(f"   Converted: {'Yes' if journey.converted else 'No'}")
    else:
        print("\n⚠️  No journeys found in the last minute.")
        print("   This could mean:")
        print("   - Celery is not running (tasks are queued but not processed)")
        print("   - There's an error in the tracking tasks")
        print("   - The middleware is not working correctly")
        
        # Check if there are any journeys at all
        all_journeys = UserJourney.objects.all().order_by('-start_time')[:5]
        if all_journeys.exists():
            print(f"\n   However, there are {UserJourney.objects.count()} total journeys in the database.")
            print("   Most recent journey:")
            latest = all_journeys.first()
            print(f"   - Created: {latest.start_time}")
            print(f"   - Session: {latest.session_id[:30]}...")
    
    # Check UserActivity records
    recent_activities = UserActivity.objects.filter(created__gte=recent_time).order_by('-created')
    print(f"\n📊 Found {recent_activities.count()} activity record(s) in the last minute")
    
    if recent_activities.exists():
        print("   Recent activities:")
        for activity in recent_activities[:3]:
            print(f"   - {activity.page_path} at {activity.created}")
    
    print("\n" + "=" * 80)
    print("✅ Test Complete!")
    print("=" * 80)
    print("\n💡 Next Steps:")
    print("   1. Visit http://127.0.0.1:8002/user-analytics/user-journey/ in your browser")
    print("   2. Check if the journey appears in the list")
    print("   3. If Celery is not running, journeys won't be created until Celery processes the tasks")
    print("=" * 80)

if __name__ == '__main__':
    test_user_journey_tracking()
