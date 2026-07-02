"""Unified student/parent career interest cards with source badges and reactions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from users.models import ParentStudentBookmark


def _career_ct():
    from careers.models import Career

    return ContentType.objects.get_for_model(Career)


def _career_card_payload(
    career,
    *,
    source: str,
    parent_name: str = "",
    parent_bookmark_id: Optional[int] = None,
    student_reaction: str = "",
    student_name: str = "",
    is_disliked: bool = False,
    sort_ts=None,
    viewer: str = "student",
) -> Dict[str, Any]:
    badge_label = _badge_label(source, parent_name, student_name, viewer=viewer)
    badge_class = ""
    if badge_label:
        if viewer == "student" and source in ("parent", "both"):
            badge_class = _badge_class("parent")
        elif viewer == "parent" and source in ("student", "both"):
            badge_class = _badge_class("student")
        else:
            badge_class = _badge_class(source)
    return {
        "career": career,
        "career_id": int(getattr(career, "id", 0) or 0),
        "source": source,
        "parent_name": parent_name,
        "parent_bookmark_id": parent_bookmark_id,
        "student_reaction": student_reaction or "",
        "student_name": student_name,
        "is_disliked": bool(is_disliked),
        "sort_ts": sort_ts,
        "badge_label": badge_label,
        "badge_class": badge_class,
        "career_slug": getattr(career, "slug", "") or "",
    }


def _badge_label(
    source: str,
    parent_name: str = "",
    student_name: str = "",
    *,
    viewer: str = "student",
) -> str:
    if viewer == "student":
        if source in ("parent", "both"):
            if parent_name:
                return f"Shortlisted by {parent_name}"
            return "Shortlisted by parent"
        return ""
    # Parent viewer: only show who shortlisted among linked students — never "by you".
    if source == "parent":
        return ""
    if source in ("student", "both"):
        if student_name:
            return f"Shortlisted by {student_name}"
        return "Shortlisted by student"
    return ""


def _badge_class(source: str) -> str:
    if source == "parent":
        return "career-source-badge career-source-badge--parent"
    if source == "both":
        return "career-source-badge career-source-badge--both"
    return "career-source-badge career-source-badge--student"


def _linked_students_for_parent(parent, *, student_id=None):
    from users.models import ParentStudentLink

    if student_id:
        link = (
            ParentStudentLink.objects.filter(parent=parent, student_id=student_id)
            .select_related("student")
            .first()
        )
        return [link.student] if link and link.student else []
    return [
        link.student
        for link in ParentStudentLink.objects.filter(parent=parent).select_related("student")
        if link.student
    ]


def sync_parent_career_shortlists_to_linked_students(parent) -> int:
    """Move parent-account CareerShortlist rows to ParentStudentBookmark for linked students."""
    from careers.models import CareerShortlist
    from users.parent_bookmark_utils import ensure_parent_student_bookmark

    students = _linked_students_for_parent(parent)
    if not students:
        return 0

    ct = _career_ct()
    created_count = 0
    for cs in list(
        CareerShortlist.objects.filter(user=parent, career__isnull=False).select_related("career")
    ):
        if not cs.career_id:
            continue
        for student in students:
            _, is_new = ensure_parent_student_bookmark(
                parent=parent,
                student=student,
                content_type=ct,
                object_id=cs.career_id,
            )
            if is_new:
                created_count += 1
        cs.delete()
    return created_count


def toggle_parent_career_bookmark(parent, career, *, student_id=None) -> Dict[str, str]:
    """Parent toggles a career for one or all linked students (student-facing suggestions)."""
    from careers.models import CareerShortlist
    from users.parent_bookmark_utils import (
        ensure_parent_student_bookmark,
        remove_parent_student_bookmarks_for_students,
    )

    students = _linked_students_for_parent(parent, student_id=student_id)
    if not students:
        career_shortlisted, created = CareerShortlist.objects.get_or_create(
            user=parent, career=career
        )
        if created:
            return {"message": "Career Shortlisted", "value": "Remove Shortlisted"}
        career_shortlisted.delete()
        return {"message": "Removed Shortlisted", "value": "Shortlist Career"}

    ct = _career_ct()
    if remove_parent_student_bookmarks_for_students(
        parent=parent, content_type=ct, object_id=career.id, students=students
    ):
        CareerShortlist.objects.filter(user=parent, career=career).delete()
        return {"message": "Removed Shortlisted", "value": "Shortlist Career"}

    from users.parent_suggestions import notify_student_parent_suggestion

    for student in students:
        bm, is_new = ensure_parent_student_bookmark(
            parent=parent,
            student=student,
            content_type=ct,
            object_id=career.id,
        )
        if is_new:
            notify_student_parent_suggestion(
                student=student,
                parent=parent,
                kind="careers",
                item_title=career.name,
                item_url=career.url() if hasattr(career, "url") else "",
                bookmark=bm,
            )
    CareerShortlist.objects.filter(user=parent, career=career).delete()
    return {"message": "Career Shortlisted", "value": "Remove Shortlisted"}


def build_student_career_interest_cards(student) -> List[Dict[str, Any]]:
    """Merge student shortlists + parent recommendations; disliked parent picks last."""
    if not student:
        return []

    from careers.models import Career, CareerShortlist
    from users.models import ParentStudentLink

    for link in ParentStudentLink.objects.filter(student=student).select_related("parent"):
        if link.parent:
            sync_parent_career_shortlists_to_linked_students(link.parent)

    ct = _career_ct()
    cards_by_career: Dict[int, Dict[str, Any]] = {}

    for cs in (
        CareerShortlist.objects.filter(user=student, career__isnull=False)
        .select_related("career")
        .order_by("-id")
    ):
        if not cs.career_id or not cs.career:
            continue
        cards_by_career[cs.career_id] = _career_card_payload(
            cs.career,
            source="student",
            sort_ts=getattr(cs, "created", None) or getattr(cs, "modified", None),
        )

    for bm in (
        ParentStudentBookmark.objects.filter(student=student, content_type=ct)
        .select_related("parent")
        .order_by("-created")
    ):
        career = Career.objects.filter(id=bm.object_id).first()
        if not career:
            continue
        parent_name = getattr(bm.parent, "name", "") or "Parent"
        reaction = (bm.student_reaction or "").strip()
        is_disliked = reaction == ParentStudentBookmark.REACTION_DISLIKED
        existing = cards_by_career.get(career.id)
        if existing:
            existing["source"] = "both"
            existing["parent_name"] = parent_name
            existing["parent_bookmark_id"] = bm.id
            existing["student_reaction"] = reaction
            existing["is_disliked"] = is_disliked
            existing["badge_label"] = _badge_label("both", parent_name, viewer="student")
            existing["badge_class"] = _badge_class("parent")
        else:
            cards_by_career[career.id] = _career_card_payload(
                career,
                source="parent",
                parent_name=parent_name,
                parent_bookmark_id=bm.id,
                student_reaction=reaction,
                is_disliked=is_disliked,
                sort_ts=getattr(bm, "created", None) or getattr(bm, "reacted_at", None),
            )

    cards = list(cards_by_career.values())
    cards.sort(key=_student_card_sort_key)
    return cards


def _student_card_sort_key(card: Dict[str, Any]):
    disliked_rank = 1 if card.get("is_disliked") else 0
    ts = card.get("sort_ts")
    ts_val = ts.timestamp() if ts else 0
    return (disliked_rank, -ts_val)


def build_parent_career_shortlist_cards(parent, user_ids, *, student=None) -> List[Dict[str, Any]]:
    """Parent-facing career cards with source + student dislike state."""
    from careers.models import Career, CareerShortlist

    if not parent:
        return []

    sync_parent_career_shortlists_to_linked_students(parent)

    ct = _career_ct()
    cards_by_career: Dict[int, Dict[str, Any]] = {}
    user_ids = list(user_ids or [])

    for cs in (
        CareerShortlist.objects.filter(user_id__in=user_ids, career__isnull=False)
        .select_related("career", "user")
        .order_by("-id")
    ):
        if not cs.career_id or not cs.career:
            continue
        if cs.career_id in cards_by_career:
            continue
        if cs.user_id == parent.id:
            cards_by_career[cs.career_id] = _career_card_payload(
                cs.career,
                source="parent",
                sort_ts=getattr(cs, "created", None) or getattr(cs, "modified", None),
                viewer="parent",
            )
            continue
        student_name = getattr(cs.user, "name", "") or "Student"
        cards_by_career[cs.career_id] = _career_card_payload(
            cs.career,
            source="student",
            student_name=student_name,
            sort_ts=getattr(cs, "created", None) or getattr(cs, "modified", None),
            viewer="parent",
        )

    bm_qs = ParentStudentBookmark.objects.filter(parent=parent, content_type=ct)
    if student is not None:
        bm_qs = bm_qs.filter(student=student)
    bm_qs = bm_qs.select_related("student", "parent").order_by("-created")

    for bm in bm_qs:
        career = Career.objects.filter(id=bm.object_id).first()
        if not career:
            continue
        student_name = getattr(bm.student, "name", "") or "Student"
        reaction = (bm.student_reaction or "").strip()
        is_disliked = reaction == ParentStudentBookmark.REACTION_DISLIKED
        existing = cards_by_career.get(career.id)
        if existing:
            existing["source"] = "both"
            existing["parent_bookmark_id"] = bm.id
            existing["student_reaction"] = reaction
            existing["student_name"] = student_name
            existing["is_disliked"] = is_disliked
            existing["badge_label"] = _badge_label("both", student_name=student_name, viewer="parent")
            existing["badge_class"] = _badge_class("student") if existing["badge_label"] else ""
        else:
            cards_by_career[career.id] = _career_card_payload(
                career,
                source="parent",
                parent_name=getattr(bm.parent, "name", "") or "You",
                parent_bookmark_id=bm.id,
                student_reaction=reaction,
                student_name=student_name,
                is_disliked=is_disliked,
                sort_ts=getattr(bm, "created", None) or getattr(bm, "reacted_at", None),
                viewer="parent",
            )

    cards = list(cards_by_career.values())
    cards.sort(key=lambda c: (-(c.get("sort_ts").timestamp() if c.get("sort_ts") else 0),))
    return cards


def set_parent_career_reaction(*, student, bookmark_id: int, reaction: str) -> Dict[str, Any]:
    """Student likes/dislikes a parent career recommendation."""
    ct = _career_ct()
    bm = (
        ParentStudentBookmark.objects.filter(
            id=bookmark_id,
            student=student,
            content_type=ct,
        )
        .select_related("parent", "student")
        .first()
    )
    if not bm:
        return {"success": False, "message": "Recommendation not found"}

    from careers.models import Career

    career = Career.objects.filter(id=bm.object_id).first()
    if not career:
        return {"success": False, "message": "Career not found"}

    reaction = (reaction or "").strip().lower()
    prev = (bm.student_reaction or "").strip()
    if reaction not in (
        ParentStudentBookmark.REACTION_LIKED,
        ParentStudentBookmark.REACTION_DISLIKED,
        ParentStudentBookmark.REACTION_NONE,
        "clear",
        "none",
    ):
        return {"success": False, "message": "Invalid reaction"}

    if reaction in ("clear", "none", ParentStudentBookmark.REACTION_NONE):
        bm.student_reaction = ParentStudentBookmark.REACTION_NONE
        bm.reacted_at = None
    else:
        bm.student_reaction = reaction
        bm.reacted_at = timezone.now()

    bm.save(update_fields=["student_reaction", "reacted_at", "modified"])

    if (
        bm.student_reaction == ParentStudentBookmark.REACTION_DISLIKED
        and prev != ParentStudentBookmark.REACTION_DISLIKED
    ):
        notify_parent_career_disliked(student=student, parent=bm.parent, career=career, bookmark=bm)
    elif (
        bm.student_reaction == ParentStudentBookmark.REACTION_LIKED
        and prev != ParentStudentBookmark.REACTION_LIKED
    ):
        notify_parent_career_liked(student=student, parent=bm.parent, career=career, bookmark=bm)

    label = "liked" if bm.student_reaction == ParentStudentBookmark.REACTION_LIKED else (
        "disliked" if bm.student_reaction == ParentStudentBookmark.REACTION_DISLIKED else "cleared"
    )
    return {
        "success": True,
        "message": f"Reaction {label}",
        "reaction": bm.student_reaction,
        "career_id": career.id,
    }


def notify_parent_career_disliked(*, student, parent, career, bookmark=None):
    from notifications.models import NotificationCategory
    from notifications.services import emit_notification, format_notification_message

    student_name = getattr(student, "name", "") or "Your student"
    career_name = getattr(career, "name", "") or "a career"
    title_default = f"{student_name} disliked your career suggestion"
    body_default = (
        f'{student_name} is not interested in "{career_name}" that you recommended. '
        "You may want to explore other options together."
    )
    title, body = format_notification_message(
        "parent.suggestion_disliked",
        {
            "student_name": student_name,
            "career_name": career_name,
            "item_title": career_name,
            "parent_name": getattr(parent, "name", "") or "Parent",
        },
        title_default,
        body_default,
    )
    dedupe = ""
    if bookmark is not None:
        dedupe = f"parent_suggestion_disliked:{bookmark.id}:{bookmark.student_reaction}"
    emit_notification(
        event_type="parent.suggestion_disliked",
        title=title,
        body=body,
        recipients=[parent],
        category=NotificationCategory.SYSTEM,
        payload={
            "kind": "careers",
            "career_id": getattr(career, "id", None),
            "career_name": career_name,
            "student_id": getattr(student, "id", None),
            "student_name": student_name,
            "reaction": ParentStudentBookmark.REACTION_DISLIKED,
        },
        source_obj=bookmark,
        dedupe_key=dedupe,
    )


def notify_parent_career_liked(*, student, parent, career, bookmark=None):
    from notifications.models import NotificationCategory
    from notifications.services import emit_notification, format_notification_message

    student_name = getattr(student, "name", "") or "Your student"
    career_name = getattr(career, "name", "") or "a career"
    title_default = f"{student_name} liked your career suggestion"
    body_default = (
        f'{student_name} is interested in "{career_name}" that you recommended.'
    )
    title, body = format_notification_message(
        "parent.suggestion_liked",
        {
            "student_name": student_name,
            "career_name": career_name,
            "item_title": career_name,
            "parent_name": getattr(parent, "name", "") or "Parent",
        },
        title_default,
        body_default,
    )
    dedupe = ""
    if bookmark is not None:
        dedupe = f"parent_suggestion_liked:{bookmark.id}:{bookmark.student_reaction}"
    emit_notification(
        event_type="parent.suggestion_liked",
        title=title,
        body=body,
        recipients=[parent],
        category=NotificationCategory.SYSTEM,
        payload={
            "kind": "careers",
            "career_id": getattr(career, "id", None),
            "career_name": career_name,
            "student_id": getattr(student, "id", None),
            "student_name": student_name,
            "reaction": ParentStudentBookmark.REACTION_LIKED,
        },
        source_obj=bookmark,
        dedupe_key=dedupe,
    )
