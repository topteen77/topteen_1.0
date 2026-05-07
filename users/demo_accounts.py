"""
Shared helper for demo accounts shown on login pages.
Uses DB only: users/institutes marked as demo in admin. No .env credentials.
Clicking "Login as" POSTs a signed token to demo-login; server logs in and redirects.
"""
from django.core.signing import Signer
from django.urls import reverse
from django.middleware.csrf import get_token

from core import choices
from .models import User


def get_demo_accounts_list(user_types=None):
    """
    Return list of demo account dicts for template: token, name, role_label.
    From DB only (is_demo_account=True).
    """
    qs = User.objects.filter(is_demo_account=True, is_active=True).select_related("user_profile")
    if user_types is not None:
        types = list(user_types) if isinstance(user_types, (list, tuple)) else [user_types]
        qs = qs.filter(user_type__in=types)
    demo_users = qs.order_by('user_type', 'name')
    signer = Signer()
    out = []
    role_map = dict(choices.UserType.CHOICES)
    for u in demo_users:
        role_label = role_map.get(u.user_type, "User")
        student_class = ""
        if u.user_type == choices.UserType.STUDENT:
            try:
                student_class = (getattr(getattr(u, "user_profile", None), "grade", None) or "").strip()
            except Exception:
                student_class = ""
            if not student_class:
                # Fallback to school "Class & Section" if profile grade isn't set.
                try:
                    sm = u.student_management.last()
                    student_class = (getattr(sm, "class_and_section", None) or "").strip()
                    # normalize "10 A" -> "10"
                    if student_class and " " in student_class:
                        student_class = student_class.split()[0].strip()
                except Exception:
                    student_class = ""
        out.append(
            {
                "token": signer.sign_object({"demo_user_id": u.pk}),
                "name": u.name or u.email or str(u.pk),
                "role_label": role_label,
                "student_class": student_class,
            }
        )
    return out


def get_demo_login_context(request, user_types=None):
    """
    Return context for demo login section: demo_accounts, demo_login_url, demo_csrf_token.
    No password or email from env; login via token POST to demo-login.
    """
    return {
        'demo_accounts': get_demo_accounts_list(user_types=user_types),
        'demo_login_url': request.build_absolute_uri(reverse('users:demo_login')),
        'demo_csrf_token': get_token(request),
    }


def get_demo_institute_login_context(request):
    """
    Return context for institute login: demo cards from institutes with is_demo_institute=True (DB only).
    """
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
