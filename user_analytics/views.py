"""
Analytics Dashboard Views for Business Owner, Accounts, and Web Owner.
Provides comprehensive analytics reports and visualizations.
"""
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.html import format_html
from django.middleware.csrf import get_token
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import unquote
import json
import logging

logger = logging.getLogger(__name__)

from user_analytics.models import UserActivity, Lead, UserEvent, UserJourney, AnalyticsCache, EnquirySource
# GA4Session imported conditionally in functions that need it
from user_analytics.ga4_service import GA4Service
from users.models import User
from payments.models import Payment
from psychometric_tests.models import PsychometricTestPayment
from core import choices


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def get_date_range_from_period(time_period, default_days=30):
    """
    Helper function to calculate date range from time period string.
    Returns (start_date, end_date) tuple. For 'alltime', returns (None, None).
    
    Args:
        time_period: One of 'today', 'yesterday', '7days', '30days', '90days', 'alltime'
        default_days: Default number of days if period is invalid (default: 30)
    
    Returns:
        tuple: (start_date, end_date) - both datetime objects, or (None, None) for 'alltime'
    """
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
    elif time_period == 'alltime':
        # For all time, return None to indicate no date filtering
        return (None, None)
    else:
        # Default to specified number of days
        start_date = end_date - timedelta(days=default_days)
    
    return (start_date, end_date)


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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Quick Stats - Filtered by period
    total_users_query = User.objects.all()
    if start_date is not None:
        total_users_query = total_users_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_users = total_users_query.count()
    
    active_users_query = User.objects.filter(is_active=True)
    if start_date is not None:
        active_users_query = active_users_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    active_users = active_users_query.count()
    
    total_payments_query = Payment.objects.all()
    if start_date is not None:
        total_payments_query = total_payments_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_payments = total_payments_query.count()
    
    successful_payments_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
    if start_date is not None:
        successful_payments_query = successful_payments_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    successful_payments = successful_payments_query.count()
    
    # Recent Activity - Filtered by period
    recent_registrations_query = User.objects.all()
    if start_date is not None:
        recent_registrations_query = recent_registrations_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    recent_registrations = recent_registrations_query.order_by('-created')[:10]
    
    recent_payments_query = Payment.objects.all()
    if start_date is not None:
        recent_payments_query = recent_payments_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    recent_payments = recent_payments_query.order_by('-created')[:10]
    
    # Analytics Summary
    total_page_views_query = UserActivity.objects.all()
    if start_date is not None:
        total_page_views_query = total_page_views_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_page_views = total_page_views_query.count()
    
    total_sessions_query = UserActivity.objects.all()
    if start_date is not None:
        total_sessions_query = total_sessions_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_sessions = total_sessions_query.values('session_id').distinct().count()
    
    total_revenue_query = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        total_revenue_query = total_revenue_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_revenue = total_revenue_query.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    total_leads_query = Lead.objects.all()
    if start_date is not None:
        total_leads_query = total_leads_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_leads = total_leads_query.count()
    
    context = {
        'time_period': time_period,
        'start_date': start_date,  # Can be None for alltime
        'end_date': end_date,  # Can be None for alltime
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Revenue Metrics - Check UserEvent first, then fallback to Payment model
    revenue_events = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        revenue_events = revenue_events.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_revenue = revenue_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    successful_payments_from_events = revenue_events.count()
    
    # Fallback to Payment model if UserEvent has no data
    if total_revenue == 0 or successful_payments_from_events == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            # Get successful payments from Payment model
            successful_payments_model = Payment.objects.filter(
                is_success=choices.YesNoChoices.YES
            )
            if start_date is not None:
                successful_payments_model = successful_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            
            # Calculate revenue from Payment model
            payment_revenue = successful_payments_model.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Use Payment model data if it has more revenue
            if payment_revenue > total_revenue:
                total_revenue = payment_revenue
                successful_payments = successful_payments_model.count()
                logger.info(f"Using Payment model data: {successful_payments} payments, {total_revenue} revenue")
            else:
                successful_payments = successful_payments_from_events
        except Exception as e:
            logger.warning(f"Error fetching Payment model data: {e}")
            successful_payments = successful_payments_from_events
    else:
        successful_payments = successful_payments_from_events
    
    # Failed Payments - Calculate count and attempted revenue
    failed_payment_events = UserEvent.objects.filter(event_type='payment_failed')
    if start_date is not None:
        failed_payment_events = failed_payment_events.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    failed_payments = failed_payment_events.count()
    failed_payments_revenue = failed_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Fallback to Payment model for failed payments if UserEvent has no data
    if failed_payments == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            failed_payments_model = Payment.objects.filter(
                is_success=choices.YesNoChoices.NO
            )
            if start_date is not None:
                failed_payments_model = failed_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            failed_payments = failed_payments_model.count()
            failed_payments_revenue = failed_payments_model.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        except Exception:
            pass
    
    # Pending Payments - Calculate count and potential revenue
    pending_payment_events = UserEvent.objects.filter(event_type='payment_pending')
    if start_date is not None:
        pending_payment_events = pending_payment_events.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    pending_payments = pending_payment_events.count()
    pending_payments_revenue = pending_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Enrollment Metrics
    enrollment_events = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered']
    )
    if start_date is not None:
        enrollment_events = enrollment_events.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_enrollments = enrollment_events.count()
    
    psychometric_query = UserEvent.objects.filter(event_type='psychometric_test_completed')
    course_query = UserEvent.objects.filter(event_type__in=['course_enrolled', 'skilllab_enrolled'])
    
    if start_date is not None:
        psychometric_query = psychometric_query.filter(created__gte=start_date, created__lte=end_date)
        course_query = course_query.filter(created__gte=start_date, created__lte=end_date)
    
    psychometric_enrollments = psychometric_query.count()
    course_enrollments = course_query.count()
    
    # Psychometric Test Revenue Breakdown
    # Class 12 = Career Direction = ADVANCED test
    class12_query = UserEvent.objects.filter(event_type='payment_success').filter(
        Q(metadata__test_name='Career Direction') |
        Q(metadata__test_type='Advanced test') |
        Q(event_name__icontains='Career Direction')
    )
    if start_date is not None:
        class12_query = class12_query.filter(created__gte=start_date, created__lte=end_date)
    
    class12_psychometric_revenue = class12_query.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    class12_psychometric_count = class12_query.count()
    
    # Stream Sorter (Class 10-11) = BASIC test
    stream_sorter_query = UserEvent.objects.filter(event_type='payment_success').filter(
        Q(metadata__test_name='Stream Sorter') |
        Q(event_name__icontains='Stream Sorter')
    )
    if start_date is not None:
        stream_sorter_query = stream_sorter_query.filter(created__gte=start_date, created__lte=end_date)
    
    stream_sorter_revenue = stream_sorter_query.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    stream_sorter_count = stream_sorter_query.count()
    
    # Conversion Funnel
    visitors_query = UserActivity.objects.all()
    registrations_query = UserEvent.objects.filter(event_type='registration')
    
    if start_date is not None:
        visitors_query = visitors_query.filter(created__gte=start_date, created__lte=end_date)
        registrations_query = registrations_query.filter(created__gte=start_date, created__lte=end_date)
    
    total_visitors = visitors_query.values('session_id').distinct().count()
    total_registrations = registrations_query.count()
    
    from core import choices
    
    total_leads_query = Lead.objects.all()
    converted_leads_query = Lead.objects.filter(is_converted=True)
    
    if start_date is not None:
        total_leads_query = total_leads_query.filter(
            first_visit__gte=start_date,
            first_visit__lte=end_date
        )
        converted_leads_query = converted_leads_query.filter(
            converted_at__gte=start_date,
            converted_at__lte=end_date
        )
    
    total_leads = total_leads_query.count()
    converted_leads = converted_leads_query.count()
    
    # Revenue by Source - Query JSONField properly
    revenue_by_source_raw = UserEvent.objects.filter(event_type='payment_success').exclude(metadata__isnull=True)
    if start_date is not None:
        revenue_by_source_raw = revenue_by_source_raw.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    
    # Process revenue by source manually since JSONField queries can be tricky
    revenue_by_source_dict = {}
    for event in revenue_by_source_raw:
        source = event.metadata.get('source', 'Unknown') if event.metadata else 'Unknown'
        if source not in revenue_by_source_dict:
            revenue_by_source_dict[source] = {'revenue': Decimal('0'), 'count': 0}
        revenue_by_source_dict[source]['revenue'] += event.event_value or Decimal('0')
        revenue_by_source_dict[source]['count'] += 1
    
    # If no revenue by source from UserEvent, try Payment model by obj_type
    if not revenue_by_source_dict or sum(data['revenue'] for data in revenue_by_source_dict.values()) == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            payment_revenue_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                payment_revenue_query = payment_revenue_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            
            # Group by obj_type (payment type)
            for payment in payment_revenue_query:
                obj_type_name = dict(choices.PaymentObjectType.CHOICES).get(payment.obj_type, f'Type {payment.obj_type}')
                if obj_type_name not in revenue_by_source_dict:
                    revenue_by_source_dict[obj_type_name] = {'revenue': Decimal('0'), 'count': 0}
                revenue_by_source_dict[obj_type_name]['revenue'] += payment.amount or Decimal('0')
                revenue_by_source_dict[obj_type_name]['count'] += 1
        except Exception as e:
            logger.warning(f"Error fetching revenue by source from Payment model: {e}")
    
    # Convert to list and sort by revenue
    revenue_by_source = [
        {'metadata__source': source, 'revenue': float(data['revenue']), 'count': data['count']}
        for source, data in sorted(revenue_by_source_dict.items(), key=lambda x: x[1]['revenue'], reverse=True)
    ][:10]
    
    # Daily Revenue Trend - Use TruncDate for better database compatibility
    # Try UserEvent first, fallback to Payment model
    daily_revenue_query = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        daily_revenue_query = daily_revenue_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    daily_revenue = daily_revenue_query.annotate(
        day=TruncDate('created')
    ).values('day').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('day')
    
    # Fallback to Payment model if no UserEvent data
    if not daily_revenue.exists():
        try:
            from payments.models import Payment
            from core import choices
            
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            daily_revenue = payment_query.annotate(
                day=TruncDate('created')
            ).values('day').annotate(
                revenue=Sum('amount'),
                count=Count('id')
            ).order_by('day')
        except Exception as e:
            logger.warning(f"Error fetching daily revenue from Payment model: {e}")
    
    # Top Products/Services
    top_products_query = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        top_products_query = top_products_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    top_products = top_products_query.values('event_name').annotate(
        revenue=Sum('event_value'),
        count=Count('id')
    ).order_by('-revenue')[:10]
    
    # Fallback to Payment model if no UserEvent data
    if not top_products.exists():
        try:
            from payments.models import Payment
            from core import choices
            
            # Get top products by payment object type
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            top_products = payment_query.values('obj_type').annotate(
                revenue=Sum('amount'),
                count=Count('id')
            ).order_by('-revenue')[:10]
            
            # Convert obj_type to readable names
            top_products_list = []
            for item in top_products:
                obj_type = item['obj_type']
                type_name = dict(choices.PaymentObjectType.CHOICES).get(obj_type, f'Type {obj_type}')
                top_products_list.append({
                    'event_name': type_name,
                    'revenue': float(item['revenue']),
                    'count': item['count']
                })
            top_products = top_products_list
        except Exception as e:
            logger.warning(f"Error fetching top products from Payment model: {e}")
    
    # Calculate summary metrics
    total_attempts = successful_payments + failed_payments + pending_payments
    success_rate = (successful_payments / total_attempts * 100) if total_attempts > 0 else 0
    
    # Calculate total attempted revenue - use Payment model if we're using it for successful/failed
    # This ensures consistency (all from Payment model or all from UserEvent)
    total_attempted_revenue = total_revenue + failed_payments_revenue + pending_payments_revenue
    
    # If we're using Payment model for successful/failed, also calculate total attempted from Payment model
    # to ensure consistency
    try:
        from payments.models import Payment
        from core import choices
        
        # Check if we should use Payment model for total attempted
        # (if successful or failed payments came from Payment model)
        payment_model_successful = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
        payment_model_failed = Payment.objects.filter(is_success=choices.YesNoChoices.NO)
        if start_date is not None:
            payment_model_successful = payment_model_successful.filter(created__gte=start_date, created__lte=end_date)
            payment_model_failed = payment_model_failed.filter(created__gte=start_date, created__lte=end_date)
        
        payment_successful_revenue = payment_model_successful.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        payment_failed_revenue = payment_model_failed.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        payment_total_attempted = payment_successful_revenue + payment_failed_revenue
        
        # If Payment model has more data, use it for total attempted
        if payment_total_attempted > total_attempted_revenue:
            total_attempted_revenue = payment_total_attempted
            logger.info(f"Using Payment model for total attempted revenue: ₹{total_attempted_revenue}")
    except Exception as e:
        logger.warning(f"Error calculating total attempted revenue from Payment model: {e}")
    
    conversion_value_rate = (total_revenue / total_attempted_revenue * 100) if total_attempted_revenue > 0 else 0
    
    # Goal-Based Analytics
    goal_events_query = UserEvent.objects.exclude(
        event_type__in=['page_view', 'payment_failed', 'payment_pending']
    )
    if start_date is not None:
        goal_events_query = goal_events_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    
    # Group goals by type
    goal_analytics = {}
    goal_types = [
        ('registration', 'User Registration'),
        ('payment_success', 'Payment Success'),
        ('psychometric_test_started', 'Psychometric Test Started'),
        ('psychometric_test_completed', 'Psychometric Test Completed'),
        ('result_generated', 'Result Generated'),
        ('course_enrolled', 'Course Enrolled'),
        ('skilllab_enrolled', 'SkillLab Course Enrolled'),
        ('institute_student_registered', 'Institute Student Registered'),
    ]
    
    for goal_type, goal_name in goal_types:
        goal_count = goal_events_query.filter(event_type=goal_type).count()
        if goal_type == 'payment_success':
            goal_value = goal_events_query.filter(event_type=goal_type).aggregate(
                total=Sum('event_value')
            )['total'] or Decimal('0')
        else:
            goal_value = Decimal('0')
        
        if goal_count > 0:
            goal_analytics[goal_type] = {
                'name': goal_name,
                'count': goal_count,
                'value': float(goal_value),
            }
    
    # Calculate goal conversion rates
    if total_visitors > 0:
        for goal_type in goal_analytics:
            goal_analytics[goal_type]['conversion_rate'] = (
                goal_analytics[goal_type]['count'] / total_visitors * 100
            )
    else:
        for goal_type in goal_analytics:
            goal_analytics[goal_type]['conversion_rate'] = 0
    
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
        'goal_analytics': goal_analytics,
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # User Registration Trends
    user_registrations = User.objects.all()
    if start_date is not None:
        user_registrations = user_registrations.filter(
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
    payment_success_query = UserEvent.objects.filter(event_type='payment_success')
    payment_failed_query = UserEvent.objects.filter(event_type='payment_failed')
    payment_pending_query = UserEvent.objects.filter(event_type='payment_pending')
    
    if start_date is not None:
        payment_success_query = payment_success_query.filter(created__gte=start_date, created__lte=end_date)
        payment_failed_query = payment_failed_query.filter(created__gte=start_date, created__lte=end_date)
        payment_pending_query = payment_pending_query.filter(created__gte=start_date, created__lte=end_date)
    
    payment_status = {
        'success': payment_success_query.count(),
        'failed': payment_failed_query.count(),
        'pending': payment_pending_query.count(),
    }
    
    # Revenue Metrics - Check UserEvent first, then fallback to Payment model
    total_revenue_query = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        total_revenue_query = total_revenue_query.filter(created__gte=start_date, created__lte=end_date)
    total_revenue = total_revenue_query.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    successful_payments_from_events = payment_success_query.count()
    
    # Fallback to Payment model if UserEvent has no data
    if total_revenue == 0 or successful_payments_from_events == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            # Get successful payments from Payment model
            successful_payments_model = Payment.objects.filter(
                is_success=choices.YesNoChoices.YES
            )
            if start_date is not None:
                successful_payments_model = successful_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            
            # Calculate revenue from Payment model
            payment_revenue = successful_payments_model.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            payment_success_count = successful_payments_model.count()
            
            # Use Payment model data if it has more revenue
            if payment_revenue > total_revenue:
                total_revenue = payment_revenue
                payment_status['success'] = payment_success_count
                logger.info(f"Using Payment model data for accounts dashboard: {payment_success_count} payments, ₹{total_revenue} revenue")
            
            # Also update failed payments count from Payment model
            failed_payments_model = Payment.objects.filter(is_success=choices.YesNoChoices.NO)
            if start_date is not None:
                failed_payments_model = failed_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            payment_failed_count = failed_payments_model.count()
            if payment_failed_count > payment_status['failed']:
                payment_status['failed'] = payment_failed_count
        except Exception as e:
            logger.warning(f"Error fetching Payment model data for accounts dashboard: {e}")
    
    # Prospects (Leads)
    total_prospects_query = Lead.objects.all()
    converted_prospects_query = Lead.objects.filter(is_converted=True)
    pending_prospects_query = Lead.objects.filter(is_converted=False)
    
    if start_date is not None:
        total_prospects_query = total_prospects_query.filter(first_visit__gte=start_date, first_visit__lte=end_date)
        converted_prospects_query = converted_prospects_query.filter(converted_at__gte=start_date, converted_at__lte=end_date)
        pending_prospects_query = pending_prospects_query.filter(first_visit__gte=start_date, first_visit__lte=end_date)
    
    total_prospects = total_prospects_query.count()
    converted_prospects = converted_prospects_query.count()
    pending_prospects = pending_prospects_query.count()
    
    # Revenue by Source - Query JSONField properly
    revenue_by_source_raw = UserEvent.objects.filter(event_type='payment_success').exclude(metadata__isnull=True)
    if start_date is not None:
        revenue_by_source_raw = revenue_by_source_raw.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    
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
    failed_payments_query = UserEvent.objects.filter(event_type='payment_failed')
    if start_date is not None:
        failed_payments_query = failed_payments_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    failed_payments = failed_payments_query.values('event_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Pending Payments
    pending_payments_query = UserEvent.objects.filter(event_type='payment_pending')
    if start_date is not None:
        pending_payments_query = pending_payments_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    pending_payments_list = pending_payments_query.select_related('user').order_by('-created')[:20]
    
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
    time_period = request.GET.get('period', 'today')
    
    # Ensure default is today if not provided or invalid
    valid_periods = ['today', 'yesterday', '7days', '30days', '90days', 'alltime']
    if time_period not in valid_periods:
        time_period = 'today'
    
    logger.info("=" * 80)
    logger.info(f"WEB OWNER DASHBOARD - Time Period: {time_period}")
    logger.info("=" * 80)
    
    # Initialize GA4 Service
    ga4_service = GA4Service()
    logger.debug("GA4 Service initialized")
    
    # Get GA4 metrics - optimized for performance
    # Load critical data first, then optional data can be loaded via AJAX
    logger.debug("Fetching GA4 metrics (optimized for performance)...")
    try:
        # Critical data - load immediately (core metrics)
        user_metrics = ga4_service.get_user_metrics(time_period, use_cache=True)
        device_breakdown = ga4_service.get_device_breakdown(time_period, use_cache=True)
        top_pages = ga4_service.get_top_pages(time_period, limit=20, use_cache=True)
        traffic_sources = ga4_service.get_traffic_sources(time_period, limit=15, use_cache=True)
        
        # Real-time data - load only if period is 'today' (most relevant)
        # For other periods, skip real-time to improve performance
        if time_period == 'today':
            real_time_users = ga4_service.get_real_time_users()
            real_time_breakdown = ga4_service.get_real_time_users_breakdown()
            real_time_users_by_country = ga4_service.get_real_time_users_by_country()
        else:
            real_time_users = None
            real_time_breakdown = None
            real_time_users_by_country = []
        
        # Optional data - can be loaded via AJAX if needed (disabled for initial load)
        # These are less critical and can be loaded on-demand
        top_pages_with_trends = []  # Disabled - makes multiple API calls, very slow
        engagement = None  # Can be loaded via AJAX if needed
        users_by_country = []  # Can be loaded via AJAX if needed
        ga4_entry_pages = []  # Can be loaded via AJAX if needed
        ga4_exit_pages = []  # Can be loaded via AJAX if needed
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
    # Only calculate if needed (optimize for performance)
    existing_users_count = 0
    organic_users_count = 0
    # Skip this expensive query for now - can be loaded via AJAX if needed
    # if UserActivity.objects.exists():
    #     # Count unique registered users in last hour
    #     recent_cutoff = timezone.now() - timedelta(hours=1)
    #     existing_users_count = UserActivity.objects.filter(
    #         created__gte=recent_cutoff,
    #         user__isnull=False
    #     ).values('user').distinct().count()
    #     
    #     # Count unique anonymous sessions in last hour
    #     organic_users_count = UserActivity.objects.filter(
    #         created__gte=recent_cutoff,
    #         user__isnull=True
    #     ).values('session_id').distinct().count()
    
    logger.info(f"GA4 Data Retrieved (Optimized):")
    logger.info(f"  - User Metrics: {'Available' if user_metrics else 'Not Available'}")
    logger.info(f"  - Device Breakdown: {'Available' if device_breakdown else 'Not Available'}")
    logger.info(f"  - Top Pages: {len(top_pages) if top_pages else 0} pages")
    logger.info(f"  - Traffic Sources: {'Available' if traffic_sources else 'Not Available'}")
    if time_period == 'today':
        logger.info(f"  - Real-time Users: {real_time_users or 0}")
        if real_time_breakdown:
            logger.info(f"    - New Users: {real_time_breakdown.get('new', 0)}")
            logger.info(f"    - Returning Users: {real_time_breakdown.get('returning', 0)}")
    else:
        logger.info(f"  - Real-time data: Skipped (not needed for {time_period})")
    logger.info(f"  - Optional data (Entry/Exit pages, Countries, Trends): Loaded via AJAX if needed")
    
    # Calculate date range for database queries
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    if start_date is not None:
        logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {(end_date - start_date).days} days")
    else:
        logger.info("Date Range: All Time (no date filtering)")
    
    # User Journey Metrics - Only calculate if needed (optimize for performance)
    # These queries can be expensive, so we'll use GA4 data primarily
    total_sessions = 0
    converted_sessions = 0
    avg_session_duration = 0
    
    # Only query database if GA4 sessions data is not available
    if not user_metrics or not user_metrics.get('sessions'):
        journey_query = UserJourney.objects.all()
        if start_date is not None:
            journey_query = journey_query.filter(
                start_time__gte=start_date,
                start_time__lte=end_date
            )
        
        total_sessions = journey_query.count()
        converted_sessions = journey_query.filter(converted=True).count()
        avg_session_duration = journey_query.aggregate(avg=Avg('total_time'))['avg'] or 0
    else:
        # Use GA4 data for sessions
        total_sessions = sum(user_metrics.get('sessions', [])) if user_metrics else 0
    
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
    
    # Top Pages - Use database as primary source (faster than GA4 API)
    # Database data is more reliable and always up-to-date
    # Only query if we need it (if GA4 top_pages is empty)
    db_top_pages = []
    if not top_pages or len(top_pages) == 0:
        db_top_pages_query = UserActivity.objects.exclude(page_path__isnull=True).exclude(page_path='')
        if start_date is not None:
            db_top_pages_query = db_top_pages_query.filter(
                created__gte=start_date,
                created__lte=end_date
            )
        db_top_pages_raw = db_top_pages_query.values('page_path', 'page_title').annotate(
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
    
    # Calculate total pageviews from database only if GA4 is unavailable (lazy evaluation)
    db_total_pageviews = 0
    db_total_users = 0
    if not user_metrics or not user_metrics.get('screenPageViews'):
        # Only query database if GA4 data is not available
        db_total_pageviews_query = UserActivity.objects.all()
        if start_date is not None:
            db_total_pageviews_query = db_total_pageviews_query.filter(
                created__gte=start_date,
                created__lte=end_date
            )
        db_total_pageviews = db_total_pageviews_query.count()
    
    if not user_metrics or not user_metrics.get('activeUsers'):
        # Only query database if GA4 data is not available
        db_total_users_query = User.objects.all()
        if start_date is not None:
            db_total_users_query = db_total_users_query.filter(
                created__gte=start_date,
                created__lte=end_date
            )
        db_total_users = db_total_users_query.count()
    
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
    
    # Check if database has any data for this time period (to determine if detail links should be clickable)
    # Only check if needed (optimize for performance)
    has_db_data = False
    if db_top_pages or total_sessions > 0:
        # If we already have database data, set flag to True
        has_db_data = True
    else:
        # Only query if we haven't already determined we have data
        has_db_data_query = UserActivity.objects.all()
        if start_date is not None:
            has_db_data_query = has_db_data_query.filter(
                created__gte=start_date,
                created__lte=end_date
            )
        has_db_data = has_db_data_query.exists()
    
    logger.info(f"Database has data for this period: {has_db_data}")
    
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
        'top_entry_pages': list(top_entry_pages) if top_entry_pages else [],
        'top_exit_pages': list(top_exit_pages) if top_exit_pages else [],
        'real_time_breakdown': real_time_breakdown,
        'real_time_users_by_country': real_time_users_by_country if real_time_users_by_country else [],
        'users_by_country': users_by_country if users_by_country else [],
        'total_country_users': sum(c.get('activeUsers', 0) for c in users_by_country) if users_by_country else 0,
        'top_pages_with_trends': top_pages_with_trends if top_pages_with_trends else [],
        'load_optional_data': False,  # Flag to indicate optional data should be loaded via AJAX
        'existing_users_count': existing_users_count,
        'organic_users_count': organic_users_count,
        'has_db_data': has_db_data,  # Flag to indicate if database has data for detail links
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
    goal_filter = request.GET.get('goal', '')  # 'registered', 'payment', 'test_started', 'test_completed', 'result_generated'
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    logger.info("=" * 80)
    logger.info(f"USER JOURNEY VIEW - User ID: {user_id}, User Type Filter: {user_type_filter}")
    
    # Calculate date range
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    if user_id:
        journeys = UserJourney.objects.filter(user_id=user_id)
    else:
        journeys = UserJourney.objects.all()
    
    if start_date is not None:
        journeys = journeys.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        )
    journeys = journeys.select_related('user').order_by('-start_time')
    
    # Apply user type filter
    if user_type_filter == 'registered':
        journeys = journeys.filter(user__isnull=False)
        logger.info("Filtering for registered users only")
    elif user_type_filter == 'organic':
        journeys = journeys.filter(user__isnull=True)
        logger.info("Filtering for organic/anonymous users only")
    
    # Apply goal filter
    if goal_filter:
        if goal_filter == 'registered':
            journeys = journeys.filter(is_registered=True)
            logger.info("Filtering for journeys with registration goal")
        elif goal_filter == 'payment':
            journeys = journeys.filter(has_payment=True)
            logger.info("Filtering for journeys with payment goal")
        elif goal_filter == 'test_started':
            journeys = journeys.filter(has_psychometric_test=True)
            logger.info("Filtering for journeys with psychometric test started goal")
        elif goal_filter == 'test_completed':
            journeys = journeys.filter(test_completed=True)
            logger.info("Filtering for journeys with test completed goal")
        elif goal_filter == 'result_generated':
            journeys = journeys.filter(result_generated=True)
            logger.info("Filtering for journeys with result generated goal")
    
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
        'goal_filter': goal_filter,
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


@login_required
@user_passes_test(is_staff_or_superuser)
def user_journey_detail_view(request, session_id):
    """
    Detailed view of a specific user journey showing all pages visited with timestamps.
    """
    try:
        # Get the journey
        journey = UserJourney.objects.select_related('user').get(session_id=session_id)
        
        # Get all activities for this session, ordered by time
        activities = UserActivity.objects.filter(session_id=session_id).order_by('created')
        
        # Define goals based on UserJourney fields
        goals_achieved = []
        
        # Goal 1: Registration
        if journey.is_registered and journey.registration_event:
            goals_achieved.append({
                'event': journey.registration_event,
                'goal': {'name': 'User Registration', 'color': 'success', 'icon': 'fa-user-plus'},
            })
        elif journey.is_registered:
            # If registered but no event, create a placeholder
            goals_achieved.append({
                'event': None,
                'event_time': journey.start_time,  # Use journey start as fallback
                'goal': {'name': 'User Registration', 'color': 'success', 'icon': 'fa-user-plus'},
            })
        
        # Goal 2: Payment
        if journey.has_payment and journey.payment_event:
            event_value = journey.payment_event.event_value or 0
            goals_achieved.append({
                'event': journey.payment_event,
                'goal': {'name': f'Payment Success - ₹{event_value}', 'color': 'success', 'icon': 'fa-check-circle'},
            })
        elif journey.has_payment:
            goals_achieved.append({
                'event': None,
                'event_time': journey.start_time,
                'goal': {'name': 'Payment Success', 'color': 'success', 'icon': 'fa-check-circle'},
            })
        
        # Goal 3: Psychometric Test Started
        if journey.has_psychometric_test and journey.psychometric_test_event:
            goals_achieved.append({
                'event': journey.psychometric_test_event,
                'goal': {'name': 'Psychometric Test Started', 'color': 'info', 'icon': 'fa-play-circle'},
            })
        elif journey.has_psychometric_test:
            goals_achieved.append({
                'event': None,
                'event_time': journey.start_time,
                'goal': {'name': 'Psychometric Test Started', 'color': 'info', 'icon': 'fa-play-circle'},
            })
        
        # Goal 4: Test Completed
        if journey.test_completed and journey.test_completion_event:
            goals_achieved.append({
                'event': journey.test_completion_event,
                'goal': {'name': 'Psychometric Test Completed', 'color': 'primary', 'icon': 'fa-check-circle'},
            })
        elif journey.test_completed:
            goals_achieved.append({
                'event': None,
                'event_time': journey.start_time,
                'goal': {'name': 'Psychometric Test Completed', 'color': 'primary', 'icon': 'fa-check-circle'},
            })
        
        # Goal 5: Result Generated
        if journey.result_generated and journey.result_generation_event:
            goals_achieved.append({
                'event': journey.result_generation_event,
                'goal': {'name': 'Result Generated', 'color': 'success', 'icon': 'fa-file-alt'},
            })
        elif journey.result_generated:
            goals_achieved.append({
                'event': None,
                'event_time': journey.start_time,
                'goal': {'name': 'Result Generated', 'color': 'success', 'icon': 'fa-file-alt'},
            })
        
        # Create a mapping of event timestamps to goals
        goal_map = {}
        for goal_data in goals_achieved:
            if goal_data['event']:
                event_time = goal_data['event'].created
            else:
                event_time = goal_data.get('event_time', journey.start_time)
            
            goal_map[event_time] = goal_data
        
        # Also check for any other events in the session that might not be linked
        events = UserEvent.objects.filter(session_id=session_id).order_by('created')
        for event in events:
            # Only add if not already in goal_map
            if event.created not in goal_map:
                goal_info = None
                if event.event_type == 'registration':
                    goal_info = {'name': 'User Registration', 'color': 'success', 'icon': 'fa-user-plus'}
                elif event.event_type == 'payment_success':
                    goal_info = {'name': f'Payment Success - ₹{event.event_value}', 'color': 'success', 'icon': 'fa-check-circle'}
                elif event.event_type == 'psychometric_test_started':
                    goal_info = {'name': 'Psychometric Test Started', 'color': 'info', 'icon': 'fa-play-circle'}
                elif event.event_type == 'psychometric_test_completed':
                    goal_info = {'name': 'Psychometric Test Completed', 'color': 'primary', 'icon': 'fa-check-circle'}
                elif event.event_type == 'result_generated':
                    goal_info = {'name': 'Result Generated', 'color': 'success', 'icon': 'fa-file-alt'}
                
                if goal_info:
                    goal_map[event.created] = {
                        'event': event,
                        'goal': goal_info,
                    }
        
        # Calculate time differences between pages and match goals
        activity_list = []
        prev_time = None
        
        for activity in activities:
            if prev_time is None:
                # First activity - calculate from journey start
                time_diff = (activity.created - journey.start_time).total_seconds()
            else:
                # Calculate from previous activity
                time_diff = (activity.created - prev_time).total_seconds()
            
            # Check if this activity corresponds to a goal (within 10 seconds tolerance)
            matched_goal = None
            matched_event_time = None
            for event_time, goal_data in goal_map.items():
                time_delta = abs((activity.created - event_time).total_seconds())
                if time_delta <= 10:  # 10 second tolerance
                    matched_goal = goal_data
                    matched_event_time = event_time
                    break
            
            # Remove matched goal from map
            if matched_event_time:
                del goal_map[matched_event_time]
            
            activity_list.append({
                'activity': activity,
                'time_since_previous': max(0, int(time_diff)),
                'timestamp': activity.created,
                'goal': matched_goal,
            })
            prev_time = activity.created
        
        # If there are unmatched goals, add them to the first activity or closest activity
        if goal_map:
            for event_time, goal_data in goal_map.items():
                # Find the closest activity to this event time
                closest_activity = None
                min_time_diff = float('inf')
                for item in activity_list:
                    time_diff = abs((item['timestamp'] - event_time).total_seconds())
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_activity = item
                
                # If we found a close activity (within 60 seconds), add the goal
                if closest_activity and min_time_diff <= 60:
                    if not closest_activity['goal']:  # Only if no goal already assigned
                        closest_activity['goal'] = goal_data
        
        # Collect all goals achieved for summary
        all_goals = []
        if journey.is_registered:
            all_goals.append({'name': 'User Registration', 'color': 'success', 'icon': 'fa-user-plus'})
        if journey.has_payment:
            all_goals.append({'name': 'Payment Success', 'color': 'success', 'icon': 'fa-check-circle'})
        if journey.has_psychometric_test:
            all_goals.append({'name': 'Psychometric Test Started', 'color': 'info', 'icon': 'fa-play-circle'})
        if journey.test_completed:
            all_goals.append({'name': 'Psychometric Test Completed', 'color': 'primary', 'icon': 'fa-check-circle'})
        if journey.result_generated:
            all_goals.append({'name': 'Result Generated', 'color': 'success', 'icon': 'fa-file-alt'})
        
        context = {
            'journey': journey,
            'activities': activity_list,
            'total_activities': len(activity_list),
            'all_goals': all_goals,
        }
        
        return render(request, 'user_analytics/user_journey_detail.html', context)
    
    except UserJourney.DoesNotExist:
        from django.http import Http404
        raise Http404("Journey not found")


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
        start_date, end_date = get_date_range_from_period(time_period, default_days=30)
        
        response_data = {}
        
        if dashboard_type == 'business':
            # Business metrics
            revenue_query = UserEvent.objects.filter(event_type='payment_success')
            if start_date is not None:
                revenue_query = revenue_query.filter(created__gte=start_date, created__lte=end_date)
            total_revenue = revenue_query.aggregate(total=Sum('event_value'))['total'] or 0
            
            payments_query = UserEvent.objects.filter(event_type='payment_success')
            enrollments_query = UserEvent.objects.filter(
                event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed']
            )
            if start_date is not None:
                payments_query = payments_query.filter(created__gte=start_date, created__lte=end_date)
                enrollments_query = enrollments_query.filter(created__gte=start_date, created__lte=end_date)
            
            response_data = {
                'total_revenue': float(total_revenue),
                'successful_payments': payments_query.count(),
                'total_enrollments': enrollments_query.count(),
            }
        
        elif dashboard_type == 'accounts':
            # Accounts metrics
            users_query = User.objects.all()
            revenue_query = UserEvent.objects.filter(event_type='payment_success')
            leads_query = Lead.objects.all()
            
            if start_date is not None:
                users_query = users_query.filter(created__gte=start_date, created__lte=end_date)
                revenue_query = revenue_query.filter(created__gte=start_date, created__lte=end_date)
                leads_query = leads_query.filter(first_visit__gte=start_date, first_visit__lte=end_date)
            
            response_data = {
                'total_registrations': users_query.count(),
                'total_revenue': float(revenue_query.aggregate(total=Sum('event_value'))['total'] or 0),
                'total_prospects': leads_query.count(),
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset - Try UserEvent first, fallback to Payment model
    payments = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # If no UserEvent data, fallback to Payment model (but API will handle the actual data)
    # For the template, we just need the count
    total_count = payments.count()
    total_revenue = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # If no UserEvent data, check Payment model for count
    if total_count == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            if search_query:
                payment_query = payment_query.filter(
                    Q(user__email__icontains=search_query) |
                    Q(user__name__icontains=search_query) |
                    Q(order_id__icontains=search_query)
                )
            total_count = payment_query.count()
            total_revenue = payment_query.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        except Exception as e:
            logger.warning(f"Error fetching Payment model data: {e}")
    
    # Create empty paginator for template (data loaded via AJAX)
    from django.core.paginator import Paginator, Page
    empty_list = []
    paginator = Paginator(empty_list, 25)
    payments_page = paginator.page(1)
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset - Try UserEvent first, fallback to Payment model
    payments = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Check if we have data, if not fallback to Payment model
    use_payment_model = False
    if payments.count() == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            
            # Apply search filter to payments
            if search_query:
                # Build Q object for search
                search_q = Q(user__email__icontains=search_query) | \
                           Q(user__name__icontains=search_query) | \
                           Q(gateway_order_id__icontains=search_query) | \
                           Q(gateway_receipt__icontains=search_query)
                
                # Also search by PaymentObjectType display name
                if hasattr(choices, 'PaymentObjectType'):
                    # Check if search query matches any PaymentObjectType display name
                    for choice_value, choice_name in choices.PaymentObjectType.CHOICES:
                        if search_query.lower() in choice_name.lower() or choice_name.lower() in search_query.lower():
                            search_q |= Q(obj_type=choice_value)
                            break
                
                payment_query = payment_query.filter(search_q)
            
            payments = payment_query.select_related('user').order_by('-created')
            use_payment_model = True
        except Exception as e:
            logger.warning(f"Error fetching Payment model data: {e}")
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    if use_payment_model:
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_count = payments.count()
    else:
        total_revenue = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
        total_count = payments.count()
    
    # Serialize data
    payments_data = []
    for payment in payments_page:
        if use_payment_model:
            # Payment model
            obj_type_name = 'Payment'
            if hasattr(choices, 'PaymentObjectType') and payment.obj_type:
                obj_type_name = dict(choices.PaymentObjectType.CHOICES).get(payment.obj_type, f'Type {payment.obj_type}')
            
            # Get gateway display name
            gateway_name = 'N/A'
            if hasattr(choices, 'GatewayChoices') and payment.gateway:
                gateway_name = dict(choices.GatewayChoices.CHOICES).get(payment.gateway, f'Gateway {payment.gateway}')
            
            payments_data.append({
                'id': payment.id,
                'user_email': payment.user.email if payment.user else 'Anonymous',
                'event_name': obj_type_name,
                'amount': float(payment.amount or 0),
                'date': payment.created.strftime('%b %d, %Y %H:%M') if payment.created else 'N/A',
                'source': 'Unknown',  # Payment model doesn't have source
                'gateway': gateway_name,
                'order_id': payment.gateway_order_id or 'N/A',
            })
        else:
            # UserEvent model
            payments_data.append({
                'id': payment.id,
                'user_email': payment.user.email if payment.user else 'Anonymous',
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset - Try UserEvent first, fallback to Payment model
    payments = UserEvent.objects.filter(event_type='payment_failed')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # If no UserEvent data, fallback to Payment model (but API will handle the actual data)
    # For the template, we just need the count
    total_count = payments.count()
    total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # If no UserEvent data, check Payment model for count
    if total_count == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.NO)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            if search_query:
                payment_query = payment_query.filter(
                    Q(user__email__icontains=search_query) |
                    Q(user__name__icontains=search_query) |
                    Q(gateway_order_id__icontains=search_query) |
                    Q(gateway_receipt__icontains=search_query)
                )
            total_count = payment_query.count()
            total_amount = payment_query.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        except Exception as e:
            logger.warning(f"Error fetching Payment model data: {e}")
    
    # Create empty paginator for template (data loaded via AJAX)
    from django.core.paginator import Paginator, Page
    empty_list = []
    paginator = Paginator(empty_list, 25)
    payments_page = paginator.page(1)
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset - Try UserEvent first, fallback to Payment model
    payments = UserEvent.objects.filter(event_type='payment_failed')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(event_name__icontains=search_query) |
            Q(metadata__icontains=search_query)
        )
    
    # Check if we have data, if not fallback to Payment model
    use_payment_model = False
    if payments.count() == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            payment_query = Payment.objects.filter(is_success=choices.YesNoChoices.NO)
            if start_date is not None:
                payment_query = payment_query.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            
            # Apply search filter to payments
            if search_query:
                # Build Q object for search
                search_q = Q(user__email__icontains=search_query) | \
                           Q(user__name__icontains=search_query) | \
                           Q(gateway_order_id__icontains=search_query) | \
                           Q(gateway_receipt__icontains=search_query)
                
                # Also search by PaymentObjectType display name
                if hasattr(choices, 'PaymentObjectType'):
                    # Check if search query matches any PaymentObjectType display name
                    for choice_value, choice_name in choices.PaymentObjectType.CHOICES:
                        if search_query.lower() in choice_name.lower() or choice_name.lower() in search_query.lower():
                            search_q |= Q(obj_type=choice_value)
                            break
                
                payment_query = payment_query.filter(search_q)
            
            payments = payment_query.select_related('user').order_by('-created')
            use_payment_model = True
        except Exception as e:
            logger.warning(f"Error fetching Payment model data: {e}")
    
    # Pagination
    paginator = Paginator(payments, 25)
    try:
        payments_page = paginator.page(page_number)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Calculate totals
    if use_payment_model:
        total_amount = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_count = payments.count()
    else:
        total_amount = payments.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
        total_count = payments.count()
    
    # Serialize data
    payments_data = []
    for payment in payments_page:
        if use_payment_model:
            # Payment model
            obj_type_name = 'Payment'
            if hasattr(choices, 'PaymentObjectType') and payment.obj_type:
                obj_type_name = dict(choices.PaymentObjectType.CHOICES).get(payment.obj_type, f'Type {payment.obj_type}')
            
            # Get gateway display name
            gateway_name = 'N/A'
            if hasattr(choices, 'GatewayChoices') and payment.gateway:
                gateway_name = dict(choices.GatewayChoices.CHOICES).get(payment.gateway, f'Gateway {payment.gateway}')
            
            payments_data.append({
                'id': payment.id,
                'user_email': payment.user.email if payment.user else 'Anonymous',
                'event_name': obj_type_name,
                'amount': float(payment.amount or 0),
                'date': payment.created.strftime('%b %d, %Y %H:%M') if payment.created else 'N/A',
                'source': 'Unknown',  # Payment model doesn't have source
                'gateway': gateway_name,
                'order_id': payment.gateway_order_id or 'N/A',
            })
        else:
            # UserEvent model
            payments_data.append({
                'id': payment.id,
                'user_email': payment.user.email if payment.user else 'Anonymous',
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
            'total_amount': float(total_amount),
            'total_revenue': float(total_amount),  # For consistency
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    payments = UserEvent.objects.filter(event_type='payment_pending')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    payments = UserEvent.objects.filter(event_type='payment_pending')
    if start_date is not None:
        payments = payments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    payments = payments.select_related('user').order_by('-created')
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered']
    )
    if start_date is not None:
        enrollments = enrollments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    enrollments = enrollments.select_related('user').order_by('-created')
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Calculate Total Revenue
    revenue_events = UserEvent.objects.filter(event_type='payment_success')
    if start_date is not None:
        revenue_events = revenue_events.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_revenue = revenue_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    successful_payments_from_events = revenue_events.count()
    
    # Fallback to Payment model if UserEvent has no data
    if total_revenue == 0 or successful_payments_from_events == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            successful_payments_model = Payment.objects.filter(is_success=choices.YesNoChoices.YES)
            if start_date is not None:
                successful_payments_model = successful_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            payment_revenue = successful_payments_model.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            if payment_revenue > total_revenue:
                total_revenue = payment_revenue
                successful_payments = successful_payments_model.count()
            else:
                successful_payments = successful_payments_from_events
        except Exception as e:
            logger.warning(f"Error fetching Payment model data in API: {e}")
            successful_payments = successful_payments_from_events
    else:
        successful_payments = successful_payments_from_events
    
    # Calculate Total Enrollments
    enrollments_query = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered']
    )
    if start_date is not None:
        enrollments_query = enrollments_query.filter(created__gte=start_date, created__lte=end_date)
    total_enrollments = enrollments_query.count()
    
    # Calculate other metrics
    failed_payment_events = UserEvent.objects.filter(event_type='payment_failed')
    if start_date is not None:
        failed_payment_events = failed_payment_events.filter(created__gte=start_date, created__lte=end_date)
    failed_payments = failed_payment_events.count()
    failed_payments_revenue = failed_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    # Fallback to Payment model for failed payments
    if failed_payments == 0:
        try:
            from payments.models import Payment
            from core import choices
            
            failed_payments_model = Payment.objects.filter(is_success=choices.YesNoChoices.NO)
            if start_date is not None:
                failed_payments_model = failed_payments_model.filter(
                    created__gte=start_date,
                    created__lte=end_date
                )
            failed_payments = failed_payments_model.count()
            failed_payments_revenue = failed_payments_model.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        except Exception:
            pass
    
    pending_payment_events = UserEvent.objects.filter(event_type='payment_pending')
    if start_date is not None:
        pending_payment_events = pending_payment_events.filter(created__gte=start_date, created__lte=end_date)
    pending_payments = pending_payment_events.count()
    pending_payments_revenue = pending_payment_events.aggregate(total=Sum('event_value'))['total'] or Decimal('0')
    
    psychometric_query = UserEvent.objects.filter(event_type='psychometric_test_completed')
    course_query = UserEvent.objects.filter(event_type__in=['course_enrolled', 'skilllab_enrolled'])
    visitors_query = UserActivity.objects.all()
    registrations_query = UserEvent.objects.filter(event_type='registration')
    
    if start_date is not None:
        psychometric_query = psychometric_query.filter(created__gte=start_date, created__lte=end_date)
        course_query = course_query.filter(created__gte=start_date, created__lte=end_date)
        visitors_query = visitors_query.filter(created__gte=start_date, created__lte=end_date)
        registrations_query = registrations_query.filter(created__gte=start_date, created__lte=end_date)
    
    psychometric_enrollments = psychometric_query.count()
    course_enrollments = course_query.count()
    total_visitors = visitors_query.values('session_id').distinct().count()
    total_registrations = registrations_query.count()
    
    from core import choices
    
    total_leads_query = Lead.objects.all()
    converted_leads_query = Lead.objects.filter(is_converted=True)
    
    if start_date is not None:
        total_leads_query = total_leads_query.filter(first_visit__gte=start_date, first_visit__lte=end_date)
        converted_leads_query = converted_leads_query.filter(converted_at__gte=start_date, converted_at__lte=end_date)
    
    total_leads = total_leads_query.count()
    converted_leads = converted_leads_query.count()
    
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
        'start_date': start_date.isoformat() if start_date is not None else None,
        'end_date': end_date.isoformat() if end_date is not None else None,
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    enrollments = UserEvent.objects.filter(
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered']
    )
    if start_date is not None:
        enrollments = enrollments.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    enrollments = enrollments.select_related('user').order_by('-created')
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    users = User.objects.all()
    if start_date is not None:
        users = users.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    users = users.order_by('-created')
    
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    # Base queryset
    leads = Lead.objects.all()
    if start_date is not None:
        leads = leads.filter(
            first_visit__gte=start_date,
            first_visit__lte=end_date
        )
    leads = leads.order_by('-first_visit')
    
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
def admin_user_analytics_view(request):
    """
    Admin User Analytics - User activities with filters, shown in the analytics dashboard.
    Filters: period, referrer source (Google, Facebook, iapply.io), device, country, search.
    """
    from user_analytics.utils import referrer_source_q
    from django.db.models import Count

    time_period = request.GET.get('period', '30days')
    source_filter = (request.GET.get('source') or '').strip()
    device_filter = (request.GET.get('device') or '').strip()
    country_filter = (request.GET.get('country') or '').strip()
    traffic_category_filter = (request.GET.get('traffic_category') or '').strip()
    search_query = (request.GET.get('search') or '').strip()
    page_number = request.GET.get('page', 1)

    if country_filter:
        country_filter = unquote(country_filter)
    if source_filter:
        source_filter = unquote(source_filter)
    if device_filter:
        device_filter = unquote(device_filter)

    start_date, end_date = get_date_range_from_period(time_period, default_days=30)

    qs = UserActivity.objects.all().select_related('user')
    if start_date is not None:
        qs = qs.filter(created__gte=start_date, created__lte=end_date)

    if source_filter:
        if source_filter.lower() in ('(direct)', 'direct', '(not set)'):
            qs = qs.filter(
                Q(utm_source__iexact='(direct)') |
                Q(utm_source__iexact='direct') |
                Q(utm_source__iexact='(not set)') |
                Q(utm_source__isnull=True) |
                Q(utm_source='')
            )
        elif source_filter.lower() in ('google', 'facebook', 'iapply', 'iapply.io'):
            qs = qs.filter(referrer_source_q(source_filter))
        else:
            qs = qs.filter(Q(utm_source__iexact=source_filter) | Q(referrer__icontains=source_filter))

    if device_filter:
        qs = qs.filter(device_type__iexact=device_filter)
    if country_filter:
        qs = qs.filter(country__icontains=country_filter)
    if traffic_category_filter:
        qs = qs.filter(traffic_source_category__iexact=traffic_category_filter)

    if search_query:
        qs = qs.filter(
            Q(session_id__icontains=search_query) |
            Q(page_path__icontains=search_query) |
            Q(referrer__icontains=search_query) |
            Q(utm_source__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    qs = qs.order_by('-created')

    # Summary stats (from same filtered queryset)
    total_activities = qs.count()
    unique_sessions = qs.values('session_id').distinct().count()

    # Counts by source (for summary cards)
    base_qs = UserActivity.objects.all()
    if start_date is not None:
        base_qs = base_qs.filter(created__gte=start_date, created__lte=end_date)
    count_google = base_qs.filter(referrer_source_q('google')).count()
    count_facebook = base_qs.filter(referrer_source_q('facebook')).count()
    count_iapply = base_qs.filter(referrer_source_q('iapply')).count()
    count_direct = base_qs.filter(
        Q(utm_source__isnull=True) | Q(utm_source='') |
        Q(utm_source__iexact='direct') | Q(utm_source__iexact='(direct)')
    ).count()

    # Counts by device
    by_device = base_qs.values('device_type').annotate(c=Count('id')).order_by('-c')
    device_counts = {r['device_type'] or 'unknown': r['c'] for r in by_device}

    paginator = Paginator(qs, 25)
    try:
        activities_page = paginator.page(page_number)
    except PageNotAnInteger:
        activities_page = paginator.page(1)
    except EmptyPage:
        activities_page = paginator.page(paginator.num_pages)

    # One-time cleanup output from POST redirect
    cleanup_output = request.session.pop('cleanup_output', None)

    context = {
        'activities': activities_page,
        'time_period': time_period,
        'source_filter': source_filter,
        'device_filter': device_filter,
        'country_filter': country_filter,
        'traffic_category_filter': traffic_category_filter,
        'search_query': search_query,
        'total_activities': total_activities,
        'unique_sessions': unique_sessions,
        'count_google': count_google,
        'count_facebook': count_facebook,
        'count_iapply': count_iapply,
        'count_direct': count_direct,
        'device_counts': device_counts,
        'start_date': start_date,
        'end_date': end_date,
        'page_title': 'Admin User Analytics',
        'cleanup_output': cleanup_output,
        'cleanup_url': reverse('user_analytics:cleanup_analytics_data'),
        'csrf_input_html': format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            get_token(request),
        ),
    }
    return render(request, 'user_analytics/admin_user_analytics.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def cleanup_analytics_data_view(request):
    """
    POST-only: run analytics data cleanup (same logic as management command).
    Expects: days (int), dry_run (optional), confirm (required when not dry_run).
    """
    from django.core.management import call_command
    from io import StringIO
    from django.contrib import messages
    from django.shortcuts import redirect

    if request.method != 'POST':
        return redirect('user_analytics:admin_user_analytics')

    days = request.POST.get('days')
    try:
        days = int(days) if days else 365
    except ValueError:
        days = 365
    dry_run = request.POST.get('dry_run') == 'on'
    confirm = request.POST.get('confirm') == 'on'

    if not dry_run and not confirm:
        messages.warning(request, 'Check "I understand this will permanently delete data" to run cleanup.')
        return redirect('user_analytics:admin_user_analytics')

    out = StringIO()
    try:
        call_command(
            'cleanup_analytics_data',
            days=days,
            dry_run=dry_run,
            stdout=out,
        )
        output = out.getvalue()
        if dry_run:
            messages.info(request, 'Dry run completed. No data was deleted.')
        else:
            messages.success(request, 'Cleanup completed. See details below.')
        request.session['cleanup_output'] = output
    except Exception as e:
        logger.exception('Cleanup failed')
        messages.error(request, 'Cleanup failed: %s' % str(e))
    return redirect('user_analytics:admin_user_analytics')


<<<<<<< HEAD
# ---------- Enquiry Sources (non-readable UTM links: ?ref=TOKEN) ----------
def _enquiry_source_stats(source):
    """Return dict of visit count and conversion counts for an EnquirySource."""
    from django.db.models import Count
    sessions = UserJourney.objects.filter(enquiry_source=source)
    visit_count = sessions.count()
    session_ids = list(sessions.values_list('session_id', flat=True))
    if not session_ids:
        return {
            'visit_count': 0,
            'registrations': 0,
            'payment_success': 0,
            'course_enrolled': 0,
            'converted_sessions': 0,
        }
    reg = UserEvent.objects.filter(session_id__in=session_ids, event_type='registration').count()
    pay = UserEvent.objects.filter(session_id__in=session_ids, event_type='payment_success').count()
    course = UserEvent.objects.filter(
        session_id__in=session_ids,
        event_type__in=['course_enrolled', 'skilllab_enrolled', 'psychometric_test_completed', 'institute_student_registered'],
    ).count()
    converted = sessions.filter(converted=True).count()
    return {
        'visit_count': visit_count,
        'registrations': reg,
        'payment_success': pay,
        'course_enrolled': course,
        'converted_sessions': converted,
    }


@login_required
@user_passes_test(is_staff_or_superuser)
def enquiry_sources_list_view(request):
    """List enquiry sources with copy URL, QR, download QR, and stats. Optional filter by agency/event."""
    from django.conf import settings
    base_url = getattr(settings, 'ENQUIRY_SOURCE_BASE_URL', '')
    sources = EnquirySource.objects.filter(object_status=choices.ObjectStatus.ACTIVE).order_by('-created')
    agency_filter = (request.GET.get('agency') or '').strip()
    event_filter = (request.GET.get('event') or '').strip()
    if agency_filter:
        sources = sources.filter(agency_name__icontains=agency_filter)
    if event_filter:
        sources = sources.filter(event__icontains=event_filter)
    source_stats = []
    for s in sources:
        full_url = s.get_full_url()
        stats = _enquiry_source_stats(s)
        source_stats.append({'source': s, 'full_url': full_url, 'stats': stats})
    # Distinct values for filter dropdowns
    all_sources = EnquirySource.objects.filter(object_status=choices.ObjectStatus.ACTIVE)
    agencies = sorted({x for x in all_sources.values_list('agency_name', flat=True).distinct() if x})
    events = sorted({x for x in all_sources.values_list('event', flat=True).distinct() if x})
    context = {
        'source_stats': source_stats,
        'enquiry_base_url': base_url,
        'agency_filter': agency_filter,
        'event_filter': event_filter,
        'agencies': agencies,
        'events': events,
        'page_title': 'Enquiry Sources (UTM Links)',
        'csrf_input_html': format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            get_token(request),
        ),
    }
    return render(request, 'user_analytics/enquiry_sources_list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def _enquiry_source_form_data(request):
    """Extract name, agency_name, user_name, event from POST. Returns (name, agency_name, user_name, event)."""
    def strip(s):
        return (s or '').strip() or None
    return (
        strip(request.POST.get('name')),
        strip(request.POST.get('agency_name')),
        strip(request.POST.get('user_name')),
        strip(request.POST.get('event')),
    )


def enquiry_source_create_view(request):
    """Create a new enquiry source (name + optional agency, user, event). Token is auto-generated."""
    from django.contrib import messages
    if request.method == 'POST':
        name, agency_name, user_name, event = _enquiry_source_form_data(request)
        if not name:
            messages.error(request, 'Name is required.')
            return redirect('user_analytics:enquiry_source_create')
        try:
            EnquirySource.objects.create(
                name=name,
                agency_name=agency_name,
                user_name=user_name,
                event=event,
            )
            messages.success(request, 'Enquiry source created. Use the link with ?ref= token only (non-readable).')
            return redirect('user_analytics:enquiry_sources_list')
        except Exception as e:
            messages.error(request, str(e))
            return redirect('user_analytics:enquiry_sources_list')
    context = {
        'source': None,
        'page_title': 'Add Enquiry Source',
        'csrf_input_html': format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            get_token(request),
        ),
    }
    return render(request, 'user_analytics/enquiry_source_form.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def enquiry_source_edit_view(request, pk):
    """Edit enquiry source name, agency, user, event. Token is not changed."""
    from django.contrib import messages
    from django.http import HttpResponseNotFound
    try:
        source = EnquirySource.objects.get(pk=pk, object_status=choices.ObjectStatus.ACTIVE)
    except EnquirySource.DoesNotExist:
        return HttpResponseNotFound('Enquiry source not found.')
    if request.method == 'POST':
        name, agency_name, user_name, event = _enquiry_source_form_data(request)
        if not name:
            messages.error(request, 'Name is required.')
            return redirect('user_analytics:enquiry_source_edit', pk=pk)
        try:
            source.name = name
            source.agency_name = agency_name
            source.user_name = user_name
            source.event = event
            source.save()
            messages.success(request, 'Enquiry source updated.')
            return redirect('user_analytics:enquiry_sources_list')
        except Exception as e:
            messages.error(request, str(e))
    context = {
        'source': source,
        'page_title': 'Edit Enquiry Source',
        'csrf_input_html': format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            get_token(request),
        ),
    }
    return render(request, 'user_analytics/enquiry_source_form.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def enquiry_source_delete_view(request, pk):
    """Soft-delete an enquiry source."""
    from django.contrib import messages
    from django.http import HttpResponseNotFound
    if request.method != 'POST':
        return redirect('user_analytics:enquiry_sources_list')
    try:
        source = EnquirySource.objects.get(pk=pk)
    except EnquirySource.DoesNotExist:
        return HttpResponseNotFound('Enquiry source not found.')
    source.delete(hard_delete=False)
    messages.success(request, 'Enquiry source deactivated.')
    return redirect('user_analytics:enquiry_sources_list')


@login_required
@user_passes_test(is_staff_or_superuser)
def enquiry_source_qr_view(request, pk):
    """Serve QR code PNG for the enquiry source link (for display and download)."""
    from django.http import HttpResponse, HttpResponseNotFound
    try:
        source = EnquirySource.objects.get(pk=pk, object_status=choices.ObjectStatus.ACTIVE)
    except EnquirySource.DoesNotExist:
        return HttpResponseNotFound('Not found.')
    fallback_base = request.build_absolute_uri('/').rstrip('/')
    full_url = source.get_full_url(fallback_base)
    if not full_url:
        return HttpResponseNotFound('No base URL configured.')
    try:
        import qrcode
        import io
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        response = HttpResponse(buf.getvalue(), content_type='image/png')
        if request.GET.get('download'):
            response['Content-Disposition'] = 'attachment; filename="qr-%s.png"' % source.token
        else:
            response['Content-Disposition'] = 'inline; filename="qr-%s.png"' % source.token
        return response
    except Exception as e:
        logger.exception('QR generation failed')
        return HttpResponseNotFound('QR generation failed.')


=======
>>>>>>> master
@login_required
@user_passes_test(is_staff_or_superuser)
def visitors_detail(request):
    """Detail page for visitors/sessions with filters"""
    from user_analytics.tasks import sync_ga4_sessions_task
    from django.utils import timezone as tz
    from django.db import connection
    
    # Import GA4Session only if table exists
    GA4Session = None
    try:
        from user_analytics.models import GA4Session as GA4SessionModel
        # Check if table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            if cursor.fetchone()[0] > 0:
                GA4Session = GA4SessionModel
    except Exception:
        pass
    
    time_period = request.GET.get('period', 'today')
    search_query = request.GET.get('search', '')
    source_filter = request.GET.get('source', '')
    device_filter = request.GET.get('device', '')
    entry_page_filter = request.GET.get('entry_page', '')
    exit_page_filter = request.GET.get('exit_page', '')
    country_filter = request.GET.get('country', '')
    user_type_filter = request.GET.get('user_type', 'all')  # all, registered, new
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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    if start_date is not None:
        logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        logger.info("Date Range: All Time (no date filtering)")
    
    # Check if GA4 data needs to be synced
    # Check if we have recent GA4 data in DB for this period
    ga4_needs_sync = False
    if GA4Session is not None and start_date is not None:
        try:
            latest_ga4_sync = GA4Session.objects.filter(
                date__gte=start_date.date(),
                date__lte=end_date.date()
            ).order_by('-synced_at').first()
            
            if not latest_ga4_sync:
                # No GA4 data in DB, trigger sync
                ga4_needs_sync = True
                logger.info("No GA4 data found in DB, triggering sync")
            else:
                # Check if sync is older than 1 hour
                sync_age = tz.now() - latest_ga4_sync.synced_at
                if sync_age.total_seconds() > 3600:  # 1 hour
                    ga4_needs_sync = True
                    logger.info(f"GA4 data is {sync_age.total_seconds()/60:.1f} minutes old, triggering sync")
        except Exception as e:
            logger.warning(f"Error checking GA4 sync status: {e}")
    else:
        logger.info("GA4Session table does not exist yet - migration needed")
        ga4_needs_sync = False  # Don't try to sync if table doesn't exist
    
    # Trigger sync if needed (in background)
    if ga4_needs_sync:
        try:
            sync_ga4_sessions_task.delay(time_period=time_period, link_users=True)
            logger.info("GA4 sync task triggered in background")
        except Exception as e:
            logger.error(f"Error triggering GA4 sync: {e}")
    
    # Start with UserJourney to apply entry_page/exit_page filters early
    # This is more efficient since UserJourney has these fields indexed
    journey_query = UserJourney.objects.all()
    if start_date is not None:
        journey_query = journey_query.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        )
    
    # Apply entry_page filter early
    if entry_page_filter:
        # Try exact match first, then contains for flexibility
        # This handles cases where entry_page might have trailing slashes or query params
        journey_query = journey_query.filter(
            Q(entry_page__iexact=entry_page_filter) |
            Q(entry_page__icontains=entry_page_filter)
        )
        logger.info(f"Filtering for entry_page: {entry_page_filter}")
    
    # Apply exit_page filter early
    if exit_page_filter:
        journey_query = journey_query.filter(
            Q(exit_page__iexact=exit_page_filter) |
            Q(exit_page__icontains=exit_page_filter)
        )
        logger.info(f"Filtering for exit_page: {exit_page_filter}")
    
    # Apply device filter on UserJourney if available
    if device_filter:
        journey_query = journey_query.filter(device_type__iexact=device_filter)
        logger.info(f"Filtering for device: {device_filter}")
    
    # Apply country filter on UserJourney if available
    if country_filter:
        journey_query = journey_query.filter(country__icontains=country_filter)
        logger.info(f"Filtering for country: {country_filter}")
    
    # Apply user type filter
    if user_type_filter == 'registered':
        journey_query = journey_query.filter(user__isnull=False)
        logger.info("Filtering for registered users only")
    elif user_type_filter == 'new':
        # New users: sessions without a linked user (anonymous/new visitors)
        journey_query = journey_query.filter(user__isnull=True)
        logger.info("Filtering for new users only")
    # 'all' means no user filter
    
    # Get session IDs from UserJourney that match the filters above
    # Only get journey session IDs if we have entry/exit/device/country filters
    has_journey_filters = entry_page_filter or exit_page_filter or device_filter or country_filter
    journey_session_ids = None
    
    if has_journey_filters:
        journey_session_ids = set(journey_query.values_list('session_id', flat=True).distinct())
        logger.info(f"Found {len(journey_session_ids)} session IDs from UserJourney matching entry/exit/device/country filters")
    else:
        logger.info("No journey filters applied, will use UserActivity as primary source")
    
    # Now filter by source from UserActivity (since source is in UserActivity)
    session_query = UserActivity.objects.all()
    if start_date is not None:
        session_query = session_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    
    # If we have journey session IDs from filters, restrict UserActivity query to those sessions
    if journey_session_ids is not None:
        if len(journey_session_ids) == 0:
            # No matching journeys, set empty session_ids and skip further filtering
            session_ids = []
            logger.info("No matching journeys found, returning empty result")
        else:
            session_query = session_query.filter(session_id__in=journey_session_ids)
    
    # Apply source filter (always check UserActivity for source)
    if source_filter and (journey_session_ids is None or len(journey_session_ids) > 0):
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
            # Use referrer_source_q for Google, Facebook, iapply.io (matches utm_source + referrer)
            from user_analytics.utils import referrer_source_q
            if source_filter.lower() in ('google', 'facebook', 'iapply', 'iapply.io'):
                session_query = session_query.filter(referrer_source_q(source_filter))
                logger.info(f"Filtering for referrer source: {source_filter}")
            else:
                session_query = session_query.filter(utm_source__iexact=source_filter)
                logger.info(f"Filtering for source: {source_filter}")
    
    # If device filter wasn't applied to UserJourney (no journey filters case), apply to UserActivity
    if device_filter and not has_journey_filters:
        session_query = session_query.filter(device_type__iexact=device_filter)
        logger.info(f"Filtering for device (UserActivity): {device_filter}")
    
    # Get final session IDs (only if we haven't already set it to empty)
    if journey_session_ids is None or (journey_session_ids is not None and len(journey_session_ids) > 0):
        session_ids = list(session_query.values_list('session_id', flat=True).distinct())
        logger.info(f"Found {len(session_ids)} unique session IDs matching all filters")
    
    # Check if we have any data at all in the date range
    total_activities_query = UserActivity.objects.all()
    if start_date is not None:
        total_activities_query = total_activities_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    total_activities = total_activities_query.count()
    logger.info(f"Total UserActivity records in date range: {total_activities}")
    
    # Check unique sources in database for debugging
    unique_sources_query = UserActivity.objects.exclude(utm_source__isnull=True).exclude(utm_source='')
    if start_date is not None:
        unique_sources_query = unique_sources_query.filter(
            created__gte=start_date,
            created__lte=end_date
        )
    unique_sources = unique_sources_query.values_list('utm_source', flat=True).distinct()[:10]
    logger.info(f"Sample unique sources in database: {list(unique_sources)}")
    
    # Also include GA4Session data from DB if available
    ga4_sessions_from_db = []
    if GA4Session is not None:
        try:
            ga4_query = GA4Session.objects.all()
            if start_date is not None:
                ga4_query = ga4_query.filter(
                    date__gte=start_date.date(),
                    date__lte=end_date.date()
                )
            
            # Apply filters to GA4Session
            if source_filter:
                if source_filter.lower() in ['(direct)', 'direct', '(not set)']:
                    ga4_query = ga4_query.filter(
                        Q(source__iexact='(direct)') |
                        Q(source__iexact='direct') |
                        Q(source__iexact='(not set)') |
                        Q(source__isnull=True) |
                        Q(source='')
                    )
                else:
                    ga4_query = ga4_query.filter(source__iexact=source_filter)
            
            if device_filter:
                ga4_query = ga4_query.filter(device__iexact=device_filter)
            
            if country_filter:
                ga4_query = ga4_query.filter(country__icontains=country_filter)
            
            if entry_page_filter:
                ga4_query = ga4_query.filter(
                    Q(entry_page__iexact=entry_page_filter) |
                    Q(entry_page__icontains=entry_page_filter)
                )
            
            if exit_page_filter:
                ga4_query = ga4_query.filter(
                    Q(exit_page__iexact=exit_page_filter) |
                    Q(exit_page__icontains=exit_page_filter)
                )
            
            # Apply user type filter
            if user_type_filter == 'registered':
                ga4_query = ga4_query.filter(user__isnull=False)
            elif user_type_filter == 'new':
                ga4_query = ga4_query.filter(user__isnull=True)
            
            # Get GA4 sessions
            for ga4_session in ga4_query[:1000]:  # Limit to prevent memory issues
                ga4_sessions_from_db.append({
                    'session_id': ga4_session.django_session_id or f"ga4-{ga4_session.ga4_client_id[:10]}",
                    'user': ga4_session.user,
                    'first_visit': tz.make_aware(datetime.combine(ga4_session.date, datetime.min.time())),
                    'page_views': ga4_session.pageviews,
                    'device_type': ga4_session.device or 'Unknown',
                    'utm_source': ga4_session.source or 'Direct',
                    'country': ga4_session.country,
                    'entry_page': ga4_session.entry_page,
                    'is_ga4_data': True,
                    'sessions_count': ga4_session.sessions_count,
                })
            
            logger.info(f"Found {len(ga4_sessions_from_db)} GA4 sessions from DB")
        except Exception as e:
            logger.error(f"Error fetching GA4 sessions from DB: {e}", exc_info=True)
    else:
        logger.info("GA4Session table does not exist - skipping GA4 data query")
    
    # If no session IDs found, try to get GA4 aggregated data from API
    use_ga4_fallback = len(session_ids) == 0 and total_activities == 0 and len(ga4_sessions_from_db) == 0
    ga4_sessions_data = None
    
    if use_ga4_fallback and (source_filter or country_filter or device_filter or entry_page_filter or exit_page_filter):
        logger.info("No database records found. Fetching aggregated GA4 data from API...")
        try:
            ga4_service = GA4Service()
            ga4_sessions_data = ga4_service.get_sessions_by_filters(
                time_period=time_period,
                source=source_filter,
                country=country_filter,
                device=device_filter,
                entry_page=entry_page_filter,
                exit_page=exit_page_filter,
                limit=1000,
                use_cache=False
            )
            if ga4_sessions_data:
                logger.info(f"Found {len(ga4_sessions_data)} aggregated session records from GA4 API")
        except Exception as e:
            logger.error(f"Error fetching GA4 sessions data: {e}", exc_info=True)
    
    # Get first activity for each session
    session_details = []
    for session_id in session_ids:
        first_activity = UserActivity.objects.filter(
            session_id=session_id
        ).order_by('created').first()
        
        if first_activity:
            # Entry/exit page, device, and country filters are already applied at the query level
            # No need to check them again here if they were applied to journey_query
            
            # However, if country filter wasn't applied earlier (no journey filters case), check it here
            if country_filter and not has_journey_filters:
                # Country filter wasn't applied to journey_query, check here
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
    
    # If we have GA4 data but no database data, convert GA4 data to session_details format
    if ga4_sessions_data and len(session_details) == 0:
        logger.info("Converting GA4 aggregated data to session details format...")
        for ga4_session in ga4_sessions_data:
            # Create a pseudo-session detail from GA4 aggregated data
            try:
                from datetime import datetime
                session_date = datetime.strptime(ga4_session.get('date', ''), '%Y%m%d')
            except:
                session_date = timezone.now()
            
            session_details.append({
                'session_id': f"ga4-{ga4_session.get('date', 'unknown')}-{ga4_session.get('source', 'unknown')[:10]}",
                'user': None,  # GA4 doesn't provide user info
                'first_visit': session_date,
                'page_views': ga4_session.get('pageviews', 0),
                'device_type': ga4_session.get('device', 'Unknown'),
                'utm_source': ga4_session.get('source', 'Direct'),
                'country': ga4_session.get('country', 'Unknown'),
                'entry_page': ga4_session.get('entry_page', 'N/A'),
                'sessions_count': ga4_session.get('sessions', 0),
                'is_ga4_data': True,  # Flag to indicate this is GA4 data
            })
        logger.info(f"Converted {len(session_details)} GA4 records to session details")
    
    # Merge GA4 sessions from DB with regular session details
    session_details.extend(ga4_sessions_from_db)
    
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
    if user_type_filter and user_type_filter != 'all':
        filter_params['user_type'] = user_type_filter
    
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
        'user_type_filter': user_type_filter,
        'filter_params': filter_params,
        'total_count': total_count,
        'total_activities_in_range': total_activities,
        'use_ga4_fallback': use_ga4_fallback,
        'has_database_data': total_activities > 0,  # Flag to indicate if database has any data
        'ga4_sessions_data': ga4_sessions_data,  # GA4 aggregated data if available
        'ga4_needs_sync': ga4_needs_sync,  # Flag to show sync status
        'page_title': 'Visitors/Sessions',
    }
    
    logger.info("=" * 80)
    
    return render(request, 'user_analytics/visitors_detail.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def visitors_filter_options_api(request):
    """
    API endpoint to return filter options for autocomplete/select dropdowns.
    Returns unique values for sources, devices, countries, and entry pages.
    """
    from user_analytics.models import UserActivity, UserJourney
    from django.db.models import Q
    from django.db import connection
    
    # Import GA4Session only if table exists
    GA4Session = None
    try:
        from user_analytics.models import GA4Session as GA4SessionModel
        # Check if table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            if cursor.fetchone()[0] > 0:
                GA4Session = GA4SessionModel
    except Exception:
        pass
    
    filter_type = request.GET.get('filter_type', '')  # source, device, country, entry_page
    time_period = request.GET.get('period', '30days')
    search_query = request.GET.get('q', '')  # Search term for filtering options
    
    # Calculate date range
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    options = set()
    
    try:
        if filter_type == 'source':
            # Preferred referrer sources (always show in dropdown for quick filter)
            preferred_sources = ['google', 'facebook', 'iapply']
            options.update(preferred_sources)
            
            # Get sources from UserActivity, UserJourney, and GA4Session
            sources_ua = UserActivity.objects.all()
            sources_uj = UserJourney.objects.all()
            
            if start_date is not None:
                sources_ua = sources_ua.filter(created__gte=start_date, created__lte=end_date)
                sources_uj = sources_uj.filter(start_time__gte=start_date, start_time__lte=end_date)
            
            sources_ua = sources_ua.exclude(utm_source__isnull=True).exclude(utm_source='').values_list('utm_source', flat=True).distinct()
            sources_uj = sources_uj.exclude(utm_source__isnull=True).exclude(utm_source='').values_list('utm_source', flat=True).distinct()
            
            # Only query GA4Session if table exists
            try:
                sources_ga4 = GA4Session.objects.filter(
                ).exclude(source__isnull=True).exclude(source='')
                if start_date is not None:
                    sources_ga4 = sources_ga4.filter(
                        date__gte=start_date.date(),
                        date__lte=end_date.date()
                    )
                sources_ga4 = sources_ga4.values_list('source', flat=True).distinct()
                options.update(sources_ga4)
            except Exception:
                # Table doesn't exist, skip
                pass
            
            options.update(sources_ua)
            options.update(sources_uj)
            
        elif filter_type == 'device':
            # Get devices from UserActivity, UserJourney, and GA4Session
            devices_ua = UserActivity.objects.all()
            devices_uj = UserJourney.objects.all()
            
            if start_date is not None:
                devices_ua = devices_ua.filter(created__gte=start_date, created__lte=end_date)
                devices_uj = devices_uj.filter(start_time__gte=start_date, start_time__lte=end_date)
            
            devices_ua = devices_ua.exclude(device_type__isnull=True).exclude(device_type='').values_list('device_type', flat=True).distinct()
            devices_uj = devices_uj.exclude(device_type__isnull=True).exclude(device_type='').values_list('device_type', flat=True).distinct()
            
            # Only query GA4Session if table exists
            try:
                devices_ga4 = GA4Session.objects.all()
                if start_date is not None:
                    devices_ga4 = devices_ga4.filter(
                        date__gte=start_date.date(),
                        date__lte=end_date.date()
                    )
                devices_ga4 = devices_ga4.exclude(device__isnull=True).exclude(device='').values_list('device', flat=True).distinct()
                options.update(devices_ga4)
            except Exception:
                # Table doesn't exist, skip
                pass
            
            options.update(devices_ua)
            options.update(devices_uj)
            
        elif filter_type == 'country':
            # Get countries from UserActivity, UserJourney, and GA4Session
            countries_ua = UserActivity.objects.all()
            countries_uj = UserJourney.objects.all()
            
            if start_date is not None:
                countries_ua = countries_ua.filter(created__gte=start_date, created__lte=end_date)
                countries_uj = countries_uj.filter(start_time__gte=start_date, start_time__lte=end_date)
            
            countries_ua = countries_ua.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct()
            countries_uj = countries_uj.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct()
            
            # Only query GA4Session if table exists
            try:
                countries_ga4 = GA4Session.objects.all()
                if start_date is not None:
                    countries_ga4 = countries_ga4.filter(
                        date__gte=start_date.date(),
                        date__lte=end_date.date()
                    )
                countries_ga4 = countries_ga4.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct()
                options.update(countries_ga4)
            except Exception:
                # Table doesn't exist, skip
                pass
            
            options.update(countries_ua)
            options.update(countries_uj)
            
        elif filter_type == 'entry_page':
            # Get entry pages from UserJourney and GA4Session
            entry_pages_uj = UserJourney.objects.all()
            if start_date is not None:
                entry_pages_uj = entry_pages_uj.filter(start_time__gte=start_date, start_time__lte=end_date)
            entry_pages_uj = entry_pages_uj.exclude(entry_page__isnull=True).exclude(entry_page='').values_list('entry_page', flat=True).distinct()
            
            # Only query GA4Session if table exists
            try:
                entry_pages_ga4 = GA4Session.objects.all()
                if start_date is not None:
                    entry_pages_ga4 = entry_pages_ga4.filter(
                        date__gte=start_date.date(),
                        date__lte=end_date.date()
                    )
                entry_pages_ga4 = entry_pages_ga4.exclude(entry_page__isnull=True).exclude(entry_page='').values_list('entry_page', flat=True).distinct()
                options.update(entry_pages_ga4)
            except Exception:
                # Table doesn't exist, skip
                pass
            
            options.update(entry_pages_uj)
        
        # Filter by search query if provided
        if search_query:
            search_lower = search_query.lower()
            options = {opt for opt in options if opt and search_lower in str(opt).lower()}
        
        # Convert to sorted list and limit
        options_list = sorted([str(opt) for opt in options if opt])[:100]  # Limit to 100 options
        
        # For source filter, include display labels for Google, Facebook, iapply.io
        response_data = {
            'success': True,
            'options': options_list,
            'count': len(options_list),
            'filter_type': filter_type,
        }
        if filter_type == 'source':
            response_data['source_labels'] = {
                'google': 'Google',
                'facebook': 'Facebook',
                'iapply': 'iapply.io',
            }
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'options': [],
        }, status=500)


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
    start_date, end_date = get_date_range_from_period(time_period, default_days=30)
    
    if start_date is not None:
        logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        logger.info("Date Range: All Time (no date filtering)")
    
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


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def web_owner_optional_data_api(request):
    """API endpoint for optional web owner dashboard data (loaded via AJAX)"""
    time_period = request.GET.get('period', 'today')
    data_type = request.GET.get('type', 'all')  # 'entry_pages', 'exit_pages', 'users_by_country', 'engagement', 'trends', 'all'
    
    try:
        ga4_service = GA4Service()
        response_data = {
            'success': True,
            'time_period': time_period,
        }
        
        # Load requested data types
        if data_type in ['all', 'entry_pages']:
            try:
                entry_pages = ga4_service.get_entry_pages(time_period, limit=10, use_cache=True)
                response_data['entry_pages'] = entry_pages if entry_pages else []
            except Exception as e:
                logger.warning(f"Error fetching entry pages: {e}")
                response_data['entry_pages'] = []
        
        if data_type in ['all', 'exit_pages']:
            try:
                exit_pages = ga4_service.get_exit_pages(time_period, limit=10, use_cache=True)
                response_data['exit_pages'] = exit_pages if exit_pages else []
            except Exception as e:
                logger.warning(f"Error fetching exit pages: {e}")
                response_data['exit_pages'] = []
        
        if data_type in ['all', 'users_by_country']:
            try:
                users_by_country = ga4_service.get_users_by_country(time_period, limit=10, use_cache=True)
                response_data['users_by_country'] = users_by_country if users_by_country else []
            except Exception as e:
                logger.warning(f"Error fetching users by country: {e}")
                response_data['users_by_country'] = []
        
        if data_type in ['all', 'engagement']:
            try:
                engagement = ga4_service.get_user_engagement(time_period, use_cache=True)
                response_data['engagement'] = engagement if engagement else None
            except Exception as e:
                logger.warning(f"Error fetching engagement: {e}")
                response_data['engagement'] = None
        
        if data_type in ['all', 'trends']:
            try:
                top_pages_with_trends = ga4_service.get_top_pages_with_trends(time_period, limit=20, use_cache=True)
                response_data['top_pages_with_trends'] = top_pages_with_trends if top_pages_with_trends else []
            except Exception as e:
                logger.warning(f"Error fetching top pages with trends: {e}")
                response_data['top_pages_with_trends'] = []
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.error(f"Error in web_owner_optional_data_api: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
