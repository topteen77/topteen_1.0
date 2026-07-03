"""Skill Lab course progress helpers for student and parent dashboards."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from django.templatetags.static import static
from django.urls import reverse

from core import choices
from users.parent_student_insights import _extract_grade_number, resolve_student_grade


SKILLLAB_SECTION_TITLE = "College & Career Readiness"
SKILLLAB_SECTION_SUBTITLE = "Skill Lab"


def skilllab_categories_for_grade(grade_bucket: str) -> List[int]:
    if grade_bucket == "12":
        return [
            choices.SkillLabCourseTypeChoice.after_12_class,
            choices.SkillLabCourseTypeChoice.BOTH,
            choices.SkillLabCourseTypeChoice.after_college,
        ]
    return [
        choices.SkillLabCourseTypeChoice.after_10_class,
        choices.SkillLabCourseTypeChoice.BOTH,
    ]


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
    chapters = list(course.skilllabcoursechapter.values_list("id", flat=True))
    if not chapters:
        completed: Set[int] = set()
        for sid in student_ids:
            summary = course.skilllabcourseprogresssummary.filter(user_id=sid).first()
            if summary and (summary.progress_percentage or 0) >= 100:
                completed.add(sid)
        return completed

    completed = set()
    for sid in student_ids:
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


def skilllab_course_start_url(course) -> str:
    return reverse("skilllabcourse:course_learning", args=[course.slug])


def skilllab_course_certificate_url(course) -> str:
    return reverse("skilllabcourse:skilllab_certificate", args=[course.slug])


def skilllab_course_detail_url(course) -> str:
    return reverse("skilllabcourse:skilllabcoursedetail", args=[course.slug])


def skilllab_course_eligible_for_student(user, course) -> bool:
    """True when the course matches the student's class (uses grades M2M when set)."""
    grade_num = _extract_grade_number(user)
    if grade_num is not None:
        return course.matches_skilllab_filters(grade=grade_num)
    grade_bucket, _ = resolve_student_grade(user)
    grade_bucket = grade_bucket if grade_bucket in ("10", "12") else "10"
    return course.category in skilllab_categories_for_grade(grade_bucket)


def skilllab_is_career_readiness_grade_student(user) -> bool:
    """Class 9–12 (or bucket 10/12 when grade not set) — target audience for this section."""
    grade_num = _extract_grade_number(user)
    if grade_num is not None:
        return grade_num in (9, 10, 11, 12)
    bucket, _ = resolve_student_grade(user)
    return bucket in ("10", "12")


def skilllab_eligible_courses_queryset(user):
    """All College & Career Readiness courses matching the student's class."""
    from skilllab.models import SkillLabCourse

    grade_num = _extract_grade_number(user)
    base = SkillLabCourse.objects.all().order_by("-modified")
    if grade_num is not None:
        matched_ids = set(
            base.filter(grades__grade_number=grade_num).values_list("id", flat=True)
        )
        for course in base.exclude(id__in=matched_ids).iterator():
            if course.matches_skilllab_filters(grade=grade_num):
                matched_ids.add(course.id)
        return base.filter(id__in=matched_ids)

    grade_bucket, _ = resolve_student_grade(user)
    grade_bucket = grade_bucket if grade_bucket in ("10", "12") else "10"
    return base.filter(category__in=skilllab_categories_for_grade(grade_bucket))


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
    return SkillLabCourse.objects.filter(id__in=active_ids).order_by("-modified")


def build_skilllab_dashboard_item(user, course) -> Dict[str, Any]:
    """Card payload for student dashboard «My courses & tests»."""
    enrolled = skilllab_course_enrolled(user, course)
    progress_pct = skilllab_course_progress_pct(user, course)
    cta = skilllab_course_cta(user, course, enrolled=enrolled)
    is_complete = cta == "Completed"

    if is_complete:
        action_url = skilllab_course_certificate_url(course)
        action_variant = "report"
    elif cta == "Enroll":
        action_url = skilllab_course_detail_url(course)
        action_variant = "start"
    else:
        action_url = skilllab_course_start_url(course)
        action_variant = "start"

    return {
        "kind": "skilllab",
        "kind_badge": "CAREER",
        "title": course.name,
        "subtitle": f"{SKILLLAB_SECTION_TITLE} · {SKILLLAB_SECTION_SUBTITLE}",
        "start_url": action_url,
        "action_label": cta,
        "action_variant": action_variant,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
        "certificate_url": skilllab_course_certificate_url(course) if is_complete else "",
        "detail_url": skilllab_course_detail_url(course),
        "image_url": course.get_image_url(),
        "icon_src": "images_new/icons/skill-labs-cion.png",
        "icon_bg": "#eef6ff",
    }


def build_student_skilllab_dashboard_items(user) -> List[Dict[str, Any]]:
    items = [
        build_skilllab_dashboard_item(user, course)
        for course in skilllab_dashboard_courses_for_user(user)
    ]
    if items or not skilllab_is_career_readiness_grade_student(user):
        return items

    eligible_count = skilllab_eligible_courses_queryset(user).count()
    if eligible_count <= 0:
        return items

    return [
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
        "start_url": skilllab_course_start_url(course),
        "certificate_url": skilllab_course_certificate_url(course) if completed else "",
        "detail_url": skilllab_course_detail_url(course),
    }


def skilllab_course_student_user_ids(course_id: int) -> Set[int]:
    """Distinct user IDs with any learning or payment data for a Skill Lab course."""
    from skilllab.models import (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabMCQAttempt,
        SkillLabUserBookmark,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabWorksheetProgress,
        SkilllabCoursePayment,
    )

    user_ids: Set[int] = set()
    user_ids.update(
        SkillLabCourseProgressSummary.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabCourseResume.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabCourseProgress.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserHighlight.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserNote.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserBookmark.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkilllabCoursePayment.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabWorksheetProgress.objects.complete()
        .filter(activity__skilllab_chapter__skilllab_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabMCQAttempt.objects.complete()
        .filter(mcq__skilllab_chapter__skilllab_id=course_id)
        .values_list("user_id", flat=True)
    )
    return {uid for uid in user_ids if uid}


def skilllab_course_student_counts_bulk(course_ids: List[int]) -> Dict[int, int]:
    """Return {course_id: distinct_student_count} for admin list display."""
    from collections import defaultdict

    from skilllab.models import (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabMCQAttempt,
        SkillLabUserBookmark,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabWorksheetProgress,
        SkilllabCoursePayment,
    )

    if not course_ids:
        return {}

    by_course: Dict[int, Set[int]] = defaultdict(set)
    id_set = set(course_ids)

    def _add_pairs(rows):
        for course_id, user_id in rows:
            if course_id in id_set and user_id:
                by_course[course_id].add(user_id)

    _add_pairs(
        SkillLabCourseProgressSummary.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabCourseResume.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabCourseProgress.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabUserHighlight.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabUserNote.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabUserBookmark.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkilllabCoursePayment.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id")
    )
    _add_pairs(
        SkillLabWorksheetProgress.objects.complete()
        .filter(activity__skilllab_chapter__skilllab_id__in=id_set)
        .values_list("activity__skilllab_chapter__skilllab_id", "user_id")
    )
    _add_pairs(
        SkillLabMCQAttempt.objects.complete()
        .filter(mcq__skilllab_chapter__skilllab_id__in=id_set)
        .values_list("mcq__skilllab_chapter__skilllab_id", "user_id")
    )

    return {cid: len(by_course.get(cid, set())) for cid in course_ids}


def skilllab_course_student_user_ids(course_id: int) -> Set[int]:
    """Distinct user IDs with any learning or payment data for a Skill Lab course."""
    from skilllab.models import (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabMCQAttempt,
        SkillLabUserBookmark,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabWorksheetProgress,
        SkilllabCoursePayment,
    )

    user_ids: Set[int] = set()
    user_ids.update(
        SkillLabCourseProgressSummary.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabCourseResume.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabCourseProgress.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserHighlight.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserNote.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabUserBookmark.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkilllabCoursePayment.objects.complete()
        .filter(skilllab_course_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabWorksheetProgress.objects.complete()
        .filter(activity__skilllab_chapter__skilllab_id=course_id)
        .values_list("user_id", flat=True)
    )
    user_ids.update(
        SkillLabMCQAttempt.objects.complete()
        .filter(mcq__skilllab_chapter__skilllab_id=course_id)
        .values_list("user_id", flat=True)
    )
    return {uid for uid in user_ids if uid}


def skilllab_course_student_counts_bulk(course_ids: List[int]) -> Dict[int, int]:
    """Return {course_id: distinct_student_count} for admin list display."""
    from collections import defaultdict

    from skilllab.models import (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabMCQAttempt,
        SkillLabUserBookmark,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabWorksheetProgress,
        SkilllabCoursePayment,
    )

    if not course_ids:
        return {}

    by_course: Dict[int, Set[int]] = defaultdict(set)
    id_set = set(course_ids)

    def _add_pairs(qs, course_field: str):
        for course_id, user_id in qs:
            if course_id in id_set and user_id:
                by_course[course_id].add(user_id)

    _add_pairs(
        SkillLabCourseProgressSummary.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabCourseResume.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabCourseProgress.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabUserHighlight.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabUserNote.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabUserBookmark.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkilllabCoursePayment.objects.complete()
        .filter(skilllab_course_id__in=id_set)
        .values_list("skilllab_course_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabWorksheetProgress.objects.complete()
        .filter(activity__skilllab_chapter__skilllab_id__in=id_set)
        .values_list("activity__skilllab_chapter__skilllab_id", "user_id"),
        "skilllab_course_id",
    )
    _add_pairs(
        SkillLabMCQAttempt.objects.complete()
        .filter(mcq__skilllab_chapter__skilllab_id__in=id_set)
        .values_list("mcq__skilllab_chapter__skilllab_id", "user_id"),
        "skilllab_course_id",
    )

    return {cid: len(by_course.get(cid, set())) for cid in course_ids}
