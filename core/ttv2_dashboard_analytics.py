"""
Shared metrics payload for Template v2 dashboard KPIs + Chart.js (institute, group, marketing, counselor).
All values are JSON-serializable (for |tojson in templates).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.db import models
from django.db.models import Count, Max, Min, Sum, Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from app.models import Results, TestCompletion

from institute.models import Institute
from counselor.models import Counselor, FollowUpStatus


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _followup_session_day_expr():
    """
    Calendar day for session / journey charts. Counselor cards count every FollowUpStatus
    row, but many rows never set `last_follow_up_date`; those were invisible in trends.
    Fall back to the row's created date so totals align with roster session counts.
    """
    return Coalesce(
        "last_follow_up_date",
        TruncDate("created"),
        output_field=models.DateField(),
    )


def _followup_qs_for_session_metrics(base_qs):
    return base_qs.annotate(_ttv2_sess_day=_followup_session_day_expr())


def _week_ranges(num_weeks: int = 4, *, reference_monday: Optional[date] = None) -> List[Tuple[date, date, str]]:
    """Return (start, end, label) for the last `num_weeks` calendar weeks (Mon–Sun), oldest first."""
    today = timezone.now().date()
    this_monday = reference_monday or _monday_of_week(today)
    out: List[Tuple[date, date, str]] = []
    for i in range(num_weeks, 0, -1):
        start = this_monday - timedelta(weeks=i)
        end = start + timedelta(days=6)
        if start.month == end.month:
            label = f"{start.strftime('%b %d')}–{end.day}"
        else:
            label = f"{start.strftime('%b %d')}–{end.strftime('%b %d')}"
        out.append((start, end, label))
    return out


def _followups_in_weeks(
    counselor_ids: Sequence[int],
    num_weeks: int = 4,
    *,
    reference_monday: Optional[date] = None,
    student_management_ids: Optional[Sequence[int]] = None,
) -> Tuple[List[str], List[int], int, int]:
    """Session-like counts from FollowUpStatus by week. Also current & previous week totals."""
    ids = [int(x) for x in counselor_ids if x]
    sm_ids = [int(x) for x in (student_management_ids or []) if x]
    if not ids and not sm_ids:
        return [], [], 0, 0

    base_qs = FollowUpStatus.objects.all()
    if ids and sm_ids:
        base_qs = base_qs.filter(Q(counselor_id__in=ids) | Q(student_id__in=sm_ids))
    elif ids:
        base_qs = base_qs.filter(counselor_id__in=ids)
    else:
        base_qs = base_qs.filter(student_id__in=sm_ids)

    base_qs = _followup_qs_for_session_metrics(base_qs)
    ranges = _week_ranges(num_weeks, reference_monday=reference_monday)
    labels = [r[2] for r in ranges]
    values: List[int] = []
    for start, end, _ in ranges:
        c = base_qs.filter(
            _ttv2_sess_day__gte=start,
            _ttv2_sess_day__lte=end,
        ).count()
        values.append(c)
    this_monday = reference_monday or _monday_of_week(timezone.now().date())
    w0_start, w0_end = this_monday, this_monday + timedelta(days=6)
    w1_start, w1_end = this_monday - timedelta(days=7), this_monday - timedelta(days=1)
    cur = base_qs.filter(
        _ttv2_sess_day__gte=w0_start,
        _ttv2_sess_day__lte=w0_end,
    ).count()
    prev = base_qs.filter(
        _ttv2_sess_day__gte=w1_start,
        _ttv2_sess_day__lte=w1_end,
    ).count()
    return labels, values, cur, prev


def _followups_in_date_range(
    counselor_ids: Sequence[int],
    *,
    start_date: date,
    end_date: date,
    student_management_ids: Optional[Sequence[int]] = None,
    max_bins: int = 8,
) -> Tuple[List[str], List[int], int, int]:
    """Session counts over a selected date range in compact bins."""
    ids = [int(x) for x in counselor_ids if x]
    sm_ids = [int(x) for x in (student_management_ids or []) if x]
    if not ids and not sm_ids:
        return [], [], 0, 0

    base_qs = FollowUpStatus.objects.all()
    if ids and sm_ids:
        base_qs = base_qs.filter(Q(counselor_id__in=ids) | Q(student_id__in=sm_ids))
    elif ids:
        base_qs = base_qs.filter(counselor_id__in=ids)
    else:
        base_qs = base_qs.filter(student_id__in=sm_ids)

    base_qs = _followup_qs_for_session_metrics(base_qs)
    start_date = min(start_date, end_date)
    end_date = max(start_date, end_date)
    total_days = max(1, (end_date - start_date).days + 1)
    bin_days = max(1, int(math.ceil(float(total_days) / max(1, int(max_bins)))))

    labels: List[str] = []
    values: List[int] = []
    cur = start_date
    while cur <= end_date:
        bend = min(end_date, cur + timedelta(days=bin_days - 1))
        labels.append(f"{cur:%d %b}–{bend:%d %b}")
        values.append(
            base_qs.filter(
                _ttv2_sess_day__gte=cur,
                _ttv2_sess_day__lte=bend,
            ).count()
        )
        cur = bend + timedelta(days=1)

    latest = values[-1] if values else 0
    prev = values[-2] if len(values) > 1 else 0
    return labels, values, latest, prev


def _followups_all_time(
    counselor_ids: Sequence[int],
    *,
    student_management_ids: Optional[Sequence[int]] = None,
    max_bins: int = 8,
) -> Tuple[List[str], List[int], int, int, Optional[date], Optional[date]]:
    """
    Session counts across the full available history (from earliest to latest follow-up date).
    Returns (labels, values, last_bin_total, prev_bin_total, start_date, end_date).
    """
    ids = [int(x) for x in counselor_ids if x]
    sm_ids = [int(x) for x in (student_management_ids or []) if x]
    if not ids and not sm_ids:
        return [], [], 0, 0, None, None

    base_qs = FollowUpStatus.objects.all()
    if ids and sm_ids:
        base_qs = base_qs.filter(Q(counselor_id__in=ids) | Q(student_id__in=sm_ids))
    elif ids:
        base_qs = base_qs.filter(counselor_id__in=ids)
    else:
        base_qs = base_qs.filter(student_id__in=sm_ids)

    base_qs = _followup_qs_for_session_metrics(base_qs)
    agg = base_qs.aggregate(
        mn=Min("_ttv2_sess_day"),
        mx=Max("_ttv2_sess_day"),
    )
    mn = agg.get("mn")
    mx = agg.get("mx")
    if not mn or not mx:
        return [], [], 0, 0, None, None
    labels, values, latest, prev = _followups_in_date_range(
        counselor_ids,
        start_date=mn,
        end_date=mx,
        student_management_ids=student_management_ids,
        max_bins=max_bins,
    )
    return labels, values, latest, prev, mn, mx


def _psych_and_risk(user_ids: Sequence[int]) -> Tuple[int, int, int, float]:
    """
    Returns: completed_count, total_students, risk_on_track, avg_clarity_gap_rounded
    (clarity = rough % of incomplete psych tests for students who have a TestCompletion row;
     students with no row count as full gap for averaging).
    """
    uids = [int(x) for x in user_ids if x]
    total = len(uids)
    if not total:
        return 0, 0, 0, 0.0

    completed = 0
    gap_sum = 0.0
    tc_by_user = {
        t.user_id: t
        for t in TestCompletion.objects.filter(user_id__in=uids)
    }
    for uid in uids:
        tc = tc_by_user.get(uid)
        if not tc:
            gap_sum += 100.0
            continue
        sub = sum(
            bool(x)
            for x in (tc.test1_complete, tc.test2_complete, tc.test3_complete)
        )
        if sub >= 3:
            completed += 1
            gap_sum += 0.0
        else:
            gap_sum += 100.0 * (1.0 - sub / 3.0)

    avg_clarity = round((gap_sum / total) if total else 0.0, 1)
    on_track = completed
    return completed, total, on_track, float(avg_clarity)


def _psychometric_success_count_students(user_ids: Sequence[int]) -> int:
    """
    Match legacy institute `test_result_count` / `ptr_count1`: students in scope with at
    least one Results row and TestCompletion 1+2+3 (same as Results.is_test_successful).
    """
    uids = {int(x) for x in user_ids if x}
    if not uids:
        return 0
    with_results = set(
        Results.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct()
    )
    if not with_results:
        return 0
    complete = set(
        TestCompletion.objects.filter(
            user_id__in=with_results,
            test1_complete=True,
            test2_complete=True,
            test3_complete=True,
        ).values_list("user_id", flat=True)
    )
    return len(uids & with_results & complete)


def _clarity_trend_4(avg: float) -> List[float]:
    """Four weekly points, ending at current `avg` (synthetic history)."""
    if avg <= 0.01:
        return [0.0, 0.0, 0.0, 0.0]
    a = max(0.0, min(100.0, float(avg)))
    w4 = a
    w1 = min(25.0, a + 8.0)
    w2 = w1 - (w1 - w4) * 0.35
    w3 = w2 - (w2 - w4) * 0.5
    return [round(x, 1) for x in (w1, w2, w3, w4)]


def _week_activity_counts(
    *,
    week_start: date,
    week_end: date,
    student_management_qs,
    user_ids: Sequence[int],
    counselor_ids: Sequence[int],
    student_management_ids: Optional[Sequence[int]] = None,
) -> Dict[str, int]:
    """Counts aligned with the selected Mon–Sun week (enrolments, psych attempts, journey touchpoints)."""
    enrollments = 0
    if student_management_qs is not None and hasattr(student_management_qs, "filter"):
        enrollments = int(
            student_management_qs.filter(
                created__date__gte=week_start, created__date__lte=week_end
            ).count()
        )

    uids = [int(x) for x in user_ids if x]
    psych_attempts = 0
    psych_completed = 0
    if uids:
        # Attempts: any of test1/test2/test3 touched during the selected week
        psych_attempts = int(
            Results.objects.filter(
                user_id__in=uids,
                test_paper__in=["test1", "test2", "test3"],
                modified__date__gte=week_start,
                modified__date__lte=week_end,
            )
            .values("user_id")
            .distinct()
            .count()
        )
        # Completion in week: user has all 3 test papers AND latest modification falls within the week
        # (uses created/modified timestamps from Results table instead of TestCompletion flags).
        psych_completed = int(
            Results.objects.filter(user_id__in=uids, test_paper__in=["test1", "test2", "test3"])
            .values("user_id")
            .annotate(n=Count("test_paper", distinct=True), last=Max("modified"))
            .filter(n__gte=3, last__date__gte=week_start, last__date__lte=week_end)
            .count()
        )

    cids = [int(x) for x in counselor_ids if x]
    sm_ids = [int(x) for x in (student_management_ids or []) if x]
    journey_touchpoints = 0
    if cids or sm_ids:
        fu_qs = FollowUpStatus.objects.all()
        if cids and sm_ids:
            fu_qs = fu_qs.filter(Q(counselor_id__in=cids) | Q(student_id__in=sm_ids))
        elif cids:
            fu_qs = fu_qs.filter(counselor_id__in=cids)
        else:
            fu_qs = fu_qs.filter(student_id__in=sm_ids)
        fu_qs = _followup_qs_for_session_metrics(fu_qs)
        journey_touchpoints = int(
            fu_qs.filter(
                _ttv2_sess_day__gte=week_start,
                _ttv2_sess_day__lte=week_end,
            ).count()
        )

    return {
        "enrollments": enrollments,
        "psych_attempts": psych_attempts,
        "psych_completed": psych_completed,
        "journey_touchpoints": journey_touchpoints,
    }


def _institute_credit_split(inst: Optional[Institute], student_count: int) -> Tuple[int, int]:
    if not inst:
        return max(0, student_count), 0
    left = inst.get_current_credits_count()
    used = max(0, int(student_count))
    if left < 0:
        left = 0
    return used, left


def build_ttv2_analytics(
    role: str,
    *,
    institute: Optional[Institute] = None,
    student_management_qs=None,
    counselor: Optional[Counselor] = None,
    week_start: Optional[date] = None,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
) -> Dict[str, Any]:
    """
    role: "institute" | "counselor" | "marketing_group" | "institute_group"
    For group/marketing, pass `institute` as None and a scoped `student_management_qs`.
    """
    counselor_ids: List[int] = []
    if role == "counselor" and counselor is not None:
        counselor_ids = [int(counselor.id)]
    elif role in ("marketing_group", "institute_group") and student_management_qs is not None:
        iids = list(
            student_management_qs.values_list("institute_id", flat=True)
            .distinct()
            .exclude(institute_id__isnull=True)
        )
        if iids:
            counselor_ids = list(
                Counselor.objects.filter(
                    counselor_admin_id__in=iids
                ).values_list("id", flat=True)
            )
    elif institute is not None:
        counselor_ids = list(
            Counselor.objects.filter(counselor_admin=institute).values_list("id", flat=True)
        )

    user_ids: List[int] = []
    # KPI "total students" must match institute roster counts (Count(student_management)),
    # including rows where student FK is still null; psychometrics use linked users only.
    n_students = 0
    if student_management_qs is not None and hasattr(student_management_qs, "count"):
        n_students = int(student_management_qs.count())
        sm_alive = student_management_qs.filter(student__isnull=False)
        user_ids = list(sm_alive.values_list("student_id", flat=True).distinct())
    student_management_ids: List[int] = []
    if student_management_qs is not None and hasattr(student_management_qs, "values_list"):
        student_management_ids = list(
            student_management_qs.values_list("id", flat=True).distinct()
        )

    # Counselor dashboards: follow-up / "sessions" trend must count rows logged by this
    # counselor only. Including student_management_ids makes the query
    # Q(counselor_id__in=…) | Q(student_id__in=…), which pulls other counselors' history
    # for the same students and skews the chart.
    followup_student_management_ids: Optional[List[int]] = (
        None if role == "counselor" else student_management_ids
    )

    distinct_classes = 0
    if student_management_qs is not None and hasattr(student_management_qs, "values"):
        distinct_classes = (
            student_management_qs.filter(class_and_section__isnull=False)
            .values("class_and_section_id")
            .distinct()
            .count()
        )

    psych_done, psych_total, on_track, clarity_avg = _psych_and_risk(user_ids)
    psych_pct = int(round(100.0 * psych_done / psych_total)) if psych_total else 0

    has_date_range = bool(date_start and date_end)
    if has_date_range:
        dr_start = min(date_start, date_end)
        dr_end = max(date_start, date_end)
        sess_labels, sess_values, sessions_week, sessions_prev = _followups_in_date_range(
            counselor_ids,
            start_date=dr_start,
            end_date=dr_end,
            student_management_ids=followup_student_management_ids,
        )
        reference_monday = _monday_of_week(dr_end)
    else:
        # Default (no date filter): show all-time sessions trend so the chart is meaningful.
        if not week_start:
            (
                sess_labels,
                sess_values,
                sessions_week,
                sessions_prev,
                _all_start,
                _all_end,
            ) = _followups_all_time(
                counselor_ids,
                student_management_ids=followup_student_management_ids,
            )
            if _all_start and _all_end:
                dr_start, dr_end = _all_start, _all_end
            else:
                dr_start, dr_end = _monday_of_week(timezone.now().date()), _monday_of_week(timezone.now().date()) + timedelta(days=6)
            reference_monday = _monday_of_week(dr_end)
        else:
            reference_monday = _monday_of_week(week_start)
            sess_labels, sess_values, sessions_week, sessions_prev = _followups_in_weeks(
                counselor_ids,
                4,
                reference_monday=reference_monday,
                student_management_ids=followup_student_management_ids,
            )
            dr_start = reference_monday
            dr_end = dr_start + timedelta(days=6)
    if not any(sess_values):
        sess_values = [0, 0, 0, sessions_week or 0]
        if not sess_labels or len(sess_labels) != len(sess_values):
            sess_labels = ["—", "—", "—", "—"]

    trend_prev = max(0.0, float(clarity_avg) + 5.0)
    clarity_trend = _clarity_trend_4(clarity_avg)

    risk_at_risk = max(0, psych_total - on_track) if psych_total else 0

    credit_used, credit_left = 0, 0
    if institute is not None and role in ("institute", "counselor"):
        credit_used, credit_left = _institute_credit_split(institute, n_students)
    elif role in ("marketing_group", "institute_group") and student_management_qs is not None:
        total_u = 0
        total_l = 0
        for iid in (
            student_management_qs.values_list("institute_id", flat=True).distinct()
        ):
            if not iid:
                continue
            try:
                inst = Institute.objects.get(pk=iid)
            except Institute.DoesNotExist:
                continue
            smc = student_management_qs.filter(institute_id=iid).count()
            u, l = _institute_credit_split(inst, smc)
            total_u += u
            total_l += l
        credit_used, credit_left = total_u, total_l
    else:
        credit_used, credit_left = n_students, 0

    top_stream = "—"
    if student_management_qs is not None and hasattr(student_management_qs, "values"):
        row = (
            student_management_qs.filter(class_and_section__stream__isnull=False)
            .exclude(class_and_section__stream="")
            .values("class_and_section__stream")
            .annotate(n=Count("id"))
            .order_by("-n")
            .first()
        )
        if row:
            top_stream = row.get("class_and_section__stream") or "—"

    if has_date_range:
        date_range_label = f"{dr_start:%d %b %Y} – {dr_end:%d %b %Y}"
    elif week_start:
        date_range_label = f"Week of {dr_start:%d}–{dr_end:%d %b %Y}"
    else:
        # All-time chart (no week / explicit range): show actual span when we have history.
        if dr_start and dr_end and (dr_end - dr_start).days > 6:
            date_range_label = f"{dr_start:%d %b %Y} – {dr_end:%d %b %Y}"
        else:
            date_range_label = "All time"

    week_activity: Optional[Dict[str, int]] = None
    if has_date_range or week_start:
        week_activity = _week_activity_counts(
            week_start=dr_start,
            week_end=dr_end,
            student_management_qs=student_management_qs,
            user_ids=user_ids,
            counselor_ids=counselor_ids,
            student_management_ids=followup_student_management_ids,
        )

    kira = (
        f"Top stream concentration: {top_stream}. "
        f"Encourage group sessions when multiple students share the same stream to reduce the clarity gap."
    )
    if psych_pct >= 80:
        kira = (
            f"Strong psychometric progress ({psych_pct}%). Consider scheduling career roadmap reviews "
            f"for the remaining {risk_at_risk} student(s)."
        )

    if credit_left <= 0:
        cred_alert = (
            f"Credit alert: no remaining credits. Add students only after the institute top-up. "
        )
    elif credit_left < 5:
        cred_alert = (
            f"Credit alert: {credit_left} credit(s) remaining. Plan sessions accordingly and request a top-up if needed."
        )
    else:
        cred_alert = f"Credits: {credit_left} remaining. Used seats: {credit_used}."

    psychometric_count = _psychometric_success_count_students(user_ids)
    psych_kpi_display = int(psychometric_count)
    if week_activity is not None:
        psych_kpi_display = int(week_activity.get("psych_attempts") or 0)

    psych_donut_payload: Dict[str, Any] = {
        "completed": psych_done,
        "total": psych_total,
        "pending": max(0, psych_total - psych_done),
        "labels": ["Completed", "Pending"],
    }
    if has_date_range or week_start:
        completed_w = 0
        if user_ids:
            completed_w = int(
                Results.objects.filter(user_id__in=user_ids, test_paper__in=["test1", "test2", "test3"])
                .values("user_id")
                .annotate(n=Count("test_paper", distinct=True), last=Max("modified"))
                .filter(n__gte=3, last__date__gte=dr_start, last__date__lte=dr_end)
                .count()
            )
        psych_donut_payload = {
            "completed": completed_w,
            "total": int(psych_total),
            "pending": max(0, int(psych_total) - completed_w),
            "labels": ["Completed", "Pending"],
        }

    if week_activity is not None:
        _prefix = "Selected range" if has_date_range else "This week"
        week_summary = (
            f"{_prefix}: {week_activity['enrollments']} new enrolments · "
            f"{week_activity['psych_attempts']} psychometric attempts · "
            f"{week_activity['psych_completed']} completions · "
            f"{week_activity['journey_touchpoints']} counseling touchpoints."
        )
    else:
        # All-time sessions chart: sessions_week / sessions_prev are latest vs previous bins.
        week_summary = (
            f"All-time counseling touchpoints by period (latest bin {sessions_week}, previous {sessions_prev}). "
            f"Psychometric completion {psych_pct}%. Avg clarity gap {clarity_avg}%."
        )

    total_credits_allocated = 0
    if institute is not None and role in ("institute", "counselor"):
        total_credits_allocated = int(institute.credit_counts or 0)
    elif role in ("marketing_group", "institute_group") and student_management_qs is not None:
        iids_tc = list(
            student_management_qs.values_list("institute_id", flat=True)
            .distinct()
            .exclude(institute_id__isnull=True)
        )
        if iids_tc:
            total_credits_allocated = int(
                Institute.objects.filter(pk__in=iids_tc).aggregate(s=Sum("credit_counts"))["s"]
                or 0
            )
    counselor_count = len(counselor_ids)

    return {
        "role": role,
        "week_activity": week_activity,
        "kpi": {
            "total_students": n_students,
            "classes_active": distinct_classes,
            "sessions_week": sessions_week,
            "sessions_prev": sessions_prev,
            "psych_pct": psych_pct,
            "psychometric_count": psych_kpi_display,
            "total_credits": int(total_credits_allocated),
            "counselor_count": int(counselor_count),
            "psych_trend": None,
            "clarity_gap": float(clarity_avg),
            "clarity_prev": float(trend_prev),
            "credits_remaining": int(credit_left),
            "credit_topup": bool(credit_left < 5),
        },
        "date_range_label": date_range_label,
        "charts": {
            "psych_donut": psych_donut_payload,
            "sessions_line": {
                "labels": sess_labels,
                "values": [int(x) for x in sess_values],
            },
            "clarity_line": {
                "labels": ["W1", "W2", "W3", "W4"],
                "values": clarity_trend,
            },
            "risk_donut": {
                "on_track": on_track,
                "at_risk": risk_at_risk,
            },
            "credit_donut": {
                "used": int(credit_used),
                "left": int(credit_left),
            },
        },
        "banners": {
            "week_summary": week_summary,
            "credit": cred_alert,
            "kira": kira,
        },
    }


def empty_ttv2_analytics() -> Dict[str, Any]:
    return {
        "role": "empty",
        "week_activity": None,
        "kpi": {
            "total_students": 0,
            "classes_active": 0,
            "sessions_week": 0,
            "sessions_prev": 0,
            "psych_pct": 0,
            "psychometric_count": 0,
            "total_credits": 0,
            "counselor_count": 0,
            "psych_trend": None,
            "clarity_gap": 0.0,
            "clarity_prev": 0.0,
            "credits_remaining": 0,
            "credit_topup": True,
        },
        "date_range_label": "—",
        "charts": {
            "psych_donut": {"completed": 0, "total": 0, "pending": 0},
            "sessions_line": {"labels": ["—", "—", "—", "—"], "values": [0, 0, 0, 0]},
            "clarity_line": {"labels": ["W1", "W2", "W3", "W4"], "values": [0, 0, 0, 0]},
            "risk_donut": {"on_track": 0, "at_risk": 0},
            "credit_donut": {"used": 0, "left": 0},
        },
        "banners": {
            "week_summary": "No analytics data yet.",
            "credit": "",
            "kira": "",
        },
    }
