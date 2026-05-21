"""Decorators for users app views."""
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy

from core import choices


def institute_dashboard_roles_only(view_func):
    """
    Logged-in marketing group admin, institute group admin, or institute user only.
    Used for self-service account actions (e.g. change own password).
    """
    allowed = (
        choices.UserType.MARKETINGGROUPADMIN,
        choices.UserType.INSTITUTEGROUPADMIN,
        choices.UserType.INSTITUTE,
    )

    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse_lazy("users:login"))
        if request.user.is_superuser or request.user.user_type in allowed:
            return view_func(request, *args, **kwargs)
        return HttpResponseRedirect("/")

    return wrap
