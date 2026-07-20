"""
Convert login redirects to JSON 401 for AJAX requests.

Without this, fetch() follows redirects to /user/login/ and injects sign_in.html
into v2 dashboard hosts (#ttv2AjaxContent, student table wrappers).
"""

from core.ajax_auth import (
    ajax_session_expired_response,
    location_is_login_redirect,
    request_is_ajax,
)


class AjaxAuthRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request_is_ajax(request):
            return response
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        location = response.get("Location") or ""
        if not location_is_login_redirect(location):
            return response
        return ajax_session_expired_response(request)
