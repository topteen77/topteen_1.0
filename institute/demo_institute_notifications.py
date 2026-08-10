"""
In-app (+ optional WhatsApp) alerts for marketing admins of demo institutes.

Events:
1. Students added to a demo institute
2. Any student generates a test result
3. All demo students of the institute have completed psychometric tests
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction

from institute.models import Institute, StudentManagement

logger = logging.getLogger(__name__)


def marketing_recipient_for_institute(institute: Institute):
    mg = getattr(institute, "marketing_group", None)
    if not mg:
        return None, None
    admin = getattr(mg, "marketing_group_admin", None)
    if not admin or not getattr(admin, "id", None) or not getattr(admin, "is_active", True):
        return None, mg
    return admin, mg


def _send_whatsapp_if_enabled(mg, recipient, text: str) -> None:
    if not mg or not getattr(mg, "whatsapp_notifications_enabled", False):
        return
    mobile = getattr(recipient, "mobile", None)
    if not mobile:
        return
    try:
        from communication.com_service import ComService

        ComService().send_whatsapp_message(str(mobile), text=text)
    except Exception:
        logger.exception(
            "Demo institute WhatsApp notify failed for user_id=%s",
            getattr(recipient, "id", None),
        )


def _send_email_if_enabled(mg, recipient, subject: str, body: str) -> None:
    if not mg or not getattr(mg, "email_notifications_enabled", False):
        return
    email = (getattr(recipient, "email", None) or "").strip()
    if not email:
        return
    try:
        from communication.com_service import ComService

        cs = ComService()
        html = (
            f"<p>{body}</p>"
            f"<p style='color:#666;font-size:12px'>TopTeen demo institute alert</p>"
        )
        cs.send_mail(cs.build_email_subject(subject), [email], body, html)
    except Exception:
        logger.exception(
            "Demo institute email notify failed for user_id=%s",
            getattr(recipient, "id", None),
        )


def _emit_marketing(
    *,
    event_type: str,
    title: str,
    body: str,
    recipient,
    institute: Institute,
    source_obj=None,
    payload=None,
    dedupe_key: str,
    whatsapp_text: str = "",
    mg=None,
) -> None:
    from notifications.models import Notification, NotificationCategory
    from notifications.services import emit_notification

    if dedupe_key and Notification.objects.filter(
        recipient_id=recipient.id, dedupe_key=dedupe_key
    ).exists():
        return

    emit_notification(
        event_type=event_type,
        title=title,
        body=body,
        recipients=[recipient],
        category=NotificationCategory.MARKETING,
        source_obj=source_obj or institute,
        payload=payload or {"institute_id": institute.id},
        dedupe_key=dedupe_key,
    )

    def _outbound():
        if whatsapp_text:
            _send_whatsapp_if_enabled(mg, recipient, whatsapp_text)
        _send_email_if_enabled(mg, recipient, title, body)

    transaction.on_commit(_outbound)


def notify_demo_institute_students_added(
    institute: Institute,
    *,
    student=None,
    count: int = 1,
    source: str = "enroll",
) -> None:
    if not institute or not getattr(institute, "is_demo_institute", False):
        return
    if getattr(institute, "is_system_demo", False):
        return
    recipient, mg = marketing_recipient_for_institute(institute)
    if not recipient:
        return

    inst_name = (institute.name or "Demo institute").strip()
    if student is not None:
        student_label = (
            getattr(student, "name", None)
            or getattr(student, "email", None)
            or f"student #{getattr(student, 'id', '')}"
        )
        title = "Demo institute: student added"
        body = f"{inst_name} added student {student_label}."
        wa = f"TopTeen: Demo institute {inst_name} added student {student_label}."
        dedupe = f"demo_inst_student_added_{institute.id}_{getattr(student, 'id', '')}"
        payload = {
            "institute_id": institute.id,
            "student_id": getattr(student, "id", None),
            "source": source,
        }
        source_obj = student
    else:
        n = max(1, int(count or 1))
        title = "Demo institute: students added"
        body = f"{inst_name} added {n} student{'s' if n != 1 else ''} ({source})."
        wa = f"TopTeen: Demo institute {inst_name} added {n} student(s)."
        dedupe = f"demo_inst_students_added_{institute.id}_{source}_{n}_{institute.demo_seed_count or 0}"
        payload = {"institute_id": institute.id, "count": n, "source": source}
        source_obj = institute

    _emit_marketing(
        event_type="marketing.demo_institute_students_added",
        title=title,
        body=body,
        recipient=recipient,
        institute=institute,
        source_obj=source_obj,
        payload=payload,
        dedupe_key=dedupe,
        whatsapp_text=wa,
        mg=mg,
    )


def notify_demo_institute_test_result(user, *, result_kind: str = "test") -> None:
    """Notify when any student at a demo institute generates a test result (once per student)."""
    if not user or not getattr(user, "id", None):
        return
    sm = (
        StudentManagement.objects.select_related(
            "institute",
            "institute__marketing_group",
            "institute__marketing_group__marketing_group_admin",
            "student",
        )
        .filter(student_id=user.id)
        .first()
    )
    if not sm:
        return
    institute = sm.institute
    if not institute or not getattr(institute, "is_demo_institute", False):
        return
    if getattr(institute, "is_system_demo", False):
        return

    recipient, mg = marketing_recipient_for_institute(institute)
    if not recipient:
        return

    inst_name = (institute.name or "Demo institute").strip()
    student_label = (
        getattr(user, "name", None) or getattr(user, "email", None) or f"student #{user.id}"
    )
    title = "Demo institute: test result generated"
    body = f"{student_label} at {inst_name} generated a {result_kind} result."
    wa = f"TopTeen: {student_label} at demo institute {inst_name} generated a test result."

    _emit_marketing(
        event_type="marketing.demo_institute_test_result",
        title=title,
        body=body,
        recipient=recipient,
        institute=institute,
        source_obj=user,
        payload={
            "institute_id": institute.id,
            "student_id": user.id,
            "result_kind": result_kind,
        },
        dedupe_key=f"demo_inst_test_result_{institute.id}_{user.id}",
        whatsapp_text=wa,
        mg=mg,
    )

    # After a result, check whether every demo student has completed.
    transaction.on_commit(lambda: notify_demo_institute_all_demos_completed(institute.id))


def notify_demo_institute_all_demos_completed(institute_id: int) -> None:
    if not institute_id:
        return
    try:
        institute = Institute.objects.select_related(
            "marketing_group",
            "marketing_group__marketing_group_admin",
        ).get(pk=institute_id)
    except Institute.DoesNotExist:
        return
    if not getattr(institute, "is_demo_institute", False) or getattr(
        institute, "is_system_demo", False
    ):
        return

    demo_uids = list(
        StudentManagement.objects.filter(
            institute_id=institute_id,
            student__is_demo_account=True,
        ).values_list("student_id", flat=True)
    )
    if not demo_uids:
        return

    from core.student_psychometric_metrics import psychometric_complete_user_ids
    from psychometric_tests.models import PsychometricTestResult

    complete = set(psychometric_complete_user_ids(demo_uids))
    central = set(
        PsychometricTestResult.objects.filter(
            assessment__central_test_candidate__user_id__in=demo_uids
        ).values_list("assessment__central_test_candidate__user_id", flat=True)
    ) | set(
        PsychometricTestResult.objects.filter(
            assessment__pyschometric_test_payment__user_id__in=demo_uids
        ).values_list("assessment__pyschometric_test_payment__user_id", flat=True)
    )
    if set(demo_uids) - (complete | central):
        return

    recipient, mg = marketing_recipient_for_institute(institute)
    if not recipient:
        return

    inst_name = (institute.name or "Demo institute").strip()
    n = len(demo_uids)
    title = "Demo institute: all demo students completed"
    body = f"All {n} demo student{'s' if n != 1 else ''} at {inst_name} have completed their tests."
    wa = (
        f"TopTeen: All {n} demo student(s) at {inst_name} have completed their psychometric tests."
    )

    _emit_marketing(
        event_type="marketing.demo_institute_all_demos_completed",
        title=title,
        body=body,
        recipient=recipient,
        institute=institute,
        source_obj=institute,
        payload={"institute_id": institute.id, "demo_student_count": n},
        dedupe_key=f"demo_inst_all_complete_{institute.id}",
        whatsapp_text=wa,
        mg=mg,
    )


def resolve_user_from_psychometric_result(result) -> Optional[object]:
    """Best-effort user for PsychometricTestResult."""
    assessment = getattr(result, "assessment", None)
    if assessment is None and getattr(result, "assessment_id", None):
        try:
            from psychometric_tests.models import CandidateTest

            assessment = (
                CandidateTest.objects.select_related(
                    "central_test_candidate",
                    "central_test_candidate__user",
                    "pyschometric_test_payment",
                    "pyschometric_test_payment__user",
                )
                .filter(pk=result.assessment_id)
                .first()
            )
        except Exception:
            assessment = None
    if not assessment:
        return None
    ctc = getattr(assessment, "central_test_candidate", None)
    if ctc is not None and getattr(ctc, "user_id", None):
        return getattr(ctc, "user", None)
    pay = getattr(assessment, "pyschometric_test_payment", None)
    if pay is not None and getattr(pay, "user_id", None):
        return getattr(pay, "user", None)
    return None
