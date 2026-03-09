"""
Redirect requests without trailing slash to the same path with trailing slash
when that path would resolve. Ensures /about-us works by redirecting to /about-us/
instead of matching the catch-all 404.

Django's APPEND_SLASH only runs when the original URL does NOT match any pattern.
This project's catch-all 404 pattern matches /about-us, so APPEND_SLASH never runs.
This middleware runs in __call__ (before the view) and redirects when path + '/' would resolve.
"""
from django.http import HttpResponseRedirect
from django.urls import resolve, Resolver404
from django.conf import settings


class AppendSlashRedirectMiddleware:
    """
    If request path has no trailing slash and path + '/' resolves, redirect to path + '/'.
    Skips paths that contain '.' (file-like) and paths under STATIC_URL or MEDIA_URL.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redirect_url = self._should_redirect_to_slash(request)
        if redirect_url is not None:
            return HttpResponseRedirect(redirect_url, status=301)
        return self.get_response(request)

    def _should_redirect_to_slash(self, request):
        """Return redirect URL (path + query string) if request should be redirected to path/, else None."""
        if request.method not in ("GET", "HEAD"):
            return None
        path = request.path
        if not path or path.endswith("/"):
            return None
        last_segment = path.split("/")[-1]
        if "." in last_segment:
            return None
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if path.startswith(static_url) or path.startswith(media_url):
            return None
        try:
            resolve(path + "/")
        except Resolver404:
            return None
        redirect_path = path + "/"
        if request.GET:
            redirect_path += "?" + request.GET.urlencode()
        return redirect_path
