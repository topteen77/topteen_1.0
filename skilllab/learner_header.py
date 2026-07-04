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


def enrich_skilllab_header_context(ctx: dict, request, course=None) -> dict:
    ctx.update(build_skilllab_learner_context(request.user))
    if course is not None:
        ctx.update(build_skilllab_course_meta_context(course))
    return ctx
