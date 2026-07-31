"""Validation helpers for Loan Desk PWA forms."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core import choices

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MOBILE_DIGITS_RE = re.compile(r"^\d{10}$")


def validate_login(email: str, password: str) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    email = (email or "").strip()
    password = password or ""
    if not email:
        errors["email"] = "Email is required."
    elif not _EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 4:
        errors["password"] = "Password looks too short."
    return (not errors, errors)


CALL_OUTCOME_CONNECTED = "connected"
CALL_OUTCOME_NOT_CONNECTED = "not_connected"
CALL_OUTCOME_CHOICES = (
    (CALL_OUTCOME_CONNECTED, "Call connected"),
    (CALL_OUTCOME_NOT_CONNECTED, "Call not connected"),
)
CALL_OUTCOME_LABELS = dict(CALL_OUTCOME_CHOICES)


def validate_call_outcome(raw: str) -> Tuple[bool, Dict[str, str], Optional[str]]:
    errors: Dict[str, str] = {}
    value = (raw or "").strip().lower()
    if value not in CALL_OUTCOME_LABELS:
        errors["call_outcome"] = "Select whether the call connected."
        return False, errors, None
    return True, errors, value


def format_remark_with_call_outcome(body: str, outcome: str) -> str:
    """Prefix call notes with connected / not-connected status."""
    label = CALL_OUTCOME_LABELS.get(outcome) or "Call"
    note = (body or "").strip()
    if note:
        return f"{label}. {note}"[:5000]
    return f"{label}."[:5000]


def parse_call_outcome_from_remark(body: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Return (outcome_key, outcome_label, note_without_prefix).
    """
    text = (body or "").strip()
    lower = text.lower()
    if lower.startswith("call not connected"):
        rest = text[len("Call not connected") :].lstrip(" .:-")
        return CALL_OUTCOME_NOT_CONNECTED, CALL_OUTCOME_LABELS[CALL_OUTCOME_NOT_CONNECTED], rest
    if lower.startswith("call connected"):
        rest = text[len("Call connected") :].lstrip(" .:-")
        return CALL_OUTCOME_CONNECTED, CALL_OUTCOME_LABELS[CALL_OUTCOME_CONNECTED], rest
    return None, None, text


def validate_client_email(subject: str, body: str) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        errors["subject"] = "Subject is required."
    elif len(subject) > 200:
        errors["subject"] = "Subject must be at most 200 characters."
    if not body:
        errors["body"] = "Message is required."
    elif len(body) < 3:
        errors["body"] = "Message must be at least 3 characters."
    elif len(body) > 8000:
        errors["body"] = "Message must be at most 8000 characters."
    return (not errors, errors)


def validate_email_template(
    name: str, subject: str, body: str, sort_order: str = "0"
) -> Tuple[bool, Dict[str, str], Dict[str, object]]:
    errors: Dict[str, str] = {}
    name = (name or "").strip()
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not name:
        errors["name"] = "Template name is required."
    elif len(name) > 120:
        errors["name"] = "Name must be at most 120 characters."
    if not subject:
        errors["subject"] = "Subject is required."
    elif len(subject) > 200:
        errors["subject"] = "Subject must be at most 200 characters."
    if not body:
        errors["body"] = "Message body is required."
    elif len(body) > 8000:
        errors["body"] = "Body must be at most 8000 characters."
    order = 0
    raw_order = (sort_order or "0").strip()
    try:
        order = int(raw_order)
        if order < 0 or order > 9999:
            errors["sort_order"] = "Sort order must be between 0 and 9999."
    except ValueError:
        errors["sort_order"] = "Sort order must be a number."
    cleaned = {
        "name": name[:120],
        "subject": subject[:200],
        "body": body[:8000],
        "sort_order": order,
    }
    return (not errors, errors, cleaned)


def validate_remark(body: str) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    body = (body or "").strip()
    if not body:
        errors["body"] = "Remark cannot be empty."
    elif len(body) < 3:
        errors["body"] = "Remark must be at least 3 characters."
    elif len(body) > 5000:
        errors["body"] = "Remark must be at most 5000 characters."
    return (not errors, errors)


def validate_follow_up(raw: str, *, allow_past: bool = False) -> Tuple[bool, Dict[str, str], Optional[object]]:
    errors: Dict[str, str] = {}
    raw = (raw or "").strip()
    if not raw:
        errors["next_follow_up_at"] = "Choose a follow-up date and time."
        return False, errors, None
    dt = parse_datetime(raw.replace("T", " ", 1))
    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                dt = None
    if dt is None:
        errors["next_follow_up_at"] = "Enter a valid date and time."
        return False, errors, None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    if not allow_past and dt < timezone.now() - timedelta(minutes=1):
        errors["next_follow_up_at"] = "Follow-up must be in the future."
        return False, errors, None
    return True, errors, dt


def validate_status(
    raw,
    *,
    has_schedule_datetime: bool = False,
) -> Tuple[bool, Dict[str, str], Optional[int]]:
    errors: Dict[str, str] = {}
    try:
        st = int(raw)
    except (TypeError, ValueError):
        errors["status"] = "Select a valid status."
        return False, errors, None
    valid = {
        c[0]
        for c in choices.EducationLoanApplicationStatus.CHOICES
        if c[0] != choices.EducationLoanApplicationStatus.DRAFT
    }
    if st not in valid:
        errors["status"] = "Select a valid status."
        return False, errors, None
    needs_date = {
        choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED,
        choices.EducationLoanApplicationStatus.FOLLOW_UP,
    }
    if st in needs_date and not has_schedule_datetime:
        errors["status"] = (
            "Schedule a date & time first (use Schedule follow-up below), "
            "then set this status."
        )
        return False, errors, None
    return True, errors, st


def validate_assignee(raw, *, team_ids: Optional[List[int]] = None) -> Tuple[bool, Dict[str, str], Optional[int]]:
    """Return (ok, errors, assigned_to_id or None for unassigned)."""
    errors: Dict[str, str] = {}
    raw = (raw or "").strip()
    if raw in ("", "0"):
        return True, errors, None
    try:
        aid = int(raw)
    except (TypeError, ValueError):
        errors["assigned_to"] = "Select a valid team member."
        return False, errors, None
    if team_ids is not None and aid not in team_ids:
        errors["assigned_to"] = "Assignee must be an enabled Loan Manager or Executive."
        return False, errors, None
    return True, errors, aid


def validate_disqualify(
    reason: str, reason_text: str = ""
) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    reason = (reason or "").strip()
    reason_text = (reason_text or "").strip()
    valid = {c[0] for c in choices.EducationLoanDisqualifyReason.CHOICES}
    if reason not in valid:
        errors["disqualify_reason"] = "Select a disqualify reason."
    elif reason == choices.EducationLoanDisqualifyReason.OTHER and len(reason_text) < 3:
        errors["disqualify_reason_text"] = "Add a short note for reason Other."
    elif len(reason_text) > 500:
        errors["disqualify_reason_text"] = "Note must be at most 500 characters."
    return (not errors, errors)


def validate_qualify_note(note: str = "") -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    note = (note or "").strip()
    if len(note) > 500:
        errors["qualification_note"] = "Note must be at most 500 characters."
    return (not errors, errors)
