"""Registration welcome bonus popup (shown once on first dashboard visit after signup)."""

from core import choices


def set_registration_welcome_popup(request, user):
    """Show gamification welcome popup on the student's first dashboard visit after signup."""
    try:
        if user and getattr(user, "user_type", None) == choices.UserType.STUDENT:
            request.session["show_registration_welcome_popup"] = True
            request.session.modified = True
    except Exception:
        pass


def set_social_registration_welcome_popup(
    strategy, details, backend, user=None, is_new=False, *args, **kwargs
):
    """Social auth pipeline step: welcome popup for new Google/Facebook student signups."""
    if is_new and user:
        set_registration_welcome_popup(strategy.request, user)
    return None
