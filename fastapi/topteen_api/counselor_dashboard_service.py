from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException


def _assert_counselor_api_access(user, counselor) -> None:
    from core import choices

    if not user or not getattr(user, "is_authenticated", True):
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.user_type == choices.UserType.COUNSELOR:
        if counselor.coun_user_id and counselor.coun_user_id != user.id:
            raise HTTPException(status_code=403, detail="Not this counselor's dashboard")
        if not counselor.coun_user_id:
            em = (getattr(counselor, "counselor_email", None) or "").strip().lower()
            uem = (getattr(user, "email", None) or "").strip().lower()
            if em and uem and em == uem:
                return
            raise HTTPException(status_code=403, detail="Not this counselor's dashboard")
    return


def load_counselor_dashboard(
    *,
    coun_id: int,
    token_email: str,
    ttv2_week_start: str | None,
    per_page: str = "10",
) -> dict[str, Any]:
    """
    Build JSON aligned with `counselor.views.CounselorDashboard` context (no HTML templates).
    """
    from django.conf import settings
    from django.contrib.auth import get_user_model

    from counselor.models import Counselor, CounselorCourse, FollowUpStatus
    from counselor.views import (
        get_class_and_sections_by_role,
        get_class_counts,
        get_students_by_role,
        get_unique_streams_by_role,
    )
    from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics

    User = get_user_model()
    counselor = (
        Counselor.objects.select_related("coun_user", "counselor_admin")
        .filter(id=coun_id)
        .first()
    )
    if not counselor:
        raise HTTPException(status_code=404, detail="Counselor not found")
    user = User.objects.filter(email__iexact=token_email.strip()).first()
    if not user:
        raise HTTPException(
            status_code=403,
            detail="No Django user with this email; log in with a matching account.",
        )
    _assert_counselor_api_access(user, counselor)

    counselor_institute = counselor.counselor_admin
    _week_start = None
    raw = (ttv2_week_start or "").strip()
    if raw:
        try:
            _week_start = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            _week_start = None

    students_to_display = get_students_by_role(
        user, counselor=counselor, institute=counselor_institute
    )
    assigned_ids = list(
        students_to_display.values_list("id", flat=True)
        if hasattr(students_to_display, "values_list")
        else [s.id for s in students_to_display]
    )
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor, student_id__in=assigned_ids
    )
    total_followed_up = follow_ups.filter(is_followed_up=True).count()

    class_and_sections = get_class_and_sections_by_role(user, students_to_display)
    class_counts = get_class_counts(students_to_display)
    unique_streams = get_unique_streams_by_role(user, students_to_display)

    students_count = (
        students_to_display.count()
        if hasattr(students_to_display, "count")
        else len(students_to_display)
    )

    counselor_course = CounselorCourse.objects.only("title").first()
    counselor_course_title = (
        ((counselor_course.title or "").strip() or "Career Counseling Course")
        if counselor_course
        else "Career Counseling Course"
    )

    # Analytics (same payload as v2 template |tojson)
    try:
        ttv2_analytics = build_ttv2_analytics(
            "counselor",
            institute=counselor_institute,
            student_management_qs=students_to_display,
            counselor=counselor,
            week_start=_week_start,
        )
    except Exception:
        ttv2_analytics = empty_ttv2_analytics()

    razorpay_key = getattr(
        settings, "RAZORPAY_KEY", None
    ) or getattr(settings, "RAZORPAY_API_KEY", None)

    classes_serialized = [
        {"id": c.id, "name": c.class_and_section or ""} for c in class_and_sections
    ]

    inst_payload = None
    if counselor_institute:
        inst_payload = {
            "id": counselor_institute.id,
            "name": getattr(counselor_institute, "name", None) or "",
        }

    return {
        "coun_id": coun_id,
        "counselor": {
            "id": counselor.id,
            "name": counselor.counselor_name,
            "email": counselor.counselor_email,
            "contact": counselor.counselor_contact_info,
            "institute": inst_payload,
        },
        "per_page": per_page,
        "students_count": students_count,
        "total_is_followed_up_count": total_followed_up,
        "class_and_sections": classes_serialized,
        "class_counts": class_counts,
        "unique_streams": unique_streams,
        "key": razorpay_key,
        "counselor_course": {
            "title": counselor_course_title,
            "show": bool(counselor_course),
        },
        "ttv2_analytics": ttv2_analytics,
    }
