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


def _skilllab_categories_for_grade(grade_bucket: str) -> List[int]:
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


def _infer_class_label_from_name(name: str) -> str:
    low = (name or "").lower()
    if "class 7" in low or "class 8" in low or "class 6" in low:
        return "Class 6–8"
    if "class 9" in low or "class 10" in low or "after 10" in low:
        return "Class 9–10"
    if "class 11" in low or "class 12" in low or "high school" in low:
        return "Class 11–12"
    if "college" in low:
        return "After college"
    return ""


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
        student_data[str(sid)] = {
            "eligible": True,
            "enrolled": enrolled,
            "steps": _journey_steps(
                enrolled=enrolled,
                started=sid in started_ids,
                completed=sid in completed_ids,
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
        student_data[str(sid)] = {
            "eligible": True,
            "enrolled": taken,
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


def _skilllab_completed_ids(student_ids: List[int], course) -> Set[int]:
    if not student_ids:
        return set()
    chapters = list(course.skilllabcoursechapter.values_list("id", flat=True))
    if not chapters:
        return set()

    completed: Set[int] = set()
    for sid in student_ids:
        done_chapters = set(
            course.skilllabcourseprogress.filter(
                user_id=sid, chapter_id__in=chapters, completed=True
            ).values_list("chapter_id", flat=True)
        )
        if len(done_chapters) >= len(chapters):
            completed.add(sid)
    return completed


def _skilllab_owned_ids(student_ids, course, is_free) -> Set[int]:
    from skilllab.models import SkilllabCoursePayment

    paid_ids = set(
        SkilllabCoursePayment.objects.filter(
            user_id__in=student_ids,
            skilllab_course_id=course.id,
            is_success=choices.YesNoChoices.YES,
        ).values_list("user_id", flat=True)
    )
    if is_free:
        return paid_ids | _skilllab_started_ids(student_ids, course)
    return paid_ids


def _skilllab_items(students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from skilllab.models import SkillLabCourse

    all_categories = {
        choices.SkillLabCourseTypeChoice.after_10_class,
        choices.SkillLabCourseTypeChoice.after_12_class,
        choices.SkillLabCourseTypeChoice.BOTH,
        choices.SkillLabCourseTypeChoice.after_college,
    }
    courses = SkillLabCourse.objects.filter(category__in=all_categories).order_by("-modified")
    items: List[Dict[str, Any]] = []

    for course in courses:
        eligible = [
            s
            for s in students
            if course.category in _skilllab_categories_for_grade(s["grade_bucket"])
        ]
        if not eligible:
            continue

        eligible_ids = [s["id"] for s in eligible]
        price_label, is_free = _price_label(course.amount)
        owned_ids = _skilllab_owned_ids(eligible_ids, course, is_free)
        started_ids = _skilllab_started_ids(list(owned_ids), course) if owned_ids else set()
        completed_ids = _skilllab_completed_ids(list(owned_ids), course) if owned_ids else set()

        class_label = _infer_class_label_from_name(course.name)
        if not class_label:
            cat_map = {
                choices.SkillLabCourseTypeChoice.after_10_class: "After Class 10",
                choices.SkillLabCourseTypeChoice.after_12_class: "After Class 12",
                choices.SkillLabCourseTypeChoice.BOTH: "Class 9–12",
                choices.SkillLabCourseTypeChoice.after_college: "After college",
            }
            class_label = cat_map.get(course.category, "Career readiness")

        eligible_id_set = set(eligible_ids)
        student_data: Dict[str, Any] = {}
        for s in students:
            sid = s["id"]
            if sid not in eligible_id_set:
                student_data[str(sid)] = {"eligible": False}
                continue
            enrolled = sid in owned_ids
            student_data[str(sid)] = {
                "eligible": True,
                "enrolled": enrolled,
                "steps": _journey_steps(
                    enrolled=enrolled,
                    started=sid in started_ids,
                    completed=sid in completed_ids,
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
                "subtitle": "Career Readiness · Skill Lab",
                "class_label": class_label,
                "price_label": price_label,
                "is_free": is_free,
                "icon_src": None,
                "icon_bx": "bx-book-reader",
                "icon_bg": "#ecfdf3",
                "image_url": course.get_image_url(),
                "image_fallback_url": static("images/skilllab-default.png"),
                "detail_url": reverse(
                    "skilllabcourse:skilllabcoursedetail", args=[course.slug]
                ),
                "student_data": student_data,
            }
        )
    return items


def build_parent_courses_catalog(parent) -> Dict[str, Any]:
    """Unified catalog for parent: courses/tests with per-student journey data."""
    from users.models import ParentStudentLink
    from core.models import MIAssessmentResult, EQAssessmentResult

    raw_students = [
        link.student
        for link in ParentStudentLink.objects.filter(parent=parent).select_related("student")
        if link.student
    ]
    students = [_student_payload(s) for s in raw_students]

    assessment_candidates = [
        _psychometric_item(
            track="10",
            title="Stream Sorter",
            subtitle="Aptitude & interest assessment for stream selection",
            class_label="Up to Class 10",
            amount=getattr(settings, "STREAM_SORTER_TEST_AMOUNT", 999),
            students=students,
        ),
        _psychometric_item(
            track="12",
            title="Career Direction",
            subtitle="Comprehensive psychometric assessment for senior students",
            class_label="Class 11+",
            amount=getattr(settings, "CAREER_DIRECTION_TEST_AMOUNT", 999),
            students=students,
        ),
        _assessment_item(
            item_id="mi-assessment",
            kind="mi",
            title="Multiple Intelligence",
            subtitle="Discover your child's learning style",
            icon_src="images_new/icons/multiple-intelligence.png",
            icon_bg="#fff4e6",
            detail_url_name="core:multiple_intelligences",
            students=students,
            result_model=MIAssessmentResult,
        ),
        _assessment_item(
            item_id="eq-assessment",
            kind="eq",
            title="Emotional Intelligence",
            subtitle="Understand EQ strengths and growth areas",
            icon_src="images_new/icons/emotions.png",
            icon_bg="#fdf2f8",
            detail_url_name="core:emotional_intelligences",
            students=students,
            result_model=EQAssessmentResult,
        ),
    ]
    assessments = [item for item in assessment_candidates if _any_eligible(item["student_data"])]

    career_courses = _skilllab_items(students)

    sections = []
    if assessments:
        sections.append(
            {
                "key": "assessments",
                "title": "Assessments & Tests",
                "subtitle": "Psychometric, MI, and EQ evaluations",
                "catalog_items": assessments,
            }
        )
    if career_courses:
        sections.append(
            {
                "key": "career_readiness",
                "title": "Career Readiness Courses",
                "subtitle": "Skill-building courses matched to your child's class",
                "catalog_items": career_courses,
            }
        )

    return {
        "linked_students": students,
        "sections": sections,
        "has_linked_students": bool(students),
    }
