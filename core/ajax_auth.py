"""Helpers for AJAX/XHR auth failures (v2 dashboards, student tables, etc.)."""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse


def request_is_ajax(request) -> bool:
    return (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest"


def ajax_session_expired_response(request, *, message: str | None = None):
    """Return a JSON 401 instead of redirecting AJAX callers to the login page HTML."""
    login_path = settings.LOGIN_URL
    try:
        if (request.path or "").lower().startswith("/student/"):
            login_path = reverse("student_login")
        elif (request.path or "").lower().startswith("/parents/"):
            login_path = reverse("parents_login")
    except Exception:
        pass

    return JsonResponse(
        {
            "success": False,
            "message": message or "Your session has expired. Please sign in again.",
            "redirect": login_path,
            "session_expired": True,
        },
        status=401,
    )


def location_is_login_redirect(location: str) -> bool:
    if not location:
        return False
    loc = location.lower()
    markers = (
        "/user/login",
        "/student/login",
        "/parents/login",
        "/institute/auth/login",
        "/counselor/auth/login",
        "/accounts/login",
    )
    return any(m in loc for m in markers)
