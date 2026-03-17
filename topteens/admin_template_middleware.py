"""
Middleware to force Django templates for admin URLs.
This ensures admin uses Django templates while frontend uses Jinja2.
"""
import json
from django.template import engines
from django.template.loader import get_template

# #region agent log
_DEBUG_LOG = "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/.cursor/debug-b428b8.log"
def _agent_log(msg, data, hypothesis_id):
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write(json.dumps({"sessionId": "b428b8", "message": msg, "data": data, "hypothesisId": hypothesis_id, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass
# #endregion


class AdminTemplateMiddleware:
    """
    Middleware that temporarily removes Jinja2 from template engines for admin URLs.
    This forces Django templates to be used for admin while keeping Jinja2 for frontend.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # #region agent log
        is_admin = request.path.startswith('/admin/')
        is_topteenadmin = request.path.startswith('/topteenadmin/')
        _agent_log("AdminTemplateMiddleware request", {"path": request.path, "forces_django": is_admin, "is_topteenadmin": is_topteenadmin}, "H1")
        # #endregion
        # Check if this is an admin URL
        if is_admin:
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
        response = self.get_response(request)
        # #region agent log
        if request.path.startswith('/topteenadmin/'):
            try:
                base_tpl = get_template('topteenadmin/base.html')
                origin_path = getattr(getattr(base_tpl, 'origin', None), 'name', None) or str(getattr(base_tpl, 'origin', ''))
                _agent_log("topteenadmin base template resolved", {"path": request.path, "base_origin": origin_path}, "H2")
            except Exception as e:
                _agent_log("topteenadmin base template resolve error", {"path": request.path, "error": str(e)}, "H2")
        # #endregion
        return response

