"""
Manual test script to verify user journey tracking is working.
This simulates browser requests and checks if journeys are created in the database.
"""
import os
import sys
import django
import time
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from user_analytics.models import UserJourney, UserActivity
from user_analytics.middleware import AnalyticsMiddleware
from django.utils import timezone
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage

User = get_user_model()

def test_middleware_directly():
    """Test the middleware directly to see if it's working"""
    print("=" * 80)
    print("Testing Analytics Middleware Directly")
    print("=" * 80)
    
    factory = RequestFactory()
    middleware = AnalyticsMiddleware(lambda request: None)
    
    # Create a mock request
    request = factory.get('/test-page/')
    request.session = {}
    # Create a mock user object
    class MockUser:
        is_authenticated = False
        id = None
    request.user = MockUser()
    request.META = {
        'HTTP_USER_AGENT': 'Mozilla/5.0 (Test Browser)',
        'HTTP_REFERER': 'https://google.com',
        'REMOTE_ADDR': '127.0.0.1',
    }
    
    # Process request
    middleware.process_request(request)
    
    if hasattr(request, 'analytics_data'):
        print("\n✅ Middleware processed request successfully!")
        print(f"   Session ID: {request.analytics_data.get('session_id')}")
        print(f"   Path: {request.analytics_data.get('path')}")
        print(f"   User ID: {request.analytics_data.get('user_id')}")
    else:
        print("\n❌ Middleware did not process request")
        return False
    
    # Create a mock response
    from django.http import HttpResponse
    response = HttpResponse("Test")
    response.status_code = 200
    
    # Process response (this should trigger tracking)
    print("\n📊 Processing response (should trigger tracking)...")
    middleware.process_response(request, response)
    
    print("✅ Response processed")
    return True


def test_synchronous_tracking():
    """Test the synchronous tracking functions directly"""
    print("\n" + "=" * 80)
    print("Testing Synchronous Tracking Functions")
    print("=" * 80)
    
    from user_analytics.tasks import track_page_view_sync, update_user_journey_sync
    
    session_id = f"test-session-{int(time.time())}"
    page_path = '/test-page/'
    
    print(f"\n📝 Testing with session_id: {session_id}")
    print(f"   Page path: {page_path}")
    
    # Test update_user_journey_sync
    print("\n1. Testing update_user_journey_sync...")
    try:
        result = update_user_journey_sync(
            session_id=session_id,
            user_id=None,
            ga4_client_id=None,
            page_path=page_path,
            referrer='https://google.com',
        )
        print(f"   ✅ Result: {result}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test track_page_view_sync
    print("\n2. Testing track_page_view_sync...")
    try:
        result = track_page_view_sync(
            session_id=session_id,
            user_id=None,
            ga4_client_id=None,
            page_path=page_path,
            page_title='Test Page',
            referrer='https://google.com',
            user_agent='Mozilla/5.0 (Test Browser)',
            ip_address='127.0.0.1',
            utm_source='',
            utm_medium='',
            utm_campaign='',
            utm_term='',
            utm_content='',
        )
        print(f"   ✅ Result: {result}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if journey was created
    print("\n3. Checking database...")
    try:
        journey = UserJourney.objects.filter(session_id=session_id).first()
        if journey:
            print(f"   ✅ Journey found in database!")
            print(f"      ID: {journey.id}")
            print(f"      Entry Page: {journey.entry_page}")
            print(f"      Total Pages: {journey.total_pages}")
            print(f"      Journey Path: {journey.journey_path}")
        else:
            print(f"   ❌ Journey NOT found in database")
            return False
    except Exception as e:
        print(f"   ❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_multiple_page_views():
    """Test tracking multiple page views in the same session"""
    print("\n" + "=" * 80)
    print("Testing Multiple Page Views (Same Session)")
    print("=" * 80)
    
    from user_analytics.tasks import update_user_journey_sync
    
    session_id = f"test-session-multi-{int(time.time())}"
    pages = ['/', '/careers/', '/blog/', '/about-us/']
    
    print(f"\n📝 Session ID: {session_id}")
    print(f"   Will visit {len(pages)} pages")
    
    for i, page_path in enumerate(pages, 1):
        print(f"\n{i}. Visiting: {page_path}")
        try:
            result = update_user_journey_sync(
                session_id=session_id,
                user_id=None,
                ga4_client_id=None,
                page_path=page_path,
                referrer=pages[i-2] if i > 1 else 'https://google.com',
            )
            print(f"   ✅ {result}")
            time.sleep(0.1)  # Small delay
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Check final journey state
    print("\n📊 Checking final journey state...")
    try:
        journey = UserJourney.objects.filter(session_id=session_id).first()
        if journey:
            print(f"   ✅ Journey found!")
            print(f"      Entry Page: {journey.entry_page}")
            print(f"      Exit Page: {journey.exit_page}")
            print(f"      Total Pages: {journey.total_pages}")
            print(f"      Journey Path: {journey.journey_path}")
            
            # Verify
            if journey.total_pages == len(pages):
                print(f"   ✅ Total pages matches expected ({len(pages)})")
            else:
                print(f"   ⚠️  Total pages ({journey.total_pages}) doesn't match expected ({len(pages)})")
            
            if journey.exit_page == pages[-1]:
                print(f"   ✅ Exit page matches last visited page")
            else:
                print(f"   ⚠️  Exit page ({journey.exit_page}) doesn't match last page ({pages[-1]})")
            
            if len(journey.journey_path) == len(pages):
                print(f"   ✅ Journey path has correct number of pages")
            else:
                print(f"   ⚠️  Journey path length ({len(journey.journey_path)}) doesn't match expected ({len(pages)})")
        else:
            print(f"   ❌ Journey NOT found in database")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def check_recent_journeys():
    """Check for recent journeys in the database"""
    print("\n" + "=" * 80)
    print("Checking Recent Journeys in Database")
    print("=" * 80)
    
    recent_time = timezone.now() - timedelta(minutes=5)
    
    try:
        recent_journeys = UserJourney.objects.filter(start_time__gte=recent_time).order_by('-start_time')
        total_journeys = UserJourney.objects.count()
        
        print(f"\n📊 Total journeys in database: {total_journeys}")
        print(f"📊 Recent journeys (last 5 min): {recent_journeys.count()}")
        
        if recent_journeys.exists():
            print("\n📈 Recent journeys:")
            for journey in recent_journeys[:10]:
                user_type = "Registered" if journey.user else "Organic"
                user_email = journey.user.email if journey.user else "Anonymous"
                print(f"\n   Journey ID: {journey.id}")
                print(f"   User: {user_email} ({user_type})")
                print(f"   Session: {journey.session_id[:40]}...")
                print(f"   Start: {journey.start_time}")
                print(f"   Entry: {journey.entry_page[:50]}")
                print(f"   Exit: {(journey.exit_page or 'N/A')[:50]}")
                print(f"   Pages: {journey.total_pages}")
                print(f"   Path: {journey.journey_path}")
        else:
            print("\n⚠️  No recent journeys found")
    except Exception as e:
        print(f"\n❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("USER JOURNEY TRACKING - MANUAL TEST")
    print("=" * 80)
    
    # Check current state
    check_recent_journeys()
    
    # Test 1: Test middleware
    print("\n\n" + "=" * 80)
    print("TEST 1: Middleware Test")
    print("=" * 80)
    middleware_ok = test_middleware_directly()
    
    # Test 2: Test synchronous functions
    print("\n\n" + "=" * 80)
    print("TEST 2: Synchronous Functions Test")
    print("=" * 80)
    sync_ok = test_synchronous_tracking()
    
    # Test 3: Test multiple page views
    print("\n\n" + "=" * 80)
    print("TEST 3: Multiple Page Views Test")
    print("=" * 80)
    multi_ok = test_multiple_page_views()
    
    # Final check
    print("\n\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Middleware Test: {'✅ PASSED' if middleware_ok else '❌ FAILED'}")
    print(f"Synchronous Functions: {'✅ PASSED' if sync_ok else '❌ FAILED'}")
    print(f"Multiple Page Views: {'✅ PASSED' if multi_ok else '❌ FAILED'}")
    
    check_recent_journeys()
    
    print("\n" + "=" * 80)
    if middleware_ok and sync_ok and multi_ok:
        print("✅ ALL TESTS PASSED - User journey tracking is working!")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    print("=" * 80)
