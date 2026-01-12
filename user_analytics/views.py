"""
Analytics Dashboard Views for Business Owner, Accounts, and Web Owner.
Provides comprehensive analytics reports and visualizations.
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import unquote
import json
import logging

logger = logging.getLogger(__name__)

from user_analytics.models import UserActivity, Lead, UserEvent, UserJourney, AnalyticsCache
from user_analytics.ga4_service import GA4Service
from users.models import User
from payments.models import Payment
from psychometric_tests.models import PsychometricTestPayment
from core import choices


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def is_superuser_only(user):
    """Check if user is superuser only"""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_superuser_only)
def admin_dashboard(request):
    """
    Main Admin Dashboard - Connects all major admin areas.
    Only accessible to superusers.
    """
    time_period = request.GET.get('period', '30days')
    
    # Calculate date range
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
    
    # Quick Stats - Filtered by period
    total_users = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    active_users = User.objects.filter(
        is_active=True,
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    total_payments = Payment.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    successful_payments = Payment.objects.filter(
        is_success=choices.YesNoChoices.YES,
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    # Recent Activity - Filtered by period
    recent_registrations = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).order_by('-created')[:10]
    
    recent_payments = Payment.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).order_by('-created')[:10]
    
    # Analytics Summary
    total_page_views = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    total_sessions = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('session_id').distinct().count()
    
    total_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    total_leads = Lead.objects.filter(
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).count()
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'total_users': total_users,
        'active_users': active_users,
        'total_payments': total_payments,
        'successful_payments': successful_payments,
        'total_page_views': total_page_views,
        'total_sessions': total_sessions,
        'total_revenue': total_revenue,
        'total_leads': total_leads,
        'recent_registrations': recent_registrations,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'user_analytics/admin_dashboard.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def dashboard(request):
    """Main analytics dashboard - redirects to business dashboard"""
    return business_dashboard(request)


@login_required
@user_passes_test(is_staff_or_superuser)
def business_dashboard(request):
    """
    Business Owner Dashboard
    Shows revenue, payments, enrollments, and conversion metrics.
    """
    time_period = request.GET.get('period', '30days')
    
    # Calculate date range
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
    
    # Revenue Metrics
    revenue_events = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    )
    total_revenue = revenue_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Payment Metrics
    successful_payments = revenue_events.count()
    
    # Failed Payments - Calculate count and attempted revenue
    failed_payment_events = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    )
    failed_payments = failed_payment_events.count()
    failed_payments_revenue = failed_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Pending Payments - Calculate count and potential revenue
    pending_payment_events = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    )
    pending_payments = pending_payment_events.count()
    pending_payments_revenue = pending_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Enrollment Metrics
    total_enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered'],
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    psychometric_enrollments = UserEvent.objects.filter(
        event_type='psychometric_test_completed',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    course_enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled'],
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    # Psychometric Test Revenue Breakdown
    # Class 12 = Career Direction = ADVANCED test
    class12_psychometric_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).filter(
        Q(metadata__test_name='Career Direction') |
        Q(metadata__test_type='Advanced test') |
        Q(event_name__icontains='Career Direction')
    ).aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    class12_psychometric_count = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).filter(
        Q(metadata__test_name='Career Direction') |
        Q(metadata__test_type='Advanced test') |
        Q(event_name__icontains='Career Direction')
    ).count()
    
    # Stream Sorter (Class 10-11) = BASIC test
    stream_sorter_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).filter(
        Q(metadata__test_name='Stream Sorter') |
        Q(event_name__icontains='Stream Sorter')
    ).aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    stream_sorter_count = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).filter(
        Q(metadata__test_name='Stream Sorter') |
        Q(event_name__icontains='Stream Sorter')
    ).count()
    
    # Conversion Funnel
    total_visitors = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('session_id').distinct().count()
    
    total_registrations = UserEvent.objects.filter(
        event_type='registration',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    total_leads = Lead.objects.filter(
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).count()
    
    converted_leads = Lead.objects.filter(
        is_converted=True,
        converted_at__gte=start_date,
        converted_at__lte=end_date
    ).count()
    
    # Revenue by Source - Query JSONField properly
    revenue_by_source_raw = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).exclude(metadata__isnull=True)
    
    # Process revenue by source manually since JSONField queries can be tricky
    revenue_by_source_dict = {}
    for event in revenue_by_source_raw:
        source = event.metadata.get('source', 'Unknown') if event.metadata else 'Unknown'
        if source not in revenue_by_source_dict:
            revenue_by_source_dict[source] = {'revenue': Decimal('0'), 'count': 0}
        revenue_by_source_dict[source]['revenue'] += event.event_value or Decimal('0')
        revenue_by_source_dict[source]['count'] += 1
    
    # Convert to list and sort by revenue
    revenue_by_source = [
        {'metadata__source': source, 'revenue': float(data['revenue']), 'count': data['count']}
        for source, data in sorted(revenue_by_source_dict.items(), key=lambda x: x[1]['revenue'], reverse=True)
    ][:10]
    
    # Daily Revenue Trend - Use TruncDate for better database compatibility
    daily_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).annotate(
        day=TruncDate('created')
    ).values('day').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('day')
    
    # Top Products/Services
    top_products = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).values('event_name').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('-revenue')[:10]
    
    # Calculate summary metrics
    total_attempts = successful_payments + failed_payments + pending_payments
    success_rate = (successful_payments / total_attempts * 100) if total_attempts > 0 else 0
    
    total_attempted_revenue = total_revenue + failed_payments_revenue + pending_payments_revenue
    conversion_value_rate = (total_revenue / total_attempted_revenue * 100) if total_attempted_revenue > 0 else 0
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'total_revenue': total_revenue,
        'successful_payments': successful_payments,
        'failed_payments': failed_payments,
        'failed_payments_revenue': failed_payments_revenue,
        'pending_payments': pending_payments,
        'pending_payments_revenue': pending_payments_revenue,
        'total_attempted_revenue': total_attempted_revenue,
        'success_rate': success_rate,
        'conversion_value_rate': conversion_value_rate,
        'total_enrollments': total_enrollments,
        'psychometric_enrollments': psychometric_enrollments,
        'course_enrollments': course_enrollments,
        'class12_psychometric_revenue': class12_psychometric_revenue,
        'class12_psychometric_count': class12_psychometric_count,
        'stream_sorter_revenue': stream_sorter_revenue,
        'stream_sorter_count': stream_sorter_count,
        'total_visitors': total_visitors,
        'total_registrations': total_registrations,
        'total_leads': total_leads,
        'converted_leads': converted_leads,
        'revenue_by_source': list(revenue_by_source),
        'daily_revenue': list(daily_revenue),
        'top_products': list(top_products),
    }
    
    return render(request, 'user_analytics/business_dashboard.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def accounts_dashboard(request):
    """
    Accounts Dashboard
    Shows user registration, payment status, prospects, and revenue breakdown.
    """
    time_period = request.GET.get('period', '30days')
    
    # Calculate date range
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
    
    # User Registration Trends
    user_registrations = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    )
    total_registrations = user_registrations.count()
    
    daily_registrations = user_registrations.extra(
        select={'day': 'DATE(created)'}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Payment Status Breakdown
    payment_status = {
        'success': UserEvent.objects.filter(
            event_type='payment_success',
            created__gte=start_date,
            created__lte=end_date
        ).count(),
        'failed': UserEvent.objects.filter(
            event_type='payment_failed',
            created__gte=start_date,
            created__lte=end_date
        ).count(),
        'pending': UserEvent.objects.filter(
            event_type='payment_pending',
            created__gte=start_date,
            created__lte=end_date
        ).count(),
    }
    
    # Revenue Metrics
    total_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Prospects (Leads)
    total_prospects = Lead.objects.filter(
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).count()
    
    converted_prospects = Lead.objects.filter(
        is_converted=True,
        converted_at__gte=start_date,
        converted_at__lte=end_date
    ).count()
    
    pending_prospects = Lead.objects.filter(
        is_converted=False,
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).count()
    
    # Revenue by Source - Query JSONField properly
    revenue_by_source_raw = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).exclude(metadata__isnull=True)
    
    # Process revenue by source manually since JSONField queries can be tricky
    revenue_by_source_dict = {}
    for event in revenue_by_source_raw:
        source = event.metadata.get('source', 'Unknown') if event.metadata else 'Unknown'
        if source not in revenue_by_source_dict:
            revenue_by_source_dict[source] = {'revenue': Decimal('0'), 'count': 0}
        revenue_by_source_dict[source]['revenue'] += event.event_value or Decimal('0')
        revenue_by_source_dict[source]['count'] += 1
    
    # Convert to list and sort by revenue
    revenue_by_source = [
        {'metadata__source': source, 'revenue': float(data['revenue']), 'count': data['count']}
        for source, data in sorted(revenue_by_source_dict.items(), key=lambda x: x[1]['revenue'], reverse=True)
    ]
    
    # Failed Payments Analysis
    failed_payments = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    ).values('event_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Pending Payments
    pending_payments_list = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')[:20]
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'total_registrations': total_registrations,
        'daily_registrations': list(daily_registrations),
        'payment_status': payment_status,
        'total_revenue': total_revenue,
        'total_prospects': total_prospects,
        'converted_prospects': converted_prospects,
        'pending_prospects': pending_prospects,
        'revenue_by_source': list(revenue_by_source),
        'failed_payments': list(failed_payments),
        'pending_payments_list': pending_payments_list,
    }
    
    return render(request, 'user_analytics/accounts_dashboard.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def web_owner_dashboard(request):
    """
    Web Owner Dashboard
    Shows traffic sources, user journey, engagement metrics, and page analytics.
    """
    time_period = request.GET.get('period', '30days')
    
    # Ensure default is 30days if not provided or invalid
    valid_periods = ['today', 'yesterday', '7days', '30days', '90days']
    if time_period not in valid_periods:
        time_period = '30days'
    
    logger.info("=" * 80)
    logger.info(f"WEB OWNER DASHBOARD - Time Period: {time_period}")
    logger.info("=" * 80)
    
    # Initialize GA4 Service
    ga4_service = GA4Service()
    logger.debug("GA4 Service initialized")
    
    # Get GA4 metrics - disable cache to ensure fresh data
    logger.debug("Fetching GA4 metrics (cache disabled)...")
    try:
        user_metrics = ga4_service.get_user_metrics(time_period, use_cache=False)
        device_breakdown = ga4_service.get_device_breakdown(time_period, use_cache=False)
        top_pages = ga4_service.get_top_pages(time_period, limit=20, use_cache=False)
        top_pages_with_trends = ga4_service.get_top_pages_with_trends(time_period, limit=20, use_cache=False)
        traffic_sources = ga4_service.get_traffic_sources(time_period, limit=15, use_cache=False)
        engagement = ga4_service.get_user_engagement(time_period, use_cache=False)
        real_time_users = ga4_service.get_real_time_users()
        real_time_breakdown = ga4_service.get_real_time_users_breakdown()
        real_time_users_by_country = ga4_service.get_real_time_users_by_country()
        users_by_country = ga4_service.get_users_by_country(time_period, limit=10, use_cache=False)
        ga4_entry_pages = ga4_service.get_entry_pages(time_period, limit=10, use_cache=False)
        ga4_exit_pages = ga4_service.get_exit_pages(time_period, limit=10, use_cache=False)
    except Exception as e:
        logger.error(f"Error fetching GA4 data: {e}", exc_info=True)
        # Set defaults to None/empty lists on error
        user_metrics = None
        device_breakdown = None
        top_pages = []
        top_pages_with_trends = []
        traffic_sources = None
        engagement = None
        real_time_users = None
        real_time_breakdown = None
        real_time_users_by_country = []
        users_by_country = []
        ga4_entry_pages = []
        ga4_exit_pages = []
    
    # Calculate existing vs organic users from database (if available)
    # This is a fallback - GA4 doesn't directly tell us registered vs anonymous
    # We can infer from our database tracking
    existing_users_count = 0
    organic_users_count = 0
    if UserActivity.objects.exists():
        # Count unique registered users in last hour
        recent_cutoff = timezone.now() - timedelta(hours=1)
        existing_users_count = UserActivity.objects.filter(
            created__gte=recent_cutoff,
            user__isnull=False
        ).values('user').distinct().count()
        
        # Count unique anonymous sessions in last hour
        organic_users_count = UserActivity.objects.filter(
            created__gte=recent_cutoff,
            user__isnull=True
        ).values('session_id').distinct().count()
    
    logger.info(f"GA4 Data Retrieved:")
    logger.info(f"  - User Metrics: {'Available' if user_metrics else 'Not Available'}")
    logger.info(f"  - Device Breakdown: {'Available' if device_breakdown else 'Not Available'}")
    logger.info(f"  - Top Pages: {len(top_pages) if top_pages else 0} pages")
    logger.info(f"  - Traffic Sources: {'Available' if traffic_sources else 'Not Available'}")
    logger.info(f"  - Engagement: {'Available' if engagement else 'Not Available'}")
    logger.info(f"  - Real-time Users: {real_time_users or 0}")
    if real_time_breakdown:
        logger.info(f"    - New Users: {real_time_breakdown.get('new', 0)}")
        logger.info(f"    - Returning Users: {real_time_breakdown.get('returning', 0)}")
    logger.info(f"  - Entry Pages: {len(ga4_entry_pages) if ga4_entry_pages else 0} pages")
    logger.info(f"  - Exit Pages: {len(ga4_exit_pages) if ga4_exit_pages else 0} pages")
    logger.info(f"  - Real-time Users by Country: {len(real_time_users_by_country) if real_time_users_by_country else 0} countries")
    logger.info(f"  - Users by Country: {len(users_by_country) if users_by_country else 0} countries")
    logger.info(f"  - Top Pages with Trends: {len(top_pages_with_trends) if top_pages_with_trends else 0} pages")
    logger.info(f"  - Existing Users (DB tracking): {existing_users_count}")
    logger.info(f"  - Organic Users (DB tracking): {organic_users_count}")
    
    # Calculate date range for database queries
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
    
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Duration: {(end_date - start_date).days} days")
    
    # User Journey Metrics
    total_sessions = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).count()
    
    converted_sessions = UserJourney.objects.filter(
        converted=True,
        start_time__gte=start_date,
        start_time__lte=end_date
    ).count()
    
    avg_session_duration = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).aggregate(avg=Avg('total_time'))['avg'] or 0
    
    logger.info(f"Database User Journey Metrics:")
    logger.info(f"  - Total Sessions: {total_sessions}")
    logger.info(f"  - Converted Sessions: {converted_sessions}")
    logger.info(f"  - Avg Session Duration: {avg_session_duration:.2f} seconds ({avg_session_duration/60:.2f} minutes)")
    
    # Use GA4 data for all sections (skip database)
    # Top Entry Pages - Use GA4
    top_entry_pages = ga4_entry_pages if ga4_entry_pages else []
    
    # Top Exit Pages - Use GA4
    top_exit_pages = ga4_exit_pages if ga4_exit_pages else []
    
    # Traffic Sources - Convert GA4 format to match template expectations
    ga4_traffic_sources_list = []
    if traffic_sources and 'sources' in traffic_sources and 'sessions' in traffic_sources:
        for i, source in enumerate(traffic_sources['sources']):
            ga4_traffic_sources_list.append({
                'utm_source': source or 'Direct',
                'sessions': traffic_sources['sessions'][i] if i < len(traffic_sources['sessions']) else 0,
                'pageviews': 0  # GA4 doesn't provide pageviews per source in this call
            })
    
    # Device Breakdown - Convert GA4 format to match template expectations
    ga4_device_breakdown_list = []
    if device_breakdown and 'devices' in device_breakdown and 'users' in device_breakdown:
        for i, device in enumerate(device_breakdown['devices']):
            ga4_device_breakdown_list.append({
                'device_type': device or 'Unknown',
                'count': device_breakdown['users'][i] if i < len(device_breakdown['users']) else 0
            })
    
    logger.info(f"GA4 Data Converted:")
    logger.info(f"  - Traffic Sources: {len(ga4_traffic_sources_list)} sources")
    logger.info(f"  - Device Breakdown: {len(ga4_device_breakdown_list)} device types")
    logger.info(f"  - Entry Pages: {len(top_entry_pages)} pages")
    logger.info(f"  - Exit Pages: {len(top_exit_pages)} pages")
    
    # Top Pages - Always use database as primary source for dynamic data
    # Database data is more reliable and always up-to-date
    db_top_pages_raw = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).exclude(page_path__isnull=True).exclude(page_path='').values('page_path', 'page_title').annotate(
        pageviews=Count('id')
    ).order_by('-pageviews')[:20]
    
    # Convert to same format as GA4 top_pages
    db_top_pages = [
        {
            'path': item.get('page_path', 'N/A'),
            'title': item.get('page_title') or item.get('page_path', 'Unknown'),
            'pageviews': item.get('pageviews', 0)
        }
        for item in db_top_pages_raw
    ]
    
    # Use database as primary source (if available), fallback to GA4
    # Database data is more reliable and always up-to-date, but GA4 has broader coverage
    if db_top_pages:
        # Database has data - use it
        final_top_pages = db_top_pages
    elif top_pages:
        # No database data, but GA4 has data - use GA4
        final_top_pages = top_pages
    else:
        # No data from either source
        final_top_pages = []
    
    # Calculate total pageviews from database if GA4 is unavailable
    db_total_pageviews = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    # Calculate total users from database if GA4 is unavailable
    db_total_users = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    logger.info(f"Database Summary Metrics:")
    logger.info(f"  - Total Users: {db_total_users}")
    logger.info(f"  - Total Pageviews: {db_total_pageviews}")
    logger.info(f"  - Top Pages (DB): {len(db_top_pages)} pages")
    
    # Summary metrics with proper fallbacks
    # Use GA4 data if available, otherwise fall back to database
    if user_metrics and 'activeUsers' in user_metrics and user_metrics['activeUsers']:
        total_users = sum(user_metrics['activeUsers'])
        users_source = "GA4"
    else:
        total_users = db_total_users
        users_source = "Database"
    
    if user_metrics and 'sessions' in user_metrics and user_metrics['sessions']:
        total_sessions_ga4 = sum(user_metrics['sessions'])
        sessions_source = "GA4"
    else:
        total_sessions_ga4 = total_sessions
        sessions_source = "Database"
    
    if user_metrics and 'screenPageViews' in user_metrics and user_metrics['screenPageViews']:
        total_pageviews = sum(user_metrics['screenPageViews'])
        pageviews_source = "GA4"
    else:
        total_pageviews = db_total_pageviews
        pageviews_source = "Database"
    
    if user_metrics and 'newUsers' in user_metrics and user_metrics['newUsers']:
        new_users = sum(user_metrics['newUsers'])
        new_users_source = "GA4"
    else:
        # For new users, we can use the same db_total_users as a fallback
        # since new users in the period would be all users created in that period
        new_users = db_total_users
        new_users_source = "Database"
    
    summary = {
        'totalUsers': total_users,
        'totalSessions': total_sessions_ga4,
        'totalPageviews': total_pageviews,
        'newUsers': new_users,
        'realTimeUsers': real_time_users or 0,
        'convertedSessions': converted_sessions,
        'avgSessionDuration': avg_session_duration or 0,
    }
    
    logger.info("=" * 80)
    logger.info("FINAL SUMMARY METRICS (What will be displayed):")
    logger.info("=" * 80)
    logger.info(f"  Total Users: {total_users} (Source: {users_source})")
    logger.info(f"  Total Sessions: {total_sessions_ga4} (Source: {sessions_source})")
    logger.info(f"  Total Pageviews: {total_pageviews} (Source: {pageviews_source})")
    logger.info(f"  New Users: {new_users} (Source: {new_users_source})")
    logger.info(f"  Real-time Users: {real_time_users or 0} (Source: GA4)")
    logger.info(f"  Converted Sessions: {converted_sessions} (Source: Database)")
    logger.info(f"  Avg Session Duration: {avg_session_duration/60:.2f} min (Source: Database)")
    logger.info(f"  Top Pages: {len(final_top_pages)} pages (Source: {'Database' if db_top_pages else 'GA4' if top_pages else 'None'})")
    
    if final_top_pages:
        logger.info("  Top 5 Pages:")
        for i, page in enumerate(final_top_pages[:5], 1):
            logger.info(f"    {i}. {page.get('title', 'Unknown')[:50]} - {page.get('pageviews', 0)} views")
    
    logger.info("=" * 80)
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'user_metrics': json.dumps(user_metrics) if user_metrics else None,
        'device_breakdown': json.dumps(device_breakdown) if device_breakdown else None,
        'db_device_breakdown': ga4_device_breakdown_list,  # Use GA4 data
        'top_pages': final_top_pages,
        'db_top_pages': db_top_pages,  # For template to know data source
        'traffic_sources': json.dumps(traffic_sources) if traffic_sources else None,
        'db_traffic_sources': ga4_traffic_sources_list,  # Use GA4 data
        'engagement': engagement,
        'summary': summary,
        'total_sessions': total_sessions,
        'converted_sessions': converted_sessions,
        'top_entry_pages': list(top_entry_pages),
        'top_exit_pages': list(top_exit_pages),
        'real_time_breakdown': real_time_breakdown,
        'real_time_users_by_country': real_time_users_by_country,
        'users_by_country': users_by_country,
        'total_country_users': sum(c.get('activeUsers', 0) for c in users_by_country) if users_by_country else 0,
        'top_pages_with_trends': top_pages_with_trends,
        'existing_users_count': existing_users_count,
        'organic_users_count': organic_users_count,
    }
    
    return render(request, 'user_analytics/web_owner_dashboard.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def user_journey_view(request, user_id=None):
    """
    User Journey Visualization
    Shows detailed journey for a specific user or all users.
    Supports filtering by user type (existing/registered vs organic/anonymous).
    """
    user_type_filter = request.GET.get('user_type', '')  # 'registered', 'organic', or ''
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    logger.info("=" * 80)
    logger.info(f"USER JOURNEY VIEW - User ID: {user_id}, User Type Filter: {user_type_filter}")
    
    # Calculate date range
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
    
    # Base queryset
    if user_id:
        journeys = UserJourney.objects.filter(
            user_id=user_id,
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('user').order_by('-start_time')
    else:
        journeys = UserJourney.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).select_related('user').order_by('-start_time')
    
    # Apply user type filter
    if user_type_filter == 'registered':
        journeys = journeys.filter(user__isnull=False)
        logger.info("Filtering for registered users only")
    elif user_type_filter == 'organic':
        journeys = journeys.filter(user__isnull=True)
        logger.info("Filtering for organic/anonymous users only")
    
    # Apply search filter
    if search_query:
        journeys = journeys.filter(
            Q(user__email__icontains=search_query) |
            Q(session_id__icontains=search_query) |
            Q(entry_page__icontains=search_query) |
            Q(exit_page__icontains=search_query)
        )
        logger.info(f"Applied search filter: {search_query}")
    
    # Calculate statistics
    total_journeys = journeys.count()
    registered_count = journeys.filter(user__isnull=False).count()
    organic_count = journeys.filter(user__isnull=True).count()
    
    logger.info(f"Journey Statistics:")
    logger.info(f"  - Total: {total_journeys}")
    logger.info(f"  - Registered Users: {registered_count}")
    logger.info(f"  - Organic Users: {organic_count}")
    
    # Pagination
    paginator = Paginator(journeys, 25)
    try:
        journeys_page = paginator.page(page_number)
    except PageNotAnInteger:
        journeys_page = paginator.page(1)
    except EmptyPage:
        journeys_page = paginator.page(paginator.num_pages)
    
    context = {
        'journeys': journeys_page,
        'user_id': user_id,
        'user_type_filter': user_type_filter,
        'time_period': time_period,
        'search_query': search_query,
        'total_count': total_journeys,
        'registered_count': registered_count,
        'organic_count': organic_count,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    logger.info("=" * 80)
    
    return render(request, 'user_analytics/user_journey.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def api_dashboard_data(request):
    """API endpoint for AJAX dashboard data updates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        dashboard_type = data.get('dashboard_type', 'business')
        time_period = data.get('period', '30days')
        
        # Calculate date range
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
        
        response_data = {}
        
        if dashboard_type == 'business':
            # Business metrics
            total_revenue = UserEvent.objects.filter(
                event_type='payment_success',
                created__gte=start_date,
                created__lte=end_date
            ).aggregate(total=Sum('event_value'))['total'] or 0
            
            response_data = {
                'total_revenue': float(total_revenue),
                'successful_payments': UserEvent.objects.filter(
                    event_type='payment_success',
                    created__gte=start_date,
                    created__lte=end_date
                ).count(),
                'total_enrollments': UserEvent.objects.filter(
                    event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed'],
                    created__gte=start_date,
                    created__lte=end_date
                ).count(),
            }
        
        elif dashboard_type == 'accounts':
            # Accounts metrics
            response_data = {
                'total_registrations': User.objects.filter(
                    created__gte=start_date,
                    created__lte=end_date
                ).count(),
                'total_revenue': float(UserEvent.objects.filter(
                    event_type='payment_success',
                    created__gte=start_date,
                    created__lte=end_date
                ).aggregate(total=Sum('event_value'))['total'] or 0),
                'total_prospects': Lead.objects.filter(
                    first_visit__gte=start_date,
                    first_visit__lte=end_date
                ).count(),
            }
        
        elif dashboard_type == 'web_owner':
            # Web owner metrics
            ga4_service = GA4Service()
            user_metrics = ga4_service.get_user_metrics(time_period)
            real_time_users = ga4_service.get_real_time_users()
            
            response_data = {
                'totalUsers': sum(user_metrics['activeUsers']) if user_metrics else 0,
                'totalSessions': sum(user_metrics['sessions']) if user_metrics else 0,
                'totalPageviews': sum(user_metrics['screenPageViews']) if user_metrics else 0,
                'realTimeUsers': real_time_users or 0,
            }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@login_required
@user_passes_test(is_staff_or_superuser)
def successful_payments_detail(request):
    """Detail page for successful payments with filters"""
    # If AJAX request, return JSON data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return successful_payments_api(request)
    
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_revenue = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    context = {
        'payments': payments_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'total_revenue': total_revenue,
        'total_amount': total_revenue,  # For consistency
        'total_count': total_count,
        'page_title': 'Successful Payments',
        'payment_type': 'successful',
    }
    
    return render(request, 'user_analytics/payments_detail.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def successful_payments_api(request):
    """API endpoint for successful payments data (AJAX)"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_revenue = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    # Serialize data
    payments_data = []
    for payment in payments_page:
        payments_data.append({
            'id': payment.id,
            'user_email': payment.user.email if payment.user else 'N/A',
            'event_name': payment.event_name or 'N/A',
            'amount': float(payment.event_value or 0),
            'date': payment.created.strftime('%b %d, %Y %H:%M') if payment.created else 'N/A',
            'source': payment.metadata.get('source', 'Unknown') if payment.metadata else 'Unknown',
            'gateway': payment.metadata.get('gateway', 'N/A') if payment.metadata else 'N/A',
            'order_id': payment.metadata.get('order_id', 'N/A') if payment.metadata else 'N/A',
        })
    
    return JsonResponse({
        'success': True,
        'payments': payments_data,
        'pagination': {
            'current_page': payments_page.number,
            'total_pages': paginator.num_pages,
            'has_previous': payments_page.has_previous(),
            'has_next': payments_page.has_next(),
            'previous_page': payments_page.previous_page_number() if payments_page.has_previous() else None,
            'next_page': payments_page.next_page_number() if payments_page.has_next() else None,
        },
        'totals': {
            'total_count': total_count,
            'total_revenue': float(total_revenue),
        }
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def failed_payments_detail(request):
    """Detail page for failed payments with filters"""
    # If AJAX request, return JSON data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return failed_payments_api(request)
    
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    context = {
        'payments': payments_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'total_amount': total_amount,
        'total_count': total_count,
        'page_title': 'Failed Payments',
        'payment_type': 'failed',
    }
    
    return render(request, 'user_analytics/payments_detail.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def failed_payments_api(request):
    """API endpoint for failed payments data (AJAX)"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    # Serialize data
    payments_data = []
    for payment in payments_page:
        payments_data.append({
            'id': payment.id,
            'user_email': payment.user.email if payment.user else 'N/A',
            'event_name': payment.event_name or 'N/A',
            'amount': float(payment.event_value or 0),
            'date': payment.created.strftime('%b %d, %Y %H:%M') if payment.created else 'N/A',
            'gateway': payment.metadata.get('gateway', 'Unknown') if payment.metadata else 'Unknown',
        })
    
    return JsonResponse({
        'success': True,
        'payments': payments_data,
        'pagination': {
            'current_page': payments_page.number,
            'total_pages': paginator.num_pages,
            'has_previous': payments_page.has_previous(),
            'has_next': payments_page.has_next(),
            'previous_page': payments_page.previous_page_number() if payments_page.has_previous() else None,
            'next_page': payments_page.next_page_number() if payments_page.has_next() else None,
        },
        'totals': {
            'total_count': total_count,
            'total_amount': float(total_amount),
        }
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def pending_payments_detail(request):
    """Detail page for pending payments with filters"""
    # If AJAX request, return JSON data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return pending_payments_api(request)
    
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    context = {
        'payments': payments_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'total_amount': total_amount,
        'total_count': total_count,
        'page_title': 'Pending Payments',
        'payment_type': 'pending',
    }
    
    return render(request, 'user_analytics/payments_detail.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def pending_payments_api(request):
    """API endpoint for pending payments data (AJAX)"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    payments = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    total_count = payments.count()
    
    # Serialize data
    payments_data = []
    for payment in payments_page:
        payments_data.append({
            'id': payment.id,
            'user_email': payment.user.email if payment.user else 'N/A',
            'event_name': payment.event_name or 'N/A',
            'amount': float(payment.event_value or 0),
            'date': payment.created.strftime('%b %d, %Y %H:%M') if payment.created else 'N/A',
            'order_id': payment.metadata.get('order_id', 'N/A') if payment.metadata else 'N/A',
        })
    
    return JsonResponse({
        'success': True,
        'payments': payments_data,
        'pagination': {
            'current_page': payments_page.number,
            'total_pages': paginator.num_pages,
            'has_previous': payments_page.has_previous(),
            'has_next': payments_page.has_next(),
            'previous_page': payments_page.previous_page_number() if payments_page.has_previous() else None,
            'next_page': payments_page.next_page_number() if payments_page.has_next() else None,
        },
        'totals': {
            'total_count': total_count,
            'total_amount': float(total_amount),
        }
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def enrollments_detail(request):
    """Detail page for enrollments with filters"""
    # If AJAX request, return JSON data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return enrollments_api(request)
    
    time_period = request.GET.get('period', '30days')
    event_type_filter = request.GET.get('event_type', '')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered'],
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply event type filter
    if event_type_filter:
        enrollments = enrollments.filter(event_type=event_type_filter)
    
    # Apply search filter
    if search_query:
        enrollments = enrollments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(enrollments, 25)
    try:
        enrollments_page = paginator.page(page_number)
    except PageNotAnInteger:
        enrollments_page = paginator.page(1)
    except EmptyPage:
        enrollments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_count = enrollments.count()
    
    # Get event type choices for filter dropdown
    event_type_choices = [
        ('', 'All Types'),
        ('course_enrolled', 'Course Enrolled'),
        ('skilllab_enrolled', 'SkillLab Enrolled'),
        ('psychometric_test_completed', 'Psychometric Test Completed'),
        ('institute_student_registered', 'Institute Student Registered'),
    ]
    
    context = {
        'enrollments': enrollments_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'event_type_filter': event_type_filter,
        'event_type_choices': event_type_choices,
        'total_count': total_count,
        'page_title': 'Enrollments',
    }
    
    return render(request, 'user_analytics/enrollments_detail.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def business_metrics_api(request):
    """API endpoint for business dashboard key metrics (AJAX)"""
    time_period = request.GET.get('period', '30days')
    
    # Calculate date range
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
    
    # Calculate Total Revenue
    revenue_events = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    )
    total_revenue = revenue_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Calculate Successful Payments
    successful_payments = revenue_events.count()
    
    # Calculate Total Enrollments
    total_enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered'],
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    # Calculate other metrics
    failed_payment_events = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    )
    failed_payments = failed_payment_events.count()
    failed_payments_revenue = failed_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    pending_payment_events = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    )
    pending_payments = pending_payment_events.count()
    pending_payments_revenue = pending_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    psychometric_enrollments = UserEvent.objects.filter(
        event_type='psychometric_test_completed',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    course_enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled'],
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    total_visitors = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('session_id').distinct().count()
    
    total_registrations = UserEvent.objects.filter(
        event_type='registration',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
    total_leads = Lead.objects.filter(
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).count()
    
    converted_leads = Lead.objects.filter(
        is_converted=True,
        converted_at__gte=start_date,
        converted_at__lte=end_date
    ).count()
    
    conversion_rate = (converted_leads / total_visitors * 100) if total_visitors > 0 else 0
    
    return JsonResponse({
        'success': True,
        'metrics': {
            'total_revenue': float(total_revenue),
            'successful_payments': successful_payments,
            'total_enrollments': total_enrollments,
            'failed_payments': failed_payments,
            'failed_payments_revenue': float(failed_payments_revenue),
            'pending_payments': pending_payments,
            'pending_payments_revenue': float(pending_payments_revenue),
            'psychometric_enrollments': psychometric_enrollments,
            'course_enrollments': course_enrollments,
            'total_visitors': total_visitors,
            'total_registrations': total_registrations,
            'total_leads': total_leads,
            'converted_leads': converted_leads,
            'conversion_rate': round(conversion_rate, 2),
        },
        'period': time_period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def enrollments_api(request):
    """API endpoint for enrollments data (AJAX)"""
    time_period = request.GET.get('period', '30days')
    event_type_filter = request.GET.get('event_type', '')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered'],
        created__gte=start_date,
        created__lte=end_date
    ).select_related('user').order_by('-created')
    
    # Apply event type filter
    if event_type_filter:
        enrollments = enrollments.filter(event_type=event_type_filter)
    
    # Apply search filter
    if search_query:
        enrollments = enrollments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(enrollments, 25)
    try:
        enrollments_page = paginator.page(page_number)
    except PageNotAnInteger:
        enrollments_page = paginator.page(1)
    except EmptyPage:
        enrollments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_count = enrollments.count()
    
    # Serialize data
    enrollments_data = []
    for enrollment in enrollments_page:
        event_type_display = 'Unknown'
        if enrollment.event_type == 'course_enrolled':
            event_type_display = 'Course Enrolled'
        elif enrollment.event_type == 'skilllab_enrolled':
            event_type_display = 'SkillLab Enrolled'
        elif enrollment.event_type == 'psychometric_test_completed':
            event_type_display = 'Psychometric Test'
        elif enrollment.event_type == 'institute_student_registered':
            event_type_display = 'Institute Student'
        
        enrollments_data.append({
            'id': enrollment.id,
            'user_email': enrollment.user.email if enrollment.user else 'N/A',
            'event_type': enrollment.event_type,
            'event_type_display': event_type_display,
            'event_name': enrollment.event_name or 'N/A',
            'date': enrollment.created.strftime('%b %d, %Y %H:%M') if enrollment.created else 'N/A',
            'amount': float(enrollment.event_value or 0),
        })
    
    return JsonResponse({
        'success': True,
        'enrollments': enrollments_data,
        'pagination': {
            'current_page': enrollments_page.number,
            'total_pages': paginator.num_pages,
            'has_previous': enrollments_page.has_previous(),
            'has_next': enrollments_page.has_next(),
            'previous_page': enrollments_page.previous_page_number() if enrollments_page.has_previous() else None,
            'next_page': enrollments_page.next_page_number() if enrollments_page.has_next() else None,
        },
        'totals': {
            'total_count': total_count,
        }
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def registrations_detail(request):
    """Detail page for user registrations with filters"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    users = User.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).order_by('-created')
    
    # Apply search filter
    if search_query:
        users = users.filter(
            Q(email__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(mobile__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 25)
    try:
        users_page = paginator.page(page_number)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_count = users.count()
    
    context = {
        'users': users_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'total_count': total_count,
        'page_title': 'User Registrations',
    }
    
    return render(request, 'user_analytics/registrations_detail.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def prospects_detail(request):
    """Detail page for prospects/leads with filters"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    converted_filter = request.GET.get('converted', '')
    page_number = request.GET.get('page', 1)
    
    # Calculate date range
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
    
    # Base queryset
    leads = Lead.objects.filter(
        first_visit__gte=start_date,
        first_visit__lte=end_date
    ).order_by('-first_visit')
    
    # Apply converted filter
    if converted_filter == 'yes':
        leads = leads.filter(is_converted=True)
    elif converted_filter == 'no':
        leads = leads.filter(is_converted=False)
    
    # Apply search filter
    if search_query:
        leads = leads.filter(
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(source__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(leads, 25)
    try:
        leads_page = paginator.page(page_number)
    except PageNotAnInteger:
        leads_page = paginator.page(1)
    except EmptyPage:
        leads_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    total_count = leads.count()
    
    context = {
        'leads': leads_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'converted_filter': converted_filter,
        'total_count': total_count,
        'page_title': 'Prospects/Leads',
    }
    
    return render(request, 'user_analytics/prospects_detail.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def visitors_detail(request):
    """Detail page for visitors/sessions with filters"""
    time_period = request.GET.get('period', 'today')
    search_query = request.GET.get('search', '')
    source_filter = request.GET.get('source', '')
    device_filter = request.GET.get('device', '')
    entry_page_filter = request.GET.get('entry_page', '')
    exit_page_filter = request.GET.get('exit_page', '')
    country_filter = request.GET.get('country', '')  # Added country filter
    page_number = request.GET.get('page', 1)
    
    logger.info("=" * 80)
    logger.info(f"VISITORS DETAIL - Time Period: {time_period}")
    logger.info(f"Source Filter (raw): {source_filter}")
    logger.info(f"Device Filter (raw): {device_filter}")
    logger.info(f"Entry Page Filter (raw): {entry_page_filter}")
    logger.info(f"Exit Page Filter (raw): {exit_page_filter}")
    logger.info(f"Country Filter (raw): {country_filter}")
    logger.info(f"Search Query: {search_query}")
    
    # Decode all URL-encoded filters
    if source_filter:
        source_filter = unquote(source_filter)
        logger.info(f"Source Filter (decoded): {source_filter}")
    if device_filter:
        device_filter = unquote(device_filter)
        logger.info(f"Device Filter (decoded): {device_filter}")
    if entry_page_filter:
        entry_page_filter = unquote(entry_page_filter)
        logger.info(f"Entry Page Filter (decoded): {entry_page_filter}")
    if exit_page_filter:
        exit_page_filter = unquote(exit_page_filter)
        logger.info(f"Exit Page Filter (decoded): {exit_page_filter}")
    if country_filter:
        country_filter = unquote(country_filter)
        logger.info(f"Country Filter (decoded): {country_filter}")
    
    # Calculate date range
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
    
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get unique session IDs with filters
    session_query = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    )
    
    if source_filter:
        # Handle variations of "direct" traffic
        # GA4 might store it as "(direct)", "direct", "(not set)", or empty/null
        if source_filter.lower() in ['(direct)', 'direct', '(not set)']:
            # Match direct traffic - could be stored as various forms
            session_query = session_query.filter(
                Q(utm_source__iexact='(direct)') |
                Q(utm_source__iexact='direct') |
                Q(utm_source__iexact='(not set)') |
                Q(utm_source__isnull=True) |
                Q(utm_source='')
            )
            logger.info("Filtering for direct traffic (handling variations)")
        else:
            # Exact match for other sources
            session_query = session_query.filter(utm_source__iexact=source_filter)
            logger.info(f"Filtering for source: {source_filter}")
    
    if device_filter:
        session_query = session_query.filter(device_type__iexact=device_filter)
        logger.info(f"Filtering for device: {device_filter}")
    
    session_ids = list(session_query.values_list('session_id', flat=True).distinct())
    logger.info(f"Found {len(session_ids)} unique session IDs matching filters")
    
    # Check if we have any data at all in the date range
    total_activities = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).count()
    logger.info(f"Total UserActivity records in date range: {total_activities}")
    
    # Check unique sources in database for debugging
    unique_sources = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).exclude(utm_source__isnull=True).exclude(utm_source='').values_list('utm_source', flat=True).distinct()[:10]
    logger.info(f"Sample unique sources in database: {list(unique_sources)}")
    
    # If no session IDs found, check if we should use GA4 data or show helpful message
    use_ga4_fallback = len(session_ids) == 0 and total_activities == 0
    
    if use_ga4_fallback:
        logger.warning("No database records found. Consider using GA4 data for visitors detail.")
        logger.info("Note: GA4 doesn't provide individual session details, only aggregated metrics.")
    
    # Get first activity for each session
    session_details = []
    for session_id in session_ids:
        first_activity = UserActivity.objects.filter(
            session_id=session_id
        ).order_by('created').first()
        
        if first_activity:
            # Apply entry/exit page filters
            if entry_page_filter:
                journey = UserJourney.objects.filter(
                    session_id=session_id,
                    entry_page=entry_page_filter
                ).first()
                if not journey:
                    continue
            
            if exit_page_filter:
                journey = UserJourney.objects.filter(
                    session_id=session_id,
                    exit_page=exit_page_filter
                ).first()
                if not journey:
                    continue
            
            # Apply country filter (check UserActivity or UserJourney)
            if country_filter:
                # Check if country matches in first activity or journey
                country_match = False
                if first_activity.country and country_filter.lower() in first_activity.country.lower():
                    country_match = True
                else:
                    journey = UserJourney.objects.filter(session_id=session_id).first()
                    if journey and journey.country and country_filter.lower() in journey.country.lower():
                        country_match = True
                if not country_match:
                    continue
            
            # Apply search filter early
            if search_query:
                user_match = first_activity.user and first_activity.user.email and search_query.lower() in first_activity.user.email.lower()
                session_match = search_query.lower() in session_id.lower()
                if not (user_match or session_match):
                    continue
            
            session_details.append({
                'session_id': session_id,
                'user': first_activity.user,
                'first_visit': first_activity.created,
                'page_views': UserActivity.objects.filter(session_id=session_id).count(),
                'device_type': first_activity.device_type,
                'utm_source': first_activity.utm_source or 'Direct',
            })
    
    # Sort by first visit
    session_details.sort(key=lambda x: x['first_visit'], reverse=True)
    
    # Calculate totals before pagination
    total_count = len(session_details)
    
    logger.info(f"Total sessions found: {total_count}")
    logger.info("=" * 80)
    
    # Manual pagination for list
    items_per_page = 25
    try:
        page_number = int(page_number)
    except (ValueError, TypeError):
        page_number = 1
    
    start_index = (page_number - 1) * items_per_page
    end_index = start_index + items_per_page
    sessions_page_data = session_details[start_index:end_index]
    
    # Create a paginator-like object for template compatibility
    from django.core.paginator import Page, Paginator
    paginator = Paginator(range(total_count), items_per_page)
    try:
        paginator_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        paginator_page = paginator.page(1)
    
    # Create a custom page object with our data
    class CustomPage:
        def __init__(self, data, paginator_page):
            self.object_list = data
            self.number = paginator_page.number
            self.paginator = paginator_page.paginator
            self.has_previous = paginator_page.has_previous()
            self.has_next = paginator_page.has_next()
            self.previous_page_number = paginator_page.previous_page_number() if self.has_previous else None
            self.next_page_number = paginator_page.next_page_number() if self.has_next else None
            self.start_index = start_index + 1
        
        @property
        def has_other_pages(self):
            return self.paginator.num_pages > 1
    
    sessions_page = CustomPage(sessions_page_data, paginator_page)
    
    # Build filter params for pagination links
    filter_params = {
        'period': time_period,
    }
    if source_filter:
        filter_params['source'] = source_filter
    if device_filter:
        filter_params['device'] = device_filter
    if entry_page_filter:
        filter_params['entry_page'] = entry_page_filter
    if exit_page_filter:
        filter_params['exit_page'] = exit_page_filter
    if country_filter:
        filter_params['country'] = country_filter
    if search_query:
        filter_params['search'] = search_query
    
    context = {
        'sessions': sessions_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'source_filter': source_filter,
        'device_filter': device_filter,
        'entry_page_filter': entry_page_filter,
        'exit_page_filter': exit_page_filter,
        'country_filter': country_filter,
        'filter_params': filter_params,
        'total_count': total_count,
        'total_activities_in_range': total_activities,
        'use_ga4_fallback': use_ga4_fallback,
        'page_title': 'Visitors/Sessions',
    }
    
    logger.info("=" * 80)
    
    return render(request, 'user_analytics/visitors_detail.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def pageviews_detail(request):
    """Detail page for pageviews with filters"""
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    path_filter = request.GET.get('path', '')
    source_filter = request.GET.get('source', '')
    page_number = request.GET.get('page', 1)
    
    logger.info("=" * 80)
    logger.info(f"PAGEVIEWS DETAIL - Time Period: {time_period}")
    logger.info(f"Path Filter (raw): {path_filter}")
    logger.info(f"Source Filter: {source_filter}")
    logger.info(f"Search Query: {search_query}")
    
    # Calculate date range
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
    
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Use GA4 data directly (skip database for now)
    ga4_pageviews = None
    data_source = 'ga4'
    pageviews_page = None
    total_count = 0
    
    # If path filter is set, get data from GA4
    if path_filter:
        # Decode URL-encoded path
        path_filter_decoded = unquote(path_filter)
        # Store decoded version for display
        path_filter = path_filter_decoded
        
        logger.info(f"Path Filter (decoded): {path_filter_decoded}")
        logger.info("Fetching data from GA4...")
        
        ga4_service = GA4Service()
        ga4_pageviews = ga4_service.get_pageviews_by_path(
            path_filter_decoded, 
            time_period=time_period, 
            limit=1000, 
            use_cache=False
        )
        
        if ga4_pageviews:
            logger.info(f"Found {len(ga4_pageviews)} pageview records from GA4")
            
            # Apply source filter if provided
            if source_filter:
                source_filter_decoded = unquote(source_filter)
                ga4_pageviews = [p for p in ga4_pageviews if p.get('source', '').lower() == source_filter_decoded.lower()]
                logger.info(f"After source filter: {len(ga4_pageviews)} records")
            
            # Apply search filter if provided
            if search_query:
                search_lower = search_query.lower()
                ga4_pageviews = [
                    p for p in ga4_pageviews 
                    if search_lower in p.get('page_title', '').lower() 
                    or search_lower in p.get('page_path', '').lower()
                    or search_lower in p.get('source', '').lower()
                ]
                logger.info(f"After search filter: {len(ga4_pageviews)} records")
            
            # Paginate GA4 data
            if ga4_pageviews:
                total_count = len(ga4_pageviews)
                items_per_page = 25
                try:
                    page_number = int(page_number)
                except (ValueError, TypeError):
                    page_number = 1
                
                start_index = (page_number - 1) * items_per_page
                end_index = start_index + items_per_page
                ga4_pageviews_page = ga4_pageviews[start_index:end_index]
                
                # Create paginator-like object for GA4 data
                paginator = Paginator(range(total_count), items_per_page)
                try:
                    paginator_page = paginator.page(page_number)
                except (PageNotAnInteger, EmptyPage):
                    paginator_page = paginator.page(1)
                
                # Create custom page object
                class GA4Page:
                    def __init__(self, data, paginator_page, total_count):
                        self.object_list = data
                        self.number = paginator_page.number
                        self.paginator = paginator_page.paginator
                        self.has_previous = paginator_page.has_previous()
                        self.has_next = paginator_page.has_next()
                        self.previous_page_number = paginator_page.previous_page_number() if self.has_previous else None
                        self.next_page_number = paginator_page.next_page_number() if self.has_next else None
                        self.start_index = (paginator_page.number - 1) * items_per_page + 1
                    
                    @property
                    def has_other_pages(self):
                        return self.paginator.num_pages > 1
                
                pageviews_page = GA4Page(ga4_pageviews_page, paginator_page, total_count)
                logger.info(f"Created GA4Page with {len(ga4_pageviews_page)} items on page {page_number}")
            else:
                # No data after filtering
                pageviews_page = None
                logger.info("No data after applying filters")
        else:
            logger.info("No GA4 data found for this path")
            pageviews_page = None
    else:
        # No path filter - show message that path filter is required
        logger.info("No path filter provided. GA4 requires a path filter to show pageview details.")
        pageviews_page = None
    
    logger.info("=" * 80)
    logger.info(f"FINAL RESULTS:")
    logger.info(f"  Data Source: {data_source}")
    logger.info(f"  Total pageviews matching filters: {total_count}")
    logger.info(f"  Page number: {page_number}")
    if pageviews_page and hasattr(pageviews_page, 'object_list'):
        logger.info(f"  Pageviews on this page: {len(pageviews_page.object_list)}")
        if pageviews_page.object_list:
            logger.info(f"  Sample data (first item): {pageviews_page.object_list[0]}")
    else:
        logger.info(f"  Pageviews on this page: None (no data)")
    logger.info("=" * 80)
    
    context = {
        'pageviews': pageviews_page,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'path_filter': path_filter,
        'source_filter': source_filter,
        'total_count': total_count,
        'page_title': 'Pageviews',
        'data_source': data_source,  # 'database' or 'ga4'
    }
    
    return render(request, 'user_analytics/pageviews_detail.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def pageviews_paths_api(request):
    """API endpoint to get all available page paths for autocomplete"""
    time_period = request.GET.get('period', '30days')
    
    logger.info("=" * 80)
    logger.info(f"PAGEVIEWS PATHS API - Time Period: {time_period}")
    
    ga4_service = GA4Service()
    paths = ga4_service.get_all_page_paths(time_period=time_period, limit=1000, use_cache=False)
    
    logger.info(f"Found {len(paths)} unique paths")
    if paths:
        logger.info(f"Sample paths (first 10): {paths[:10]}")
    logger.info("=" * 80)
    
    return JsonResponse({
        'success': True,
        'paths': paths,
        'count': len(paths)
    })
