"""Build parent-dashboard payloads from real student profile / test / hub data."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from django.urls import reverse

from core import choices
from core.student_psychometric_metrics import (
    legacy_complete_user_ids,
    post_matric_complete_user_ids,
    psychometric_complete_user_ids,
)


def _extract_grade_number(student) -> Optional[int]:
    """Numeric class from the student's latest profile (UserProfile, then institute record)."""
    grade_raw = ""
    try:
        if getattr(student, "user_profile", None) and getattr(student.user_profile, "grade", None):
            grade_raw = str(student.user_profile.grade).strip()
    except Exception:
        grade_raw = ""

    if not grade_raw:
        try:
            sm = student.student_management.last()
            if sm and getattr(sm, "class_and_section", None):
                cs = sm.class_and_section
                class_name = getattr(cs, "class_and_section", None) or str(cs)
                grade_raw = str(class_name).strip()
        except Exception:
            grade_raw = ""

    nums = re.findall(r"\d+", grade_raw)
    if nums:
        return int(nums[0])
    lowered = grade_raw.lower()
    if lowered.startswith("12"):
        return 12
    if lowered.startswith("10"):
        return 10
    return None


def resolve_assessment_track(student) -> str:
    """Class 10 → Stream Sorter; Class 11+ → Career Direction (matches student dashboard)."""
    grade_number = _extract_grade_number(student)
    if grade_number is not None:
        return "12" if grade_number >= 11 else "10"
    return "10"


def resolve_student_grade(student) -> Tuple[str, str]:
    """Return (assessment_track_bucket, display_label) e.g. ('10', 'Class 10')."""
    grade_number = _extract_grade_number(student)
    if grade_number is not None:
        track = "12" if grade_number >= 11 else "10"
        return track, f"Class {grade_number}"
    return "10", "Grade not set"


def _central_test_result_url(student) -> str:
    try:
        from psychometric_tests.models import CentralTestCandidate

        ctc = CentralTestCandidate.objects.filter(user=student).first()
        if not ctc:
            return ""
        test = ctc.candidate_test.last()
        if not test or getattr(test, "is_success", None) != choices.YesNoChoices.YES:
            return ""
        if not getattr(test, "psychometric_test_results", None):
            return ""
        return test.get_pyschometric_test_result_url() or ""
    except Exception:
        return ""


def get_student_results_url(student) -> str:
    """Parent-safe results URL — uses parents_student_results gateway when any track has reports."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid:
        return ""
    track_complete = (
        sid in legacy_complete_user_ids([sid])
        or sid in post_matric_complete_user_ids([sid])
    )
    central_url = _central_test_result_url(student)
    if track_complete or central_url:
        return reverse("parents_student_results", args=[sid])
    return ""


def student_has_class10_assessment(student) -> bool:
    """True when the student has taken or purchased the Class 10 (Stream Sorter) assessment."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid:
        return False
    try:
        from app.models import Results, TestCompletion
        from psychometric_tests.models import PsychometricTestPayment

        if Results.objects.filter(user=student).exists():
            return True
        tc = TestCompletion.objects.filter(user=student).first()
        if tc and any(
            [
                bool(tc.test1_complete),
                bool(tc.test2_complete),
                bool(tc.test3_complete),
            ]
        ):
            return True
        if PsychometricTestPayment.objects.filter(
            user=student,
            test_type=choices.PsychometricTestType.BASIC,
            is_success=choices.YesNoChoices.YES,
        ).exists():
            return True
    except Exception:
        pass
    return False


def student_has_class12_assessment(student) -> bool:
    """True when the student has taken or purchased the Class 12 (Career Direction) assessment."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid:
        return False
    try:
        from app_post_matric.models import TestSession
        from psychometric_tests.models import PsychometricTestPayment

        if TestSession.objects.filter(user=student).exists():
            return True
        if PsychometricTestPayment.objects.filter(
            user=student,
            test_type=choices.PsychometricTestType.ADVANCED,
            is_success=choices.YesNoChoices.YES,
        ).exists():
            return True
    except Exception:
        pass
    return False


def resolve_stream_sorter_report_url(student, *, for_self: bool = True) -> str:
    """Psychometric report URL for Stream Sorter (Class 10)."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid or not student_has_class10_assessment(student):
        return ""
    try:
        if sid in legacy_complete_user_ids([sid]):
            from app.models import TestCompletion

            tc = TestCompletion.objects.filter(user=student).first()
            if tc and tc.test1_complete and tc.test2_complete and tc.test3_complete:
                all_subtests = (
                    tc.numerical_complete
                    and tc.verbal_complete
                    and tc.logical_complete
                    and tc.emotional_complete
                    and tc.machanical_complete
                    and tc.language_complete
                    and tc.spatial_complete
                )
                if all_subtests:
                    if for_self:
                        return reverse("app:dashboard")
                    return reverse("app:dashboard_for_user", args=[sid])
        return reverse("app:test_buttons")
    except Exception:
        return reverse("app:test_buttons")


def resolve_career_direction_report_url(student, *, for_self: bool = True) -> str:
    """Psychometric report URL for Career Direction (Class 12)."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid or not student_has_class12_assessment(student):
        return ""
    try:
        if sid in post_matric_complete_user_ids([sid]):
            return reverse("post_matric:combined_report", kwargs={"user_id": sid})
        return reverse("post_matric:tests")
    except Exception:
        return reverse("post_matric:tests")


def _class10_test_steps(student) -> List[Dict[str, Any]]:
    from app.models import TestCompletion

    labels = [
        ("Personality", "test1_complete"),
        ("Career Interest", "test2_complete"),
        ("Intelligence", "test3_complete"),
    ]
    tc = TestCompletion.objects.filter(user=student).first()
    steps = []
    for label, attr in labels:
        done = bool(tc and getattr(tc, attr, False))
        steps.append({"label": label, "percent": 100 if done else 0, "complete": done})
    return steps


def _class12_test_steps(student) -> List[Dict[str, Any]]:
    from app_post_matric.models import TestSession

    names = {
        1: "Career Motivation",
        2: "Career Interest",
        3: "Aptitude",
        4: "Personality",
    }
    steps = []
    for tid in range(1, 5):
        done = TestSession.objects.filter(user=student, test_id=tid, is_completed=True).exists()
        steps.append(
            {
                "label": names.get(tid, f"Test {tid}"),
                "percent": 100 if done else 0,
                "complete": done,
            }
        )
    return steps


def _class10_psychometric_bars(student) -> List[Dict[str, Any]]:
    from app.models import Results

    bars: List[Dict[str, Any]] = []
    try:
        t1 = Results.objects.filter(user=student, test_paper="test1").first()
        if t1 and t1.results:
            top = max(t1.results.items(), key=lambda x: x[1], default=(None, 0))
            if top[0]:
                pct = max(0, min(100, int(round(float(top[1])))))
                bars.append({"label": "Personality", "percent": pct, "hint": str(top[0]).title()})
    except Exception:
        pass
    try:
        t2 = Results.objects.filter(user=student, test_paper="test2").first()
        if t2 and t2.scores:
            top = max(t2.scores.items(), key=lambda x: x[1], default=(None, 0))
            total = sum(t2.scores.values()) or 1
            pct = max(0, min(100, int(round(100 * float(top[1]) / total))))
            bars.append({"label": "Career Interest", "percent": pct, "hint": str(top[0]).title() if top[0] else ""})
    except Exception:
        pass
    try:
        t3 = Results.objects.filter(user=student, test_paper="test3").first()
        if t3 and t3.scores:
            top = max(t3.scores.items(), key=lambda x: x[1], default=(None, 0))
            pct = max(0, min(100, int(round(float(top[1])))))
            bars.append({"label": "Intelligence", "percent": pct, "hint": str(top[0]).replace("_", " ").title() if top[0] else ""})
    except Exception:
        pass
    return bars


def _central_riasec_bars(student) -> List[Dict[str, Any]]:
    from users.parent_dashboard_ai import interest_scores_from_test_result

    try:
        from psychometric_tests.models import CentralTestCandidate

        ctc = CentralTestCandidate.objects.filter(user=student).first()
        if not ctc:
            return []
        test = ctc.candidate_test.last()
        ptr = getattr(test, "psychometric_test_results", None) if test else None
        scores = interest_scores_from_test_result(ptr)
        if not scores:
            return []
        items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:6]
        max_score = max(v for _, v in items) or 1
        return [
            {
                "label": k.replace("_", " ").title(),
                "percent": max(0, min(100, int(round(100 * v / max_score)))),
                "hint": f"{int(round(v))} pts",
            }
            for k, v in items
        ]
    except Exception:
        return []


def get_pathway_dimensions(student) -> Dict[str, int]:
    from users.views import _hub_nav_counts

    hub = _hub_nav_counts(student)
    try:
        profile = max(0, min(100, int(student.get_profile_completion_percentage() or 0)))
    except Exception:
        profile = 0
    resume_sections = int(hub.get("hub_resume_sections") or 0)
    shortlist = int(hub.get("hub_shortlist_count") or 0)
    notes = int(hub.get("hub_notes_count") or 0)
    dim_resume = min(resume_sections * 8, 100)
    dim_college = min(shortlist * 10, 100)
    dim_notes = min(notes * 10, 100)
    readiness = int(round(profile * 0.5 + dim_resume * 0.3 + dim_college * 0.2))
    return {
        "profile": profile,
        "resume": dim_resume,
        "college": dim_college,
        "notes": dim_notes,
        "readiness": max(0, min(100, readiness)),
    }


def get_engagement_stats(student) -> Dict[str, Any]:
    try:
        from core.dashboard_stats import get_student_dashboard_stats

        return get_student_dashboard_stats(student)
    except Exception:
        return {
            "trophies_unlocked": 0,
            "total_points": 0,
            "streak_days": 0,
            "current_level": "Rookie",
            "level_progress_percent": 0,
        }


def build_student_dashboard_basic(student) -> Dict[str, Any]:
    """Lightweight payload for the parent dashboard student switcher.

    Only computes the fields the dashboard frontend actually renders
    (name / email / mobile / class / grade). Avoids the heavy assessment,
    pathway, engagement and AI-insight computations in build_student_insights.
    """
    sid = int(getattr(student, "id", 0) or 0)
    bucket, grade_label = resolve_student_grade(student)
    grade_number = _extract_grade_number(student)
    class_display = (
        str(grade_number)
        if grade_number is not None
        else (grade_label.replace("Class ", "").strip() or "—")
    )
    student_mobile = getattr(student, "mobile", None) or ""
    if not student_mobile:
        try:
            if getattr(student, "user_profile", None):
                student_mobile = getattr(student.user_profile, "mobile", None) or ""
        except Exception:
            student_mobile = ""
    return {
        "id": sid,
        "name": getattr(student, "name", "") or "Student",
        "email": getattr(student, "email", "") or "",
        "mobile": student_mobile or "—",
        "class_display": class_display,
        "grade_label": grade_label,
        "grade_bucket": bucket,
    }


def build_student_insights(student, request=None) -> Dict[str, Any]:
    """Single-student payload for parent dashboard JS."""
    assessment_track = resolve_assessment_track(student)
    bucket, grade_label = resolve_student_grade(student)
    sid = int(getattr(student, "id", 0) or 0)
    legacy_complete = sid in legacy_complete_user_ids([sid])
    post_matric_complete = sid in post_matric_complete_user_ids([sid])
    central_url = _central_test_result_url(student)
    track_complete = legacy_complete or post_matric_complete
    results_enabled = bool(track_complete or central_url)

    if assessment_track == "12":
        test_steps = _class12_test_steps(student)
        test_name = "Career Direction"
        psychometric_bars = []
    else:
        test_steps = _class10_test_steps(student)
        test_name = "Stream Sorter"
        psychometric_bars = _class10_psychometric_bars(student)

    if not psychometric_bars:
        riasec = _central_riasec_bars(student)
        if riasec:
            psychometric_bars = riasec
            test_name = "RIASEC Assessment"

    if test_steps:
        done = sum(1 for s in test_steps if s.get("complete"))
        completion_percent = int(round(100 * done / len(test_steps)))
    elif results_enabled:
        completion_percent = 100
    else:
        completion_percent = 0

    pathway = get_pathway_dimensions(student)
    engagement = get_engagement_stats(student)
    results_url = get_student_results_url(student) if results_enabled else ""

    status_label = "Completed" if results_enabled else (
        "In progress" if completion_percent > 0 else "Not started"
    )

    report_payload = build_student_test_reports(student)

    student_mobile = getattr(student, "mobile", None) or ""
    if not student_mobile:
        try:
            if getattr(student, "user_profile", None):
                student_mobile = getattr(student.user_profile, "mobile", None) or ""
        except Exception:
            student_mobile = ""
    grade_number = _extract_grade_number(student)
    class_display = str(grade_number) if grade_number is not None else (grade_label.replace("Class ", "").strip() or "—")

    has10 = student_has_class10_assessment(student)
    has12 = student_has_class12_assessment(student)
    if has10 and has12:
        track_label = "Stream Sorter · Class 10 and Career Direction · Class 12"
    elif has12:
        track_label = "Career Direction · Class 12"
    else:
        track_label = "Stream Sorter · Class 10"

    return {
        "id": sid,
        "name": getattr(student, "name", "") or "Student",
        "email": getattr(student, "email", "") or "",
        "mobile": student_mobile or "—",
        "class_display": class_display,
        "grade_label": grade_label,
        "grade_bucket": bucket,
        "assessment_track": assessment_track,
        "assessment_track_label": track_label,
        "test_name": test_name,
        "results_enabled": results_enabled,
        "results_url": results_url or report_payload.get("primary_url", ""),
        "test_reports": report_payload.get("groups", []),
        "test_reports_primary_url": report_payload.get("primary_url", ""),
        "has_test_reports": report_payload.get("has_reports", False),
        "test_report_count": report_payload.get("report_count", 0),
        "psychometric_completion_percent": completion_percent if not results_enabled else 100,
        "psychometric_status_label": status_label,
        "test_steps": test_steps,
        "psychometric_bars": psychometric_bars,
        "pathway": pathway,
        "engagement": {
            "trophies": engagement.get("trophies_unlocked", 0),
            "points": engagement.get("total_points", 0),
            "streak_days": engagement.get("streak_days", 0),
            "level": engagement.get("current_level", "Rookie"),
            "level_progress": engagement.get("level_progress_percent", 0),
        },
        "career_readiness": pathway["readiness"],
        "dashboard_url": reverse("parents_student_dashboard", args=[sid]),
        "profile_url": reverse("parents_student_view_profile", args=[sid]),
        "careers_explore_url": reverse("careers:career") + f"?student_id={sid}",
        "careers_shortlist_url": reverse("parents_careers"),
        "legacy_complete": legacy_complete,
        "post_matric_complete": post_matric_complete,
        "central_report_available": bool(central_url),
    }


def parent_can_view_student_reports(viewer, student) -> bool:
    """True when viewer is the student or a linked parent."""
    if not viewer or not student:
        return False
    if getattr(viewer, "id", None) == getattr(student, "id", None):
        return True
    if getattr(viewer, "user_type", None) != choices.UserType.PARENT:
        return False
    try:
        from users.models import ParentStudentLink

        return ParentStudentLink.objects.filter(parent=viewer, student=student).exists()
    except Exception:
        return False


def build_student_test_reports(student) -> Dict[str, Any]:
    """Individual + combined psychometric reports for the student's current class track."""
    sid = int(getattr(student, "id", 0) or 0)
    if not sid:
        return {"groups": [], "primary_url": "", "has_reports": False, "report_count": 0}

    assessment_track = resolve_assessment_track(student)
    groups: List[Dict[str, Any]] = []

    def _item(label: str, url: str, *, is_combined: bool = False) -> Dict[str, Any]:
        return {"label": label, "url": url, "ready": True, "is_combined": is_combined}

    class10_reports: List[Dict[str, Any]] = []
    if student_has_class10_assessment(student):
        try:
            from app.models import Results

            if Results.objects.filter(user=student, test_paper="test1").exists():
                class10_reports.append(_item("Personality", reverse("app:test1_report_html", args=[sid])))
            if Results.objects.filter(user=student, test_paper="test2").exists():
                class10_reports.append(_item("Career Interest", reverse("app:test2_report_html", args=[sid])))
            if Results.objects.filter(user=student, test_paper="test3").exists():
                class10_reports.append(_item("Intelligence (Aptitude)", reverse("app:test3_report_html", args=[sid])))
            if len(class10_reports) >= 3:
                class10_reports.append(
                    _item(
                        "Psychometric dashboard",
                        reverse("app:dashboard_for_user", args=[sid]),
                        is_combined=True,
                    )
                )
        except Exception:
            pass
        if class10_reports:
            groups.append({"label": "Stream Sorter · Class 10", "reports": class10_reports})

    class12_reports: List[Dict[str, Any]] = []
    if student_has_class12_assessment(student):
        try:
            from app_post_matric.models import TestSession

            names = {1: "Career Motivation", 2: "Career Interest", 3: "Aptitude", 4: "Personality"}
            completed = {
                tid: TestSession.objects.filter(user=student, test_id=tid, is_completed=True).exists()
                for tid in range(1, 5)
            }
            for tid, label in names.items():
                if completed.get(tid):
                    class12_reports.append(
                        _item(label, f"{reverse('post_matric:results')}?test_id={tid}&user_id={sid}")
                    )
            if all(completed.values()):
                class12_reports.append(
                    _item("Combined report", reverse("post_matric:combined_report", args=[sid]), is_combined=True)
                )
        except Exception:
            pass
        if class12_reports:
            groups.append({"label": "Career Direction · Class 12", "reports": class12_reports})

    central_url = _central_test_result_url(student)
    if central_url:
        groups.append({"label": "RIASEC Assessment", "reports": [_item("Assessment report", central_url)]})

    other_reports: List[Dict[str, Any]] = []
    try:
        from core.models import EQAssessmentResult, MIAssessmentResult

        if MIAssessmentResult.objects.filter(user=student).exists():
            other_reports.append(
                _item("Multiple Intelligence", f"{reverse('core:mi_report_pdf_user', args=[sid])}?inline=1")
            )
        if EQAssessmentResult.objects.filter(user=student).exists():
            other_reports.append(
                _item("Emotional Intelligence", f"{reverse('core:eq_report_pdf_user', args=[sid])}?inline=1")
            )
    except Exception:
        pass
    if other_reports:
        groups.append({"label": "Other assessments", "reports": other_reports})

    ordered = groups
    flat = [r for g in ordered for r in g.get("reports", [])]
    primary_url = ""
    for r in flat:
        if r.get("is_combined"):
            primary_url = r.get("url") or ""
            break
    if not primary_url and flat:
        primary_url = flat[-1].get("url", "")

    return {
        "groups": ordered,
        "primary_url": primary_url,
        "has_reports": bool(flat),
        "report_count": len(flat),
    }


def resolve_parent_student_report_redirect(student):
    """Target URL for ParentStudentPsychometricResultView — uses current class track."""
    sid = int(getattr(student, "id", 0) or 0)
    assessment_track = resolve_assessment_track(student)
    if assessment_track == "12" and sid in post_matric_complete_user_ids([sid]):
        return reverse("post_matric:combined_report", kwargs={"user_id": sid})
    if assessment_track == "10" and sid in legacy_complete_user_ids([sid]):
        return reverse("app:dashboard_for_user", kwargs={"user_id": sid})
    central = _central_test_result_url(student)
    if central and central != "#":
        return central
    return ""


def _map_domain_to_careers(label: str) -> List[str]:
    d = (label or "").lower()
    if any(x in d for x in ("analyt", "logic", "numer", "math", "intelligence")):
        return ["Data Scientist", "Software Engineer", "Actuary"]
    if any(x in d for x in ("creative", "design", "art")):
        return ["UI/UX Designer", "Architect", "Content Strategist"]
    if any(x in d for x in ("lead", "social", "communication", "personality")):
        return ["Business Manager", "Law Professional", "Public Relations Specialist"]
    if any(x in d for x in ("science", "research", "bio", "interest")):
        return ["Medical Researcher", "Biotechnologist", "Clinical Psychologist"]
    return []


def _resolve_career_detail_url(title: str, explore_fallback: str = "") -> str:
    from careers.models import Career

    t = (title or "").strip()
    if not t:
        return explore_fallback or "#"
    qs = Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)
    career = qs.filter(name__iexact=t).first()
    if not career:
        career = qs.filter(name__icontains=t).order_by("name").first()
    if not career and " " in t:
        career = qs.filter(name__icontains=t.split()[0]).order_by("name").first()
    if career:
        try:
            return career.url()
        except Exception:
            pass
    return explore_fallback or "#"


def build_career_suggestions_with_urls(
    *,
    career_paths: List[str],
    psychometric_bars: List[Dict[str, Any]],
    explore_url: str = "",
    limit: int = 4,
) -> List[Dict[str, str]]:
    """Psychometric career cards for parent dashboard — each links to a career detail when possible."""
    titles: List[Tuple[str, str]] = []
    seen: set = set()
    for name in career_paths or []:
        t = str(name).strip()
        key = t.lower()
        if t and key not in seen:
            titles.append((t, "Suggested from psychometric profile."))
            seen.add(key)
            if len(titles) >= limit:
                break
    if not titles and psychometric_bars:
        for bar in psychometric_bars[:3]:
            label = str(bar.get("label") or "")
            percent = int(bar.get("percent") or 0)
            for career in _map_domain_to_careers(label):
                key = career.lower()
                if key not in seen:
                    titles.append((career, f"Strong {label or 'score'} ({percent}%)."))
                    seen.add(key)
                    if len(titles) >= limit:
                        break
            if len(titles) >= limit:
                break
    return [
        {
            "title": title,
            "reason": reason,
            "url": _resolve_career_detail_url(title, explore_url),
        }
        for title, reason in titles[:limit]
    ]


def render_parent_assessment_report_html(request, student) -> str:
    """Inline assessment report HTML for the parent dashboard (no iframe)."""
    from django.template.loader import render_to_string

    sid = int(getattr(student, "id", 0) or 0)
    if not sid:
        return ""

    track = resolve_assessment_track(student)

    if track == "12" and sid in post_matric_complete_user_ids([sid]):
        from app_post_matric.views import build_combined_report_context

        ctx = build_combined_report_context(request, student)
        if ctx.get("no_results"):
            return ""
        ctx.update(
            {
                "embed_mode": True,
                "parent_inline_mode": True,
                "viewing_student_report": True,
            }
        )
        return render_to_string(
            "template20/parents/includes/parent_assessment_report_inline.html",
            ctx,
            request=request,
        )

    if sid in legacy_complete_user_ids([sid]):
        from app.psychometric_dashboard_context import build_psychometric_dashboard_context

        ctx = build_psychometric_dashboard_context(
            request,
            student,
            embed_mode=True,
        )
        ctx.update(
            {
                "embed_mode": True,
                "parent_inline_mode": True,
                "report_user_id": sid,
            }
        )
        return render_to_string(
            "template20/parents/includes/parent_class10_assessment_report_inline.html",
            ctx,
            request=request,
        )

    return ""


def parent_assessment_report_empty_html(student) -> str:
    track = resolve_assessment_track(student)
    track_label = (
        "Career Direction (Class 12)"
        if track == "12"
        else "Stream Sorter (Class 10)"
    )
    return (
        '<p class="parent-empty-note mb-0">No '
        + track_label
        + " assessment report is available yet for this student. "
        "Reports appear here once they complete the assessment for their current class.</p>"
    )


def build_parent_loan_form_students_payload(parent) -> List[Dict[str, Any]]:
    """Linked students plus shortlisted colleges/courses for the loan application form."""
    from users.models import ParentStudentLink
    from colleges.models import CollegeShortlist
    from courses.models import CourseShortlist

    linked = ParentStudentLink.objects.filter(parent=parent).select_related("student")
    students = [x.student for x in linked if x.student]
    payload: List[Dict[str, Any]] = []

    for student in students:
        colleges: List[str] = []
        seen_colleges: set = set()
        for row in (
            CollegeShortlist.objects.filter(user=student)
            .select_related("college")
            .order_by("-id")
        ):
            college = row.college
            if not college or not college.id or college.id in seen_colleges:
                continue
            name = (college.name or "").strip()
            if name:
                colleges.append(name)
                seen_colleges.add(college.id)

        courses: List[str] = []
        seen_courses: set = set()
        for row in (
            CourseShortlist.objects.filter(user=student)
            .select_related("course")
            .order_by("-id")
        ):
            course = row.course
            if not course or not course.id or course.id in seen_courses:
                continue
            name = (course.name or "").strip()
            if name:
                courses.append(name)
                seen_courses.add(course.id)

        payload.append(
            {
                "id": int(student.id),
                "name": (getattr(student, "name", None) or "").strip() or "Student",
                "email": getattr(student, "email", None) or "",
                "mobile": getattr(student, "mobile", None) or "",
                "colleges": colleges,
                "courses": courses,
            }
        )

    return payload
