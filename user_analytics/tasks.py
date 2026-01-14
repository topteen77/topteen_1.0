"""
Celery tasks for async analytics processing.
All tracking operations are performed asynchronously to maintain website performance.
"""
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from user_analytics.models import UserActivity, UserJourney, Lead, UserEvent, GA4Session
from user_analytics.utils import parse_user_agent_info, get_referrer_source
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def track_page_view_async(
    self,
    session_id,
    user_id=None,
    ga4_client_id=None,
    page_path='',
    page_title='',
    referrer='',
    user_agent='',
    ip_address='',
    utm_source='',
    utm_medium='',
    utm_campaign='',
    utm_term='',
    utm_content='',
):
    """
    Async task to track page view.
    
    Args:
        session_id: Unique session identifier
        user_id: User ID if authenticated
        page_path: URL path
        page_title: Page title
        referrer: HTTP referrer
        user_agent: User agent string
        ip_address: Client IP address
        utm_source: UTM source parameter
        utm_medium: UTM medium parameter
        utm_campaign: UTM campaign parameter
        utm_term: UTM term parameter
        utm_content: UTM content parameter
    """
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Parse user agent
        ua_info = parse_user_agent_info(user_agent)
        
        # Determine source if UTM not provided
        source = utm_source or get_referrer_source(referrer)
        
        # Create or update user activity
        with transaction.atomic():
            activity = UserActivity.objects.create(
                user=user,
                session_id=session_id,
                page_path=page_path,
                page_title=page_title,
                referrer=referrer,
                utm_source=utm_source or source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                utm_term=utm_term,
                utm_content=utm_content,
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=ua_info['device_type'],
                browser=ua_info['browser'],
                os=ua_info['os'],
            )
            
            # Update or create lead if user is not authenticated
            if not user and (utm_source or referrer):
                email = None  # We don't have email for anonymous users
                # Try to get email from session or create lead with session ID
                lead, created = Lead.objects.get_or_create(
                    email=f"session_{session_id}@temp.topteen.in",
                    defaults={
                        'source': source,
                        'medium': utm_medium,
                        'campaign': utm_campaign,
                        'referrer': referrer,
                        'landing_page': page_path,
                        'first_visit': timezone.now(),
                        'last_visit': timezone.now(),
                    }
                )
                if not created:
                    lead.last_visit = timezone.now()
                    lead.visit_count += 1
                    lead.save()
        
        return f"Tracked page view: {page_path}"
    
    except Exception as exc:
        logger.error(f"Error tracking page view: {exc}", exc_info=True)
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_user_journey_async(
    self,
    session_id,
    user_id=None,
    ga4_client_id=None,
    page_path='',
    referrer='',
):
    """
    Async task to update user journey.
    
    Args:
        session_id: Unique session identifier
        user_id: User ID if authenticated
        page_path: URL path
        referrer: HTTP referrer
    """
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        with transaction.atomic():
            defaults = {
                'user': user,
                'start_time': timezone.now(),
                'entry_page': page_path,
                'referrer': referrer,
                'journey_path': [page_path],
            }
            if ga4_client_id:
                defaults['ga4_client_id'] = ga4_client_id
            
            journey, created = UserJourney.objects.get_or_create(
                session_id=session_id,
                defaults=defaults
            )
            
            if not created:
                # Update existing journey
                journey.end_time = timezone.now()
                journey.total_pages += 1
                journey.exit_page = page_path
                
                # Update GA4 client ID if provided and not already set
                if ga4_client_id and not journey.ga4_client_id:
                    journey.ga4_client_id = ga4_client_id
                
                # Add to journey path if not already there
                if page_path not in journey.journey_path:
                    journey.journey_path.append(page_path)
                
                journey.save()
        
        return f"Updated journey: {session_id}"
    
    except Exception as exc:
        logger.error(f"Error updating user journey: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def track_user_event_async(
    self,
    event_type,
    event_name,
    user_id=None,
    event_value=0,
    content_type_id=None,
    object_id=None,
    metadata=None,
    session_id=None,
):
    """
    Async task to track user events (payments, enrollments, etc.).
    
    Args:
        event_type: Type of event (from UserEvent.EVENT_TYPES)
        event_name: Name of the event
        user_id: User ID
        event_value: Monetary value if applicable
        content_type_id: ContentType ID for generic foreign key
        object_id: Object ID for generic foreign key
        metadata: Additional event data (dict)
        session_id: Session ID
    """
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        from django.contrib.contenttypes.models import ContentType
        content_type = None
        if content_type_id:
            try:
                content_type = ContentType.objects.get(id=content_type_id)
            except ContentType.DoesNotExist:
                pass
        
        with transaction.atomic():
            event = UserEvent.objects.create(
                user=user,
                event_type=event_type,
                event_name=event_name,
                event_value=event_value,
                content_type=content_type,
                object_id=object_id,
                metadata=metadata or {},
                session_id=session_id,
            )
            
            # Update lead conversion if applicable
            if user and event_type in ['payment_success', 'course_enrolled', 'psychometric_test_completed']:
                # Mark lead as converted
                leads = Lead.objects.filter(user=user, is_converted=False)
                for lead in leads:
                    lead.is_converted = True
                    lead.converted_at = timezone.now()
                    lead.conversion_value = float(event_value)
                    lead.save()
                
                # Update user journey conversion
                if session_id:
                    journeys = UserJourney.objects.filter(
                        session_id=session_id,
                        converted=False
                    )
                    for journey in journeys:
                        journey.converted = True
                        journey.conversion_event = event
                        journey.save()
        
        return f"Tracked event: {event_name}"
    
    except Exception as exc:
        logger.error(f"Error tracking user event: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task
def aggregate_daily_analytics(date=None):
    """
    Periodic task to aggregate daily analytics data.
    Runs daily to create summary reports.
    
    Args:
        date: Date to aggregate (defaults to yesterday)
    """
    from datetime import timedelta
    from user_analytics.models import AnalyticsCache
    from django.db.models import Count, Sum, Avg
    from django.utils import timezone
    
    if not date:
        date = (timezone.now() - timedelta(days=1)).date()
    
    try:
        # Aggregate user activities
        activities = UserActivity.objects.filter(
            created__date=date
        )
        
        # Aggregate user events
        events = UserEvent.objects.filter(
            created__date=date
        )
        
        # Calculate metrics
        total_page_views = activities.count()
        unique_visitors = activities.values('session_id').distinct().count()
        total_revenue = events.filter(
            event_type='payment_success'
        ).aggregate(total=Sum('event_value'))['total'] or 0
        
        total_registrations = events.filter(
            event_type='registration'
        ).count()
        
        total_conversions = events.filter(
            event_type__in=['payment_success', 'course_enrolled', 'psychometric_test_completed']
        ).count()
        
        # Create cache entry
        cache_data = {
            'date': str(date),
            'total_page_views': total_page_views,
            'unique_visitors': unique_visitors,
            'total_revenue': float(total_revenue),
            'total_registrations': total_registrations,
            'total_conversions': total_conversions,
        }
        
        cache_key = f"daily_summary_{date}"
        cache, created = AnalyticsCache.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                'cache_type': 'daily_summary',
                'date_range_start': date,
                'date_range_end': date,
                'cached_data': cache_data,
                'expires_at': timezone.now() + timedelta(days=30),
            }
        )
        
        logger.info(f"Aggregated daily analytics for {date}")
        return cache_data
    
    except Exception as exc:
        logger.error(f"Error aggregating daily analytics: {exc}", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
def sync_ga4_sessions_task(self, time_period='30days', link_users=True):
    """
    Background task to sync GA4 session data to database.
    Called automatically on first dashboard visit if data is missing.
    
    Args:
        time_period: Time period string ('today', 'yesterday', '7days', '30days', '90days')
        link_users: Whether to attempt linking sessions to Django users
    """
    try:
        from user_analytics.ga4_service import GA4Service
        
        ga4_service = GA4Service()
        result = ga4_service.sync_sessions_to_db(time_period=time_period, link_users=link_users)
        
        if result.get('success'):
            logger.info(f"GA4 sync task completed successfully: {result}")
            return result
        else:
            logger.error(f"GA4 sync task failed: {result.get('error')}")
            raise Exception(result.get('error', 'Unknown error'))
            
    except Exception as exc:
        logger.error(f"Error in GA4 sync task: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes

