"""
Analytics Middleware for tracking user activities asynchronously.
This middleware captures page views, sessions, referrer information,
and GA4 client IDs without blocking the request/response cycle.
Falls back to synchronous execution if Celery is unavailable.
"""
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from urllib.parse import urlparse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from user_analytics.tasks import (
    track_page_view_async, 
    update_user_journey_async,
    track_page_view_sync,
    update_user_journey_sync,
    link_analytics_session_to_user,
    reconcile_recent_user_events,
)
import logging

logger = logging.getLogger(__name__)

# Short timeout for Celery worker check to avoid blocking the request (prevents 502 when broker is slow)
CELERY_INSPECT_TIMEOUT_SECONDS = 2
DEDUP_WINDOW_SECONDS = 8
DIRECT_LOGIN_PATH_PREFIXES = (
    '/student/login/',
    '/parents/login/',
    '/login/',
    '/user/login/',
)

# Paths that never get page/journey tracking (Django admin, staff dashboards, static, attribution ping, etc.).
# Nested JSON endpoints under app mounts (e.g. /forum/api/, /notifications/api/) are skipped when
# the path contains the substring /api/ (see _should_skip_analytics_path).
_BASE_ANALYTICS_SKIP_PATH_PREFIXES = (
    '/admin/',
    '/topteenadmin/',
    '/user-analytics/',
    '/seo-dashboard/',
    '/notifications/',
    '/analytics/',
    '/static/',
    '/media/',
    '/entry/attribution/',
    '/api-auth/',
    '/__debug__/',
    '/ws/',
    '/socket.io/',
    '/health/',
    '/metrics/',
    '/.well-known/',
)

_BASE_ANALYTICS_SKIP_EXACT_PATHS = (
    '/favicon.ico',
    '/robots.txt',
    '/manifest.json',
    '/service-worker.js',
    '/sw.js',
    '/sitemap.xml',
)


def _get_analytics_skip_path_prefixes():
    from django.conf import settings
    extra = getattr(settings, 'USER_ANALYTICS_EXTRA_SKIP_PATH_PREFIXES', None) or ()
    return _BASE_ANALYTICS_SKIP_PATH_PREFIXES + tuple(extra)


def _should_skip_analytics_path(path):
    """
    Skip page view / journey tracking for admin areas, internal tools, static/media,
    notification polling, nested * /api/* routes, and REST mounts under /api/.
    """
    if not path:
        return False
    if path in _BASE_ANALYTICS_SKIP_EXACT_PATHS:
        return True
    # REST and nested app APIs (e.g. /api/v1/, /forum/api/queries/, /careers/api/...)
    if path.startswith('/api/') or path == '/api' or '/api/' in path:
        return True
    for prefix in _get_analytics_skip_path_prefixes():
        if path.startswith(prefix):
            return True
    return False


class AnalyticsMiddleware(MiddlewareMixin):
    """
    Middleware to track user activities asynchronously using Celery.
    Captures page views, sessions, referrers, and UTM parameters.
    """
    
    @staticmethod
    def _normalize_path(path):
        if not path:
            return '/'
        if path != '/' and path.endswith('/'):
            return path[:-1]
        return path

    @staticmethod
    def _is_private_or_local_host(host):
        h = (host or '').strip().lower()
        if not h:
            return False
        if h in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
            return True
        if h.startswith('localhost:') or h.startswith('127.0.0.1:') or h.startswith('0.0.0.0:'):
            return True
        if h.startswith('192.168.') or h.startswith('10.'):
            return True
        if h.startswith('172.'):
            # best-effort private range check for 172.16-31.*
            try:
                second = int(h.split('.')[1])
                if 16 <= second <= 31:
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _is_internal_host(host):
        h = (host or '').strip().lower()
        return ('topteen.in' in h) or AnalyticsMiddleware._is_private_or_local_host(h)

    def _acquisition_signature(self, request, path):
        """
        Build a stable acquisition signature to decide when to start a new analytics session.
        New session starts when signature changes for:
        - ref token
        - utm params
        - external referrer (non topteen / non local)
        - direct login entry
        """
        ref_token = (request.GET.get('ref') or '').strip()
        if ref_token:
            return 'ref:%s' % ref_token

        utm_items = []
        for key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'):
            val = (request.GET.get(key) or '').strip()
            if val:
                utm_items.append('%s=%s' % (key, val))
        if utm_items:
            return 'utm:' + '&'.join(utm_items)

        referrer = (request.META.get('HTTP_REFERER') or '').strip()
        ref_host = ''
        if referrer:
            try:
                ref_host = (urlparse(referrer).hostname or '').strip().lower()
            except Exception:
                ref_host = ''
        if ref_host and not self._is_internal_host(ref_host):
            return 'external_ref:%s' % ref_host

        # Explicitly treat direct login landings as a fresh session boundary.
        if not referrer and any(path.startswith(p) for p in DIRECT_LOGIN_PATH_PREFIXES):
            return 'direct_login'
        return ''

    def _ensure_session_for_request(self, request, path):
        """
        Ensure analytics_session_id exists, and rotate when a new acquisition signal arrives.
        """
        current_sid = request.session.get('analytics_session_id')
        previous_sig = request.session.get('analytics_acquisition_sig') or ''
        current_sig = self._acquisition_signature(request, path)

        rotate = False
        if not current_sid:
            rotate = True
        elif current_sig and current_sig != previous_sig:
            rotate = True

        if rotate:
            request.session['analytics_session_id'] = str(uuid.uuid4())
            request.session['analytics_acquisition_sig'] = current_sig
        elif current_sig and not previous_sig:
            # Keep existing session but persist discovered signature for consistency.
            request.session['analytics_acquisition_sig'] = current_sig

    def _is_recent_duplicate_page_hit(self, request):
        """
        Prevent multiple rows on rapid refresh/reload for same session+path+device.
        """
        try:
            from datetime import timedelta
            from user_analytics.models import UserActivity
            from user_analytics.utils import parse_user_agent_info

            a = request.analytics_data
            session_id = a.get('session_id')
            if not session_id:
                return False

            norm_path = self._normalize_path(a.get('path') or '/')
            device_type = parse_user_agent_info(a.get('user_agent') or '').get('device_type')
            cutoff = timezone.now() - timedelta(seconds=DEDUP_WINDOW_SECONDS)

            qs = UserActivity.objects.filter(
                session_id=session_id,
                created__gte=cutoff,
                page_path__in=[norm_path, (a.get('path') or '/')],
            )
            if device_type:
                qs = qs.filter(device_type=device_type)
            if a.get('user_id'):
                qs = qs.filter(user_id=a['user_id'])
            return qs.exists()
        except Exception:
            return False

    def process_request(self, request):
        """Process request and extract analytics data"""
        from django.conf import settings
        if not getattr(settings, 'ENABLE_USER_ANALYTICS_TRACKING', True):
            return None
        # Skip tracking for admin, staff dashboards, notifications, static/media, all API traffic, etc.
        path = request.path
        if _should_skip_analytics_path(path):
            return None
        
        # Generate/get session ID, rotating for new acquisition signals.
        self._ensure_session_for_request(request, path)
        
        # Extract GA4 client ID from cookies
        ga4_client_id = self.extract_ga4_client_id(request)
        if ga4_client_id:
            # Store in session for linking
            request.session['ga4_client_id'] = ga4_client_id
        
        # Non-readable enquiry link: ?ref=TOKEN (no utm_* in URL – admin identifies source by name in dashboard)
        ref_token = request.GET.get('ref', '').strip()
        enquiry_source_id = None
        if ref_token:
            try:
                from user_analytics.models import EnquirySource
                from core import choices
                # Only active, non–soft-deleted sources; exact token match
                es = EnquirySource.objects.filter(
                    token=ref_token,
                    is_active=True,
                    object_status=choices.ObjectStatus.ACTIVE,
                ).first()
                if es:
                    enquiry_source_id = es.id
                    # Persist enquiry source in session for the current browser session.
                    request.session['enquiry_source_id'] = es.id
                    request.session['enquiry_ref_token'] = es.token
                    logger.debug("Enquiry ref=%s -> source id=%s", ref_token[:8], enquiry_source_id)
                else:
                    logger.debug("Enquiry ref=%s -> no matching active source", ref_token[:8])
            except Exception as e:
                logger.warning("Enquiry source lookup failed for ref=%s: %s", ref_token[:8], e)
        else:
            # Fallback: keep attributing page hits to source stored in session.
            session_enquiry_source_id = request.session.get('enquiry_source_id')
            if session_enquiry_source_id:
                try:
                    from user_analytics.models import EnquirySource
                    from core import choices
                    es = EnquirySource.objects.filter(
                        id=session_enquiry_source_id,
                        is_active=True,
                        object_status=choices.ObjectStatus.ACTIVE,
                    ).first()
                    if es:
                        enquiry_source_id = es.id
                    else:
                        request.session.pop('enquiry_source_id', None)
                        request.session.pop('enquiry_ref_token', None)
                except Exception:
                    pass

        # Store analytics data in request for async processing
        page_url = request.build_absolute_uri(path) if path else ''
        request.analytics_data = {
            'session_id': request.session.get('analytics_session_id'),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ga4_client_id': ga4_client_id,
            'path': self._normalize_path(path),
            'page_url': page_url,
            'referrer': request.META.get('HTTP_REFERER', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self.get_client_ip(request),
            'utm_source': request.GET.get('utm_source', ''),
            'utm_medium': request.GET.get('utm_medium', ''),
            'utm_campaign': request.GET.get('utm_campaign', ''),
            'utm_term': request.GET.get('utm_term', ''),
            'utm_content': request.GET.get('utm_content', ''),
            'enquiry_source_id': enquiry_source_id,
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
        # Track GET requests that either return 200, or had ?ref= (enquiry link) even on redirect (3xx)
        # so that "link was hit" is counted when the server responds with redirect (e.g. login, trailing slash)
        if not (hasattr(request, 'analytics_data') and request.method == 'GET'):
            return response
        status = response.status_code
        allow_track = status == 200 or (
            status in (301, 302, 303, 307, 308) and request.analytics_data.get('enquiry_source_id')
        )
        if not allow_track:
            return response
        if self._is_recent_duplicate_page_hit(request):
            return response

        try:
            session_id = request.analytics_data.get('session_id')
            if request.user.is_authenticated and session_id:
                link_analytics_session_to_user(session_id, request.user)
                reconcile_recent_user_events(request.user, session_id)

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
                enquiry_source_id = request.analytics_data.get('enquiry_source_id')
                if enquiry_source_id:
                    logger.warning(
                        "Enquiry tracking: recording visit for source_id=%s path=%s (response %s)",
                        enquiry_source_id, request.analytics_data['path'], response.status_code,
                    )
                track_page_view_sync(
                    session_id=request.analytics_data['session_id'],
                    user_id=request.analytics_data['user_id'],
                    ga4_client_id=request.analytics_data.get('ga4_client_id'),
                    page_path=request.analytics_data['path'],
                    page_url=request.analytics_data.get('page_url'),
                    page_title=page_title,
                    referrer=request.analytics_data['referrer'],
                    user_agent=request.analytics_data['user_agent'],
                    ip_address=request.analytics_data['ip_address'],
                    utm_source=request.analytics_data['utm_source'],
                    utm_medium=request.analytics_data['utm_medium'],
                    utm_campaign=request.analytics_data['utm_campaign'],
                    utm_term=request.analytics_data['utm_term'],
                    utm_content=request.analytics_data['utm_content'],
                    enquiry_source_id=enquiry_source_id,
                )
                
                # Get device and country from user agent
                device_type = None
                country = None
                if request.analytics_data.get('user_agent'):
                    from user_analytics.utils import parse_user_agent_info
                    ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                    device_type = ua_info.get('device_type')
                
                # Get country from UserActivity (just saved by track_page_view_sync or previous page views)
                try:
                    from user_analytics.models import UserActivity
                    recent_activity = UserActivity.objects.filter(
                        session_id=request.analytics_data['session_id']
                    ).order_by('-created').first()
                    if recent_activity and recent_activity.country:
                        country = recent_activity.country
                    if recent_activity and recent_activity.traffic_source_category:
                        traffic_category = recent_activity.traffic_source_category
                    else:
                        from user_analytics.utils import get_referrer_source, get_traffic_source_category
                        src = request.analytics_data.get('utm_source') or get_referrer_source(request.analytics_data.get('referrer') or '')
                        traffic_category = get_traffic_source_category(request.analytics_data.get('utm_source') or src, request.analytics_data.get('referrer') or '')
                except Exception:
                    traffic_category = None
                
                update_user_journey_sync(
                    session_id=request.analytics_data['session_id'],
                    user_id=request.analytics_data['user_id'],
                    ga4_client_id=request.analytics_data.get('ga4_client_id'),
                    page_path=request.analytics_data['path'],
                    referrer=request.analytics_data['referrer'],
                    device_type=device_type,
                    country=country,
                    utm_source=request.analytics_data.get('utm_source'),
                    traffic_source_category=traffic_category,
                    enquiry_source_id=request.analytics_data.get('enquiry_source_id'),
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
                        page_url=request.analytics_data.get('page_url'),
                        page_title=page_title,
                        referrer=request.analytics_data['referrer'],
                        user_agent=request.analytics_data['user_agent'],
                        ip_address=request.analytics_data['ip_address'],
                        utm_source=request.analytics_data['utm_source'],
                        utm_medium=request.analytics_data['utm_medium'],
                        utm_campaign=request.analytics_data['utm_campaign'],
                        utm_term=request.analytics_data['utm_term'],
                        utm_content=request.analytics_data['utm_content'],
                        enquiry_source_id=request.analytics_data.get('enquiry_source_id'),
                    )
                    
                    # Get device and country from user agent / latest activity
                    device_type = None
                    country = None
                    traffic_category = None
                    if request.analytics_data.get('user_agent'):
                        from user_analytics.utils import parse_user_agent_info
                        ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                        device_type = ua_info.get('device_type')
                    try:
                        from user_analytics.models import UserActivity
                        from user_analytics.utils import get_referrer_source, get_traffic_source_category
                        recent_activity = UserActivity.objects.filter(
                            session_id=request.analytics_data['session_id']
                        ).order_by('-created').first()
                        if recent_activity:
                            if recent_activity.country:
                                country = recent_activity.country
                            if recent_activity.traffic_source_category:
                                traffic_category = recent_activity.traffic_source_category
                        if traffic_category is None:
                            src = request.analytics_data.get('utm_source') or get_referrer_source(request.analytics_data.get('referrer') or '')
                            traffic_category = get_traffic_source_category(request.analytics_data.get('utm_source') or src, request.analytics_data.get('referrer') or '')
                    except Exception:
                        pass
                    
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
                        traffic_source_category=traffic_category,
                        enquiry_source_id=request.analytics_data.get('enquiry_source_id'),
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
                        page_url=request.analytics_data.get('page_url'),
                        page_title=page_title,
                        referrer=request.analytics_data['referrer'],
                        user_agent=request.analytics_data['user_agent'],
                        ip_address=request.analytics_data['ip_address'],
                        utm_source=request.analytics_data['utm_source'],
                        utm_medium=request.analytics_data['utm_medium'],
                        utm_campaign=request.analytics_data['utm_campaign'],
                        utm_term=request.analytics_data['utm_term'],
                        utm_content=request.analytics_data['utm_content'],
                        enquiry_source_id=request.analytics_data.get('enquiry_source_id'),
                    )
                    
                    # Get device and country from user agent / latest activity
                    device_type = None
                    country = None
                    traffic_category = None
                    if request.analytics_data.get('user_agent'):
                        from user_analytics.utils import parse_user_agent_info
                        ua_info = parse_user_agent_info(request.analytics_data['user_agent'])
                        device_type = ua_info.get('device_type')
                    try:
                        from user_analytics.models import UserActivity
                        from user_analytics.utils import get_referrer_source, get_traffic_source_category
                        recent_activity = UserActivity.objects.filter(
                            session_id=request.analytics_data['session_id']
                        ).order_by('-created').first()
                        if recent_activity:
                            if recent_activity.country:
                                country = recent_activity.country
                            if recent_activity.traffic_source_category:
                                traffic_category = recent_activity.traffic_source_category
                        if traffic_category is None:
                            src = request.analytics_data.get('utm_source') or get_referrer_source(request.analytics_data.get('referrer') or '')
                            traffic_category = get_traffic_source_category(request.analytics_data.get('utm_source') or src, request.analytics_data.get('referrer') or '')
                    except Exception:
                        pass
                    
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
                        traffic_source_category=traffic_category,
                        enquiry_source_id=request.analytics_data.get('enquiry_source_id'),
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
