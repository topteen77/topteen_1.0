"""Template context processors for users app."""
from core import choices


def student_scrapbook_hub(request):
    """Sidebar scrapbook badge + highlights on all authenticated student pages."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if getattr(request.user, "user_type", None) != choices.UserType.STUDENT:
        return {}
    try:
        from users.parent_suggestions import apply_scrapbook_parent_updates_context

        ctx = {}
        apply_scrapbook_parent_updates_context(ctx, request.user)
        return ctx
    except Exception:
        return {
            "hub_scrapbook_unread_count": 0,
            "scrapbook_parent_unread": {},
            "scrapbook_has_parent_updates": False,
        }
