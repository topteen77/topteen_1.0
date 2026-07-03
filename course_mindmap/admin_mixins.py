"""Admin mixins for course mindmap."""

from __future__ import annotations

from django.contrib import admin, messages

from course_mindmap.registry import get_adapter
from course_mindmap.service import delete_complete_course_mindmap, delete_complete_for_queryset


def _course_label(content_type, object_id: int, course_type_key: str = "") -> str:
    try:
        if course_type_key:
            adapter = get_adapter(course_type_key)
            course = adapter.get_course_by_id(object_id)
            if course:
                return adapter.get_course_display_name(course)
    except Exception:
        pass
    return f"course #{object_id}"


class CompleteMindmapDeleteMixin:
    """
    Deleting any mindmap record removes the full package for that course:
    data, configuration, and generation logs.
    """

    delete_confirmation_template = "admin/course_mindmap/delete_complete_confirmation.html"
    delete_selected_confirmation_template = "admin/course_mindmap/delete_complete_selected_confirmation.html"

    @admin.action(description="Delete complete mindmap (data + config + all logs)")
    def delete_complete_course_mindmap(self, request, queryset):
        totals = delete_complete_for_queryset(queryset)
        label = totals["courses"]
        self.message_user(
            request,
            (
                f"Deleted complete mindmap for {label} course(s): "
                f"{totals['data_rows']} data row(s), "
                f"{totals['config_rows']} config(s), "
                f"{totals['generation_rows']} generation log(s)."
            ),
            messages.SUCCESS,
        )

    def delete_model(self, request, obj):
        label = _course_label(obj.content_type, obj.object_id, getattr(obj, "course_type_key", ""))
        totals = delete_complete_course_mindmap(
            content_type=obj.content_type,
            object_id=obj.object_id,
        )
        self.message_user(
            request,
            (
                f"Deleted complete mindmap for {label}: "
                f"{totals['data_rows']} data row(s), "
                f"{totals['config_rows']} config(s), "
                f"{totals['generation_rows']} generation log(s)."
            ),
            messages.SUCCESS,
        )

    def delete_queryset(self, request, queryset):
        totals = delete_complete_for_queryset(queryset)
        self.message_user(
            request,
            (
                f"Deleted complete mindmap for {totals['courses']} course(s): "
                f"{totals['data_rows']} data row(s), "
                f"{totals['config_rows']} config(s), "
                f"{totals['generation_rows']} generation log(s)."
            ),
            messages.SUCCESS,
        )
