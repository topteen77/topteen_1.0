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
import json

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
    
    # Quick Stats
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    total_payments = Payment.objects.count()
    successful_payments = Payment.objects.filter(is_success=choices.YesNoChoices.YES).count()
    
    # Recent Activity
    recent_registrations = User.objects.order_by('-created')[:10]
    recent_payments = Payment.objects.order_by('-created')[:10]
    
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
    
    # Initialize GA4 Service
    ga4_service = GA4Service()
    
    # Get GA4 metrics
    user_metrics = ga4_service.get_user_metrics(time_period)
    device_breakdown = ga4_service.get_device_breakdown(time_period)
    top_pages = ga4_service.get_top_pages(time_period, limit=20)
    traffic_sources = ga4_service.get_traffic_sources(time_period, limit=15)
    engagement = ga4_service.get_user_engagement(time_period)
    real_time_users = ga4_service.get_real_time_users()
    
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
    
    # Top Entry Pages
    top_entry_pages = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).values('entry_page').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Top Exit Pages
    top_exit_pages = UserJourney.objects.filter(
        start_time__gte=start_date,
        start_time__lte=end_date
    ).exclude(exit_page__isnull=True).values('exit_page').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Traffic Sources (from database)
    db_traffic_sources = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('utm_source').annotate(
        sessions=Count('session_id', distinct=True),
        pageviews=Count('id')
    ).order_by('-sessions')[:15]
    
    # Device Breakdown (from database)
    db_device_breakdown = UserActivity.objects.filter(
        created__gte=start_date,
        created__lte=end_date
    ).values('device_type').annotate(
        count=Count('session_id', distinct=True)
    ).order_by('-count')
    
    # Summary metrics
    summary = {
        'totalUsers': sum(user_metrics['activeUsers']) if user_metrics else 0,
        'totalSessions': sum(user_metrics['sessions']) if user_metrics else total_sessions,
        'totalPageviews': sum(user_metrics['screenPageViews']) if user_metrics else 0,
        'newUsers': sum(user_metrics['newUsers']) if user_metrics else 0,
        'realTimeUsers': real_time_users or 0,
        'convertedSessions': converted_sessions,
        'avgSessionDuration': avg_session_duration,
    }
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'user_metrics': json.dumps(user_metrics) if user_metrics else None,
        'device_breakdown': json.dumps(device_breakdown) if device_breakdown else None,
        'db_device_breakdown': list(db_device_breakdown),
        'top_pages': top_pages or [],
        'traffic_sources': json.dumps(traffic_sources) if traffic_sources else None,
        'db_traffic_sources': list(db_traffic_sources),
        'engagement': engagement,
        'summary': summary,
        'total_sessions': total_sessions,
        'converted_sessions': converted_sessions,
        'top_entry_pages': list(top_entry_pages),
        'top_exit_pages': list(top_exit_pages),
    }
    
    return render(request, 'user_analytics/web_owner_dashboard.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def user_journey_view(request, user_id=None):
    """
    User Journey Visualization
    Shows detailed journey for a specific user or all users.
    """
    if user_id:
        journeys = UserJourney.objects.filter(user_id=user_id).order_by('-start_time')
    else:
        journeys = UserJourney.objects.all().order_by('-start_time')[:100]
    
    context = {
        'journeys': journeys,
        'user_id': user_id,
    }
    
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
