from django.conf import settings


REMEMBER_ME_SESSION_AGE = getattr(settings, "REMEMBER_ME_SESSION_AGE", 2592000)  # 30 days
DEFAULT_LOGIN_SESSION_AGE = getattr(settings, "DEFAULT_LOGIN_SESSION_AGE", 1209600)  # 14 days
DEMO_LOGIN_SESSION_AGE = getattr(settings, "DEMO_LOGIN_SESSION_AGE", 0)  # browser session


def _is_truthy(value):
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def apply_login_session_expiry(request, remember_me=False, demo=False):
    """
    Keep users signed in across tabs and mobile browser backgrounding.

    Without remember_me we use DEFAULT_LOGIN_SESSION_AGE (not browser-session expiry),
    because set_expiry(0) is cleared aggressively on mobile Safari/Chrome.
    """
    if demo:
        request.session.set_expiry(DEMO_LOGIN_SESSION_AGE)
    elif _is_truthy(remember_me):
        request.session.set_expiry(REMEMBER_ME_SESSION_AGE)
    else:
        request.session.set_expiry(DEFAULT_LOGIN_SESSION_AGE)
