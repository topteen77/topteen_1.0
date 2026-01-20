#!/usr/bin/env python
"""
Script to check if analytics data is being stored in the database.
Run this to verify that the tracking middleware is working.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from user_analytics.models import UserActivity, UserJourney
try:
    from user_analytics.models import GA4Session
except ImportError:
    GA4Session = None

def check_analytics_data():
    """Check if analytics data exists in the database"""
    print("=" * 80)
    print("ANALYTICS DATA STORAGE CHECK")
    print("=" * 80)
    
    # Check UserActivity
    total_activities = UserActivity.objects.count()
    recent_activities = UserActivity.objects.filter(
        created__gte=timezone.now() - timedelta(days=7)
    ).count()
    today_activities = UserActivity.objects.filter(
        created__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    print(f"\n1. UserActivity Records:")
    print(f"   Total: {total_activities}")
    print(f"   Last 7 days: {recent_activities}")
    print(f"   Today: {today_activities}")
    
    if total_activities > 0:
        latest = UserActivity.objects.order_by('-created').first()
        print(f"   Latest: {latest.created} - {latest.page_path}")
        print(f"   Sample sources: {list(UserActivity.objects.exclude(utm_source__isnull=True).exclude(utm_source='').values_list('utm_source', flat=True).distinct()[:10])}")
        print(f"   Sample devices: {list(UserActivity.objects.exclude(device_type__isnull=True).exclude(device_type='').values_list('device_type', flat=True).distinct()[:10])}")
        print(f"   Sample countries: {list(UserActivity.objects.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct()[:10])}")
    else:
        print("   ⚠️  NO DATA FOUND - Tracking middleware may not be running!")
    
    # Check UserJourney
    total_journeys = UserJourney.objects.count()
    recent_journeys = UserJourney.objects.filter(
        start_time__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    print(f"\n2. UserJourney Records:")
    print(f"   Total: {total_journeys}")
    print(f"   Last 7 days: {recent_journeys}")
    
    if total_journeys > 0:
        latest = UserJourney.objects.order_by('-start_time').first()
        print(f"   Latest: {latest.start_time} - Session: {latest.session_id[:20]}...")
        print(f"   Registered users: {UserJourney.objects.filter(user__isnull=False).count()}")
        print(f"   Anonymous users: {UserJourney.objects.filter(user__isnull=True).count()}")
    else:
        print("   ⚠️  NO DATA FOUND")
    
    # Check GA4Session (may not exist if migration not run)
    print(f"\n3. GA4Session Records (Synced from Google Analytics):")
    if GA4Session is None:
        print(f"   ⚠️  GA4Session model not available")
    else:
        try:
            total_ga4 = GA4Session.objects.count()
            recent_ga4 = GA4Session.objects.filter(
                synced_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            print(f"   Total: {total_ga4}")
            print(f"   Last 7 days: {recent_ga4}")
            
            if total_ga4 > 0:
                latest = GA4Session.objects.order_by('-synced_at').first()
                print(f"   Latest sync: {latest.synced_at}")
                from django.db.models import Min, Max
                date_range = GA4Session.objects.aggregate(min_date=Min('date'), max_date=Max('date'))
                print(f"   Date range: {date_range['min_date']} to {date_range['max_date']}")
            else:
                print("   ⚠️  NO DATA FOUND - GA4 sync may not have run yet")
        except Exception as e:
            print(f"   ⚠️  Table does not exist - Run migration: python manage.py migrate user_analytics")
            print(f"   Error: {str(e)[:100]}")
    
    # Summary
    print(f"\n" + "=" * 80)
    print("SUMMARY:")
    if total_activities > 0 or total_journeys > 0:
        print("✅ Analytics data IS being stored in the database")
        print(f"   - {total_activities} page views tracked")
        print(f"   - {total_journeys} user journeys tracked")
        if total_ga4 > 0:
            print(f"   - {total_ga4} GA4 sessions synced")
    else:
        print("❌ NO analytics data found in database")
        print("\nPossible issues:")
        print("   1. AnalyticsMiddleware may not be enabled in settings.py")
        print("   2. Celery worker may not be running (for async tracking)")
        print("   3. No users have visited the site recently")
        print("   4. Tracking may be disabled or blocked")
    
    print("=" * 80)

if __name__ == '__main__':
    check_analytics_data()
