from django.conf import settings


REMEMBER_ME_SESSION_AGE = getattr(settings, "REMEMBER_ME_SESSION_AGE", 2592000)  # 30 days
DEFAULT_LOGIN_SESSION_AGE = getattr(settings, "DEFAULT_LOGIN_SESSION_AGE", 1209600)  # 14 days
DEMO_LOGIN_SESSION_AGE = getattr(settings, "DEMO_LOGIN_SESSION_AGE", 0)  # browser session
DEFAULT_LOGIN_BACKEND = "users.backends.CustomUserBackend"


def _is_truthy(value):
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def apply_login_session_expiry(request, remember_me=False, demo=False):
    """
    Set how long the session cookie should last.

    Call after django.contrib.auth.login() so session cycle_key does not drop custom expiry.
    """
    if demo:
        request.session.set_expiry(DEMO_LOGIN_SESSION_AGE)
    elif _is_truthy(remember_me):
        request.session.set_expiry(REMEMBER_ME_SESSION_AGE)
    else:
        request.session.set_expiry(DEFAULT_LOGIN_SESSION_AGE)
    request.session.modified = True


def login_user_with_session(request, user, remember_me=False, demo=False, backend=None):
    """Log in and apply persistent session expiry in the correct order."""
    from django.contrib.auth import login

    login(request, user, backend=backend or DEFAULT_LOGIN_BACKEND)
    apply_login_session_expiry(request, remember_me=remember_me, demo=demo)
    return user


def session_settings_summary():
    """Human-readable session config for debugging/support."""
    age = getattr(settings, "SESSION_COOKIE_AGE", 0) or 0
    return {
        "session_cookie_age_seconds": age,
        "session_cookie_age_days": round(age / 86400, 2) if age else 0,
        "default_login_session_age_seconds": DEFAULT_LOGIN_SESSION_AGE,
        "remember_me_session_age_seconds": REMEMBER_ME_SESSION_AGE,
        "session_save_every_request": getattr(settings, "SESSION_SAVE_EVERY_REQUEST", False),
        "session_expire_at_browser_close": getattr(settings, "SESSION_EXPIRE_AT_BROWSER_CLOSE", False),
        "session_cookie_secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
        "session_cookie_samesite": getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
        "use_https": getattr(settings, "USE_HTTPS", False),
    }
