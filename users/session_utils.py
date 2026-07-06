from django.conf import settings


REMEMBER_ME_SESSION_AGE = getattr(settings, "REMEMBER_ME_SESSION_AGE", 2592000)  # 30 days
DEFAULT_LOGIN_SESSION_AGE = getattr(settings, "DEFAULT_LOGIN_SESSION_AGE", 604800)  # 7 days
DEMO_LOGIN_SESSION_AGE = getattr(settings, "DEMO_LOGIN_SESSION_AGE", DEFAULT_LOGIN_SESSION_AGE)
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
    Demo and normal logins use the same default duration (1 week) unless remember-me is checked.
    """
    if _is_truthy(remember_me):
        request.session.set_expiry(REMEMBER_ME_SESSION_AGE)
    else:
        request.session.set_expiry(DEFAULT_LOGIN_SESSION_AGE)
    request.session.modified = True


def login_user_with_session(request, user, remember_me=False, demo=False, backend=None):
    """Log in and apply persistent session expiry in the correct order."""
    from django.contrib.auth import login

    # Flags are read by user_logged_in (social/admin logins) and cleared after login().
    if demo:
        request.session["_pending_demo_login"] = True
    elif _is_truthy(remember_me):
        request.session["_pending_remember_me"] = True

    login(request, user, backend=backend or DEFAULT_LOGIN_BACKEND)

    remember_me = _is_truthy(remember_me) or bool(
        request.session.pop("_pending_remember_me", False)
    )
    demo = demo or bool(request.session.pop("_pending_demo_login", False))
    apply_login_session_expiry(request, remember_me=remember_me, demo=demo)
    request.session["fresh_login"] = True
    request.session.modified = True
    try:
        request.session.save()
    except Exception:
        pass
    return user


def session_settings_summary():
    """Human-readable session config for debugging/support."""
    age = getattr(settings, "SESSION_COOKIE_AGE", 0) or 0
    return {
        "session_engine": getattr(settings, "SESSION_ENGINE", ""),
        "session_cache_alias": getattr(settings, "SESSION_CACHE_ALIAS", ""),
        "session_use_signed_cookies": getattr(settings, "SESSION_USE_SIGNED_COOKIES", False),
        "session_cookie_age_seconds": age,
        "session_cookie_age_days": round(age / 86400, 2) if age else 0,
        "default_login_session_age_seconds": DEFAULT_LOGIN_SESSION_AGE,
        "remember_me_session_age_seconds": REMEMBER_ME_SESSION_AGE,
        "session_save_every_request": getattr(settings, "SESSION_SAVE_EVERY_REQUEST", False),
        "session_expire_at_browser_close": getattr(settings, "SESSION_EXPIRE_AT_BROWSER_CLOSE", False),
        "session_cookie_secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
        "session_cookie_samesite": getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
        "session_cookie_domain": getattr(settings, "SESSION_COOKIE_DOMAIN", None),
        "session_cookie_name": getattr(settings, "SESSION_COOKIE_NAME", "sessionid"),
        "use_https": getattr(settings, "USE_HTTPS", False),
    }
