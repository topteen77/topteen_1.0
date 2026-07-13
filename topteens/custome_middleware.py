from topteenadmin.utils import check_permissions
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings
from social_django.middleware import SocialAuthExceptionMiddleware
from django.shortcuts import HttpResponse
from social_core.exceptions import SocialAuthBaseException
from urllib.parse import quote
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.api import MessageFailure
from social_core.utils import social_logger


class SlideSessionForAuthenticatedMiddleware:
    """
    When SESSION_SAVE_EVERY_REQUEST=False, still refresh session expiry for
    logged-in users on each request (keeps them signed in while browsing).

    Anonymous traffic (homepage Locust, guests) does not force a session write
    unless something actually changed the session (login, analytics, CSRF flow).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        if user is not None and getattr(user, "is_authenticated", False) and session is not None:
            session.modified = True
        return response


class TopteenAdminPermissionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user and request.user.is_authenticated:
            if request.path.startswith('/topteenadmin/managed/'):
                path=request.path.replace('/topteenadmin/managed/','')
                has_perm=check_permissions(request.user,path)
                if has_perm ==False:
                    raise PermissionDenied()
        response = self.get_response(request)
        return response
    

NONE_AUTH_ACCOUNT_PATHS = [
    settings.STATIC_URL,
    reverse('topteenadmin:login'),
    reverse('topteenadmin:forgotpassword'),
    reverse('topteenadmin:changepassword',kwargs={'uidb64':'uid','token':'token'}).replace('/uid/token',''),
    #we just need the starting url to match, for eg. account/password-reset-confirm, so later part replaced with blank string
]

class TopteenAdminRequireLoginCheck(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
    
    def _is_none_auth_path(self, path):
        for none_auth_path in NONE_AUTH_ACCOUNT_PATHS:
            if path.startswith(none_auth_path):
                return True
        return False

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated and (request.path.startswith('/topteenadmin/managed/') or (request.path.startswith('/topteenadmin/') and not self._is_none_auth_path(request.path))):
            return redirect('%s?next=%s' % (reverse('topteenadmin:login'), request.path))
        return None
    
class CustomeSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        strategy = getattr(request, "social_strategy", None)
        if strategy is not None:
            return strategy.setting("RAISE_EXCEPTIONS", settings.DEBUG)