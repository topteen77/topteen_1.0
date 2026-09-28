"""Template context processors for users app."""
from core import choices


def student_scrapbook_hub(request):
    """Sidebar scrapbook badge + highlights on all authenticated student pages."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if getattr(request.user, "user_type", None) != choices.UserType.STUDENT:
        return {}
    ctx = {}
    try:
        from users.parent_suggestions import apply_scrapbook_parent_updates_context

        apply_scrapbook_parent_updates_context(ctx, request.user)
    except Exception:
        ctx.update(
            {
                "hub_scrapbook_unread_count": 0,
                "scrapbook_parent_unread": {},
                "scrapbook_has_parent_updates": False,
            }
        )
    # Individual / custom package students (e.g. Class 12 Personality only) are often
    # 12th-pass and not current school students — hide class in the sidebar.
    try:
        from core.assessment_access import get_student_custom_package_names, packages_enabled

        custom_names = get_student_custom_package_names(request.user) if packages_enabled() else []
        ctx["psychometric_custom_package_names"] = custom_names
        ctx["hide_student_sidebar_class"] = bool(custom_names)
    except Exception:
        ctx.setdefault("hide_student_sidebar_class", False)
        ctx.setdefault("psychometric_custom_package_names", [])
    return ctx
