"""
Celery tasks for async analytics processing.
All tracking operations are performed asynchronously to maintain website performance.
Also includes synchronous helper functions for fallback when Celery is unavailable.
"""
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from user_analytics.models import UserActivity, UserJourney, Lead, UserEvent, GA4Session
from communication.models import CommunicationLog
from core import choices
from user_analytics.utils import (
    parse_user_agent_info,
    get_referrer_source,
    get_geolocation_from_ip,
    get_traffic_source_category,
)
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


def _check_celery_workers_active():
    """Best-effort check for active Celery workers."""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        active_workers = inspect.active()
        return bool(active_workers)
    except Exception:
        return False


def link_analytics_session_to_user(session_id, user):
    """
    Link anonymous analytics rows to the authenticated user for attribution continuity.
    """
    if not session_id or not user:
        return {'activities': 0, 'journeys': 0}

    activities_updated = UserActivity.objects.filter(
        session_id=session_id,
        user__isnull=True,
    ).update(user=user)
    journeys_updated = UserJourney.objects.filter(
        session_id=session_id,
        user__isnull=True,
    ).update(user=user)
    return {'activities': activities_updated, 'journeys': journeys_updated}


def reconcile_recent_user_events(user, session_id, minutes=20):
    """
    Backfill missing session_id for recent business events and refresh journey flags.
    """
    if not user or not session_id:
        return 0
    since = timezone.now() - timedelta(minutes=minutes)
    events = UserEvent.objects.filter(
        user=user,
        created__gte=since,
        session_id__isnull=True,
    ) | UserEvent.objects.filter(
        user=user,
        created__gte=since,
        session_id='',
    )
    updated_count = 0
    for event in events.distinct().order_by('-created'):
        event.session_id = session_id
        event.save(update_fields=['session_id'])
        update_journey_from_event(event, session_id=session_id)
        updated_count += 1
    return updated_count


@shared_task
def send_daily_new_user_report(force_send=False, override_recipients=None):
    """
    Send daily new user report (today + this week) to WEBADMINEMAIL.
    Runs only when ENVIRONMENT=production and WEBADMINEMAIL is configured,
    unless force_send=True (manual testing).
    """
    environment = str(getattr(settings, "ENVIRONMENT", "")).strip().lower()
    web_admin_email = (
        str(override_recipients).strip()
        if override_recipients is not None
        else str(getattr(settings, "WEBADMINEMAIL", "")).strip()
    )

    if (not force_send) and environment != "production":
        logger.info("Skipping daily new user report: ENVIRONMENT is not production.")
        return "skipped_non_production"

    if not web_admin_email:
        logger.info("Skipping daily new user report: WEBADMINEMAIL not configured.")
        return "skipped_missing_recipient"

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # Monday

    today_new_users = User.objects.filter(created__date=today).count()
    week_new_users = User.objects.filter(created__date__gte=week_start, created__date__lte=today).count()

    subject = f"[TopTeen] Daily new user report - {today.isoformat()}"
    text_body = (
        "TopTeen Daily User Report\n\n"
        f"Date: {today.isoformat()}\n"
        f"New users today: {today_new_users}\n"
        f"Total new users this week (Mon-Today): {week_new_users}\n"
    )
    html_body = (
        "<h3>TopTeen Daily User Report</h3>"
        f"<p><strong>Date:</strong> {today.isoformat()}</p>"
        f"<p><strong>New users today:</strong> {today_new_users}</p>"
        f"<p><strong>Total new users this week (Mon-Today):</strong> {week_new_users}</p>"
    )

    recipients = [email.strip() for email in web_admin_email.split(",") if email.strip()]
    if not recipients:
        logger.info("Skipping daily new user report: WEBADMINEMAIL has no valid recipients.")
        return "skipped_invalid_recipient"

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(
        settings, "TOPTEEN_FROM_EMAIL", "noreply@example.com"
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipients,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        CommunicationLog.objects.create(
            to=",".join(recipients),
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="success",
        )
        logger.info(
            "Daily new user report sent successfully (recipient_count=%s, today=%s, week=%s).",
            len(recipients),
            today_new_users,
            week_new_users,
        )
        return {
            "date": today.isoformat(),
            "today_new_users": today_new_users,
            "week_new_users": week_new_users,
            "recipient_count": len(recipients),
        }
    except Exception as exc:
        CommunicationLog.objects.create(
            to=web_admin_email or "WEBADMINEMAIL_NOT_SET",
            body=subject if "subject" in locals() else "Daily new user report",
            type=choices.CommunicationTypeChooices.EMAIL,
            response="failed: {}".format(exc),
        )
        logger.error("Failed to send daily new user report: %s", exc, exc_info=True)
        raise


# Synchronous helper functions (can be called directly when Celery is unavailable)
def track_page_view_sync(
    session_id,
    user_id=None,
    ga4_client_id=None,
    page_path='',
    page_url=None,
    page_title='',
    referrer='',
    user_agent='',
    ip_address='',
    utm_source='',
    utm_medium='',
    utm_campaign='',
    utm_term='',
    utm_content='',
    enquiry_source_id=None,
):
    """
    Synchronous version of track_page_view_async.
    Can be called directly when Celery is unavailable.
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
        
        # Determine source if UTM not provided (ref= token is non-readable; we store enquiry_source_id only)
        source = utm_source or get_referrer_source(referrer)
        if enquiry_source_id:
            source = 'enquiry'  # Don't expose token in lead source
        traffic_category = get_traffic_source_category(utm_source or source, referrer)
        
        # Resolve country/city from IP (short timeout to avoid blocking)
        geo = get_geolocation_from_ip(ip_address, timeout=2) if ip_address else {}
        
        # Create or update user activity
        with transaction.atomic():
            activity_kw = {
                'user': user,
                'session_id': session_id,
                'page_path': page_path,
                'page_title': page_title,
                'referrer': referrer,
                'utm_source': utm_source or source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'utm_term': utm_term,
                'utm_content': utm_content,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'device_type': ua_info['device_type'],
                'browser': ua_info['browser'],
                'os': ua_info['os'],
                'country': geo.get('country'),
                'city': geo.get('city'),
                'traffic_source_category': traffic_category,
            }
            if page_url:
                activity_kw['page_url'] = page_url[:500]
            if enquiry_source_id:
                activity_kw['enquiry_source_id'] = enquiry_source_id
            activity = UserActivity.objects.create(**activity_kw)
            
            # Update or create lead if user is not authenticated
            if not user and (utm_source or referrer or enquiry_source_id):
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
        logger.error(f"Error tracking page view (sync): {exc}", exc_info=True)
        return None


def update_user_journey_sync(
    session_id,
    user_id=None,
    ga4_client_id=None,
    page_path='',
    referrer='',
    device_type=None,
    country=None,
    utm_source=None,
    traffic_source_category=None,
    enquiry_source_id=None,
):
    """
    Synchronous version of update_user_journey_async.
    Can be called directly when Celery is unavailable.
    """
    try:
        user = None
        is_new_user = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                # Check if user is new (registered in last 24 hours)
                from datetime import timedelta
                is_new_user = user.created > (timezone.now() - timedelta(hours=24))
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
            if device_type:
                defaults['device_type'] = device_type
            if country:
                defaults['country'] = country
            if utm_source:
                defaults['utm_source'] = utm_source
            if traffic_source_category:
                defaults['traffic_source_category'] = traffic_source_category
            if enquiry_source_id:
                defaults['enquiry_source_id'] = enquiry_source_id
            
            try:
                journey, created = UserJourney.objects.get_or_create(
                    session_id=session_id,
                    defaults=defaults
                )
            except IntegrityError:
                # Race: another request may have created this session_id; fetch if exists
                journey = UserJourney.objects.filter(session_id=session_id).first()
                if journey is None:
                    logger.warning(
                        "IntegrityError on UserJourney get_or_create but no record found for session_id=%s",
                        session_id,
                    )
                    return f"Updated journey: {session_id}"
                created = False
            
            if not created:
                # Update existing journey
                journey.end_time = timezone.now()
                journey.total_pages += 1
                journey.exit_page = page_path
                
                # Update GA4 client ID if provided and not already set
                if ga4_client_id and not journey.ga4_client_id:
                    journey.ga4_client_id = ga4_client_id
                
                # Update device/country/source category if not set
                if device_type and not journey.device_type:
                    journey.device_type = device_type
                if country and not journey.country:
                    journey.country = country
                if utm_source and not journey.utm_source:
                    journey.utm_source = utm_source
                if traffic_source_category and not journey.traffic_source_category:
                    journey.traffic_source_category = traffic_source_category
                if enquiry_source_id and not journey.enquiry_source_id:
                    journey.enquiry_source_id = enquiry_source_id
                
                # Add to journey path if not already there
                if page_path not in journey.journey_path:
                    journey.journey_path.append(page_path)
                
                journey.save()
        
        return f"Updated journey: {session_id}"
    
    except Exception as exc:
        logger.error(f"Error updating user journey (sync): {exc}", exc_info=True)
        return None


@shared_task(bind=True, max_retries=3)
def track_page_view_async(
    self,
    session_id,
    user_id=None,
    ga4_client_id=None,
    page_path='',
    page_url=None,
    page_title='',
    referrer='',
    user_agent='',
    ip_address='',
    utm_source='',
    utm_medium='',
    utm_campaign='',
    utm_term='',
    utm_content='',
    enquiry_source_id=None,
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
        enquiry_source_id: Set when user arrived via ?ref= token (non-readable link)
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
        
        # Determine source if UTM not provided (ref= token: store enquiry_source_id only, non-readable)
        source = utm_source or get_referrer_source(referrer)
        if enquiry_source_id:
            source = 'enquiry'
        traffic_category = get_traffic_source_category(utm_source or source, referrer)
        
        # Resolve country/city from IP
        geo = get_geolocation_from_ip(ip_address, timeout=2) if ip_address else {}
        
        # Create or update user activity
        with transaction.atomic():
            activity_kw = {
                'user': user,
                'session_id': session_id,
                'page_path': page_path,
                'page_title': page_title,
                'referrer': referrer,
                'utm_source': utm_source or source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'utm_term': utm_term,
                'utm_content': utm_content,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'device_type': ua_info['device_type'],
                'browser': ua_info['browser'],
                'os': ua_info['os'],
                'country': geo.get('country'),
                'city': geo.get('city'),
                'traffic_source_category': traffic_category,
            }
            if page_url:
                activity_kw['page_url'] = page_url[:500]
            if enquiry_source_id:
                activity_kw['enquiry_source_id'] = enquiry_source_id
            activity = UserActivity.objects.create(**activity_kw)
            
            # Update or create lead if user is not authenticated
            if not user and (utm_source or referrer or enquiry_source_id):
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
    device_type=None,
    country=None,
    utm_source=None,
    traffic_source_category=None,
    enquiry_source_id=None,
):
    """
    Async task to update user journey.
    
    Args:
        session_id: Unique session identifier
        user_id: User ID if authenticated
        page_path: URL path
        referrer: HTTP referrer
        device_type: Device type (mobile, desktop, tablet)
        country: User country
        utm_source: UTM source (inquiry source)
        traffic_source_category: search, social, referral, direct, internal
        enquiry_source_id: Set when user arrived via ?ref= token (non-readable link)
    """
    try:
        user = None
        is_new_user = False
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                # Check if user is new (registered in last 24 hours)
                from datetime import timedelta
                is_new_user = user.created > (timezone.now() - timedelta(hours=24))
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
            if device_type:
                defaults['device_type'] = device_type
            if country:
                defaults['country'] = country
            if utm_source:
                defaults['utm_source'] = utm_source
            if traffic_source_category:
                defaults['traffic_source_category'] = traffic_source_category
            if enquiry_source_id:
                defaults['enquiry_source_id'] = enquiry_source_id
            
            try:
                journey, created = UserJourney.objects.get_or_create(
                    session_id=session_id,
                    defaults=defaults
                )
            except IntegrityError:
                journey = UserJourney.objects.filter(session_id=session_id).first()
                if journey is None:
                    logger.warning(
                        "IntegrityError on UserJourney get_or_create but no record found for session_id=%s",
                        session_id,
                    )
                    return f"Updated journey: {session_id}"
                created = False
            
            if not created:
                # Update existing journey
                journey.end_time = timezone.now()
                journey.total_pages += 1
                journey.exit_page = page_path
                
                # Update GA4 client ID if provided and not already set
                if ga4_client_id and not journey.ga4_client_id:
                    journey.ga4_client_id = ga4_client_id
                
                # Update device/country/source category if not set
                if device_type and not journey.device_type:
                    journey.device_type = device_type
                if country and not journey.country:
                    journey.country = country
                if utm_source and not journey.utm_source:
                    journey.utm_source = utm_source
                if traffic_source_category and not journey.traffic_source_category:
                    journey.traffic_source_category = traffic_source_category
                if enquiry_source_id and not journey.enquiry_source_id:
                    journey.enquiry_source_id = enquiry_source_id
                
                # Add to journey path if not already there
                if page_path not in journey.journey_path:
                    journey.journey_path.append(page_path)
                
                journey.save()
        
        return f"Updated journey: {session_id}"
    
    except Exception as exc:
        logger.error(f"Error updating user journey: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


def update_journey_from_event(event, session_id=None):
    """
    Update user journey based on event type.
    Links events to journeys and updates journey flags.
    """
    try:
        from user_analytics.models import UserJourney
        
        # Get session_id from event if not provided
        if not session_id and event.session_id:
            session_id = event.session_id
        
        if not session_id:
            return
        
        # Find journeys with this session_id
        journeys = UserJourney.objects.filter(session_id=session_id)
        
        for journey in journeys:
            updated = False
            
            # Update based on event type
            if event.event_type == 'registration':
                journey.is_registered = True
                journey.registration_event = event
                updated = True
            elif event.event_type == 'payment_success':
                journey.has_payment = True
                journey.payment_event = event
                journey.converted = True
                journey.conversion_event = event
                updated = True
            elif event.event_type == 'psychometric_test_started':
                journey.has_psychometric_test = True
                journey.psychometric_test_event = event
                updated = True
            elif event.event_type == 'psychometric_test_completed':
                journey.test_completed = True
                journey.test_completion_event = event
                updated = True
            elif event.event_type == 'result_generated' or 'result' in event.event_name.lower():
                journey.result_generated = True
                journey.result_generation_event = event
                updated = True
            
            if updated:
                journey.save()
                logger.debug(f"Updated journey {journey.id} from event {event.id} ({event.event_type})")
    
    except Exception as e:
        logger.error(f"Error updating journey from event: {e}", exc_info=True)


def _track_user_event_common(
    event_type,
    event_name,
    user_id=None,
    event_value=0,
    content_type_id=None,
    object_id=None,
    metadata=None,
    session_id=None,
):
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

        if user and event_type in ['payment_success', 'course_enrolled', 'psychometric_test_completed']:
            leads = Lead.objects.filter(user=user, is_converted=False)
            for lead in leads:
                lead.is_converted = True
                lead.converted_at = timezone.now()
                lead.conversion_value = float(event_value)
                lead.save()

        if session_id or event.session_id:
            update_journey_from_event(event, session_id or event.session_id)

    return event


def track_user_event_sync(
    event_type,
    event_name,
    user_id=None,
    event_value=0,
    content_type_id=None,
    object_id=None,
    metadata=None,
    session_id=None,
):
    """Synchronous event tracking fallback."""
    try:
        event = _track_user_event_common(
            event_type=event_type,
            event_name=event_name,
            user_id=user_id,
            event_value=event_value,
            content_type_id=content_type_id,
            object_id=object_id,
            metadata=metadata,
            session_id=session_id,
        )
        return f"Tracked event: {event.event_name}"
    except Exception as exc:
        logger.error(f"Error tracking user event (sync): {exc}", exc_info=True)
        return None


def safe_track_user_event(
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
    Use Celery when available, otherwise run synchronously.
    """
    payload = {
        'event_type': event_type,
        'event_name': event_name,
        'user_id': user_id,
        'event_value': event_value,
        'content_type_id': content_type_id,
        'object_id': object_id,
        'metadata': metadata,
        'session_id': session_id,
    }
    try:
        if _check_celery_workers_active():
            return track_user_event_async.delay(**payload)
    except Exception:
        pass
    return track_user_event_sync(**payload)


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
        event = _track_user_event_common(
            event_type=event_type,
            event_name=event_name,
            user_id=user_id,
            event_value=event_value,
            content_type_id=content_type_id,
            object_id=object_id,
            metadata=metadata,
            session_id=session_id,
        )
        return f"Tracked event: {event.event_name}"
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

