#!/usr/bin/env python
"""Verify data accuracy on Web Owner Dashboard"""
import os
import sys
import django
from datetime import timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.utils import timezone
from django.db.models import Count, Avg, Sum
from user_analytics.models import UserActivity, UserJourney, Lead, UserEvent
from users.models import User
from user_analytics.ga4_service import GA4Service
import json

def calculate_date_range(time_period):
    """Calculate date range for time period"""
    end_date = timezone.now()
    if time_period == 'today':
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_period == 'yesterday':
        start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
    elif time_period == '7days':
        start_date = end_date - timedelta(days=7)
    elif time_period == '30days':
        start_date = end_date - timedelta(days=30)
    elif time_period == '90days':
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=30)
    return start_date, end_date

def verify_web_owner_dashboard(time_period='30days'):
    """Verify all metrics on web owner dashboard"""
    print("=" * 80)
    print(f"WEB OWNER DASHBOARD DATA VERIFICATION - {time_period.upper()}")
    print("=" * 80)
    
    start_date, end_date = calculate_date_range(time_period)
    print(f"\nDate Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {(end_date - start_date).days} days\n")
    
    # Initialize GA4 Service
    ga4_service = GA4Service()
    
    # ========== SUMMARY METRICS ==========
    print("\n" + "=" * 80)
    print("SUMMARY METRICS")
    print("=" * 80)
    
    # 1. Total Users
    print("\n1. TOTAL USERS")
    print("-" * 80)
    
    # Database count
    db_total_users = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    print(f"   Database: {db_total_users} users")
    
    # GA4 data
    user_metrics = ga4_service.get_user_metrics(time_period, use_cache=False)
    if user_metrics and 'activeUsers' in user_metrics:
        ga4_total_users = sum(user_metrics['activeUsers'])
        print(f"   GA4:      {ga4_total_users} active users")
        print(f"   ✓ Using:  GA4 ({ga4_total_users})" if ga4_total_users else f"   ✓ Using:  Database ({db_total_users})")
    else:
        print(f"   GA4:      Not available")
        print(f"   ✓ Using:  Database ({db_total_users})")
    
    # 2. Total Sessions
    print("\n2. TOTAL SESSIONS")
    print("-" * 80)
    
    # Database count
    db_total_sessions = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).count()
    print(f"   Database: {db_total_sessions} sessions")
    
    # GA4 data
    if user_metrics and 'sessions' in user_metrics:
        ga4_total_sessions = sum(user_metrics['sessions'])
        print(f"   GA4:      {ga4_total_sessions} sessions")
        print(f"   ✓ Using:  GA4 ({ga4_total_sessions})" if ga4_total_sessions else f"   ✓ Using:  Database ({db_total_sessions})")
    else:
        print(f"   GA4:      Not available")
        print(f"   ✓ Using:  Database ({db_total_sessions})")
    
    # 3. Total Pageviews
    print("\n3. TOTAL PAGEVIEWS")
    print("-" * 80)
    
    # Database count
    db_total_pageviews = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    print(f"   Database: {db_total_pageviews} pageviews")
    
    # GA4 data
    if user_metrics and 'screenPageViews' in user_metrics:
        ga4_total_pageviews = sum(user_metrics['screenPageViews'])
        print(f"   GA4:      {ga4_total_pageviews} pageviews")
        print(f"   ✓ Using:  GA4 ({ga4_total_pageviews})" if ga4_total_pageviews else f"   ✓ Using:  Database ({db_total_pageviews})")
    else:
        print(f"   GA4:      Not available")
        print(f"   ✓ Using:  Database ({db_total_pageviews})")
    
    # 4. New Users
    print("\n4. NEW USERS")
    print("-" * 80)
    
    # Database count (same as total users for period)
    print(f"   Database: {db_total_users} new users")
    
    # GA4 data
    if user_metrics and 'newUsers' in user_metrics:
        ga4_new_users = sum(user_metrics['newUsers'])
        print(f"   GA4:      {ga4_new_users} new users")
        print(f"   ✓ Using:  GA4 ({ga4_new_users})" if ga4_new_users else f"   ✓ Using:  Database ({db_total_users})")
    else:
        print(f"   GA4:      Not available")
        print(f"   ✓ Using:  Database ({db_total_users})")
    
    # 5. Converted Sessions
    print("\n5. CONVERTED SESSIONS")
    print("-" * 80)
    
    converted_sessions = UserJourney.objects.filter(
        converted=True,
        start_time__gte=start_date,
        start_time__lte=end_date
    ).count()
    print(f"   Database: {converted_sessions} converted sessions")
    print(f"   ✓ Using:  Database ({converted_sessions})")
    
    # 6. Avg Session Duration
    print("\n6. AVG SESSION DURATION")
    print("-" * 80)
    
    avg_session_duration = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).aggregate(avg=Avg('total_time'))['avg'] or 0
    
    print(f"   Database: {avg_session_duration:.2f} seconds ({avg_session_duration/60:.2f} minutes)")
    print(f"   ✓ Using:  Database ({avg_session_duration/60:.2f} min)")
    
    # 7. Real-time Users
    print("\n7. REAL-TIME USERS")
    print("-" * 80)
    
    real_time_users = ga4_service.get_real_time_users()
    print(f"   GA4:      {real_time_users or 0} real-time users")
    print(f"   ✓ Using:  GA4 ({real_time_users or 0})")
    
    # ========== TOP PAGES ==========
    print("\n" + "=" * 80)
    print("TOP PAGES")
    print("=" * 80)
    
    # Database top pages
    db_top_pages = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).exclude(page_path__isnull=True).exclude(page_path='').values(
        'page_path', 'page_title'
    ).annotate(
        pageviews=Count('id')
    ).order_by('-pageviews')[:20]
    
    print(f"\nDatabase Top Pages: {len(db_top_pages)} pages")
    if db_top_pages:
        for i, page in enumerate(db_top_pages[:10], 1):
            path = page.get('page_path', 'N/A')
            title = page.get('page_title') or path
            views = page.get('pageviews', 0)
            print(f"   {i:2d}. {title[:50]:50s} | {views:6d} views")
    else:
        print("   No database pages found")
    
    # GA4 top pages
    ga4_top_pages = ga4_service.get_top_pages(time_period, limit=20, use_cache=False)
    print(f"\nGA4 Top Pages: {len(ga4_top_pages) if ga4_top_pages else 0} pages")
    if ga4_top_pages:
        for i, page in enumerate(ga4_top_pages[:10], 1):
            path = page.get('path', 'N/A')
            title = page.get('title', 'Unknown')
            views = page.get('pageviews', 0)
            print(f"   {i:2d}. {title[:50]:50s} | {views:6d} views")
    else:
        print("   No GA4 pages found")
    
    if db_top_pages:
        print(f"\n   ✓ Using:  Database ({len(db_top_pages)} pages)")
    elif ga4_top_pages:
        print(f"\n   ✓ Using:  GA4 ({len(ga4_top_pages)} pages)")
    else:
        print(f"\n   ⚠ No data available from either source")
    
    # ========== TRAFFIC SOURCES ==========
    print("\n" + "=" * 80)
    print("TRAFFIC SOURCES (Database)")
    print("=" * 80)
    
    db_traffic_sources = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('utm_source').annotate(
        sessions=Count('session_id', distinct=True),
        pageviews=Count('id')
    ).order_by('-sessions')[:15]
    
    print(f"\nDatabase Traffic Sources: {len(db_traffic_sources)} sources")
    if db_traffic_sources:
        for i, source in enumerate(db_traffic_sources[:10], 1):
            src = source.get('utm_source', 'Unknown')
            sessions = source.get('sessions', 0)
            pageviews = source.get('pageviews', 0)
            print(f"   {i:2d}. {src[:40]:40s} | {sessions:6d} sessions | {pageviews:6d} pageviews")
    else:
        print("   No traffic sources found")
    
    # ========== DEVICE BREAKDOWN ==========
    print("\n" + "=" * 80)
    print("DEVICE BREAKDOWN (Database)")
    print("=" * 80)
    
    db_device_breakdown = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('device_type').annotate(
        count=Count('session_id', distinct=True)
    ).order_by('-count')
    
    print(f"\nDatabase Device Breakdown: {len(db_device_breakdown)} device types")
    if db_device_breakdown:
        for i, device in enumerate(db_device_breakdown[:10], 1):
            device_type = device.get('device_type', 'Unknown')
            count = device.get('count', 0)
            print(f"   {i:2d}. {device_type[:40]:40s} | {count:6d} users")
    else:
        print("   No device data found")
    
    # ========== TOP ENTRY/EXIT PAGES ==========
    print("\n" + "=" * 80)
    print("TOP ENTRY PAGES")
    print("=" * 80)
    
    top_entry_pages = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).values('entry_page').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print(f"\nDatabase Entry Pages: {len(top_entry_pages)} pages")
    if top_entry_pages:
        for i, page in enumerate(top_entry_pages, 1):
            entry_page = page.get('entry_page', 'N/A')
            count = page.get('count', 0)
            print(f"   {i:2d}. {entry_page[:60]:60s} | {count:6d} sessions")
    else:
        print("   No entry pages found")
    
    print("\n" + "=" * 80)
    print("TOP EXIT PAGES")
    print("=" * 80)
    
    top_exit_pages = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).exclude(exit_page__isnull=True).values('exit_page').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print(f"\nDatabase Exit Pages: {len(top_exit_pages)} pages")
    if top_exit_pages:
        for i, page in enumerate(top_exit_pages, 1):
            exit_page = page.get('exit_page', 'N/A')
            count = page.get('count', 0)
            print(f"   {i:2d}. {exit_page[:60]:60s} | {count:6d} sessions")
    else:
        print("   No exit pages found")
    
    # ========== ENGAGEMENT METRICS ==========
    print("\n" + "=" * 80)
    print("ENGAGEMENT METRICS (GA4)")
    print("=" * 80)
    
    engagement = ga4_service.get_user_engagement(time_period, use_cache=False)
    if engagement:
        avg_duration = engagement.get('averageSessionDuration', 0) if isinstance(engagement, dict) else getattr(engagement, 'averageSessionDuration', 0)
        engagement_duration = engagement.get('engagementDuration', 0) if isinstance(engagement, dict) else getattr(engagement, 'engagementDuration', 0)
        bounce_rate = engagement.get('bounceRate', 0) if isinstance(engagement, dict) else getattr(engagement, 'bounceRate', 0)
        print(f"\n   Avg Session Duration: {avg_duration:.2f} min")
        print(f"   User Engagement: {engagement_duration:.2f} min")
        print(f"   Bounce Rate: {bounce_rate:.2f}%")
    else:
        print("\n   ⚠ Engagement metrics not available from GA4")
    
    # ========== DATA ACCURACY SUMMARY ==========
    print("\n" + "=" * 80)
    print("DATA ACCURACY SUMMARY")
    print("=" * 80)
    
    issues = []
    warnings = []
    
    # Check for data discrepancies
    if user_metrics:
        if ga4_total_users and db_total_users:
            diff = abs(ga4_total_users - db_total_users)
            if diff > ga4_total_users * 0.1:  # More than 10% difference
                issues.append(f"User count discrepancy: GA4={ga4_total_users}, DB={db_total_users} (diff: {diff})")
        
        if ga4_total_sessions and db_total_sessions:
            diff = abs(ga4_total_sessions - db_total_sessions)
            if diff > ga4_total_sessions * 0.1:
                issues.append(f"Session count discrepancy: GA4={ga4_total_sessions}, DB={db_total_sessions} (diff: {diff})")
    
    if db_total_pageviews == 0:
        warnings.append("No pageviews in database - Top Pages will only show GA4 data")
    
    if db_total_sessions == 0:
        warnings.append("No sessions in database - Session metrics will only show GA4 data")
    
    if not user_metrics:
        warnings.append("GA4 data not available - Dashboard will use database data only")
    
    if issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("\n✓ No major issues found")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   - {warning}")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    # Test different time periods
    for period in ['today', '7days', '30days']:
        verify_web_owner_dashboard(period)
        print("\n\n")
