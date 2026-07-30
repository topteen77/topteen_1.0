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
