from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="loan_desk.tasks.send_loan_enquiry_notify")
def send_loan_enquiry_notify(application_id: int, event: str = "enquiry"):
    from loan_desk.services import notify_team_of_enquiry
    from users.models import EducationLoanApplication

    app = EducationLoanApplication.objects.filter(id=application_id).first()
    if not app:
        return 0
    return notify_team_of_enquiry(app, event=event)


@shared_task(name="loan_desk.tasks.send_loan_assignment_notify")
def send_loan_assignment_notify(application_id: int, assigned_by_id: int | None = None):
    from loan_desk.services import notify_lead_assignee
    from users.models import EducationLoanApplication, User

    app = (
        EducationLoanApplication.objects.select_related("assigned_to")
        .filter(id=application_id)
        .first()
    )
    if not app or not app.assigned_to_id:
        return 0
    assigned_by = None
    if assigned_by_id:
        assigned_by = User.objects.filter(id=assigned_by_id).first()
    return notify_lead_assignee(app, assigned_by=assigned_by)


@shared_task(name="loan_desk.tasks.send_loan_daily_report")
def send_loan_daily_report():
    from communication.com_service import ComService
    from loan_desk.services import build_daily_report_body
    from users.models import EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    if not ops.daily_report_enabled:
        return 0
    emails = ops.manager_email_list()
    if not emails:
        return 0
    body = build_daily_report_body()
    subject = f"Loan enquiry daily report — {timezone.localdate().isoformat()}"
    ok = ComService().send_mail(subject, emails, body, f"<pre>{body}</pre>")
    return 1 if ok else 0


@shared_task(name="loan_desk.tasks.send_loan_overdue_followup_reminders")
def send_loan_overdue_followup_reminders():
    """
    Email for leads that still need follow-up:
    - Fresh enquiries older than admin rule (default 24h) with no follow-up done
    - Scheduled follow-ups past due and not actioned since

    Once a remark (follow-up) is saved, last_followed_up_at is set and the lead
    drops off this list until a new next_follow_up_at becomes overdue again.
    """
    from communication.com_service import ComService
    from django.urls import reverse
    from loan_desk.services import leads_needing_followup_reminder
    from users.models import EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    if not ops.reminder_enabled:
        return 0

    leads, hours = leads_needing_followup_reminder(limit=50)
    if not leads:
        return 0

    sent = 0
    cs = ComService()
    for app in leads:
        user = app.assigned_to
        email = (getattr(user, "email", None) or "").strip() if user else ""
        if not email:
            emails = ops.manager_email_list()
            if not emails:
                continue
            email = emails[0]
        path = reverse("loan_desk:detail", kwargs={"pk": app.id})
        if app.last_followed_up_at is None and not (
            app.next_follow_up_at and app.next_follow_up_at < timezone.now()
        ):
            reason = f"No follow-up within {hours} hours of enquiry"
        else:
            reason = f"Scheduled follow-up overdue (due {app.next_follow_up_at})"
        body = (
            f"Loan follow-up reminder — enquiry #{app.id}\n"
            f"Reason: {reason}\n"
            f"Student: {app.student_name}\n"
            f"Lead follow: {app.lead_follow_username}\n"
            f"Open: {path}\n"
        )
        if cs.send_mail(
            f"Loan follow-up reminder — #{app.id}",
            [email],
            body,
            f"<pre>{body}</pre>",
        ):
            sent += 1
    return sent
