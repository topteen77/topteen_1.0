"""One daily email when the website recorded AI or other failures yesterday."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

logger = logging.getLogger(__name__)

_MAX_SAMPLES = 5


def report_day(day=None):
    """Calendar day the digest covers. Default is yesterday in the site timezone."""
    if day is not None:
        return day
    return timezone.localdate() - timedelta(days=1)


def alert_recipients(override_recipients=None):
    if override_recipients is not None:
        raw = str(override_recipients)
    else:
        raw = str(getattr(settings, "WEBADMINEMAIL", "") or "")
    emails = [part.strip() for part in raw.split(",") if part.strip()]
    if emails:
        return emails
    seen = []
    for email in list(getattr(settings, "EXCEPTION_EMAIL_TO", []) or []):
        email = str(email or "").strip()
        if email and email not in seen:
            seen.append(email)
    for _name, email in list(getattr(settings, "ADMINS", []) or []):
        email = str(email or "").strip()
        if email and email not in seen:
            seen.append(email)
    return seen


def _day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
    return start, start + timedelta(days=1)


def _ai_failures(day):
    from core.models import LLMUsageLog

    start, end = _day_bounds(day)
    rows = list(
        LLMUsageLog.objects.filter(success=False, created_at__gte=start, created_at__lt=end)
        .order_by("-created_at")
        .values("feature", "provider", "model", "error_message")
    )
    grouped = Counter()
    samples = {}
    for row in rows:
        key = (row["feature"] or "other", row["provider"] or "", row["model"] or "")
        grouped[key] += 1
        samples.setdefault(key, (row["error_message"] or "")[:180])
    lines = []
    for key, count in grouped.most_common(12):
        feature, provider, model = key
        lines.append({
            "label": "{} / {} / {}".format(feature, provider or "unknown", model or "unknown"),
            "count": count,
            "detail": samples.get(key) or "",
        })
    return len(rows), lines


def _email_failures(day):
    from communication.models import CommunicationLog
    from core import choices
    from topteens.email_logging import _parse_ts, load_email_log_entries_newest_first

    start, end = _day_bounds(day)
    jsonl_rows = []
    try:
        entries = load_email_log_entries_newest_first()
    except Exception:
        logger.exception("Could not read email send log for the daily failure alert")
        entries = []
    for entry in entries:
        if str(entry.get("status") or "").lower() != "failed":
            continue
        ts = _parse_ts(entry.get("ts"))
        if ts is None or timezone.localtime(ts).date() != day:
            continue
        jsonl_rows.append(entry)

    if jsonl_rows:
        lines = []
        for entry in jsonl_rows[:_MAX_SAMPLES]:
            lines.append({
                "label": (entry.get("subject") or "(no subject)")[:120],
                "count": 1,
                "detail": (entry.get("error") or "")[:180],
            })
        return len(jsonl_rows), lines

    logs = CommunicationLog.objects.filter(
        type=choices.CommunicationTypeChooices.EMAIL,
        created__gte=start,
        created__lt=end,
        response__istartswith="failed",
    ).order_by("-created")
    count = logs.count()
    lines = []
    for row in logs[:_MAX_SAMPLES]:
        lines.append({
            "label": (row.to or "")[:120],
            "count": 1,
            "detail": (row.response or "")[:180],
        })
    return count, lines


def _other_message_failures(day):
    from communication.models import CommunicationLog
    from core import choices

    start, end = _day_bounds(day)
    logs = CommunicationLog.objects.filter(
        created__gte=start,
        created__lt=end,
        response__istartswith="failed",
    ).exclude(type=choices.CommunicationTypeChooices.EMAIL)
    count = logs.count()
    lines = []
    for row in logs.order_by("-created")[:_MAX_SAMPLES]:
        lines.append({
            "label": "{} to {}".format(row.get_type_display(), (row.to or "")[:80]),
            "count": 1,
            "detail": (row.response or "")[:180],
        })
    return count, lines


def _payment_failures(day):
    from user_analytics.models import UserEvent

    start, end = _day_bounds(day)
    rows = UserEvent.objects.filter(
        event_type="payment_failed",
        created__gte=start,
        created__lt=end,
    ).order_by("-created")
    count = rows.count()
    lines = []
    for row in rows[:_MAX_SAMPLES]:
        meta = row.metadata if isinstance(row.metadata, dict) else {}
        detail = meta.get("error") or meta.get("reason") or row.event_name or ""
        lines.append({
            "label": (row.event_name or "Payment failed")[:120],
            "count": 1,
            "detail": str(detail)[:180],
        })
    return count, lines


def _server_errors(day):
    log_dir = getattr(settings, "LOG_DIR", "") or ""
    path = Path(log_dir) / "django_error.log"
    if not path.is_file():
        return 0, []
    prefix = day.isoformat()
    matched = []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - 2_000_000))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        logger.exception("Could not read django_error.log for the daily failure alert")
        return 0, []
    for line in text.splitlines():
        if line.startswith(prefix) and " ERROR " in line:
            matched.append(line.strip()[:220])
    samples = []
    for line in matched[-_MAX_SAMPLES:]:
        samples.append({"label": "Server error", "count": 1, "detail": line})
    return len(matched), samples


def collect_failures(day):
    sections = []
    total = 0
    for title, collector in (
        ("AI calls", _ai_failures),
        ("Email", _email_failures),
        ("SMS and WhatsApp", _other_message_failures),
        ("Payments", _payment_failures),
        ("Server errors", _server_errors),
    ):
        count, lines = collector(day)
        if count:
            sections.append({"title": title, "count": count, "lines": lines})
            total += count
    return total, sections


def _render(day, total, sections):
    subject = "[TopTeen] Daily failure alert - {}".format(day.isoformat())
    text_parts = [
        "TopTeen daily failure alert",
        "",
        "Date: {}".format(day.isoformat()),
        "Failures: {}".format(total),
        "",
    ]
    html_parts = [
        "<h3>TopTeen daily failure alert</h3>",
        "<p><strong>Date:</strong> {}</p>".format(escape(day.isoformat())),
        "<p><strong>Failures:</strong> {}</p>".format(total),
    ]
    for section in sections:
        text_parts.append("{}: {}".format(section["title"], section["count"]))
        html_parts.append(
            "<h4>{} ({})</h4><ul>".format(escape(section["title"]), section["count"])
        )
        for line in section["lines"]:
            detail = " — {}".format(line["detail"]) if line["detail"] else ""
            extra = ""
            if line["count"] > 1:
                extra = " ({} calls)".format(line["count"])
            text_parts.append("- {}{}{}".format(line["label"], extra, detail))
            html_parts.append(
                "<li><strong>{}</strong>{}{}</li>".format(
                    escape(line["label"]),
                    escape(extra),
                    escape(detail),
                )
            )
        html_parts.append("</ul>")
    text_parts.append("")
    text_parts.append("This is the only failure email for this day.")
    html_parts.append("<p>This is the only failure email for this day.</p>")
    return subject, "\n".join(text_parts), "".join(html_parts)


def send_daily_failure_alert(force_send=False, override_recipients=None, report_date=None):
    """
    Email one summary of yesterday's website failures.

    Skips a quiet day. Skips non-production unless force_send=True.
    Sends at most once per report date unless force_send=True.
    """
    from communication.models import CommunicationLog
    from core import choices

    environment = str(getattr(settings, "ENVIRONMENT", "")).strip().lower()
    if (not force_send) and environment != "production":
        logger.info("Skipping daily failure alert: ENVIRONMENT is not production.")
        return "skipped_non_production"

    day = report_day(report_date)
    subject, text_body, html_body = _render(day, 0, [])
    already_sent = CommunicationLog.objects.filter(
        type=choices.CommunicationTypeChooices.EMAIL,
        body=subject,
        response="success",
    ).exists()
    if already_sent and not force_send:
        logger.info("Skipping daily failure alert: already sent for %s.", day.isoformat())
        return "skipped_already_sent"

    total, sections = collect_failures(day)
    if total == 0:
        logger.info("Skipping daily failure alert: no failures on %s.", day.isoformat())
        return "skipped_no_failures"

    recipients = alert_recipients(override_recipients)
    if not recipients:
        logger.info("Skipping daily failure alert: no admin recipients configured.")
        return "skipped_missing_recipient"

    subject, text_body, html_body = _render(day, total, sections)
    from_email = (getattr(settings, "TOPTEEN_FROM_EMAIL", "") or "").strip() or getattr(
        settings, "DEFAULT_FROM_EMAIL", None
    ) or "noreply@example.com"

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipients,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
        CommunicationLog.objects.create(
            to=",".join(recipients),
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="success",
        )
        logger.info(
            "Daily failure alert sent (date=%s, failures=%s, recipients=%s).",
            day.isoformat(),
            total,
            len(recipients),
        )
        return {
            "date": day.isoformat(),
            "failures": total,
            "recipient_count": len(recipients),
        }
    except Exception as exc:
        CommunicationLog.objects.create(
            to=",".join(recipients),
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="failed: {}".format(exc),
        )
        logger.error("Failed to send daily failure alert: %s", exc, exc_info=True)
        raise
