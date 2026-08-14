"""
Record when a demo student's psychometric report is viewed (student or staff).

Used by marketing demo-institute journey stage "Report viewed".
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

REPORT_VIEW_EVENT_TYPE = "report_viewed"
REPORT_VIEW_EVENT_NAME = "psychometric_report_viewed"


def maybe_record_demo_student_report_view(subject_user, *, report_kind: str = "") -> bool:
    """
    If ``subject_user`` is a marketing demo student, record one report-viewed event.

    Returns True when an event was written (or already existed).
    """
    if not subject_user or not getattr(subject_user, "pk", None):
        return False
    if not getattr(subject_user, "is_demo_account", False):
        return False
    if getattr(subject_user, "is_system_demo", False):
        return False

    try:
        from institute.models import StudentManagement

        linked = StudentManagement.objects.filter(
            student_id=subject_user.pk,
            institute__is_demo_institute=True,
            institute__is_system_demo=False,
        ).exists()
        if not linked:
            return False

        from user_analytics.models import UserEvent

        if UserEvent.objects.filter(
            user_id=subject_user.pk,
            event_type=REPORT_VIEW_EVENT_TYPE,
        ).exists():
            return True

        from user_analytics.tasks import track_user_event_sync

        track_user_event_sync(
            event_type=REPORT_VIEW_EVENT_TYPE,
            event_name=REPORT_VIEW_EVENT_NAME,
            user_id=int(subject_user.pk),
            metadata={
                "report_kind": (report_kind or "").strip()[:80],
                "source": "demo_institute_journey",
            },
        )
        return True
    except Exception:
        logger.exception(
            "Failed to record demo report view for user_id=%s",
            getattr(subject_user, "pk", None),
        )
        return False
