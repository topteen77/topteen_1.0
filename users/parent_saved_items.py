"""Parent saved-item helpers for careers, blogs, and videos."""
from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.contenttypes.models import ContentType


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
            return {"success": True, "bookmarked": False, "message": "Removed Bookmark"}
        BlogShortlist.objects.create(user=parent, blog=blog)
        return {"success": True, "bookmarked": True, "message": "Blog Bookmarked"}

    from users.parent_suggestions import notify_student_parent_suggestion
    from django.urls import reverse

    ct = ContentType.objects.get_for_model(blog.__class__)
    if remove_parent_student_bookmarks_for_students(
        parent=parent, content_type=ct, object_id=blog.id, students=students
    ):
        BlogShortlist.objects.filter(user=parent, blog=blog).delete()
        return {"success": True, "bookmarked": False, "message": "Removed Bookmark"}

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
    return {"success": True, "bookmarked": True, "message": "Blog Bookmarked"}


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
            return {"success": True, "bookmarked": False, "message": "Removed Bookmark"}
        video.shortlist.add(parent)
        return {"success": True, "bookmarked": True, "message": "Video Bookmarked"}

    from users.parent_suggestions import notify_student_parent_suggestion
    from django.urls import reverse

    ct = ContentType.objects.get_for_model(Videos)
    if remove_parent_student_bookmarks_for_students(
        parent=parent, content_type=ct, object_id=video.id, students=students
    ):
        video.shortlist.remove(parent)
        return {"success": True, "bookmarked": False, "message": "Removed Bookmark"}

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
    return {"success": True, "bookmarked": True, "message": "Video Bookmarked"}


def remove_parent_saved_career(parent, *, career_slug: str) -> bool:
    from careers.models import Career, CareerShortlist
    from users.models import ParentStudentBookmark

    career = Career.objects.filter(slug=career_slug).first()
    if not career:
        return False
    ct = ContentType.objects.get_for_model(Career)
    ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=career.id
    ).delete()
    CareerShortlist.objects.filter(
        user_id__in=_linked_family_user_ids(parent), career_id=career.id
    ).delete()
    return True


def remove_parent_saved_blog(parent, *, blog_id: int) -> bool:
    from blog.models import Blog, BlogShortlist
    from users.models import ParentStudentBookmark

    blog = Blog.objects.filter(id=blog_id).first()
    if not blog:
        return False
    ct = ContentType.objects.get_for_model(Blog)
    ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=blog.id
    ).delete()
    BlogShortlist.objects.filter(
        user_id__in=_linked_family_user_ids(parent), blog_id=blog.id
    ).delete()
    return True


def remove_parent_saved_video(parent, *, video_id: int) -> bool:
    from careers.models import Videos
    from users.models import ParentStudentBookmark

    video = Videos.objects.filter(id=video_id).first()
    if not video:
        return False
    ct = ContentType.objects.get_for_model(Videos)
    ParentStudentBookmark.objects.filter(
        parent=parent, content_type=ct, object_id=video.id
    ).delete()
    for uid in _linked_family_user_ids(parent):
        video.shortlist.remove(uid)
    return True


def build_parent_blog_cards(parent, user_ids) -> List[Dict[str, Any]]:
    from blog.models import Blog as BlogModel, BlogShortlist
    from users.models import ParentStudentBookmark

    sync_parent_blog_shortlists_to_linked_students(parent)

    cards_by_id: Dict[int, Dict[str, Any]] = {}
    user_ids = list(user_ids or [])

    for bs in BlogShortlist.objects.filter(
        user_id__in=user_ids, blog__isnull=False
    ).select_related("blog", "user").order_by("-id"):
        if not bs.blog_id or not bs.blog or bs.blog_id in cards_by_id:
            continue
        if bs.user_id == parent.id:
            cards_by_id[bs.blog_id] = {
                "blog": bs.blog,
                "blog_id": bs.blog_id,
                "badge_label": "",
                "badge_class": "",
                "remove_blog_id": bs.blog_id,
            }
            continue
        owner_name = getattr(bs.user, "name", "") or "Student"
        cards_by_id[bs.blog_id] = {
            "blog": bs.blog,
            "blog_id": bs.blog_id,
            "badge_label": f"Shortlisted by {owner_name}",
            "badge_class": "career-source-badge career-source-badge--student",
            "remove_blog_id": bs.blog_id,
        }

    ct = ContentType.objects.get_for_model(BlogModel)
    for bm in ParentStudentBookmark.objects.filter(parent=parent, content_type=ct).order_by("-created"):
        blog = BlogModel.get_published_objects().filter(id=bm.object_id).first()
        if not blog:
            continue
        student_name = getattr(bm.student, "name", "") or "Student"
        existing = cards_by_id.get(blog.id)
        if existing:
            existing["badge_label"] = f"Shortlisted by {student_name}"
            existing["badge_class"] = "career-source-badge career-source-badge--student"
        else:
            cards_by_id[blog.id] = {
                "blog": blog,
                "blog_id": blog.id,
                "badge_label": "",
                "badge_class": "",
                "remove_blog_id": blog.id,
            }

    return list(cards_by_id.values())


def build_parent_video_cards(parent, user_ids) -> List[Dict[str, Any]]:
    from careers.models import Videos
    from users.models import ParentStudentBookmark, User

    sync_parent_video_shortlists_to_linked_students(parent)

    cards_by_id: Dict[int, Dict[str, Any]] = {}
    user_ids = list(user_ids or [])

    for vid in Videos.objects.filter(shortlist__in=user_ids).distinct().order_by("-id"):
        if vid.id in cards_by_id:
            continue
        owner_name = "Student"
        owner_is_parent = False
        for uid in user_ids:
            if vid.shortlist.filter(id=uid).exists():
                owner = User.objects.filter(id=uid).first()
                owner_name = getattr(owner, "name", "") or "Student"
                owner_is_parent = uid == parent.id
                break
        cards_by_id[vid.id] = {
            "video": vid,
            "video_id": vid.id,
            "badge_label": "" if owner_is_parent else f"Shortlisted by {owner_name}",
            "badge_class": "" if owner_is_parent else "career-source-badge career-source-badge--student",
            "remove_video_id": vid.id,
        }

    ct = ContentType.objects.get_for_model(Videos)
    for bm in ParentStudentBookmark.objects.filter(parent=parent, content_type=ct).order_by("-created"):
        video = Videos.objects.filter(id=bm.object_id).first()
        if not video:
            continue
        student_name = getattr(bm.student, "name", "") or "Student"
        existing = cards_by_id.get(video.id)
        if existing:
            existing["badge_label"] = f"Shortlisted by {student_name}"
            existing["badge_class"] = "career-source-badge career-source-badge--student"
        else:
            cards_by_id[video.id] = {
                "video": video,
                "video_id": video.id,
                "badge_label": "",
                "badge_class": "",
                "remove_video_id": video.id,
            }

    return list(cards_by_id.values())
