"""
Analytics Middleware for tracking user activities asynchronously.
This middleware captures page views, sessions, referrer information,
and GA4 client IDs without blocking the request/response cycle.
Falls back to synchronous execution if Celery is unavailable.
"""
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from user_analytics.tasks import (
    track_page_view_async, 
    update_user_journey_async,
    track_page_view_sync,
    update_user_journey_sync
)
import logging

logger = logging.getLogger(__name__)

# Short timeout for Celery worker check to avoid blocking the request (prevents 502 when broker is slow)
CELERY_INSPECT_TIMEOUT_SECONDS = 2


class AnalyticsMiddleware(MiddlewareMixin):
    """
    Middleware to track user activities asynchronously using Celery.
    Captures page views, sessions, referrers, and UTM parameters.
    """
    
    def process_request(self, request):
        """Process request and extract analytics data"""
        # Skip tracking for admin, static files, and API endpoints
        path = request.path
        skip_paths = ['/admin/', '/static/', '/media/', '/api/', '/analytics/api/']
        
        if any(path.startswith(skip) for skip in skip_paths):
            return None
        
        # Generate or get session ID
        if 'analytics_session_id' not in request.session:
            request.session['analytics_session_id'] = str(uuid.uuid4())
        
        # Extract GA4 client ID from cookies
        ga4_client_id = self.extract_ga4_client_id(request)
        if ga4_client_id:
            # Store in session for linking
            request.session['ga4_client_id'] = ga4_client_id
        
        # Store analytics data in request for async processing
        request.analytics_data = {
            'session_id': request.session.get('analytics_session_id'),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ga4_client_id': ga4_client_id,
            'path': path,
            'referrer': request.META.get('HTTP_REFERER', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self.get_client_ip(request),
            'utm_source': request.GET.get('utm_source', ''),
            'utm_medium': request.GET.get('utm_medium', ''),
            'utm_campaign': request.GET.get('utm_campaign', ''),
            'utm_term': request.GET.get('utm_term', ''),
            'utm_content': request.GET.get('utm_content', ''),
        }
        
        return None
    
    def _check_celery_workers_active(self):
        """Check if Celery workers are active. Runs in thread to avoid blocking."""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            return bool(active_workers)
        except Exception:
            return False

    def process_response(self, request, response):
        """Process response and trigger async tracking with fallback to sync.
        All tracking is wrapped in try/except so failures never cause 502 or break the response.
        Celery worker check runs with a short timeout to avoid blocking when broker is slow.
        """
        # Only track successful GET requests
        if not (hasattr(request, 'analytics_data') and request.method == 'GET' and response.status_code == 200):
            return response

        try:
            page_title = getattr(response, 'page_title', '')

            # Check if Celery worker is running with a short timeout to avoid blocking (prevents 502)
            use_sync = True
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._check_celery_workers_active)
                    use_sync = not future.result(timeout=CELERY_INSPECT_TIMEOUT_SECONDS)
            except (FuturesTimeoutError, Exception):
                use_sync = True
                logger.debug("Celery check timed out or failed, using synchronous tracking")

            if use_sync:
                # Use synchronous tracking (worker not running)
                track_page_view_sync(
                    session_id=request.analytics_data['session_id'],
                    user_id=request.analytics_data['user_id'],
                    ga4_client_id=request.analytics_data.get('ga4_client_id'),
                    page_path=request.analytics_data['path'],
                    page_title=page_title,
                    referrer=request.analytics_data['referrer'],
                    user_agent=request.analytics_data['user_agent'],
                    ip_address=request.analytics_data['ip_address'],
                    utm_source=request.analytics_data['utm_source'],
                    utm_medium=request.analytics_data['utm_medium'],
                    utm_campaign=request.analytics_data['utm_campaign'],
                    utm_term=request.analytics_data['utm_term'],
                    utm_content=request.analytics_data['utm_content'],
                )
                
                # Get device and country from user agent
                device_type = None
                country = None
                if request.analytics_data.get('user_agent'):
                    from user_analytics.utils import parse_user_agent_info
                    ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                    device_type = ua_info.get('device_type')
                
                # Get country from UserActivity if available (from previous page views)
                try:
                    from user_analytics.models import UserActivity
                    recent_activity = UserActivity.objects.filter(
                        session_id=request.analytics_data['session_id']
                    ).order_by('-created').first()
                    if recent_activity and recent_activity.country:
                        country = recent_activity.country
                except Exception:
                    pass
                
                update_user_journey_sync(
                    session_id=request.analytics_data['session_id'],
                    user_id=request.analytics_data['user_id'],
                    ga4_client_id=request.analytics_data.get('ga4_client_id'),
                    page_path=request.analytics_data['path'],
                    referrer=request.analytics_data['referrer'],
                    device_type=device_type,
                    country=country,
                    utm_source=request.analytics_data.get('utm_source'),
                )
            else:
                # Try async tracking first, fall back to sync if it fails
                try:
                    # Trigger async task for page view tracking
                    track_page_view_async.delay(
                        session_id=request.analytics_data['session_id'],
                        user_id=request.analytics_data['user_id'],
                        ga4_client_id=request.analytics_data.get('ga4_client_id'),
                        page_path=request.analytics_data['path'],
                        page_title=page_title,
                        referrer=request.analytics_data['referrer'],
                        user_agent=request.analytics_data['user_agent'],
                        ip_address=request.analytics_data['ip_address'],
                        utm_source=request.analytics_data['utm_source'],
                        utm_medium=request.analytics_data['utm_medium'],
                        utm_campaign=request.analytics_data['utm_campaign'],
                        utm_term=request.analytics_data['utm_term'],
                        utm_content=request.analytics_data['utm_content'],
                    )
                    
                    # Get device and country from user agent
                    device_type = None
                    country = None
                    if request.analytics_data.get('user_agent'):
                        from user_analytics.utils import parse_user_agent_info
                        ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                        device_type = ua_info.get('device_type')
                    
                    # Update user journey asynchronously
                    update_user_journey_async.delay(
                        session_id=request.analytics_data['session_id'],
                        user_id=request.analytics_data['user_id'],
                        ga4_client_id=request.analytics_data.get('ga4_client_id'),
                        page_path=request.analytics_data['path'],
                        referrer=request.analytics_data['referrer'],
                        device_type=device_type,
                        country=country,
                        utm_source=request.analytics_data.get('utm_source'),
                    )
                except Exception as e:
                    # Celery is unavailable, fall back to synchronous execution
                    logger.warning(f"Celery unavailable, using synchronous tracking: {e}")
                    
                    # Track page view synchronously
                    track_page_view_sync(
                        session_id=request.analytics_data['session_id'],
                        user_id=request.analytics_data['user_id'],
                        ga4_client_id=request.analytics_data.get('ga4_client_id'),
                        page_path=request.analytics_data['path'],
                        page_title=page_title,
                        referrer=request.analytics_data['referrer'],
                        user_agent=request.analytics_data['user_agent'],
                        ip_address=request.analytics_data['ip_address'],
                        utm_source=request.analytics_data['utm_source'],
                        utm_medium=request.analytics_data['utm_medium'],
                        utm_campaign=request.analytics_data['utm_campaign'],
                        utm_term=request.analytics_data['utm_term'],
                        utm_content=request.analytics_data['utm_content'],
                    )
                    
                    # Get device and country from user agent
                    device_type = None
                    country = None
                    if request.analytics_data.get('user_agent'):
                        from user_analytics.utils import parse_user_agent_info
                        ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                        device_type = ua_info.get('device_type')
                    
                    # Update user journey synchronously
                    update_user_journey_sync(
                        session_id=request.analytics_data['session_id'],
                        user_id=request.analytics_data['user_id'],
                        ga4_client_id=request.analytics_data.get('ga4_client_id'),
                        page_path=request.analytics_data['path'],
                        referrer=request.analytics_data['referrer'],
                        device_type=device_type,
                        country=country,
                        utm_source=request.analytics_data.get('utm_source'),
                    )
        except Exception as e:
            # Never let analytics break the response (prevents 502 when tracking fails or blocks)
            logger.warning("Analytics tracking failed, response unchanged: %s", e, exc_info=True)
        return response
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def extract_ga4_client_id(request):
        """
        Extract GA4 client ID from cookies.
        GA4 stores client ID in cookies like:
        - _ga: GA1.2.XXXXXXXXX.YYYYYYYYY (format: GA<version>.<domain hash>.<random1>.<random2>)
        - _ga_<PROPERTY_ID>: similar format
        
        Returns the client ID in format: XXXXXXXXX.YYYYYYYYY
        """
        # Try _ga cookie first (universal GA cookie)
        ga_cookie = request.COOKIES.get('_ga')
        if ga_cookie:
            # Format: GA1.2.XXXXXXXXX.YYYYYYYYY
            # Extract the last two parts (client ID)
            parts = ga_cookie.split('.')
            if len(parts) >= 4:
                return f"{parts[2]}.{parts[3]}"
        
        # Try _ga_<PROPERTY_ID> cookies (GA4 specific)
        for cookie_name in request.COOKIES.keys():
            if cookie_name.startswith('_ga_'):
                ga4_cookie = request.COOKIES.get(cookie_name)
                if ga4_cookie:
                    # Format: GS1.1.XXXXXXXXX.YYYYYYYYY
                    parts = ga4_cookie.split('.')
                    if len(parts) >= 4:
                        return f"{parts[2]}.{parts[3]}"
        
        # Try to get from custom header if set by frontend
        ga4_header = request.META.get('HTTP_X_GA4_CLIENT_ID')
        if ga4_header:
            return ga4_header
        
        return None
