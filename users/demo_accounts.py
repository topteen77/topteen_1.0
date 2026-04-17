"""
Shared helper for demo accounts shown on login pages.
Uses DB only: users/institutes marked as demo in admin. No .env credentials.
Clicking "Login as" POSTs a signed token to demo-login; server logs in and redirects.
"""
from django.conf import settings
from django.core.signing import Signer
from django.urls import reverse
from django.middleware.csrf import get_token

from core import choices
from .models import User

# Core → Configuration (admin: Demo account visibility). Values: true/false.
CONFIG_SHOW_DEMO_PRODUCTION = "SHOW_DEMO_ACCOUNT_ON_PRODUCTION"
CONFIG_SHOW_DEMO_DEVELOPMENT = "SHOW_DEMO_ACCOUNT_ON_DEVELOPMENT"


def _config_bool_true(val):
    return str(val or "").strip().lower() in ("true", "1", "yes", "on")


def is_demo_login_ui_enabled():
    """
    Whether login pages may show demo account cards and demo-login POST is allowed.
    Uses Django DEBUG: development when DEBUG is True, production when False.
    """
    try:
        from core.models import Configuration

        if getattr(settings, "DEBUG", False):
            return _config_bool_true(
                Configuration.get(CONFIG_SHOW_DEMO_DEVELOPMENT, default="true", editable=True)
            )
        return _config_bool_true(
            Configuration.get(CONFIG_SHOW_DEMO_PRODUCTION, default="false", editable=True)
        )
    except Exception:
        return bool(getattr(settings, "DEBUG", False))


def get_demo_accounts_list(user_types=None):
    """
    Return list of demo account dicts for template: token, name, role_label.
    From DB only (is_demo_account=True).
    """
    qs = User.objects.filter(is_demo_account=True, is_active=True)
    if user_types is not None:
        types = list(user_types) if isinstance(user_types, (list, tuple)) else [user_types]
        qs = qs.filter(user_type__in=types)
    demo_users = qs.order_by('user_type', 'name')
    signer = Signer()
    return [
        {
            'token': signer.sign_object({'demo_user_id': u.pk}),
            'name': u.name or u.email or str(u.pk),
            'role_label': dict(choices.UserType.CHOICES).get(u.user_type, 'User'),
        }
        for u in demo_users
    ]


def get_demo_login_context(request, user_types=None):
    """
    Return context for demo login section: demo_accounts, demo_login_url, demo_csrf_token.
    No password or email from env; login via token POST to demo-login.
    """
    if not is_demo_login_ui_enabled():
        return {
            "demo_accounts": [],
            "demo_login_url": request.build_absolute_uri(reverse("users:demo_login")),
            "demo_csrf_token": get_token(request),
        }
    return {
        'demo_accounts': get_demo_accounts_list(user_types=user_types),
        'demo_login_url': request.build_absolute_uri(reverse('users:demo_login')),
        'demo_csrf_token': get_token(request),
    }


def get_demo_institute_login_context(request):
    """
    Return context for institute login: demo cards from institutes with is_demo_institute=True (DB only).
    """
    if not is_demo_login_ui_enabled():
        return {
            "demo_accounts": [],
            "demo_login_url": request.build_absolute_uri(reverse("institute:demo_login")),
            "demo_csrf_token": get_token(request),
        }
    from institute.models import Institute

    signer = Signer()
    demo_accounts = []
    for inst in Institute.objects.filter(is_demo_institute=True).select_related('created_by').order_by('name'):
        user = inst.created_by
        if user and user.is_active:
            demo_accounts.append({
                'token': signer.sign_object({'demo_user_id': user.pk}),
                'name': inst.name or (user.name or user.email or str(user.pk)),
                'role_label': 'Institute',
            })
    return {
        'demo_accounts': demo_accounts,
        'demo_login_url': request.build_absolute_uri(reverse('institute:demo_login')),
        'demo_csrf_token': get_token(request),
    }
