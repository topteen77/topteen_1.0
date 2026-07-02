"""Parent shortlists for linked students — student-facing suggestions + notifications."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from core import choices
from users.models import ParentStudentBookmark, ParentStudentLink


KIND_LABELS = {
    "careers": "career",
    "videos": "video",
    "blogs": "blog",
    "colleges": "college",
}

PARENT_SUGGESTION_EVENT = "parent.suggestion_added"
SCRAPBOOK_PARENT_KINDS = ("careers", "videos", "blogs", "colleges")

_CT_KIND_CACHE: Dict[int, str] = {}


def _kind_for_content_type_id(ct_id: int) -> str:
    if ct_id in _CT_KIND_CACHE:
        return _CT_KIND_CACHE[ct_id]
    for kind in SCRAPBOOK_PARENT_KINDS:
        model = _model_for_kind(kind)
        if not model:
            continue
        cid = ContentType.objects.get_for_model(model).id
        _CT_KIND_CACHE[cid] = kind
    return _CT_KIND_CACHE.get(ct_id, "")


def _bookmark_object(bm, kind: str):
    model = _model_for_kind(kind)
    if not model or not bm:
        return None
    if kind == "blogs":
        return model.get_published_objects().filter(id=bm.object_id).first()
    return model.objects.filter(id=bm.object_id).first()


def _unseen_parent_bookmarks_qs(student):
    if not student:
        return ParentStudentBookmark.objects.none()
    return ParentStudentBookmark.objects.filter(student=student, student_seen_at__isnull=True)


def _model_for_kind(kind: str):
    kind = (kind or "").lower()
    if kind == "careers":
        from careers.models import Career
        return Career
    if kind == "videos":
        from careers.models import Videos
        return Videos
    if kind == "blogs":
        from blog.models import Blog
        return Blog
    if kind == "colleges":
        from colleges.models import College
        return College
    return None


def _item_payload(kind: str, obj, parent_name: str = "") -> Dict[str, Any]:
    kind = (kind or "").lower()
    title = ""
    url = "#"
    if kind == "careers":
        title = getattr(obj, "name", "") or str(obj)
        try:
            url = obj.url()
        except Exception:
            url = reverse("careers:careerdetail", args=[obj.slug, obj.id])
    elif kind == "videos":
        title = getattr(obj, "name", "") or str(obj)
        url = reverse("careers:videodetail", args=[obj.slug])
    elif kind == "blogs":
        title = getattr(obj, "title", "") or str(obj)
        url = reverse("blog:blogdetail", args=[obj.slug])
    elif kind == "colleges":
        title = getattr(obj, "name", "") or str(obj)
        url = reverse("colleges:collegedetail", args=[obj.slug])
    return {
        "id": int(getattr(obj, "id", 0) or 0),
        "title": title,
        "url": url,
        "parent_name": parent_name,
        "kind": kind,
    }


def get_parent_suggestion_items(student, kind: str, limit: int = 12) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return (items, parent_names) for a student and content kind."""
    model = _model_for_kind(kind)
    if not model or not student:
        return [], []

    if kind == "blogs":
        from users.parent_saved_items import sync_parent_blog_shortlists_to_linked_students

        for link in ParentStudentLink.objects.filter(student=student).select_related("parent"):
            if link.parent:
                sync_parent_blog_shortlists_to_linked_students(link.parent)
    elif kind == "videos":
        from users.parent_saved_items import sync_parent_video_shortlists_to_linked_students

        for link in ParentStudentLink.objects.filter(student=student).select_related("parent"):
            if link.parent:
                sync_parent_video_shortlists_to_linked_students(link.parent)

    ct = ContentType.objects.get_for_model(model)
    bookmarks = (
        ParentStudentBookmark.objects.filter(student=student, content_type=ct)
        .select_related("parent")
        .order_by("-created")
    )
    if limit:
        bookmarks = bookmarks[: limit * 3]

    parent_names = []
    seen_parents = set()
    obj_ids = []
    seen_ids = set()
    bookmark_parent = {}
    for bm in bookmarks:
        oid = bm.object_id
        if not oid or oid in seen_ids:
            continue
        pname = getattr(bm.parent, "name", "") or "Parent"
        if bm.parent_id and bm.parent_id not in seen_parents:
            parent_names.append(pname)
            seen_parents.add(bm.parent_id)
        bookmark_parent[oid] = pname
        obj_ids.append(oid)
        seen_ids.add(oid)
        if len(obj_ids) >= limit:
            break

    if not obj_ids:
        return [], parent_names

    if kind == "blogs":
        qs = model.get_published_objects().filter(id__in=obj_ids)
    else:
        qs = model.objects.filter(id__in=obj_ids)
    obj_map = {o.id: o for o in qs}

    items = []
    for oid in obj_ids:
        obj = obj_map.get(oid)
        if not obj:
            continue
        items.append(_item_payload(kind, obj, bookmark_parent.get(oid, "Parent")))
    return items, parent_names


def apply_student_parent_suggestions_context(ctx: dict, request, kind: str) -> dict:
    """Inject student-facing parent suggestion section (not when parent is browsing for student)."""
    ctx.setdefault("show_parent_suggestions", False)
    ctx.setdefault("parent_suggested_items", [])
    ctx.setdefault("parent_suggestion_parents", [])
    ctx.setdefault("parent_suggestion_kind", kind)
    ctx.setdefault("parent_suggestion_heading", "Suggested by Parent")

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return ctx
    if getattr(request.user, "user_type", None) != choices.UserType.STUDENT:
        return ctx
    if ctx.get("is_parent_student_context"):
        return ctx

    items, parents = get_parent_suggestion_items(request.user, kind)
    ctx["parent_suggested_items"] = items
    ctx["parent_suggestion_parents"] = parents
    ctx["show_parent_suggestions"] = bool(items)
    if parents:
        if len(parents) == 1:
            ctx["parent_suggestion_heading"] = f"Suggested by {parents[0]}"
        else:
            ctx["parent_suggestion_heading"] = "Suggested by your parents"
    return ctx


def _unread_parent_suggestion_qs(student):
    from notifications.models import Notification

    if not student:
        return Notification.objects.none()
    return Notification.objects.filter(
        recipient=student,
        is_read=False,
        event_type=PARENT_SUGGESTION_EVENT,
    )


def get_unread_parent_suggestion_counts(student) -> Dict[str, int]:
    """Unseen parent bookmarks grouped by scrapbook kind (source of truth for badges)."""
    counts = {k: 0 for k in SCRAPBOOK_PARENT_KINDS}
    if not student:
        return counts
    for bm in _unseen_parent_bookmarks_qs(student).only("content_type_id"):
        kind = _kind_for_content_type_id(bm.content_type_id)
        if kind in counts:
            counts[kind] += 1
    return counts


def get_scrapbook_unread_total(student) -> int:
    if not student:
        return 0
    return _unseen_parent_bookmarks_qs(student).count()


def mark_parent_suggestions_read_for_kind(student, kind: str) -> int:
    """Mark parent bookmarks seen for one scrapbook category and dismiss matching notifications."""
    from django.utils import timezone

    kind_key = (kind or "").lower()
    if not student or kind_key not in SCRAPBOOK_PARENT_KINDS:
        return 0
    model = _model_for_kind(kind_key)
    if not model:
        return 0
    ct = ContentType.objects.get_for_model(model)
    now = timezone.now()
    updated = (
        ParentStudentBookmark.objects.filter(
            student=student,
            content_type=ct,
            student_seen_at__isnull=True,
        ).update(student_seen_at=now)
    )
    deleted, _ = _unread_parent_suggestion_qs(student).filter(payload__kind=kind_key).delete()
    _invalidate_notification_cache(student)
    return int(updated or deleted)


def ensure_parent_suggestion_notifications(student) -> int:
    """
    Create in-app notifications for unseen parent bookmarks that do not have one yet.
    Backfills rows created before notify was wired, without re-notifying seen items.
    """
    if not student:
        return 0
    from notifications.models import Notification

    created = 0
    for bm in _unseen_parent_bookmarks_qs(student).select_related("parent", "content_type"):
        kind = _kind_for_content_type_id(bm.content_type_id)
        if not kind:
            continue
        dedupe = f"parent_suggestion:{student.id}:{bm.content_type_id}:{bm.object_id}"
        if Notification.objects.filter(
            recipient=student,
            event_type=PARENT_SUGGESTION_EVENT,
            dedupe_key=dedupe,
        ).exists():
            continue
        obj = _bookmark_object(bm, kind)
        if not obj:
            continue
        title = getattr(obj, "name", None) or getattr(obj, "title", None) or str(obj)
        url = "#"
        try:
            if kind == "careers":
                url = obj.url()
            elif kind == "videos":
                url = reverse("careers:videodetail", args=[obj.slug])
            elif kind == "blogs":
                url = reverse("blog:blogdetail", args=[obj.slug])
            elif kind == "colleges":
                url = reverse("colleges:collegedetail", args=[obj.slug])
        except Exception:
            pass
        notify_student_parent_suggestion(
            student=student,
            parent=bm.parent,
            kind=kind,
            item_title=title,
            item_url=url,
            bookmark=bm,
        )
        created += 1
    return created


def _invalidate_notification_cache(student) -> None:
    if not student or not getattr(student, "id", None):
        return
    try:
        from django.core.cache import cache

        cache.delete(f"notif_latest:{student.id}")
    except Exception:
        pass


def apply_scrapbook_parent_updates_context(ctx: dict, student) -> dict:
    """Scrapbook grid highlights + sidebar unread badge."""
    ensure_parent_suggestion_notifications(student)
    counts = get_unread_parent_suggestion_counts(student)
    total = sum(counts.values())
    ctx["scrapbook_parent_unread"] = counts
    ctx["hub_scrapbook_unread_count"] = total
    ctx["scrapbook_has_parent_updates"] = total > 0
    return ctx


def maybe_mark_parent_suggestions_seen(request, kind: str, *, is_parent_student_context: bool = False) -> None:
    """Mark parent picks seen when a student opens the matching browse/list page."""
    if is_parent_student_context:
        return
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return
    if getattr(user, "user_type", None) != choices.UserType.STUDENT:
        return
    mark_parent_suggestions_read_for_kind(user, kind)


def load_all_parent_suggestions_for_student(student) -> Dict[str, Any]:
    """Dashboard payload: careers, videos, blogs, colleges."""
    careers, _ = get_parent_suggestion_items(student, "careers", limit=6)
    videos, parents_v = get_parent_suggestion_items(student, "videos", limit=6)
    blogs, parents_b = get_parent_suggestion_items(student, "blogs", limit=6)
    colleges, parents_c = get_parent_suggestion_items(student, "colleges", limit=6)
    parent_names = []
    seen = set()
    for name in parents_v + parents_b + parents_c:
        if name and name not in seen:
            parent_names.append(name)
            seen.add(name)
    return {
        "parent_suggested_careers": careers,
        "parent_suggested_videos": videos,
        "parent_suggested_blogs": blogs,
        "parent_suggested_colleges": colleges,
        "suggested_by_parents": parent_names,
        "show_parent_suggestions": bool(careers or videos or blogs or colleges),
    }


def notify_student_parent_suggestion(*, student, parent, kind: str, item_title: str, item_url: str = "", bookmark=None):
    """Emit in-app notification when parent shortlists content for a student."""
    from notifications.models import NotificationCategory
    from notifications.services import emit_notification, format_notification_message

    kind_key = (kind or "").lower()
    label = KIND_LABELS.get(kind_key, "item")
    parent_name = getattr(parent, "name", "") or "Your parent"
    student_name = getattr(student, "name", "") or "Student"
    title_default = f"New {label} suggestion from {parent_name}"
    body_default = f'{parent_name} shortlisted "{item_title}" for you. Tap to view.'
    title, body = format_notification_message(
        "parent.suggestion_added",
        {
            "parent_name": parent_name,
            "student_name": student_name,
            "item_title": item_title,
            "item_kind": label,
            "item_url": item_url or "",
        },
        title_default,
        body_default,
    )
    dedupe = ""
    if bookmark is not None:
        dedupe = f"parent_suggestion:{student.id}:{bookmark.content_type_id}:{bookmark.object_id}"
    emit_notification(
        event_type="parent.suggestion_added",
        title=title,
        body=body,
        recipients=[student],
        category=NotificationCategory.SYSTEM,
        payload={
            "kind": kind_key,
            "item_title": item_title,
            "item_url": item_url or "",
            "parent_id": getattr(parent, "id", None),
            "student_id": getattr(student, "id", None),
        },
        source_obj=bookmark,
        dedupe_key=dedupe,
    )
    _invalidate_notification_cache(student)
