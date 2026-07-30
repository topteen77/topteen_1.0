"""Parent saved-item helpers for careers, blogs, and videos."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from users.career_interests import (
    _attach_linked_student,
    _badge_class,
    _badge_label,
    _refresh_parent_badge,
)
from users.models import ParentStudentBookmark


def _linked_family_user_ids(parent) -> List[int]:
    from users.models import ParentStudentLink

    ids = [parent.id]
    for sid in ParentStudentLink.objects.filter(parent=parent).values_list("student_id", flat=True):
        if sid:
            ids.append(sid)
    out, seen = [], set()
    for uid in ids:
        if uid and uid not in seen:
            out.append(uid)
            seen.add(uid)
    return out


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


def sync_parent_blog_shortlists_to_linked_students(parent) -> int:
    from blog.models import Blog, BlogShortlist
    from users.parent_bookmark_utils import ensure_parent_student_bookmark

    students = _linked_students_for_parent(parent)
    if not students:
        return 0

    ct = ContentType.objects.get_for_model(Blog)
    created_count = 0
    for bs in list(
        BlogShortlist.objects.filter(user=parent, blog__isnull=False).select_related("blog")
    ):
        if not bs.blog_id:
            continue
        for student in students:
            _, is_new = ensure_parent_student_bookmark(
                parent=parent,
                student=student,
                content_type=ct,
                object_id=bs.blog_id,
            )
            if is_new:
                created_count += 1
        bs.delete()
    return created_count


def toggle_parent_blog_bookmark(parent, blog, *, student_id=None) -> Dict[str, Any]:
    from blog.models import BlogShortlist
    from users.parent_bookmark_utils import (
        ensure_parent_student_bookmark,
        remove_parent_student_bookmarks_for_students,
    )

    students = _linked_students_for_parent(parent, student_id=student_id)
    if not students:
        obj = BlogShortlist.objects.filter(user=parent, blog=blog).first()
        if obj:
            obj.delete()
            return {"success": True, "bookmarked": False, "message": "Removed from shortlist"}
        BlogShortlist.objects.create(user=parent, blog=blog)
        return {"success": True, "bookmarked": True, "message": "Blog shortlisted"}

    from users.parent_suggestions import notify_student_parent_suggestion
    from django.urls import reverse

    ct = ContentType.objects.get_for_model(blog.__class__)
    if remove_parent_student_bookmarks_for_students(
        parent=parent, content_type=ct, object_id=blog.id, students=students
    ):
        BlogShortlist.objects.filter(user=parent, blog=blog).delete()
        return {"success": True, "bookmarked": False, "message": "Removed from shortlist"}

    for student in students:
        bm, is_new = ensure_parent_student_bookmark(
            parent=parent,
            student=student,
            content_type=ct,
            object_id=blog.id,
        )
        if is_new:
            notify_student_parent_suggestion(
                student=student,
                parent=parent,
                kind="blogs",
                item_title=getattr(blog, "title", str(blog)),
                item_url=reverse("blog:blogdetail", args=[blog.slug]),
                bookmark=bm,
            )
    BlogShortlist.objects.filter(user=parent, blog=blog).delete()
    return {"success": True, "bookmarked": True, "message": "Blog shortlisted"}


def sync_parent_video_shortlists_to_linked_students(parent) -> int:
    from careers.models import Videos
    from users.parent_bookmark_utils import ensure_parent_student_bookmark

    students = _linked_students_for_parent(parent)
    if not students:
        return 0

    ct = ContentType.objects.get_for_model(Videos)
    created_count = 0
    for video in Videos.objects.filter(shortlist=parent).distinct():
        for student in students:
            _, is_new = ensure_parent_student_bookmark(
                parent=parent,
                student=student,
                content_type=ct,
                object_id=video.id,
            )
            if is_new:
                created_count += 1
        video.shortlist.remove(parent)
    return created_count


def toggle_parent_video_bookmark(parent, video, *, student_id=None) -> Dict[str, Any]:
    from careers.models import Videos
    from users.parent_bookmark_utils import (
        ensure_parent_student_bookmark,
        remove_parent_student_bookmarks_for_students,
    )

    students = _linked_students_for_parent(parent, student_id=student_id)
    if not students:
        if video.shortlist.filter(id=parent.id).exists():
            video.shortlist.remove(parent)
            return {"success": True, "bookmarked": False, "message": "Removed from shortlist"}
        video.shortlist.add(parent)
        return {"success": True, "bookmarked": True, "message": "Video shortlisted"}

    from users.parent_suggestions import notify_student_parent_suggestion
    from django.urls import reverse

    ct = ContentType.objects.get_for_model(Videos)
    if remove_parent_student_bookmarks_for_students(
        parent=parent, content_type=ct, object_id=video.id, students=students
    ):
        video.shortlist.remove(parent)
        return {"success": True, "bookmarked": False, "message": "Removed from shortlist"}

    for student in students:
        bm, is_new = ensure_parent_student_bookmark(
            parent=parent,
            student=student,
            content_type=ct,
            object_id=video.id,
        )
        if is_new:
            notify_student_parent_suggestion(
                student=student,
                parent=parent,
                kind="videos",
                item_title=getattr(video, "name", str(video)),
                item_url=reverse("careers:videodetail", args=[video.slug]),
                bookmark=bm,
            )
    video.shortlist.remove(parent)
    return {"success": True, "bookmarked": True, "message": "Video shortlisted"}


def remove_parent_saved_career(parent, *, career_slug: str, student_id: Optional[int] = None) -> bool:
    from careers.models import Career, CareerShortlist
    from users.models import ParentStudentBookmark

    career = Career.objects.filter(slug=career_slug).first()
    if not career:
        return False
    ct = ContentType.objects.get_for_model(Career)
    bm_qs = ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=career.id
    )
    if student_id:
        bm_qs = bm_qs.filter(student_id=int(student_id))
        bm_qs.delete()
        CareerShortlist.objects.filter(user_id=int(student_id), career_id=career.id).delete()
        return True
    bm_qs.delete()
    CareerShortlist.objects.filter(
        user_id__in=_linked_family_user_ids(parent), career_id=career.id
    ).delete()
    return True


def remove_parent_saved_blog(parent, *, blog_id: int, student_id: Optional[int] = None) -> bool:
    from blog.models import Blog, BlogShortlist
    from users.models import ParentStudentBookmark

    blog = Blog.objects.filter(id=blog_id).first()
    if not blog:
        return False
    ct = ContentType.objects.get_for_model(Blog)
    bm_qs = ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=blog.id
    )
    if student_id:
        bm_qs = bm_qs.filter(student_id=int(student_id))
        bm_qs.delete()
        BlogShortlist.objects.filter(user_id=int(student_id), blog_id=blog.id).delete()
        return True
    bm_qs.delete()
    BlogShortlist.objects.filter(
        user_id__in=_linked_family_user_ids(parent), blog_id=blog.id
    ).delete()
    return True


def remove_parent_saved_video(parent, *, video_id: int, student_id: Optional[int] = None) -> bool:
    from careers.models import Videos
    from users.models import ParentStudentBookmark

    video = Videos.objects.filter(id=video_id).first()
    if not video:
        return False
    ct = ContentType.objects.get_for_model(Videos)
    bm_qs = ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=video.id
    )
    if student_id:
        bm_qs = bm_qs.filter(student_id=int(student_id))
        bm_qs.delete()
        video.shortlist.remove(int(student_id))
        return True
    bm_qs.delete()
    for uid in _linked_family_user_ids(parent):
        video.shortlist.remove(uid)
    return True


def build_parent_blog_cards(parent, user_ids, *, student=None) -> List[Dict[str, Any]]:
    from blog.models import Blog as BlogModel, BlogShortlist
    from users.models import ParentStudentBookmark

    sync_parent_blog_shortlists_to_linked_students(parent)

    cards_by_id: Dict[int, Dict[str, Any]] = {}
    user_ids = list(user_ids or [])

    for bs in BlogShortlist.objects.filter(
        user_id__in=user_ids, blog__isnull=False
    ).select_related("blog", "user").order_by("-id"):
        if not bs.blog_id or not bs.blog:
            continue
        if bs.user_id == parent.id:
            if bs.blog_id not in cards_by_id:
                cards_by_id[bs.blog_id] = {
                    "blog": bs.blog,
                    "blog_id": bs.blog_id,
                    "source": "parent",
                    "badge_label": "",
                    "badge_class": "",
                    "student_ids": [],
                    "student_names": [],
                    "student_name": "",
                    "remove_blog_id": bs.blog_id,
                }
            continue
        existing = cards_by_id.get(bs.blog_id)
        if existing:
            if existing.get("source") == "parent":
                existing["source"] = "both"
            _attach_linked_student(existing, bs.user)
            _refresh_parent_badge(existing)
            continue
        card = {
            "blog": bs.blog,
            "blog_id": bs.blog_id,
            "source": "student",
            "badge_label": "",
            "badge_class": "",
            "student_ids": [],
            "student_names": [],
            "student_name": "",
            "remove_blog_id": bs.blog_id,
        }
        _attach_linked_student(card, bs.user)
        _refresh_parent_badge(card)
        cards_by_id[bs.blog_id] = card

    ct = ContentType.objects.get_for_model(BlogModel)
    bm_qs = ParentStudentBookmark.objects.filter(parent=parent, content_type=ct)
    if student is not None:
        bm_qs = bm_qs.filter(student=student)
    for bm in bm_qs.select_related("student").order_by("-created"):
        blog = BlogModel.get_published_objects().filter(id=bm.object_id).first()
        if not blog:
            continue
        existing = cards_by_id.get(blog.id)
        if existing:
            if existing.get("source") == "student":
                existing["source"] = "both"
            elif existing.get("source") != "both":
                existing["source"] = "parent"
            _attach_linked_student(existing, bm.student)
            _refresh_parent_badge(existing)
        else:
            card = {
                "blog": blog,
                "blog_id": blog.id,
                "source": "parent",
                "badge_label": "",
                "badge_class": "",
                "student_ids": [],
                "student_names": [],
                "student_name": "",
                "remove_blog_id": blog.id,
            }
            _attach_linked_student(card, bm.student)
            _refresh_parent_badge(card)
            cards_by_id[blog.id] = card

    cards = list(cards_by_id.values())
    if student is not None:
        sid = int(getattr(student, "id", 0) or 0)
        sname = (getattr(student, "name", None) or "").strip() or "Student"
        scoped = []
        for c in cards:
            if sid not in (c.get("student_ids") or []):
                continue
            c["student_ids"] = [sid]
            c["student_names"] = [sname]
            c["student_name"] = sname
            _refresh_parent_badge(c)
            scoped.append(c)
        cards = scoped
    return cards


def _merge_student_reaction(card: Dict[str, Any], reaction: str, student) -> None:
    """Aggregate a linked student's reaction to a parent suggestion onto a card.

    A dislike always wins over a like; used so the parent sees whether any linked
    student reacted to the video they suggested.
    """
    reaction = (reaction or "").strip()
    if reaction == ParentStudentBookmark.REACTION_DISLIKED:
        card["student_reaction"] = ParentStudentBookmark.REACTION_DISLIKED
        card["is_disliked"] = True
        card["student_name"] = card.get("student_name") or (getattr(student, "name", "") or "Student")
    elif reaction == ParentStudentBookmark.REACTION_LIKED and not card.get("is_disliked"):
        card["student_reaction"] = ParentStudentBookmark.REACTION_LIKED
        card["student_name"] = card.get("student_name") or (getattr(student, "name", "") or "Student")


def build_parent_video_cards(parent, user_ids, *, student=None) -> List[Dict[str, Any]]:
    from careers.models import Videos
    from users.models import User

    sync_parent_video_shortlists_to_linked_students(parent)

    cards_by_id: Dict[int, Dict[str, Any]] = {}
    student_direct_ids: set = set()
    user_ids = list(user_ids or [])
    student_ids = [uid for uid in user_ids if uid != parent.id]

    # Step 1: independent shortlists via the Videos.shortlist M2M. A student appearing
    # here shortlisted the video themselves (not because the parent picked it for them).
    for vid in Videos.objects.filter(shortlist__in=user_ids).distinct().order_by("-id"):
        student_owners = list(
            User.objects.filter(id__in=student_ids, video_shortlist=vid)
        ) if student_ids else []
        if student_owners:
            student_direct_ids.add(vid.id)
            card = cards_by_id.get(vid.id)
            if not card:
                card = _video_card_payload(
                    vid,
                    source="student",
                    sort_ts=getattr(vid, "created", None) or getattr(vid, "modified", None),
                    viewer="parent",
                )
                cards_by_id[vid.id] = card
            for owner in student_owners:
                _attach_linked_student(card, owner)
            _refresh_parent_badge(card)
        elif vid.shortlist.filter(id=parent.id).exists() and vid.id not in cards_by_id:
            cards_by_id[vid.id] = _video_card_payload(
                vid,
                source="parent",
                sort_ts=getattr(vid, "created", None) or getattr(vid, "modified", None),
                viewer="parent",
            )

    # Step 2: the parent's own picks, stored as one ParentStudentBookmark per linked
    # student. These are all the *parent's* action, so multiple rows for one video must
    # not be mistaken for a student shortlist.
    ct = ContentType.objects.get_for_model(Videos)
    bm_qs = ParentStudentBookmark.objects.filter(parent=parent, content_type=ct)
    if student is not None:
        bm_qs = bm_qs.filter(student=student)
    bm_qs = bm_qs.select_related("student", "parent").order_by("-created")

    for bm in bm_qs:
        video = Videos.objects.filter(id=bm.object_id).first()
        if not video:
            continue
        reaction = (bm.student_reaction or "").strip()
        existing = cards_by_id.get(video.id)
        if existing:
            if not existing.get("parent_bookmark_id"):
                existing["parent_bookmark_id"] = bm.id
            # Only a genuine student-initiated shortlist upgrades the card to "both".
            if video.id in student_direct_ids and existing.get("source") != "both":
                existing["source"] = "both"
            elif existing.get("source") != "both" and existing.get("source") != "student":
                existing["source"] = "parent"
            _attach_linked_student(existing, bm.student)
            _merge_student_reaction(existing, reaction, bm.student)
            _refresh_parent_badge(existing)
        else:
            card = _video_card_payload(
                video,
                source="parent",
                parent_name=getattr(bm.parent, "name", "") or "You",
                parent_bookmark_id=bm.id,
                sort_ts=getattr(bm, "created", None) or getattr(bm, "reacted_at", None),
                viewer="parent",
            )
            _attach_linked_student(card, bm.student)
            _merge_student_reaction(card, reaction, bm.student)
            _refresh_parent_badge(card)
            cards_by_id[video.id] = card

    cards = list(cards_by_id.values())
    if student is not None:
        sid = int(getattr(student, "id", 0) or 0)
        sname = (getattr(student, "name", None) or "").strip() or "Student"
        scoped = []
        for c in cards:
            if sid not in (c.get("student_ids") or []):
                continue
            c["student_ids"] = [sid]
            c["student_names"] = [sname]
            c["student_name"] = sname
            _refresh_parent_badge(c)
            scoped.append(c)
        cards = scoped
    cards.sort(key=lambda c: (-(c.get("sort_ts").timestamp() if c.get("sort_ts") else 0),))
    return cards


def _video_card_payload(
    video,
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
        "video": video,
        "video_id": int(getattr(video, "id", 0) or 0),
        "source": source,
        "parent_name": parent_name,
        "parent_bookmark_id": parent_bookmark_id,
        "student_reaction": student_reaction or "",
        "student_name": student_name,
        "student_ids": [],
        "student_names": [],
        "is_disliked": bool(is_disliked),
        "sort_ts": sort_ts,
        "badge_label": badge_label,
        "badge_class": badge_class,
        "remove_video_id": int(getattr(video, "id", 0) or 0),
    }


def _student_video_card_sort_key(card: Dict[str, Any]):
    disliked_rank = 1 if card.get("is_disliked") else 0
    ts = card.get("sort_ts")
    ts_val = ts.timestamp() if ts else 0
    return (disliked_rank, -ts_val)


def build_student_video_cards(student) -> List[Dict[str, Any]]:
    """Merge student bookmarks + parent recommendations with source badges."""
    from careers.models import Videos
    from users.models import ParentStudentLink

    if not student:
        return []

    for link in ParentStudentLink.objects.filter(student=student).select_related("parent"):
        if link.parent:
            sync_parent_video_shortlists_to_linked_students(link.parent)

    ct = ContentType.objects.get_for_model(Videos)
    cards_by_id: Dict[int, Dict[str, Any]] = {}
    student_direct_ids: set = set()

    for video in Videos.objects.filter(shortlist=student).order_by("-id"):
        student_direct_ids.add(video.id)
        cards_by_id[video.id] = _video_card_payload(
            video,
            source="student",
            sort_ts=getattr(video, "created", None) or getattr(video, "modified", None),
        )

    for bm in (
        ParentStudentBookmark.objects.filter(student=student, content_type=ct)
        .select_related("parent")
        .order_by("-created")
    ):
        video = Videos.objects.filter(id=bm.object_id).first()
        if not video:
            continue
        parent_name = getattr(bm.parent, "name", "") or "Parent"
        reaction = (bm.student_reaction or "").strip()
        is_disliked = reaction == ParentStudentBookmark.REACTION_DISLIKED
        existing = cards_by_id.get(video.id)
        if existing:
            if not existing.get("parent_bookmark_id"):
                existing["parent_bookmark_id"] = bm.id
                existing["parent_name"] = parent_name
                existing["student_reaction"] = reaction
                existing["is_disliked"] = is_disliked
            # Only mark "both" when the student independently shortlisted the video too.
            if video.id in student_direct_ids and existing.get("source") != "both":
                existing["source"] = "both"
                existing["badge_label"] = _badge_label("both", parent_name, viewer="student")
                existing["badge_class"] = _badge_class("parent")
        else:
            cards_by_id[video.id] = _video_card_payload(
                video,
                source="parent",
                parent_name=parent_name,
                parent_bookmark_id=bm.id,
                student_reaction=reaction,
                is_disliked=is_disliked,
                sort_ts=getattr(bm, "created", None) or getattr(bm, "reacted_at", None),
            )

    cards = list(cards_by_id.values())
    cards.sort(key=_student_video_card_sort_key)
    return cards


def set_parent_bookmark_reaction(*, student, bookmark_id: int, reaction: str) -> Dict[str, Any]:
    """Student likes/dislikes a parent recommendation (careers, videos, blogs, etc.)."""
    bm = (
        ParentStudentBookmark.objects.filter(id=bookmark_id, student=student)
        .select_related("parent", "student")
        .first()
    )
    if not bm:
        return {"success": False, "message": "Recommendation not found"}

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

    from users.parent_suggestions import _kind_for_content_type_id

    kind = _kind_for_content_type_id(bm.content_type_id)
    if kind == "careers":
        from careers.models import Career
        from users.career_interests import notify_parent_career_disliked, notify_parent_career_liked

        career = Career.objects.filter(id=bm.object_id).first()
        if career:
            if (
                bm.student_reaction == ParentStudentBookmark.REACTION_DISLIKED
                and prev != ParentStudentBookmark.REACTION_DISLIKED
            ):
                notify_parent_career_disliked(
                    student=student, parent=bm.parent, career=career, bookmark=bm
                )
            elif (
                bm.student_reaction == ParentStudentBookmark.REACTION_LIKED
                and prev != ParentStudentBookmark.REACTION_LIKED
            ):
                notify_parent_career_liked(
                    student=student, parent=bm.parent, career=career, bookmark=bm
                )

    label = "liked" if bm.student_reaction == ParentStudentBookmark.REACTION_LIKED else (
        "disliked" if bm.student_reaction == ParentStudentBookmark.REACTION_DISLIKED else "cleared"
    )
    return {
        "success": True,
        "message": f"Reaction {label}",
        "reaction": bm.student_reaction,
        "bookmark_id": bm.id,
        "kind": kind,
    }
