"""Build parent-facing courses & tests catalog (unified, per-student journeys)."""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from core import choices
from core.student_psychometric_metrics import (
    legacy_complete_user_ids,
    post_matric_complete_user_ids,
)
from users.parent_student_insights import resolve_student_grade
from users.skilllab_dashboard import (
    SKILLLAB_SECTION_SUBTITLE,
    SKILLLAB_SECTION_TITLE,
    skilllab_course_eligible_for_student,
)


def _price_label(amount) -> Tuple[str, bool]:
    try:
        val = float(amount or 0)
    except (TypeError, ValueError):
        val = 0
    if val <= 0:
        return "FREE", True
    return f"₹{int(val):,}", False


def _journey_steps(
    *,
    enrolled: bool,
    started: bool,
    completed: bool,
    final_label: str,
) -> List[Dict[str, str]]:
    """Three-step journey. When not enrolled the first step is a clickable action."""
    enrol_state = "done" if enrolled else "action"

    if not enrolled:
        progress_label, progress_state = "Started", "pending"
        cert_state = "pending"
    else:
        if completed:
            progress_label, progress_state = "Completed", "done"
            cert_state = "done"
        elif started:
            progress_label, progress_state = "Started", "active"
            cert_state = "pending"
        else:
            progress_label, progress_state = "Started", "active"
            cert_state = "pending"

    return [
        {"label": "Enroll", "state": enrol_state},
        {"label": progress_label, "state": progress_state},
        {"label": final_label, "state": cert_state},
    ]


def _student_payload(student) -> Dict[str, Any]:
    grade_bucket, grade_label = resolve_student_grade(student)
    return {
        "id": int(getattr(student, "id", 0) or 0),
        "name": getattr(student, "name", "") or "Student",
        "grade_label": grade_label,
        "grade_bucket": grade_bucket,
    }


def _any_eligible(student_data: Dict[str, Any]) -> bool:
    return any(v.get("eligible") for v in student_data.values())


# ---------------------------------------------------------------------------
# Psychometric
# ---------------------------------------------------------------------------

def _psychometric_item(
    *,
    track: str,
    title: str,
    subtitle: str,
    class_label: str,
    amount,
    students: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from psychometric_tests.models import PsychometricTestPayment

    test_type = (
        choices.PsychometricTestType.ADVANCED
        if track == "12"
        else choices.PsychometricTestType.BASIC
    )
    eligible = [s for s in students if s["grade_bucket"] == track]
    eligible_ids = [s["id"] for s in eligible]

    owned_ids = set(
        PsychometricTestPayment.objects.filter(
            user_id__in=eligible_ids,
            test_type=test_type,
            is_success=choices.YesNoChoices.YES,
        ).values_list("user_id", flat=True)
    )

    started_ids: Set[int] = set()
    completed_ids: Set[int] = set()
    if owned_ids:
        owned_list = list(owned_ids)
        if track == "12":
            from app_post_matric.models import TestSession

            completed_ids = post_matric_complete_user_ids(owned_list)
            started_ids = set(
                TestSession.objects.filter(user_id__in=owned_list).values_list(
                    "user_id", flat=True
                )
            )
        else:
            from app.models import Results, TestCompletion

            completed_ids = legacy_complete_user_ids(owned_list)
            started_ids = set(
                Results.objects.filter(user_id__in=owned_list).values_list(
                    "user_id", flat=True
                )
            )
            started_ids.update(
                TestCompletion.objects.filter(user_id__in=owned_list).values_list(
                    "user_id", flat=True
                )
            )

    price_label, is_free = _price_label(amount)
    detail_url = (
        reverse("psychometrictests:PsychometricTest12")
        if track == "12"
        else reverse("psychometrictests:psychometrictest")
    )

    student_data: Dict[str, Any] = {}
    for s in students:
        sid = s["id"]
        if s["grade_bucket"] != track:
            student_data[str(sid)] = {"eligible": False}
            continue
        enrolled = sid in owned_ids
        started = sid in started_ids
        completed = sid in completed_ids
        progress_url = ""
        action_label = "View progress"
        if enrolled:
            if completed:
                # Parent-safe gateway → Stream Sorter / Career Direction report for this student
                progress_url = reverse("parents_student_results", args=[sid])
                action_label = "View report"
            elif track == "12":
                progress_url = reverse("post_matric:tests")
            else:
                progress_url = reverse("app:dashboard_for_user", args=[sid])
        student_data[str(sid)] = {
            "eligible": True,
            "enrolled": enrolled,
            "started": started,
            "completed": completed,
            "progress_url": progress_url,
            "action_label": action_label,
            "steps": _journey_steps(
                enrolled=enrolled,
                started=started,
                completed=completed,
                final_label="Report",
            ),
        }

    return {
        "id": f"psychometric-{track}",
        "kind": "psychometric",
        "enroll_track": track,
        "enroll_slug": "",
        "title": title,
        "subtitle": subtitle,
        "class_label": class_label,
        "price_label": price_label,
        "is_free": is_free,
        "icon_src": "images_new/icons/psychometric.png",
        "icon_bg": "#eef2ff",
        "icon_bx": "",
        "image_url": "",
        "detail_url": detail_url,
        "student_data": student_data,
    }


# ---------------------------------------------------------------------------
# MI / EQ (free assessments)
# ---------------------------------------------------------------------------

def _assessment_item(
    *,
    item_id: str,
    kind: str,
    title: str,
    subtitle: str,
    icon_src: str,
    icon_bg: str,
    detail_url_name: str,
    students: List[Dict[str, Any]],
    result_model,
    report_url_name: str,
) -> Dict[str, Any]:
    student_ids = [s["id"] for s in students]
    done_ids = set(
        result_model.objects.filter(user_id__in=student_ids).values_list(
            "user_id", flat=True
        )
    )

    student_data: Dict[str, Any] = {}
    for s in students:
        sid = s["id"]
        taken = sid in done_ids
        progress_url = ""
        action_label = "View progress"
        if taken:
            progress_url = f"{reverse(report_url_name, args=[sid])}?inline=1"
            action_label = "View report"
        student_data[str(sid)] = {
            "eligible": True,
            "enrolled": taken,
            "started": taken,
            "completed": taken,
            "progress_url": progress_url,
            "action_label": action_label,
            "steps": _journey_steps(
                enrolled=taken,
                started=taken,
                completed=taken,
                final_label="Report",
            ),
        }

    return {
        "id": item_id,
        "kind": kind,
        "enroll_track": "",
        "enroll_slug": "",
        "title": title,
        "subtitle": subtitle,
        "class_label": "All classes",
        "price_label": "FREE",
        "is_free": True,
        "icon_src": icon_src,
        "icon_bg": icon_bg,
        "icon_bx": "",
        "image_url": "",
        "detail_url": reverse(detail_url_name),
        "student_data": student_data,
    }


# ---------------------------------------------------------------------------
# Skill Lab courses
# ---------------------------------------------------------------------------

def _skilllab_started_ids(student_ids, course) -> Set[int]:
    from users.skilllab_dashboard import skilllab_started_user_ids

    return skilllab_started_user_ids(student_ids, course)


def _skilllab_completed_ids(student_ids: List[int], course) -> Set[int]:
    from users.skilllab_dashboard import skilllab_completed_user_ids

    return skilllab_completed_user_ids(student_ids, course)


def _skilllab_owned_ids(student_ids, course, is_free) -> Set[int]:
    from users.skilllab_dashboard import skilllab_owned_user_ids

    return skilllab_owned_user_ids(student_ids, course, is_free)


def _skilllab_items(
    students: List[Dict[str, Any]],
    student_users_by_id: Dict[int, Any],
) -> List[Dict[str, Any]]:
    from skilllab.models import SkillLabCourse
    from users.skilllab_dashboard import (
        bulk_skilllab_status_for_users,
        skilllab_course_eligible_for_student,
        skilllab_cta_from_flags,
        skilllab_course_certificate_url,
        skilllab_course_detail_url,
        skilllab_course_resume_url,
        skilllab_course_start_url,
    )

    courses = list(
        SkillLabCourse.objects.all()
        .select_related("topic_category")
        .prefetch_related("grades")
        .order_by("-modified")
    )
    user_ids = [int(sid) for sid in student_users_by_id.keys()]
    status_by_user = bulk_skilllab_status_for_users(user_ids, courses)

    items: List[Dict[str, Any]] = []
    for course in courses:
        price_label, is_free = _price_label(course.amount)
        class_label = course.get_grade_label()
        category_label = course.get_topic_category_display()
        detail_url = reverse(
            "skilllabcourse:skilllabcoursedetail", args=[course.slug]
        )
        cert_url = skilllab_course_certificate_url(course)
        resume_url = skilllab_course_resume_url(course)
        start_url = skilllab_course_start_url(course)

        student_data: Dict[str, Any] = {}
        for s in students:
            sid = s["id"]
            user = student_users_by_id.get(sid)
            grade_match = bool(
                user and skilllab_course_eligible_for_student(user, course)
            )
            ustatus = status_by_user.get(int(sid), {})
            enrolled = bool(ustatus.get("enrolled", {}).get(course.id, False))
            started = bool(ustatus.get("started", {}).get(course.id, False))
            completed = bool(ustatus.get("completed", {}).get(course.id, False))
            progress_pct = int(ustatus.get("progress_pct", {}).get(course.id, 0) or 0)
            cta = skilllab_cta_from_flags(
                enrolled=enrolled, started=started, completed=completed
            )
            student_data[str(sid)] = {
                "eligible": True,
                "grade_match": grade_match,
                "enrolled": enrolled,
                "started": started,
                "completed": completed,
                "progress_pct": progress_pct,
                "cta": cta,
                "start_url": resume_url if cta == "Resume" else start_url,
                "certificate_url": cert_url if completed else "",
                "student_dashboard_url": reverse("parents_student_dashboard", args=[sid]),
                "steps": _journey_steps(
                    enrolled=enrolled,
                    started=started,
                    completed=completed,
                    final_label="Certificate",
                ),
            }

        items.append(
            {
                "id": f"skilllab-{course.id}",
                "kind": "skilllab",
                "enroll_track": "",
                "enroll_slug": course.slug,
                "title": course.name,
                "subtitle": f"{SKILLLAB_SECTION_TITLE} · {SKILLLAB_SECTION_SUBTITLE}",
                "class_label": class_label,
                "category_label": category_label,
                "price_label": price_label,
                "is_free": is_free,
                "icon_src": None,
                "icon_bx": "bx-book-reader",
                "icon_bg": "#ecfdf3",
                "image_url": course.get_image_url(),
                "image_fallback_url": static("images/skilllab-default.png"),
                "detail_url": detail_url,
                "student_data": student_data,
            }
        )
    return items


def build_parent_skilllab_suggestions(
    students: List[Dict[str, Any]],
    student_users_by_id: Dict[int, Any],
    *,
    preview_limit: int = 4,
) -> Dict[str, Any]:
    """Per-student class-matched course suggestions for the parent dashboard."""
    items = _skilllab_items(students, student_users_by_id)
    by_student: Dict[str, Any] = {}

    for s in students:
        sid = str(s["id"])
        grade_label = s.get("grade_label") or "Your class"
        class_courses: List[Dict[str, Any]] = []

        for item in items:
            sd = item["student_data"].get(sid) or {}
            if not sd.get("eligible") or not sd.get("grade_match"):
                continue
            class_courses.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "subtitle": item.get("subtitle", ""),
                    "detail_url": item["detail_url"],
                    "class_label": item.get("class_label", ""),
                    "category_label": item.get("category_label", ""),
                    "price_label": item.get("price_label", ""),
                    "is_free": item.get("is_free", False),
                    "image_url": item.get("image_url", ""),
                    "cta": sd.get("cta", "Enroll"),
                    "progress_pct": sd.get("progress_pct", 0),
                    "enrolled": sd.get("enrolled", False),
                    "student_dashboard_url": sd.get("student_dashboard_url", ""),
                    "action_url": sd.get("start_url")
                    or sd.get("certificate_url")
                    or item.get("detail_url", ""),
                }
            )

        by_student[sid] = {
            "grade_label": grade_label,
            "class_section_title": f"{grade_label} courses",
            "class_courses": class_courses[:preview_limit],
            "class_total": len(class_courses),
        }

    return by_student


def build_parent_courses_catalog(parent) -> Dict[str, Any]:
    """Unified catalog for parent: Skill Lab courses with per-student journeys.

    Psychometric / MI / EQ assessments are shown on the parent dashboard, not here.
    """
    from users.parent_student_insights import linked_students_for_parent

    raw_students = linked_students_for_parent(parent)
    students = [_student_payload(s) for s in raw_students]
    student_users_by_id = {int(s.id): s for s in raw_students if getattr(s, "id", None)}
    career_courses = _skilllab_items(students, student_users_by_id)

    sections = []
    if career_courses:
        sections.append(
            {
                "key": "career_readiness_class",
                "title": "Class courses",
                "title_dynamic": True,
                "filter": "grade_match",
                "subtitle": "Recommended for your child's class",
                "catalog_items": career_courses,
            }
        )
        sections.append(
            {
                "key": "career_readiness_other",
                "title": "Other class courses",
                "title_dynamic": False,
                "filter": "other",
                "subtitle": "Explore courses from other grade levels",
                "catalog_items": career_courses,
            }
        )

    return {
        "linked_students": students,
        "sections": sections,
        "has_linked_students": bool(students),
    }
