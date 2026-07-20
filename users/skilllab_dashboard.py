"""Skill Lab course progress helpers for student and parent dashboards."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from django.templatetags.static import static
from django.urls import reverse

from core import choices
from skilllab.learner_header import skilllab_course_card_labels
from users.parent_student_insights import _extract_grade_number, resolve_student_grade


SKILLLAB_SECTION_TITLE = "College & Career Readiness"
SKILLLAB_SECTION_SUBTITLE = "Skill Lab"


def skilllab_started_user_ids(student_ids, course) -> Set[int]:
    if not student_ids:
        return set()
    started = set(
        course.skilllabcourseresume.filter(user_id__in=student_ids).values_list(
            "user_id", flat=True
        )
    )
    started.update(
        course.skilllabcourseprogress.filter(user_id__in=student_ids).values_list(
            "user_id", flat=True
        )
    )
    started.update(
        course.skilllabcourseprogresssummary.filter(
            user_id__in=student_ids, progress_percentage__gt=0
        ).values_list("user_id", flat=True)
    )
    return started


def skilllab_completed_user_ids(student_ids: List[int], course) -> Set[int]:
    if not student_ids:
        return set()

    completed = set(
        course.certifications.filter(user_id__in=student_ids).values_list("user_id", flat=True)
    )

    chapters = list(course.skilllabcoursechapter.values_list("id", flat=True))
    if not chapters:
        for sid in student_ids:
            if sid in completed:
                continue
            summary = course.skilllabcourseprogresssummary.filter(user_id=sid).first()
            if summary and (summary.progress_percentage or 0) >= 100:
                completed.add(sid)
        return completed

    for sid in student_ids:
        if sid in completed:
            continue
        done_chapters = set(
            course.skilllabcourseprogress.filter(
                user_id=sid, chapter_id__in=chapters, completed=True
            ).values_list("chapter_id", flat=True)
        )
        if len(done_chapters) >= len(chapters):
            completed.add(sid)
    return completed


def skilllab_owned_user_ids(student_ids, course, is_free: bool) -> Set[int]:
    from skilllab.models import SkilllabCoursePayment

    paid_ids = set(
        SkilllabCoursePayment.objects.filter(
            user_id__in=student_ids,
            skilllab_course_id=course.id,
            is_success=choices.YesNoChoices.YES,
        ).values_list("user_id", flat=True)
    )
    if is_free:
        return paid_ids | skilllab_started_user_ids(student_ids, course)
    return paid_ids


def skilllab_course_progress_pct(user, course) -> int:
    from skilllab.models import SkillLabCertification

    if SkillLabCertification.objects.filter(user=user, skilllab_course=course).exists():
        return 100
    summary = course.skilllabcourseprogresssummary.filter(user=user).first()
    if summary and summary.progress_percentage is not None:
        return int(summary.progress_percentage or 0)

    chapters = list(course.skilllabcoursechapter.values_list("id", flat=True))
    if not chapters:
        return 0
    done = course.skilllabcourseprogress.filter(
        user=user, chapter_id__in=chapters, completed=True
    ).count()
    return int((done / len(chapters)) * 100)


def skilllab_course_completed(user, course) -> bool:
    return user.id in skilllab_completed_user_ids([user.id], course)


def skilllab_course_enrolled(user, course) -> bool:
    try:
        val = float(course.amount or 0)
    except (TypeError, ValueError):
        val = 0
    is_free = val <= 0
    return user.id in skilllab_owned_user_ids([user.id], course, is_free)


def skilllab_course_cta(user, course, *, enrolled: Optional[bool] = None) -> str:
    if enrolled is None:
        enrolled = skilllab_course_enrolled(user, course)
    if not enrolled:
        return "Enroll"
    if skilllab_course_completed(user, course):
        return "Completed"
    if course.user_has_started(user):
        return "Resume"
    return "Start"


def skilllab_course_start_url(course, *, resume=False) -> str:
    url = reverse("skilllabcourse:course_learning", args=[course.slug])
    if resume:
        return f"{url}?entry=resume"
    return url


def skilllab_course_resume_url(course) -> str:
    return skilllab_course_start_url(course, resume=True)


def skilllab_course_certificate_url(course) -> str:
    return reverse("skilllabcourse:skilllab_certificate", args=[course.slug])


def skilllab_course_detail_url(course) -> str:
    return reverse("skilllabcourse:skilllabcoursedetail", args=[course.slug])


def skilllab_course_eligible_for_student(user, course) -> bool:
    """True when the course's class grades include the student's class."""
    grade_num = _extract_grade_number(user)
    if grade_num is None:
        return False
    return course.matches_skilllab_filters(grade=grade_num)


def skilllab_is_career_readiness_grade_student(user) -> bool:
    """Class 9–12 (or bucket 10/12 when grade not set) — target audience for this section."""
    grade_num = _extract_grade_number(user)
    if grade_num is not None:
        return grade_num in (9, 10, 11, 12)
    bucket, _ = resolve_student_grade(user)
    return bucket in ("10", "12")


def skilllab_eligible_course_count(user) -> int:
    """Fast count for dashboard browse CTA (M2M + rare ungraded name fallback)."""
    from django.db.models import Count

    from skilllab.models import SkillLabCourse

    grade_num = _extract_grade_number(user)
    if grade_num is None:
        return 0
    count = (
        SkillLabCourse.objects.filter(grades__grade_number=grade_num)
        .distinct()
        .count()
    )
    ungraded = SkillLabCourse.objects.annotate(_gc=Count("grades")).filter(_gc=0)
    if not ungraded.exists():
        return count
    for course in ungraded.iterator(chunk_size=100):
        if course.matches_skilllab_filters(grade=grade_num):
            count += 1
    return count


def skilllab_eligible_courses_queryset(user):
    """Courses whose Grades M2M includes the student's class number.

    Avoids iterating the full course catalog on every dashboard hit. Name-based
    grade fallback only runs for courses with no Grades M2M (usually none).
    """
    from django.db.models import Count

    from skilllab.models import SkillLabCourse

    grade_num = _extract_grade_number(user)
    base = SkillLabCourse.objects.all().order_by("-modified")
    if grade_num is None:
        return base.none()
    matched_ids = set(
        base.filter(grades__grade_number=grade_num).values_list("id", flat=True)
    )
    ungraded = base.annotate(_grade_count=Count("grades")).filter(_grade_count=0)
    if ungraded.exists():
        for course in ungraded.iterator(chunk_size=100):
            if course.matches_skilllab_filters(grade=grade_num):
                matched_ids.add(course.id)
    return base.filter(id__in=matched_ids)

_SKILLLAB_DASH_CACHE_TTL = 90
_SKILLLAB_DASH_CACHE_PREFIX = "skilllab:dash:items:v2:"


def invalidate_skilllab_dashboard_items_cache(user_id: int) -> None:
    try:
        from django.core.cache import cache

        cache.delete(f"{_SKILLLAB_DASH_CACHE_PREFIX}{int(user_id)}")
    except Exception:
        pass


def skilllab_active_course_ids_for_user(user) -> Set[int]:
    """Course IDs the student has paid for or already started (free or paid)."""
    from skilllab.models import (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkilllabCoursePayment,
    )

    active = set(
        SkilllabCoursePayment.objects.filter(
            user=user,
            is_success=choices.YesNoChoices.YES,
            skilllab_course__isnull=False,
        ).values_list("skilllab_course_id", flat=True)
    )
    active.update(
        SkillLabCourseResume.objects.filter(user=user).values_list(
            "skilllab_course_id", flat=True
        )
    )
    active.update(
        SkillLabCourseProgress.objects.filter(user=user).values_list(
            "skilllab_course_id", flat=True
        )
    )
    active.update(
        SkillLabCourseProgressSummary.objects.filter(
            user=user, progress_percentage__gt=0
        ).values_list("skilllab_course_id", flat=True)
    )
    return {cid for cid in active if cid}


def skilllab_dashboard_courses_for_user(user):
    """Courses the student has started or paid for.

    Grade tags are NOT applied here: once a student actively starts or buys a
    course, it belongs on their dashboard regardless of the course's class tags
    (a Class 12 student may still have opened a course tagged for another grade).
    The grade filter only gates the browse/discover suggestion in
    ``build_student_skilllab_dashboard_items``.
    """
    from skilllab.models import SkillLabCourse

    active_ids = skilllab_active_course_ids_for_user(user)
    if not active_ids:
        return SkillLabCourse.objects.none()
    return SkillLabCourse.objects.filter(id__in=active_ids).select_related(
        "topic_category"
    ).prefetch_related("grades").order_by("-modified")


def build_skilllab_dashboard_item(
    user,
    course,
    *,
    enrolled: Optional[bool] = None,
    progress_pct: Optional[int] = None,
    completed: Optional[bool] = None,
    started: Optional[bool] = None,
) -> Dict[str, Any]:
    """Card payload for student dashboard «My courses & tests».

    enrolled/progress_pct/completed/started may be supplied by the bulk builder
    to avoid per-course queries; when omitted they are computed individually.
    """
    if enrolled is None:
        enrolled = skilllab_course_enrolled(user, course)
    if progress_pct is None:
        progress_pct = skilllab_course_progress_pct(user, course)
    if completed is None:
        completed = skilllab_course_completed(user, course)
    if started is None:
        started = course.user_has_started(user)

    # cta mirrors skilllab_course_cta() using the (possibly precomputed) flags.
    if not enrolled:
        cta = "Enroll"
    elif completed:
        cta = "Completed"
    elif started:
        cta = "Resume"
    else:
        cta = "Start"
    is_complete = cta == "Completed"

    if is_complete:
        action_url = skilllab_course_certificate_url(course)
        action_variant = "report"
    elif cta == "Enroll":
        action_url = skilllab_course_detail_url(course)
        action_variant = "start"
    else:
        action_url = skilllab_course_resume_url(course) if cta == "Resume" else skilllab_course_start_url(course)
        action_variant = "start"

    card_labels = skilllab_course_card_labels(course)
    class_label = card_labels["class_label"]
    category_label = card_labels["category_label"]
    subtitle_parts = [p for p in (class_label, category_label) if p]
    card_subtitle = " · ".join(subtitle_parts) if subtitle_parts else SKILLLAB_SECTION_SUBTITLE

    return {
        "kind": "skilllab",
        "kind_badge": category_label or "CAREER",
        "class_label": class_label,
        "category_label": category_label,
        "title": course.name,
        "subtitle": card_subtitle,
        "start_url": action_url,
        "action_label": cta,
        "action_variant": action_variant,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
        "certificate_url": skilllab_course_certificate_url(course) if is_complete else "",
        "view_course_url": skilllab_course_resume_url(course) if is_complete else "",
        "detail_url": skilllab_course_detail_url(course),
        "image_url": course.get_image_url(),
        "icon_src": "images_new/icons/skill-labs-cion.png",
        "icon_bg": "#eef6ff",
    }


def _bulk_skilllab_status(user, courses) -> Dict[str, Dict[int, Any]]:
    """Compute enrolled/progress/completed/started for many courses in a fixed
    number of queries (instead of ~10 per course). Semantics match the
    per-course helpers (skilllab_course_enrolled/_progress_pct/_completed and
    course.user_has_started)."""
    from skilllab.models import (
        SkillLabCertification,
        SkillLabCourseChapter,
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkilllabCoursePayment,
    )

    ids = [c.id for c in courses]
    paid = set(
        SkilllabCoursePayment.objects.filter(
            user=user, skilllab_course_id__in=ids, is_success=choices.YesNoChoices.YES
        ).values_list("skilllab_course_id", flat=True)
    )
    resume = set(
        SkillLabCourseResume.objects.filter(
            user=user, skilllab_course_id__in=ids
        ).values_list("skilllab_course_id", flat=True)
    )
    cert = set(
        SkillLabCertification.objects.filter(
            user=user, skilllab_course_id__in=ids
        ).values_list("skilllab_course_id", flat=True)
    )
    summary = {
        cid: pct
        for cid, pct in SkillLabCourseProgressSummary.objects.filter(
            user=user, skilllab_course_id__in=ids
        ).values_list("skilllab_course_id", "progress_percentage")
    }

    progress_course_ids: Set[int] = set()
    done_chapters_by_course: Dict[int, Set[int]] = {}
    for cid, chid, comp in SkillLabCourseProgress.objects.filter(
        user=user, skilllab_course_id__in=ids
    ).values_list("skilllab_course_id", "chapter_id", "completed"):
        progress_course_ids.add(cid)
        if comp:
            done_chapters_by_course.setdefault(cid, set()).add(chid)

    # SkillLabCourseChapter's FK to the course is named `skilllab` (skilllab_id).
    chapters_by_course: Dict[int, Set[int]] = {}
    for cid, chid in SkillLabCourseChapter.objects.filter(
        skilllab_id__in=ids
    ).values_list("skilllab_id", "id"):
        chapters_by_course.setdefault(cid, set()).add(chid)

    enrolled: Dict[int, bool] = {}
    progress_pct: Dict[int, int] = {}
    completed: Dict[int, bool] = {}
    started: Dict[int, bool] = {}
    for course in courses:
        cid = course.id
        is_started = (
            cid in resume or (summary.get(cid) or 0) > 0 or cid in progress_course_ids
        )
        started[cid] = is_started
        try:
            amount = float(course.amount or 0)
        except (TypeError, ValueError):
            amount = 0
        is_free = amount <= 0
        enrolled[cid] = (cid in paid) or (is_free and is_started)

        chapters = chapters_by_course.get(cid, set())
        done_ch = done_chapters_by_course.get(cid, set())

        if cid in cert:
            completed[cid] = True
        elif not chapters:
            completed[cid] = (summary.get(cid) or 0) >= 100
        else:
            completed[cid] = len(done_ch & chapters) >= len(chapters)

        if cid in cert:
            progress_pct[cid] = 100
        elif cid in summary and summary.get(cid) is not None:
            progress_pct[cid] = int(summary.get(cid) or 0)
        elif not chapters:
            progress_pct[cid] = 0
        else:
            progress_pct[cid] = int((len(done_ch & chapters) / len(chapters)) * 100)

    return {
        "enrolled": enrolled,
        "progress_pct": progress_pct,
        "completed": completed,
        "started": started,
    }


def build_student_skilllab_dashboard_items(user) -> List[Dict[str, Any]]:
    from django.core.cache import cache

    uid = int(getattr(user, "id", 0) or 0)
    cache_key = f"{_SKILLLAB_DASH_CACHE_PREFIX}{uid}" if uid else None
    if cache_key:
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

    courses = list(skilllab_dashboard_courses_for_user(user))
    if courses:
        status = _bulk_skilllab_status(user, courses)
        items = [
            build_skilllab_dashboard_item(
                user,
                course,
                enrolled=status["enrolled"].get(course.id, False),
                progress_pct=status["progress_pct"].get(course.id, 0),
                completed=status["completed"].get(course.id, False),
                started=status["started"].get(course.id, False),
            )
            for course in courses
        ]
    else:
        items = []
    if items or not skilllab_is_career_readiness_grade_student(user):
        if cache_key:
            try:
                cache.set(cache_key, items, _SKILLLAB_DASH_CACHE_TTL)
            except Exception:
                pass
        return items

    eligible_count = skilllab_eligible_course_count(user)
    if eligible_count <= 0:
        if cache_key:
            try:
                cache.set(cache_key, items, _SKILLLAB_DASH_CACHE_TTL)
            except Exception:
                pass
        return items

    items = [
        {
            "kind": "skilllab",
            "kind_badge": "CAREER",
            "title": SKILLLAB_SECTION_TITLE,
            "subtitle": f"{eligible_count} courses for your class — choose one or more to start",
            "start_url": reverse("skilllabcourse:skilllabcourselist"),
            "action_label": "Browse courses",
            "action_variant": "start",
            "hide_progress": True,
            "icon_src": "images_new/icons/skill-labs-cion.png",
            "icon_bg": "#eef6ff",
        }
    ]
    if cache_key:
        try:
            cache.set(cache_key, items, _SKILLLAB_DASH_CACHE_TTL)
        except Exception:
            pass
    return items


def skilllab_student_status(user, course) -> Dict[str, Any]:
    """Per-student fields for parent catalog cards."""
    enrolled = skilllab_course_enrolled(user, course)
    started = course.user_has_started(user)
    completed = skilllab_course_completed(user, course)
    progress_pct = skilllab_course_progress_pct(user, course)
    cta = skilllab_course_cta(user, course, enrolled=enrolled)
    return {
        "enrolled": enrolled,
        "started": started,
        "completed": completed,
        "progress_pct": progress_pct,
        "cta": cta,
        "start_url": skilllab_course_resume_url(course) if cta == "Resume" else skilllab_course_start_url(course),
        "certificate_url": skilllab_course_certificate_url(course) if completed else "",
        "view_course_url": skilllab_course_resume_url(course) if completed else "",
        "detail_url": skilllab_course_detail_url(course),
    }


def skilllab_course_student_user_ids(course_id: int, *, include_deleted: bool = False) -> Set[int]:
    """Distinct user IDs with progress summary for a Skill Lab course."""
    from skilllab.models import SkillLabCourseProgressSummary

    qs = SkillLabCourseProgressSummary.objects
    if include_deleted:
        qs = qs.complete()
    user_ids = qs.filter(skilllab_course_id=course_id).values_list("user_id", flat=True)
    return {uid for uid in user_ids if uid}


def skilllab_course_student_counts_bulk(course_ids: List[int]) -> Dict[int, Dict[str, int]]:
    """Return {course_id: {"active": N, "deleted": M}} for admin list display."""
    from collections import defaultdict

    from skilllab.models import SkillLabCourseProgressSummary

    if not course_ids:
        return {}

    active_by_course: Dict[int, Set[int]] = defaultdict(set)
    deleted_by_course: Dict[int, Set[int]] = defaultdict(set)
    id_set = set(course_ids)

    rows = (
        SkillLabCourseProgressSummary.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id", "object_status")
    )
    for course_id, user_id, object_status in rows:
        if not user_id:
            continue
        if object_status == choices.ObjectStatus.DELETED:
            deleted_by_course[course_id].add(user_id)
        elif object_status == choices.ObjectStatus.ACTIVE:
            active_by_course[course_id].add(user_id)

    return {
        cid: {
            "active": len(active_by_course.get(cid, set())),
            "deleted": len(deleted_by_course.get(cid, set())),
        }
        for cid in course_ids
    }
