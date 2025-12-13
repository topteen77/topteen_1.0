"""
Analytics Dashboard Views for Business Owner, Accounts, and Web Owner.
Provides comprehensive analytics reports and visualizations.
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
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
    failed_payments = UserEvent.objects.filter(
        event_type='payment_failed',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    pending_payments = UserEvent.objects.filter(
        event_type='payment_pending',
        created__gte=start_date,
        created__lte=end_date
    ).count()
    
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
    
    # Revenue by Source
    revenue_by_source = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).values('metadata__source').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('-revenue')[:10]
    
    # Daily Revenue Trend
    daily_revenue = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).extra(
        select={'day': 'DATE(created)'}
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
    
    context = {
        'time_period': time_period,
        'start_date': start_date,
        'end_date': end_date,
        'total_revenue': total_revenue,
        'successful_payments': successful_payments,
        'failed_payments': failed_payments,
        'pending_payments': pending_payments,
        'total_enrollments': total_enrollments,
        'psychometric_enrollments': psychometric_enrollments,
        'course_enrollments': course_enrollments,
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
    
    # Revenue by Source
    revenue_by_source = UserEvent.objects.filter(
        event_type='payment_success',
        created__gte=start_date,
        created__lte=end_date
    ).values('metadata__source').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('-revenue')
    
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
