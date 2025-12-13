"""
Analytics Middleware for tracking user activities asynchronously.
This middleware captures page views, sessions, and referrer information
without blocking the request/response cycle.
"""
import uuid
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from user_analytics.tasks import track_page_view_async, update_user_journey_async


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
        
        # Store analytics data in request for async processing
        request.analytics_data = {
            'session_id': request.session.get('analytics_session_id'),
            'user_id': request.user.id if request.user.is_authenticated else None,
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
    
    def process_response(self, request, response):
        """Process response and trigger async tracking"""
        # Only track successful GET requests
        if hasattr(request, 'analytics_data') and request.method == 'GET' and response.status_code == 200:
            # Get page title from response if available
            page_title = getattr(response, 'page_title', '')
            
            # Trigger async task for page view tracking
            track_page_view_async.delay(
                session_id=request.analytics_data['session_id'],
                user_id=request.analytics_data['user_id'],
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
            
            # Update user journey asynchronously
            update_user_journey_async.delay(
                session_id=request.analytics_data['session_id'],
                user_id=request.analytics_data['user_id'],
                page_path=request.analytics_data['path'],
                referrer=request.analytics_data['referrer'],
            )
        
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

