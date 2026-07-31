"""Loan desk business helpers: instant login, notify, callback, team users."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Iterable, List, Optional

from django.contrib.auth import login
from django.urls import reverse
from django.utils import timezone

from core import choices

logger = logging.getLogger(__name__)


def loan_desk_team_users(*, enabled_only: bool = True):
    from users.models import User

    qs = User.objects.filter(user_type__in=choices.UserType.LOAN_DESK_TYPES)
    if enabled_only:
        qs = qs.filter(user_status=choices.UserStatus.UNBLOCK)
    return qs.order_by("user_type", "name", "email")


def loan_desk_managers(*, enabled_only: bool = True):
    from users.models import User

    qs = User.objects.filter(user_type=choices.UserType.LOAN_MANAGER)
    if enabled_only:
        qs = qs.filter(user_status=choices.UserStatus.UNBLOCK)
    return qs.order_by("name", "email")


def create_instant_login_token(user, application, *, ttl_hours: int = 48) -> str:
    """Create token row; return raw token string for URL."""
    from users.models import LoanInstantLoginToken

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    LoanInstantLoginToken.objects.create(
        token_hash=token_hash,
        user=user,
        application=application,
        expires_at=timezone.now() + timedelta(hours=max(1, int(ttl_hours or 48))),
    )
    return raw


def consume_instant_login_token(raw_token: str):
    """Validate and consume token. Returns (user, application) or (None, None)."""
    from users.models import LoanInstantLoginToken

    if not raw_token:
        return None, None
    token_hash = hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()
    row = (
        LoanInstantLoginToken.objects.select_related("user", "application")
        .filter(token_hash=token_hash, used_at__isnull=True)
        .first()
    )
    if not row:
        return None, None
    if row.expires_at and row.expires_at < timezone.now():
        return None, None
    user = row.user
    if getattr(user, "user_type", None) not in choices.UserType.LOAN_DESK_TYPES:
        if not getattr(user, "is_superuser", False):
            return None, None
    try:
        if not bool(user.get_user_status()):
            return None, None
    except Exception:
        if getattr(user, "user_status", None) == choices.UserStatus.BLOCK:
            return None, None
    row.used_at = timezone.now()
    row.save(update_fields=["used_at"])
    return user, row.application


def _public_site_base_url() -> str:
    """Canonical public site origin for email links (never relative / internal hosts)."""
    from django.conf import settings

    base = (
        getattr(settings, "TOPTEEN_SITE_URL", None)
        or getattr(settings, "SITE_URL", None)
        or getattr(settings, "BASE_URL", None)
        or getattr(settings, "SITE_BASE_URL", None)
        or ""
    )
    base = str(base or "").strip().rstrip("/")
    if base:
        return base
    try:
        from communication.email_layout import _email_site_url

        return (_email_site_url() or "").rstrip("/")
    except Exception:
        return "https://www.topteen.in"


def absolute_public_url(path: str, *, request=None) -> str:
    """Build an absolute URL on the public base domain."""
    path = path or "/"
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    base = _public_site_base_url()
    if base:
        return f"{base}{path}"
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    return path


def instant_login_url(request, user, application) -> str:
    from users.models import EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    raw = create_instant_login_token(
        user, application, ttl_hours=ops.instant_login_ttl_hours
    )
    path = reverse("loan_desk:instant_login", kwargs={"token": raw})
    return absolute_public_url(path, request=request)


def schedule_parent_callback(application, *, preferred_at, note: str = "") -> None:
    application.callback_preferred_at = preferred_at
    application.callback_note = (note or "")[:500]
    if application.status in (
        choices.EducationLoanApplicationStatus.ENQUIRY_SENT,
        choices.EducationLoanApplicationStatus.IN_PROGRESS,
        choices.EducationLoanApplicationStatus.FOLLOW_UP,
    ):
        application.status = choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED
    application.save(
        update_fields=[
            "callback_preferred_at",
            "callback_note",
            "status",
            "modified",
        ]
    )


def _log_loan_email_failure(*, to_email: str, subject: str, error) -> None:
    """Ensure loan notify failures appear on the Email logs page even before SMTP send."""
    try:
        from django.conf import settings
        from topteens.email_logging import append_email_send_log

        append_email_send_log(
            to_emails=[to_email] if to_email else [],
            subject=subject or "",
            from_email=str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""),
            status="failed",
            error=str(error or "Loan email notify failed"),
        )
    except Exception:
        logger.warning("Could not append loan email failure to email_send.jsonl", exc_info=True)


def notify_team_of_enquiry(application, *, request=None, event: str = "enquiry") -> int:
    """Email Loan Managers with summary + instant-login links. Returns send count."""
    from users.models import EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    if not ops.notify_on_enquiry:
        return 0

    recipients = list(loan_desk_managers(enabled_only=True))
    sent = 0
    for user in recipients:
        email = (getattr(user, "email", None) or "").strip()
        if not email or "@" not in email:
            continue
        subject = _enquiry_email_subject(application, event)
        try:
            url = instant_login_url(request, user, application)
            ok = _send_enquiry_email_to_user(
                user, application, instant_url=url, event=event
            )
            if ok:
                sent += 1
        except Exception as exc:
            logger.exception("Failed loan enquiry notify to user %s", user.id)
            _log_loan_email_failure(to_email=email, subject=subject, error=exc)

    # Also notify configured manager report emails (if not already covered)
    already = {
        (getattr(u, "email", None) or "").strip().lower()
        for u in recipients
        if (getattr(u, "email", None) or "").strip()
    }
    for email in ops.manager_email_list():
        if email.lower() in already:
            continue
        subject = _enquiry_email_subject(application, event)
        try:
            ok = _send_enquiry_email_to_address(
                email, application, request=request, event=event, instant_url=""
            )
            if ok:
                sent += 1
        except Exception as exc:
            logger.exception("Failed loan enquiry notify to %s", email)
            _log_loan_email_failure(to_email=email, subject=subject, error=exc)
    return sent


def notify_lead_assignee(application, *, request=None, assigned_by=None) -> int:
    """Email the assigned executive/manager when a lead is assigned to them."""
    user = getattr(application, "assigned_to", None)
    if not user:
        return 0
    email = (getattr(user, "email", None) or "").strip()
    if not email or "@" not in email:
        return 0
    try:
        if not bool(user.get_user_status()):
            return 0
    except Exception:
        if getattr(user, "user_status", None) == choices.UserStatus.BLOCK:
            return 0

    from communication.com_service import ComService

    try:
        url = instant_login_url(request, user, application)
    except Exception:
        logger.exception("Failed to build instant login for assignee %s", user.id)
        url = absolute_public_url(
            reverse("loan_desk:detail", kwargs={"pk": application.id}), request=request
        )
    by_name = ""
    if assigned_by is not None:
        by_name = (
            getattr(assigned_by, "name", None)
            or getattr(assigned_by, "email", None)
            or ""
        )
    subject = f"Loan lead assigned to you — #{application.id}"
    lines = [
        f"A loan enquiry has been assigned to you as lead follow.",
        f"Assigned by: {by_name or '—'}",
        "",
    ] + _enquiry_summary_lines(application)
    lines.append("")
    lines.append("View enquiry (instant login):")
    lines.append(url)
    body = "\n".join(lines)
    html = (
        "<p>A loan enquiry has been assigned to you as lead follow."
        + (f"<br>Assigned by: {by_name}" if by_name else "")
        + "</p><p>"
        + "<br>".join(_enquiry_summary_lines(application))
        + "</p>"
        + _enquiry_cta_html(url)
    )
    try:
        ok = ComService().send_mail(subject, [email], body, html)
        return 1 if ok else 0
    except Exception:
        logger.exception("Failed assignment notify to user %s", user.id)
        return 0


def _enquiry_status_label(application) -> str:
    """Prefer Callback Scheduled when a preferred callback time is already set."""
    if (
        getattr(application, "callback_preferred_at", None)
        or getattr(application, "status", None)
        == choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED
    ):
        return "Callback Scheduled"
    return application.get_status_display()


def _enquiry_summary_lines(application) -> List[str]:
    return [
        f"Enquiry ID: {application.id}",
        f"Status: {_enquiry_status_label(application)}",
        f"Student: {application.student_name or '—'}",
        f"Parent: {application.parent_name or '—'}",
        f"Mobile: {application.mobile or '—'}",
        f"Email: {application.email or '—'}",
        f"Institute: {application.institute_name or '—'}",
        f"Course: {application.course_name or '—'}",
        f"Loan amount: {application.loan_amount or '—'}",
        f"Country: {application.country_preference or '—'}",
        f"Callback: {application.callback_preferred_at or '—'}",
        f"Lead follow: {application.lead_follow_username}",
    ]


def _enquiry_cta_html(url: str, *, label: str = "View enquiry (instant login)") -> str:
    """Button CTA plus raw hyperlink on the next line (email-client friendly)."""
    href = (url or "").strip()
    if not href:
        return ""
    btn_style = (
        "display:inline-block;padding:12px 22px;background-color:#4f46e5;color:#ffffff;"
        "text-decoration:none;border-radius:8px;font-weight:700;font-size:14px;"
        "line-height:1.4;border:1px solid #4338ca;"
    )
    return (
        f'<p style="margin:20px 0 12px;">'
        f'<a href="{href}" target="_blank" rel="noopener" style="{btn_style}">{label}</a>'
        f"</p>"
        f'<p style="margin:0;font-size:13px;line-height:1.5;word-break:break-all;">'
        f'<a href="{href}" target="_blank" rel="noopener" style="color:#4f46e5;">{href}</a>'
        f"</p>"
    )


def _enquiry_email_subject(application, event: str) -> str:
    if event == "callback" or getattr(application, "callback_preferred_at", None):
        return f"Loan callback scheduled — #{application.id}"
    return f"New loan enquiry — #{application.id}"


def _send_enquiry_email_to_user(user, application, *, instant_url: str, event: str) -> bool:
    from communication.com_service import ComService

    subject = _enquiry_email_subject(application, event)
    lines = _enquiry_summary_lines(application)
    lines.append("")
    lines.append("View enquiry (instant login):")
    lines.append(instant_url or "")
    body = "\n".join(lines)
    html = (
        "<p>"
        + "<br>".join(_enquiry_summary_lines(application))
        + "</p>"
        + _enquiry_cta_html(instant_url)
    )
    return bool(
        ComService().send_mail(
            subject,
            [user.email],
            body,
            html,
        )
    )


def _send_enquiry_email_to_address(
    email: str, application, *, request=None, event: str = "enquiry", instant_url: str = ""
) -> bool:
    from communication.com_service import ComService

    subject = _enquiry_email_subject(application, event)
    desk = absolute_public_url(reverse("loan_desk:dashboard"), request=request)
    link = (instant_url or desk or "").strip()
    lines = _enquiry_summary_lines(application)
    lines.append("")
    lines.append("View enquiry (instant login):")
    lines.append(link)
    body = "\n".join(lines)
    html = (
        "<p>"
        + "<br>".join(_enquiry_summary_lines(application))
        + "</p>"
        + _enquiry_cta_html(link)
    )
    return bool(ComService().send_mail(subject, [email], body, html))


def enquiry_anchor_time(application):
    """When the lead became an active enquiry (for fresh-lead reminder age)."""
    return application.submitted_at or application.created


def _reminder_filter_q(*, now, threshold):
    """Q for leads that belong on the follow-up reminder email list."""
    from django.db.models import F, Q

    fresh_q = Q(last_followed_up_at__isnull=True) & (
        Q(next_follow_up_at__isnull=True) | Q(next_follow_up_at__lte=now)
    ) & (
        Q(submitted_at__isnull=False, submitted_at__lte=threshold)
        | Q(submitted_at__isnull=True, created__lte=threshold)
    )
    overdue_q = Q(next_follow_up_at__lt=now) & (
        Q(last_followed_up_at__isnull=True) | Q(last_followed_up_at__lt=F("next_follow_up_at"))
    )
    return fresh_q | overdue_q


def leads_needing_followup_reminder(*, limit: int = 50):
    """
    Open leads that should appear on reminder emails:

    1. Fresh leads: never followed up, and older than ops.reminder_unfollowed_after_hours
       (default 24h / 1 day), with no future desk follow-up scheduled.
    2. Overdue scheduled follow-ups: next_follow_up_at in the past and not yet
       actioned after that due time (last_followed_up_at missing or before due).

    Doing a follow-up (remark → last_followed_up_at) removes the lead from both lists.
    """
    from users.models import EducationLoanApplication, EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    now = timezone.now()
    hours = max(1, int(ops.reminder_unfollowed_after_hours or 24))
    threshold = now - timedelta(hours=hours)

    qs = (
        EducationLoanApplication.objects.filter(
            status__in=choices.EducationLoanApplicationStatus.OPEN_STATUSES,
        )
        .filter(_reminder_filter_q(now=now, threshold=threshold))
        .select_related("assigned_to")
        .distinct()
        .order_by("next_follow_up_at", "id")
    )
    return list(qs[: max(1, int(limit or 50))]), hours


def build_daily_report_body() -> str:
    from users.models import EducationLoanApplication, EducationLoanOpsSettings

    today = timezone.localdate()
    ops = EducationLoanOpsSettings.load()
    hours = max(1, int(ops.reminder_unfollowed_after_hours or 24))
    now = timezone.now()
    threshold = now - timedelta(hours=hours)

    qs = EducationLoanApplication.objects.exclude(
        status=choices.EducationLoanApplicationStatus.DRAFT
    )
    new_today = qs.filter(submitted_at__date=today).count()
    callbacks = qs.filter(
        status=choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED
    ).count()
    open_qs = qs.filter(status__in=choices.EducationLoanApplicationStatus.OPEN_STATUSES)
    reminder_count = (
        open_qs.filter(_reminder_filter_q(now=now, threshold=threshold)).distinct().count()
    )
    open_total = open_qs.count()
    closed = qs.filter(status=choices.EducationLoanApplicationStatus.CLOSED).count()
    qualified = qs.filter(
        status=choices.EducationLoanApplicationStatus.QUALIFIED
    ).count()
    not_qualified = qs.filter(
        status=choices.EducationLoanApplicationStatus.NOT_QUALIFIED
    ).count()
    return (
        f"Loan enquiry daily report — {today.isoformat()}\n\n"
        f"New today: {new_today}\n"
        f"Open (pipeline): {open_total}\n"
        f"Callback scheduled: {callbacks}\n"
        f"Needs follow-up reminder (rule: {hours}h): {reminder_count}\n"
        f"Qualified: {qualified}\n"
        f"Not qualified: {not_qualified}\n"
        f"Closed: {closed}\n"
    )


def _add_system_remark(application, body: str, *, author=None) -> None:
    from users.models import EducationLoanRemark

    EducationLoanRemark.objects.create(
        application=application,
        author=author,
        body=(body or "")[:5000],
    )


def qualify_lead(application, *, actor, note: str = "") -> tuple:
    """Mark lead Qualified. Returns (ok, message)."""
    if application.status == choices.EducationLoanApplicationStatus.DRAFT:
        return False, "Draft leads cannot be qualified."
    if application.status == choices.EducationLoanApplicationStatus.NOT_QUALIFIED:
        return False, "Not-qualified leads cannot be re-qualified from here. Re-open via status first."
    note = (note or "").strip()[:500]
    application.status = choices.EducationLoanApplicationStatus.QUALIFIED
    application.qualification_decision_at = timezone.now()
    application.qualification_decided_by = actor
    application.qualification_note = note
    application.disqualify_reason = ""
    application.disqualify_reason_text = ""
    application.save(
        update_fields=[
            "status",
            "qualification_decision_at",
            "qualification_decided_by",
            "qualification_note",
            "disqualify_reason",
            "disqualify_reason_text",
            "modified",
        ]
    )
    who = getattr(actor, "name", None) or getattr(actor, "email", None) or "Manager"
    remark = f"Qualified by {who}."
    if note:
        remark += f" Note: {note}"
    _add_system_remark(application, remark, author=actor)
    return True, "Lead marked as Qualified."


def disqualify_lead(
    application,
    *,
    actor,
    reason: str = "",
    reason_text: str = "",
) -> tuple:
    """Mark lead Not Qualified. Returns (ok, message)."""
    if application.status == choices.EducationLoanApplicationStatus.DRAFT:
        return False, "Draft leads cannot be disqualified."
    if application.status == choices.EducationLoanApplicationStatus.QUALIFIED:
        return False, "Qualified leads cannot be marked Not Qualified. Change status first if needed."
    reason = (reason or "").strip()
    reason_text = (reason_text or "").strip()[:500]
    valid_reasons = {c[0] for c in choices.EducationLoanDisqualifyReason.CHOICES}
    if reason not in valid_reasons:
        return False, "Select a disqualify reason."
    if reason == choices.EducationLoanDisqualifyReason.OTHER and len(reason_text) < 3:
        return False, "Add a short note for reason Other."
    application.status = choices.EducationLoanApplicationStatus.NOT_QUALIFIED
    application.qualification_decision_at = timezone.now()
    application.qualification_decided_by = actor
    application.disqualify_reason = reason
    application.disqualify_reason_text = reason_text
    application.qualification_note = ""
    application.save(
        update_fields=[
            "status",
            "qualification_decision_at",
            "qualification_decided_by",
            "disqualify_reason",
            "disqualify_reason_text",
            "qualification_note",
            "modified",
        ]
    )
    reason_label = dict(choices.EducationLoanDisqualifyReason.CHOICES).get(reason, reason)
    who = getattr(actor, "name", None) or getattr(actor, "email", None) or "Manager"
    remark = f"Not qualified by {who}. Reason: {reason_label}."
    if reason_text:
        remark += f" {reason_text}"
    _add_system_remark(application, remark, author=actor)
    return True, "Lead marked as Not Qualified."


def education_loan_enquiry_delete_counts(*, application_ids=None) -> dict:
    """Counts for hard-delete confirmation (includes soft-deleted rows)."""
    from users.models import (
        EducationLoanApplication,
        EducationLoanRemark,
        LoanInstantLoginToken,
    )

    apps = EducationLoanApplication.objects.complete()
    if application_ids is not None:
        apps = apps.filter(pk__in=list(application_ids))
    app_ids = list(apps.values_list("pk", flat=True))
    if not app_ids:
        return {"applications": 0, "remarks": 0, "tokens": 0}
    return {
        "applications": len(app_ids),
        "remarks": EducationLoanRemark.objects.complete()
        .filter(application_id__in=app_ids)
        .count(),
        "tokens": LoanInstantLoginToken.objects.filter(application_id__in=app_ids).count(),
    }


def hard_delete_education_loan_enquiries(*, application_ids=None) -> dict:
    """
    Permanently remove loan enquiries and related remarks / instant-login tokens.
    Uses the complete manager so soft-deleted rows are removed too.
    Pass application_ids=None to wipe all enquiries.
    """
    from django.db import transaction

    from users.models import (
        EducationLoanApplication,
        EducationLoanRemark,
        LoanInstantLoginToken,
    )

    apps = EducationLoanApplication.objects.complete()
    if application_ids is not None:
        apps = apps.filter(pk__in=list(application_ids))
    app_ids = list(apps.values_list("pk", flat=True))
    if not app_ids:
        return {"applications": 0, "remarks": 0, "tokens": 0}

    with transaction.atomic():
        remarks_deleted, _ = (
            EducationLoanRemark.objects.complete()
            .filter(application_id__in=app_ids)
            .delete()
        )
        tokens_deleted, _ = LoanInstantLoginToken.objects.filter(
            application_id__in=app_ids
        ).delete()
        apps_deleted, _ = (
            EducationLoanApplication.objects.complete()
            .filter(pk__in=app_ids)
            .delete()
        )

    return {
        "applications": apps_deleted,
        "remarks": remarks_deleted,
        "tokens": tokens_deleted,
    }


CLIENT_EMAIL_TEMPLATE_VARIABLES = (
    ("student_name", "Student name"),
    ("parent_name", "Parent name"),
    ("mobile", "Mobile"),
    ("email", "Client email"),
    ("institute_name", "Institute / college"),
    ("course_name", "Course"),
    ("loan_amount", "Loan amount"),
    ("enquiry_id", "Enquiry id"),
    ("manager_name", "Sender name (logged-in user)"),
)

SAMPLE_CLIENT_EMAIL_SUBJECT = (
    "Education Loan Enquiry update (ID: {{enquiry_id}}) for {{student_name}}"
)

SAMPLE_CLIENT_EMAIL_BODY = """Dear {{parent_name}},

Thank you for reaching out regarding an education loan for {{student_name}}.

We have received your enquiry for the {{course_name}} program at {{institute_name}} for a requested loan amount of INR {{loan_amount}}. Your Enquiry ID is {{enquiry_id}}.

Our team is currently reviewing your request. We will contact you shortly on {{mobile}} or via {{email}} to discuss the next steps, required documentation, and customized repayment options.

If you have any immediate questions, please feel free to reply directly to this email.

Best regards,
{{manager_name}}
Loan Operations Manager
{{institute_name}} Financial Services Team"""


def client_email_template_variables(application, *, actor=None) -> dict:
    """String values for {{variable}} substitution in client email templates."""
    amount = getattr(application, "loan_amount", None)
    who = ""
    if actor is not None:
        who = (
            getattr(actor, "name", None)
            or getattr(actor, "email", None)
            or ""
        )
    return {
        "student_name": (getattr(application, "student_name", None) or "").strip(),
        "parent_name": (getattr(application, "parent_name", None) or "").strip(),
        "mobile": (getattr(application, "mobile", None) or "").strip(),
        "email": (getattr(application, "email", None) or "").strip(),
        "institute_name": (getattr(application, "institute_name", None) or "").strip(),
        "course_name": (getattr(application, "course_name", None) or "").strip(),
        "loan_amount": str(amount) if amount is not None else "",
        "enquiry_id": str(getattr(application, "id", "") or ""),
        "manager_name": str(who).strip(),
    }


def render_client_email_template_text(template: str, variables: dict) -> str:
    from users.education_loan_crm import substitute_template

    return substitute_template(template or "", variables or {})


def active_client_email_templates():
    from users.models import EducationLoanClientEmailTemplate

    return list(
        EducationLoanClientEmailTemplate.objects.filter(is_active=True).order_by(
            "sort_order", "name", "id"
        )
    )


def rendered_client_email_templates_for(application, *, actor=None) -> list:
    """Active templates with subject/body already substituted for this lead."""
    variables = client_email_template_variables(application, actor=actor)
    out = []
    for tpl in active_client_email_templates():
        out.append(
            {
                "id": tpl.id,
                "name": tpl.name,
                "subject": render_client_email_template_text(tpl.subject, variables)[:200],
                "body": render_client_email_template_text(tpl.body, variables),
            }
        )
    return out


def send_client_email(application, *, actor, subject: str, body: str) -> tuple:
    """Write and send an email to the enquiry client (parent email)."""
    from communication.com_service import ComService

    to_email = (getattr(application, "email", None) or "").strip()
    if not to_email or "@" not in to_email:
        return False, "This lead has no client email address."
    subject = (subject or "").strip()[:200]
    body = (body or "").strip()
    if not subject or not body:
        return False, "Subject and message are required."

    who = getattr(actor, "name", None) or getattr(actor, "email", None) or "Loan Desk"
    html = "<p>" + "<br>".join(
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for line in body.splitlines()
    ) + "</p>"
    html += f"<p style='color:#5b7178;font-size:12px;'>Sent by {who} via TopTeen Loan Desk</p>"

    try:
        ok = ComService().send_mail(subject, [to_email], body, html)
    except Exception as exc:
        logger.exception("Client email failed for lead %s", application.id)
        return False, str(exc)[:500]

    if not ok:
        return False, "Mail service returned failure."

    _add_system_remark(
        application,
        f"Email sent to client ({to_email}): {subject}",
        author=actor,
    )
    return True, f"Email sent to {to_email}."


def push_lead_to_bank_email(application, *, actor) -> tuple:
    """Email qualified lead packet to bank recipients. Returns (ok, message)."""
    from communication.com_service import ComService
    from users.models import EducationLoanOpsSettings

    if application.status != choices.EducationLoanApplicationStatus.QUALIFIED:
        return False, "Only qualified leads can be pushed to the bank by email."

    ops = EducationLoanOpsSettings.load()
    recipients = ops.bank_email_list()
    if not recipients:
        return False, "No bank email recipients configured in Ops settings."

    template = (ops.bank_email_subject_template or "Qualified education loan lead — #{id}").strip()
    try:
        subject = template.format(id=application.id)
    except Exception:
        subject = f"Qualified education loan lead — #{application.id}"

    lines = _enquiry_summary_lines(application)
    lines.extend(
        [
            f"Interest rate: {application.interest_rate or '—'}",
            f"Tenure (years): {application.tenure_years or '—'}",
            f"Estimated EMI: {application.estimated_emi or '—'}",
            f"Qualification note: {application.qualification_note or '—'}",
            f"Additional details: {application.additional_details or '—'}",
        ]
    )
    body = "\n".join(lines)
    html = "<p>" + "<br>".join(lines) + "</p>"

    application.bank_email_status = choices.EducationLoanBankEmailStatus.PENDING
    application.bank_email_last_error = ""
    application.save(
        update_fields=["bank_email_status", "bank_email_last_error", "modified"]
    )

    try:
        ok = ComService().send_mail(subject, recipients, body, html)
    except Exception as exc:
        logger.exception("Bank email push failed for lead %s", application.id)
        application.bank_email_status = choices.EducationLoanBankEmailStatus.ERROR
        application.bank_email_last_error = str(exc)[:2000]
        application.save(
            update_fields=["bank_email_status", "bank_email_last_error", "modified"]
        )
        _add_system_remark(
            application,
            f"Bank email push failed: {application.bank_email_last_error}",
            author=actor,
        )
        return False, application.bank_email_last_error

    if not ok:
        application.bank_email_status = choices.EducationLoanBankEmailStatus.ERROR
        application.bank_email_last_error = "Mail service returned failure."
        application.save(
            update_fields=["bank_email_status", "bank_email_last_error", "modified"]
        )
        _add_system_remark(
            application,
            "Bank email push failed: mail service returned failure.",
            author=actor,
        )
        return False, application.bank_email_last_error

    application.bank_email_status = choices.EducationLoanBankEmailStatus.SENT
    application.bank_email_sent_at = timezone.now()
    application.bank_email_last_error = ""
    application.bank_email_message_id = ""
    application.save(
        update_fields=[
            "bank_email_status",
            "bank_email_sent_at",
            "bank_email_last_error",
            "bank_email_message_id",
            "modified",
        ]
    )
    _add_system_remark(
        application,
        f"Bank email sent to {', '.join(recipients)}.",
        author=actor,
    )
    return True, f"Bank email sent to {len(recipients)} recipient(s)."


def push_lead_to_bank_api(application, *, actor, force: bool = True) -> tuple:
    """Push qualified lead to Bank API; log remark. Returns (ok, message)."""
    from users.education_loan_crm import sync_education_loan_lead_to_crm

    if application.status != choices.EducationLoanApplicationStatus.QUALIFIED:
        return False, "Only qualified leads can be pushed to the Bank API."

    ok, message = sync_education_loan_lead_to_crm(
        application, force=force, require_qualified=True
    )
    application.refresh_from_db(
        fields=["crm_sync_status", "crm_sync_response", "crm_external_id", "crm_synced_at"]
    )
    if ok:
        ext = application.crm_external_id or "—"
        _add_system_remark(
            application,
            f"Bank API push succeeded. External id: {ext}.",
            author=actor,
        )
    else:
        _add_system_remark(
            application,
            f"Bank API push failed: {message}",
            author=actor,
        )
    return ok, message


def desk_base_queryset(user):
    """Non-draft leads scoped for manager (all) or executive (assigned/unassigned)."""
    from django.db.models import Q
    from users.models import EducationLoanApplication

    from loan_desk.decorators import is_loan_manager

    qs = (
        EducationLoanApplication.objects.exclude(
            status=choices.EducationLoanApplicationStatus.DRAFT
        )
        .select_related("assigned_to", "parent", "qualification_decided_by")
        .order_by("-submitted_at", "-id")
    )
    if not is_loan_manager(user) and not getattr(user, "is_superuser", False):
        qs = qs.filter(Q(assigned_to=user) | Q(assigned_to__isnull=True))
    return qs


def desk_search_clients(qs, query: str):
    """Filter leads by client name, mobile, email, institute, or enquiry id."""
    from django.db.models import Q

    q = (query or "").strip()
    if not q:
        return qs
    digits = "".join(ch for ch in q if ch.isdigit())
    filt = (
        Q(student_name__icontains=q)
        | Q(parent_name__icontains=q)
        | Q(email__icontains=q)
        | Q(institute_name__icontains=q)
        | Q(course_name__icontains=q)
        | Q(mobile__icontains=q)
    )
    if digits:
        filt |= Q(mobile__icontains=digits)
    if q.isdigit():
        try:
            filt |= Q(id=int(q))
        except (TypeError, ValueError):
            pass
    return qs.filter(filt)


def _local_day_bounds(day=None):
    """Return aware [start, end) for a local calendar day."""
    from datetime import datetime, time, timedelta

    from django.utils import timezone as dj_tz

    day = day or dj_tz.localdate()
    start = dj_tz.make_aware(
        datetime.combine(day, time.min), dj_tz.get_current_timezone()
    )
    return start, start + timedelta(days=1)


def _due_in_range_q(start, end):
    """Follow-up or callback scheduled within [start, end)."""
    from django.db.models import Q

    return Q(next_follow_up_at__gte=start, next_follow_up_at__lt=end) | Q(
        callback_preferred_at__gte=start, callback_preferred_at__lt=end
    )


def _uncleared_follow_up_q():
    """Scheduled follow-up/callback not yet actioned after its due time."""
    from django.db.models import F, Q

    St = choices.EducationLoanApplicationStatus
    next_uncleared = Q(next_follow_up_at__isnull=False) & (
        Q(last_followed_up_at__isnull=True)
        | Q(last_followed_up_at__lt=F("next_follow_up_at"))
    )
    callback_uncleared = (
        Q(callback_preferred_at__isnull=False)
        & Q(status=St.CALLBACK_SCHEDULED)
        & (
            Q(last_followed_up_at__isnull=True)
            | Q(last_followed_up_at__lt=F("callback_preferred_at"))
        )
    )
    return next_uncleared | callback_uncleared


def desk_queue_filter(qs, queue: str):
    """Apply named Loan Desk queue filter."""
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone as dj_tz

    queue = (queue or "not_started").strip().lower()
    if queue == "new":
        queue = "not_started"
    St = choices.EducationLoanApplicationStatus
    today = dj_tz.localdate()
    today_start, today_end = _local_day_bounds(today)
    y_start, y_end = _local_day_bounds(today - timedelta(days=1))

    if queue in ("not_started", "new"):
        # Brand-new enquiries — no desk work started yet
        return qs.filter(status=St.ENQUIRY_SENT)
    if queue == "not_followed_up":
        # In pipeline, never logged a follow-up (excludes pure "not started")
        return qs.filter(
            status__in=St.PENDING_STATUSES,
            last_followed_up_at__isnull=True,
        )
    if queue == "today":
        # Due today only (not older overdue)
        return (
            qs.filter(status__in=St.OPEN_STATUSES)
            .filter(_due_in_range_q(today_start, today_end))
            .filter(_uncleared_follow_up_q())
        )
    if queue == "missed_yesterday":
        # Scheduled for yesterday and still not cleared
        return (
            qs.filter(status__in=St.OPEN_STATUSES)
            .filter(_due_in_range_q(y_start, y_end))
            .filter(_uncleared_follow_up_q())
        )
    if queue == "pending":
        return qs.filter(status__in=St.PENDING_STATUSES)
    if queue == "qualified":
        return qs.filter(status=St.QUALIFIED)
    if queue == "not_qualified":
        return qs.filter(status=St.NOT_QUALIFIED)
    if queue == "unassigned":
        return qs.filter(assigned_to__isnull=True).exclude(
            status__in=(St.CLOSED, St.QUALIFIED, St.NOT_QUALIFIED)
        )
    if queue == "all":
        return qs
    return qs.filter(status=St.ENQUIRY_SENT)


def lead_identity_key(application) -> str:
    """
    Identity for unique-lead grouping.
    Prefer mobile (last 10 digits), then email, then parent+student name.
    """
    digits = "".join(ch for ch in str(getattr(application, "mobile", None) or "") if ch.isdigit())
    if len(digits) >= 10:
        return f"m:{digits[-10:]}"
    email = (getattr(application, "email", None) or "").strip().lower()
    if email and "@" in email:
        return f"e:{email}"
    parent_id = getattr(application, "parent_id", None)
    student = (getattr(application, "student_name", None) or "").strip().lower()
    if parent_id:
        return f"p:{parent_id}:{student}"
    return f"id:{getattr(application, 'id', 0)}"


def _attach_reenquiry_meta(latest, siblings: list) -> None:
    """Mutate latest app with re-enquiry fields for templates."""
    count = len(siblings)
    latest.enquiry_count = count
    latest.is_reenquired = count > 1
    latest.reenquiry_count = max(0, count - 1)
    # older enquiries (exclude latest)
    older = [a for a in siblings if a.id != latest.id]
    latest.previous_enquiries = older[:8]


def whatsapp_api_url(mobile: str) -> str:
    """
    Build api.whatsapp.com click-to-chat/call URL for a mobile number.
    Normalizes 10-digit Indian numbers to 91XXXXXXXXXX.
    """
    digits = "".join(ch for ch in str(mobile or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        digits = f"91{digits}"
    elif len(digits) == 11 and digits.startswith("0"):
        digits = f"91{digits[1:]}"
    elif digits.startswith("91") and len(digits) > 12:
        # keep country code + local; trim accidental extras only if clearly wrong
        digits = digits
    return f"https://api.whatsapp.com/send?phone={digits}"


def format_desk_datetime(dt) -> str:
    """Local date+time for caller-facing follow-up schedules."""
    if not dt:
        return ""
    local = timezone.localtime(dt)
    return local.strftime("%d %b %Y, %I:%M %p").lstrip("0").replace(" 0", " ")


def follow_up_action_for(application) -> dict:
    """
    What/when the caller should act on.
    Callback-scheduled leads use parent callback time; otherwise desk follow-up.
    """
    St = choices.EducationLoanApplicationStatus
    next_at = getattr(application, "next_follow_up_at", None)
    callback_at = getattr(application, "callback_preferred_at", None)
    note = (getattr(application, "callback_note", None) or "").strip()
    status = getattr(application, "status", None)

    if status == St.CALLBACK_SCHEDULED and callback_at:
        return {
            "kind": "callback",
            "label": "Callback",
            "when": callback_at,
            "when_label": format_desk_datetime(callback_at),
            "note": note,
        }
    if next_at:
        return {
            "kind": "follow_up",
            "label": "Follow-up call",
            "when": next_at,
            "when_label": format_desk_datetime(next_at),
            "note": note,
        }
    if callback_at:
        return {
            "kind": "callback",
            "label": "Callback",
            "when": callback_at,
            "when_label": format_desk_datetime(callback_at),
            "note": note,
        }
    return {
        "kind": "call",
        "label": "Call lead",
        "when": None,
        "when_label": "",
        "note": note,
    }


def attach_list_call_context(applications, *, remark_limit: int = 3) -> list:
    """
    Attach follow-up action + recent call remarks for queue cards.
    Remarks include notes from earlier enquiries of the same person (re-enquiries).
    """
    from collections import defaultdict

    from users.models import EducationLoanRemark

    apps = list(applications or [])
    if not apps:
        return apps

    source_ids_by_app = {}
    all_ids = []
    for app in apps:
        ids = [app.id]
        for prev in getattr(app, "previous_enquiries", None) or []:
            pid = getattr(prev, "id", None)
            if pid and pid not in ids:
                ids.append(pid)
        source_ids_by_app[app.id] = ids
        all_ids.extend(ids)

    remarks_by_app_id: dict = defaultdict(list)
    if all_ids:
        for remark in (
            EducationLoanRemark.objects.filter(application_id__in=all_ids)
            .select_related("author")
            .order_by("-created")
            .iterator(chunk_size=200)
        ):
            remarks_by_app_id[remark.application_id].append(remark)

    for app in apps:
        action = follow_up_action_for(app)
        app.follow_up_action = action
        app.follow_up_label = action["label"]
        app.follow_up_when_label = action["when_label"]
        app.follow_up_note = action["note"]
        app.whatsapp_url = whatsapp_api_url(getattr(app, "mobile", None) or "")

        from loan_desk.validation import parse_call_outcome_from_remark

        collected = []
        for rid in source_ids_by_app.get(app.id, [app.id]):
            collected.extend(remarks_by_app_id.get(rid, []))
        collected.sort(key=lambda r: r.created or timezone.now(), reverse=True)
        recent = []
        for remark in collected[: max(1, int(remark_limit or 3))]:
            author = remark.author
            outcome_key, outcome_label, note = parse_call_outcome_from_remark(
                remark.body or ""
            )
            recent.append(
                {
                    "when_label": format_desk_datetime(remark.created),
                    "author": (
                        (getattr(author, "name", None) or getattr(author, "email", None))
                        if author
                        else "System"
                    ),
                    "body": note or (remark.body or "").strip(),
                    "call_outcome": outcome_key,
                    "call_outcome_label": outcome_label,
                    "is_prior_enquiry": remark.application_id != app.id,
                }
            )
        app.recent_remarks = recent
        app.recent_remark_count = len(collected)
    return apps


def unique_leads_latest(qs) -> list:
    """
    One row per identity: latest submitted enquiry.
    Marks is_reenquired / enquiry_count when the same person enquired before.
    Identity counts use the full non-draft history for that key (not just the queue).
    """
    from collections import OrderedDict

    from users.models import EducationLoanApplication

    # Latest in this queryset (queue-filtered)
    latest_by_key: "OrderedDict[str, object]" = OrderedDict()
    for app in qs.iterator(chunk_size=300):
        key = lead_identity_key(app)
        if key not in latest_by_key:
            latest_by_key[key] = app

    if not latest_by_key:
        return []

    # Full history counts for those identities (all non-draft)
    keys = list(latest_by_key.keys())
    mobiles = [k[2:] for k in keys if k.startswith("m:")]
    emails = [k[2:] for k in keys if k.startswith("e:")]
    parent_pairs = []
    for k in keys:
        if k.startswith("p:"):
            parts = k.split(":", 2)
            if len(parts) == 3:
                try:
                    parent_pairs.append((int(parts[1]), parts[2]))
                except ValueError:
                    pass

    from django.db.models import Q

    hist_q = Q(id__in=[a.id for a in latest_by_key.values()])
    if mobiles:
        mq = Q()
        for m in mobiles:
            mq |= Q(mobile__endswith=m) | Q(mobile=m)
        hist_q |= mq
    if emails:
        eq = Q()
        for e in emails:
            eq |= Q(email__iexact=e)
        hist_q |= eq
    if parent_pairs:
        pq = Q()
        for pid, sname in parent_pairs:
            if sname:
                pq |= Q(parent_id=pid, student_name__iexact=sname)
            else:
                pq |= Q(parent_id=pid, student_name="")
        hist_q |= pq

    history = (
        EducationLoanApplication.objects.exclude(
            status=choices.EducationLoanApplicationStatus.DRAFT
        )
        .filter(hist_q)
        .only(
            "id",
            "mobile",
            "email",
            "parent_id",
            "student_name",
            "status",
            "submitted_at",
            "created",
        )
        .order_by("-submitted_at", "-id")
    )

    siblings_by_key: dict = {}
    for app in history.iterator(chunk_size=400):
        key = lead_identity_key(app)
        siblings_by_key.setdefault(key, []).append(app)

    unique = []
    for key, latest in latest_by_key.items():
        siblings = siblings_by_key.get(key) or [latest]
        _attach_reenquiry_meta(latest, siblings)
        unique.append(latest)
    return unique


def related_enquiries_for(application, *, limit: int = 10) -> list:
    """Other non-draft enquiries for the same identity (newest first, exclude self)."""
    from django.db.models import Q
    from users.models import EducationLoanApplication

    key = lead_identity_key(application)
    qs = EducationLoanApplication.objects.exclude(
        status=choices.EducationLoanApplicationStatus.DRAFT
    ).exclude(id=application.id)

    if key.startswith("m:"):
        m = key[2:]
        qs = qs.filter(Q(mobile__endswith=m) | Q(mobile=m))
    elif key.startswith("e:"):
        qs = qs.filter(email__iexact=key[2:])
    elif key.startswith("p:"):
        parts = key.split(":", 2)
        if len(parts) == 3:
            try:
                pid = int(parts[1])
            except ValueError:
                return []
            sname = parts[2]
            if sname:
                qs = qs.filter(parent_id=pid, student_name__iexact=sname)
            else:
                qs = qs.filter(parent_id=pid, student_name="")
        else:
            return []
    else:
        return []

    return list(qs.order_by("-submitted_at", "-id")[: max(1, int(limit or 10))])


def desk_queue_counts(user) -> dict:
    """Unique-lead counts per operational queue (latest identity only)."""
    base = desk_base_queryset(user)
    total = len(unique_leads_latest(desk_queue_filter(base, "all")))
    not_started = len(unique_leads_latest(desk_queue_filter(base, "not_started")))
    return {
        "total": total,
        "all": total,
        "not_started": not_started,
        "new": not_started,  # alias for older templates / links
        "not_followed_up": len(
            unique_leads_latest(desk_queue_filter(base, "not_followed_up"))
        ),
        "today": len(unique_leads_latest(desk_queue_filter(base, "today"))),
        "missed_yesterday": len(
            unique_leads_latest(desk_queue_filter(base, "missed_yesterday"))
        ),
        "pending": len(unique_leads_latest(desk_queue_filter(base, "pending"))),
        "qualified": len(unique_leads_latest(desk_queue_filter(base, "qualified"))),
        "not_qualified": len(
            unique_leads_latest(desk_queue_filter(base, "not_qualified"))
        ),
        "unassigned": len(unique_leads_latest(desk_queue_filter(base, "unassigned"))),
    }


def desk_dashboard_context(user) -> dict:
    """KPI + preview lists for manager/executive dashboard."""
    from loan_desk.decorators import is_loan_manager

    base = desk_base_queryset(user)
    counts = desk_queue_counts(user)
    return {
        "queue_counts": counts,
        "today_leads": unique_leads_latest(desk_queue_filter(base, "today"))[:6],
        "missed_leads": unique_leads_latest(
            desk_queue_filter(base, "missed_yesterday")
        )[:6],
        "not_started_leads": unique_leads_latest(
            desk_queue_filter(base, "not_started")
        )[:6],
        "not_followed_leads": unique_leads_latest(
            desk_queue_filter(base, "not_followed_up")
        )[:5],
        "qualified_leads": unique_leads_latest(
            desk_queue_filter(base, "qualified")
        )[:5],
        "unassigned_leads": unique_leads_latest(
            desk_queue_filter(base, "unassigned")
        )[:5],
        "is_manager": is_loan_manager(user) or getattr(user, "is_superuser", False),
    }
