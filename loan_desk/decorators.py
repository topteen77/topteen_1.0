"""Access helpers for Loan Desk (Manager / Executive)."""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from core import choices


def is_loan_desk_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    ut = getattr(user, "user_type", None)
    if ut not in choices.UserType.LOAN_DESK_TYPES:
        return False
    try:
        # get_user_status() returns True when UNBLOCK
        return bool(user.get_user_status())
    except Exception:
        return getattr(user, "user_status", None) == choices.UserStatus.UNBLOCK


def is_loan_manager(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "user_type", None) == choices.UserType.LOAN_MANAGER


def loan_desk_user_only(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=reverse("loan_desk:login"))
        if not is_loan_desk_user(request.user):
            return HttpResponseForbidden("Loan Desk access required.")
        return view_func(request, *args, **kwargs)

    return _wrapped
