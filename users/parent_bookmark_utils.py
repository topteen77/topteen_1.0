"""Helpers for parent→student bookmarks (handles soft-deleted rows)."""
from __future__ import annotations

from typing import Tuple

from core import choices


def _all_bookmarks_qs():
    from users.models import ParentStudentBookmark

    return ParentStudentBookmark.objects.complete()


def hard_delete_parent_student_bookmarks(**filters) -> int:
    count = 0
    for bm in list(_all_bookmarks_qs().filter(**filters)):
        bm.delete(hard_delete=True)
        count += 1
    return count


def ensure_parent_student_bookmark(*, parent, student, content_type, object_id):
    """
    Return (bookmark, is_new).
    Reactivates soft-deleted rows instead of failing on unique constraints.
    """
    from users.models import ParentStudentBookmark

    bm = _all_bookmarks_qs().filter(
        parent=parent,
        student=student,
        content_type=content_type,
        object_id=object_id,
    ).first()
    if bm:
        if bm.object_status != choices.ObjectStatus.ACTIVE:
            bm.object_status = choices.ObjectStatus.ACTIVE
            bm.student_reaction = ParentStudentBookmark.REACTION_NONE
            bm.reacted_at = None
            bm.student_seen_at = None
            bm.save(
                update_fields=[
                    "object_status",
                    "student_reaction",
                    "reacted_at",
                    "student_seen_at",
                    "modified",
                ]
            )
            return bm, True
        return bm, False

    bm = ParentStudentBookmark.objects.create(
        parent=parent,
        student=student,
        content_type=content_type,
        object_id=object_id,
    )
    return bm, True


def active_parent_student_bookmarks(**filters):
    from users.models import ParentStudentBookmark

    return ParentStudentBookmark.objects.filter(**filters)


def remove_parent_student_bookmarks_for_students(*, parent, content_type, object_id, students) -> bool:
    """Hard-delete active bookmarks for toggle-off."""
    student_ids = [s.id for s in students if s and s.id]
    if not student_ids:
        return False
    qs = active_parent_student_bookmarks(
        parent=parent,
        content_type=content_type,
        object_id=object_id,
        student_id__in=student_ids,
    )
    if not qs.exists():
        return False
    ids = list(qs.values_list("id", flat=True))
    hard_delete_parent_student_bookmarks(id__in=ids)
    return True
