"""
Demo-institute engagement journey for marketing follow-up.

Stages (in order):
1. account_created — demo institute exists
2. students — at least one demo student added
3. test_complete — at least one demo student completed a psychometric test
4. report_viewed — at least one demo student's report was opened
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.db.models import Count
from django.utils import timezone

from institute.models import Institute, StudentManagement

STAGE_DEFS = (
    ("account_created", "Account created"),
    ("students", "Demo students added"),
    ("test_complete", "1st psychometric test"),
    ("report_viewed", "Report viewed"),
)


def _demo_student_ids(institute_id: int) -> List[int]:
    return list(
        StudentManagement.objects.filter(
            institute_id=institute_id,
            student__is_demo_account=True,
            student__is_system_demo=False,
        ).values_list("student_id", flat=True)
    )


def _student_ids_with_results(user_ids: Sequence[int]) -> set:
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return set()
    from core.student_psychometric_metrics import psychometric_complete_user_ids
    from app.models import Results
    from psychometric_tests.models import PsychometricTestResult

    done = set(psychometric_complete_user_ids(uids))
    done |= set(
        Results.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct()
    )
    done |= set(
        PsychometricTestResult.objects.filter(
            assessment__central_test_candidate__user_id__in=uids
        ).values_list("assessment__central_test_candidate__user_id", flat=True)
    )
    done |= set(
        PsychometricTestResult.objects.filter(
            assessment__pyschometric_test_payment__user_id__in=uids
        ).values_list("assessment__pyschometric_test_payment__user_id", flat=True)
    )
    try:
        from app_post_matric.models import TestResult

        done |= set(
            TestResult.objects.filter(session__user_id__in=uids).values_list(
                "session__user_id", flat=True
            )
        )
    except Exception:
        pass
    return uids & done


def _student_ids_with_report_viewed(user_ids: Sequence[int]) -> set:
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return set()
    try:
        from institute.demo_report_view_tracking import REPORT_VIEW_EVENT_TYPE
        from user_analytics.models import UserEvent

        return set(
            UserEvent.objects.filter(
                user_id__in=uids,
                event_type=REPORT_VIEW_EVENT_TYPE,
            )
            .values_list("user_id", flat=True)
            .distinct()
        )
    except Exception:
        return set()


def _short_date(dt) -> str:
    if not dt:
        return ""
    try:
        return timezone.localtime(dt).strftime("%d %b")
    except Exception:
        try:
            return dt.strftime("%d %b")
        except Exception:
            return ""


def _first_demo_student_added_at(institute_id: int):
    return (
        StudentManagement.objects.filter(
            institute_id=institute_id,
            student__is_demo_account=True,
            student__is_system_demo=False,
        )
        .order_by("created")
        .values_list("created", flat=True)
        .first()
    )


def _first_test_completed_at(user_ids: Sequence[int]):
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return None
    candidates = []
    try:
        from app.models import Results

        dt = (
            Results.objects.filter(user_id__in=uids)
            .order_by("created")
            .values_list("created", flat=True)
            .first()
        )
        if dt:
            candidates.append(dt)
    except Exception:
        pass
    try:
        from psychometric_tests.models import PsychometricTestResult

        dt = (
            PsychometricTestResult.objects.filter(
                assessment__central_test_candidate__user_id__in=uids
            )
            .order_by("created")
            .values_list("created", flat=True)
            .first()
        )
        if dt:
            candidates.append(dt)
        dt2 = (
            PsychometricTestResult.objects.filter(
                assessment__pyschometric_test_payment__user_id__in=uids
            )
            .order_by("created")
            .values_list("created", flat=True)
            .first()
        )
        if dt2:
            candidates.append(dt2)
    except Exception:
        pass
    try:
        from app_post_matric.models import TestResult

        dt = (
            TestResult.objects.filter(session__user_id__in=uids)
            .order_by("created")
            .values_list("created", flat=True)
            .first()
        )
        if dt:
            candidates.append(dt)
    except Exception:
        pass
    return min(candidates) if candidates else None


def _first_report_viewed_at(user_ids: Sequence[int]):
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return None
    try:
        from institute.demo_report_view_tracking import REPORT_VIEW_EVENT_TYPE
        from user_analytics.models import UserEvent

        return (
            UserEvent.objects.filter(
                user_id__in=uids,
                event_type=REPORT_VIEW_EVENT_TYPE,
            )
            .order_by("created")
            .values_list("created", flat=True)
            .first()
        )
    except Exception:
        return None


def build_demo_institute_journey(institute: Institute) -> Optional[Dict[str, Any]]:
    if not institute or not getattr(institute, "is_demo_institute", False):
        return None
    if getattr(institute, "is_system_demo", False):
        return None

    created_by = getattr(institute, "created_by", None)
    last_login = getattr(created_by, "last_login", None) if created_by else None

    demo_uids = _demo_student_ids(institute.pk) if institute.pk else []
    demo_total = len(demo_uids)
    with_results = _student_ids_with_results(demo_uids) if demo_uids else set()
    with_report = _student_ids_with_report_viewed(demo_uids) if demo_uids else set()
    results_count = len(with_results)
    report_count = len(with_report)

    student_count = int(getattr(institute, "student_count", None) or 0)
    if not student_count and getattr(institute, "pk", None):
        student_count = StudentManagement.objects.filter(institute_id=institute.pk).count()

    created_at = getattr(institute, "created", None)
    students_at = _first_demo_student_added_at(institute.pk) if demo_total else None
    test_at = _first_test_completed_at(demo_uids) if results_count else None
    report_at = _first_report_viewed_at(demo_uids) if report_count else None

    stage_ats = {
        "account_created": created_at,
        "students": students_at,
        "test_complete": test_at,
        "report_viewed": report_at,
    }

    done_flags = {
        "account_created": True,
        "students": demo_total > 0,
        "test_complete": results_count > 0,
        "report_viewed": report_count > 0,
    }

    stages = []
    current_key = "account_created"
    for key, label in STAGE_DEFS:
        done = bool(done_flags.get(key))
        at = stage_ats.get(key) if done else None
        stages.append(
            {
                "key": key,
                "label": label,
                "done": done,
                "at": at,
                "date_short": _short_date(at) if done else "",
            }
        )
        if done:
            current_key = key

    done_n = sum(1 for s in stages if s["done"])
    total_n = len(stages)
    percent = int(round(100.0 * done_n / total_n)) if total_n else 0

    if not done_flags["students"]:
        next_action = "Add demo Class 10 / 12 students."
    elif not done_flags["test_complete"]:
        next_action = "Complete the first psychometric test."
    elif not done_flags["report_viewed"]:
        next_action = "Open and review the student report."
    else:
        next_action = "Ready to convert to paid."

    last_login_display = ""
    if last_login:
        try:
            last_login_display = timezone.localtime(last_login).strftime("%d %b %Y %H:%M")
        except Exception:
            last_login_display = str(last_login)

    created_display = _short_date(created_at)
    if created_at and not created_display:
        try:
            created_display = str(created_at)
        except Exception:
            created_display = ""

    return {
        "stages": stages,
        "current_key": current_key,
        "current_label": dict(STAGE_DEFS).get(current_key, current_key),
        "percent": percent,
        "done_count": done_n,
        "total_count": total_n,
        "student_count": student_count,
        "demo_student_count": demo_total,
        "demo_results_count": results_count,
        "demo_report_viewed_count": report_count,
        "admin_last_login": last_login_display,
        "created_display": created_display,
        "next_action": next_action,
        "followup_note": (getattr(institute, "marketing_followup_note", None) or "").strip(),
        "followup_at": getattr(institute, "marketing_followup_at", None),
        "fully_complete": all(done_flags.values()),
    }


def attach_demo_journeys(institutes: Iterable) -> None:
    """Attach ``_demo_journey`` dict on each demo institute in an iterable / page."""
    items = list(institutes) if not isinstance(institutes, list) else institutes
    for ins in items:
        try:
            journey = build_demo_institute_journey(ins)
        except Exception:
            journey = None
        try:
            ins._demo_journey = journey
        except Exception:
            pass


def build_demo_marketing_performance(group_admin) -> Dict[str, Any]:
    """
    Aggregate funnel stats for demo institutes owned by this marketing admin.
    """
    demos = list(
        Institute.objects.filter(
            marketing_group__marketing_group_admin=group_admin,
            is_demo_institute=True,
            is_system_demo=False,
        )
        .annotate(student_count=Count("student_management"))
        .select_related("created_by", "marketing_group")
        .order_by("-created")
    )
    attach_demo_journeys(demos)

    stage_counts = {key: 0 for key, _ in STAGE_DEFS}
    rows = []
    fully_complete = 0
    for ins in demos:
        j = getattr(ins, "_demo_journey", None) or {}
        for s in j.get("stages") or []:
            if s.get("done"):
                stage_counts[s["key"]] = stage_counts.get(s["key"], 0) + 1
        if j.get("fully_complete"):
            fully_complete += 1
        rows.append(
            {
                "id": ins.id,
                "name": ins.name,
                "slug": ins.slug,
                "created": ins.created,
                "journey": j,
                "student_count": int(getattr(ins, "student_count", 0) or 0),
            }
        )

    total = len(demos)
    funnel = []
    for key, label in STAGE_DEFS:
        n = stage_counts.get(key, 0)
        funnel.append(
            {
                "key": key,
                "label": label,
                "count": n,
                "percent": int(round(100.0 * n / total)) if total else 0,
            }
        )

    return {
        "total_demo_institutes": total,
        "fully_complete": fully_complete,
        "funnel": funnel,
        "rows": rows,
        "stage_defs": [{"key": k, "label": lab} for k, lab in STAGE_DEFS],
    }
