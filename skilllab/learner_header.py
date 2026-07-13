"""Context helpers for Skill Lab course headers (category, class, learner info)."""
from __future__ import annotations

from typing import Any, Dict

from users.parent_student_insights import resolve_student_grade


def skilllab_course_queryset():
    from skilllab.models import SkillLabCourse

    return SkillLabCourse.objects.select_related("topic_category").prefetch_related("grades")


def build_skilllab_learner_context(user) -> Dict[str, Any]:
    if not user or not getattr(user, "is_authenticated", False) or not user.is_authenticated:
        return {
            "learner_logged_in": False,
            "learner_name": "",
            "learner_school": "",
            "learner_class": "",
        }

    name = (getattr(user, "name", None) or "").strip()
    if not name:
        name = (getattr(user, "email", None) or "").strip()

    school = ""
    try:
        profile = getattr(user, "user_profile", None)
        if profile and getattr(profile, "schoolname", None):
            school = str(profile.schoolname).strip()
    except Exception:
        pass

    _, grade_label = resolve_student_grade(user)
    learner_class = grade_label if grade_label != "Grade not set" else ""

    return {
        "learner_logged_in": True,
        "learner_name": name,
        "learner_school": school,
        "learner_class": learner_class,
    }


def build_skilllab_course_meta_context(course) -> Dict[str, str]:
    return {
        "course_topic_category": course.get_topic_category_display(),
        "course_grade_label": course.get_grade_label(),
    }


def related_skilllab_courses(course, *, limit: int = 3):
    """Courses with the same class grades; prefer same topic category.

    Uses Grades M2M (e.g. Class 11–12), not legacy audience ``category``.
    """
    from skilllab.models import SkillLabCourse

    grade_nums = course.get_grade_numbers()
    topic_id = getattr(course, "topic_category_id", None)
    others = list(
        SkillLabCourse.objects.exclude(pk=course.pk)
        .select_related("topic_category")
        .prefetch_related("grades")
        .order_by("-modified")
    )
    if not grade_nums:
        # No class set — fall back to same topic category only.
        if topic_id:
            return [c for c in others if c.topic_category_id == topic_id][:limit]
        return others[:limit]

    same_class = [c for c in others if c.get_grade_numbers() == grade_nums]
    if topic_id:
        same_class.sort(key=lambda c: (0 if c.topic_category_id == topic_id else 1, c.name or ""))
    return same_class[:limit]


def enrich_skilllab_header_context(ctx: dict, request, course=None) -> dict:
    ctx.update(build_skilllab_learner_context(request.user))
    if course is not None:
        ctx.update(build_skilllab_course_meta_context(course))
    return ctx
