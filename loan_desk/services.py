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


def instant_login_url(request, user, application) -> str:
    from users.models import EducationLoanOpsSettings

    ops = EducationLoanOpsSettings.load()
    raw = create_instant_login_token(
        user, application, ttl_hours=ops.instant_login_ttl_hours
    )
    path = reverse("loan_desk:instant_login", kwargs={"token": raw})
    if request is not None:
        return request.build_absolute_uri(path)
    from django.conf import settings

    base = getattr(settings, "SITE_URL", "") or getattr(settings, "BASE_URL", "") or ""
    return f"{base.rstrip('/')}{path}" if base else path


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
        try:
            url = instant_login_url(request, user, application)
            _send_enquiry_email_to_user(
                user, application, instant_url=url, event=event
            )
            sent += 1
        except Exception:
            logger.exception("Failed loan enquiry notify to user %s", user.id)

    # Also notify configured manager report emails (if not already covered)
    already = {
        (getattr(u, "email", None) or "").strip().lower()
        for u in recipients
        if (getattr(u, "email", None) or "").strip()
    }
    for email in ops.manager_email_list():
        if email.lower() in already:
            continue
        try:
            _send_enquiry_email_to_address(
                email, application, request=request, event=event, instant_url=""
            )
            sent += 1
        except Exception:
            logger.exception("Failed loan enquiry notify to %s", email)
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
        url = reverse("loan_desk:detail", kwargs={"pk": application.id})

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
    lines.append(f"Open enquiry (instant login): {url}")
    body = "\n".join(lines)
    html = (
        "<p>A loan enquiry has been assigned to you as lead follow."
        + (f"<br>Assigned by: {by_name}" if by_name else "")
        + "</p><p>"
        + "<br>".join(_enquiry_summary_lines(application))
        + f'</p><p><a href="{url}">View enquiry (instant login)</a></p>'
    )
    try:
        ok = ComService().send_mail(subject, [email], body, html)
        return 1 if ok else 0
    except Exception:
        logger.exception("Failed assignment notify to user %s", user.id)
        return 0


def _send_enquiry_email_to_user(user, application, *, instant_url: str, event: str) -> None:
    from communication.com_service import ComService

    subject = (
        f"Loan callback scheduled — #{application.id}"
        if event == "callback"
        else f"New loan enquiry — #{application.id}"
    )
    lines = _enquiry_summary_lines(application)
    lines.append("")
    lines.append(f"Open enquiry (instant login): {instant_url}")
    body = "\n".join(lines)
    html = (
        "<p>"
        + "<br>".join(_enquiry_summary_lines(application))
        + f'</p><p><a href="{instant_url}">View enquiry (instant login)</a></p>'
    )
    ComService().send_mail(
        subject,
        [user.email],
        body,
        html,
    )


def _send_enquiry_email_to_address(
    email: str, application, *, request=None, event: str = "enquiry", instant_url: str = ""
) -> None:
    from communication.com_service import ComService

    subject = (
        f"Loan callback scheduled — #{application.id}"
        if event == "callback"
        else f"New loan enquiry — #{application.id}"
    )
    desk = reverse("loan_desk:home")
    if request is not None:
        desk = request.build_absolute_uri(desk)
    lines = _enquiry_summary_lines(application)
    lines.append("")
    lines.append(f"Loan Desk: {instant_url or desk}")
    body = "\n".join(lines)
    ComService().send_mail(subject, [email], body, f"<pre>{body}</pre>")


def _enquiry_summary_lines(application) -> List[str]:
    return [
        f"Enquiry ID: {application.id}",
        f"Status: {application.get_status_display()}",
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
    return (
        f"Loan enquiry daily report — {today.isoformat()}\n\n"
        f"New today: {new_today}\n"
        f"Open: {open_total}\n"
        f"Callback scheduled: {callbacks}\n"
        f"Needs follow-up reminder (rule: {hours}h): {reminder_count}\n"
        f"Closed: {closed}\n"
    )
