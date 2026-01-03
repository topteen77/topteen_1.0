"""
Middleware to force Django templates for admin URLs.
This ensures admin uses Django templates while frontend uses Jinja2.
"""
from django.template import engines


class AdminTemplateMiddleware:
    """
    Middleware that temporarily removes Jinja2 from template engines for admin URLs.
    This forces Django templates to be used for admin while keeping Jinja2 for frontend.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is an admin URL
        if request.path.startswith('/admin/'):
            # Store original engines
            original_engines = engines._engines.copy()
            try:
                # Remove Jinja2 from available engines for this request
                # This forces Django to use Django templates
                django_engine = engines['django']
                engines._engines = {'django': django_engine}
                response = self.get_response(request)
            finally:
                # Restore original engines after request
                engines._engines = original_engines
            return response
        
        # For non-admin URLs, use normal template resolution
        return self.get_response(request)

