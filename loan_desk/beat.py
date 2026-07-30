"""Sync loan daily-report send times into Celery beat_schedule."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from celery.schedules import crontab

logger = logging.getLogger(__name__)

LOAN_DAILY_REPORT_TASK = "loan_desk.tasks.send_loan_daily_report"
LOAN_DAILY_REPORT_PREFIX = "send-loan-daily-report"
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_daily_report_times(raw: str) -> List[Tuple[int, int]]:
    """Parse HH:MM values from commas / newlines / spaces. Deduped, sorted."""
    if not raw:
        return []
    found: List[Tuple[int, int]] = []
    seen = set()
    for part in re.split(r"[\s,;]+", str(raw).strip()):
        part = part.strip()
        if not part:
            continue
        m = _HHMM_RE.match(part)
        if not m:
            continue
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        key = (hour, minute)
        if key in seen:
            continue
        seen.add(key)
        found.append(key)
    found.sort()
    return found


def format_daily_report_times(times: List[Tuple[int, int]]) -> str:
    return "\n".join(f"{h:02d}:{m:02d}" for h, m in times)


def sync_loan_daily_report_beat_schedule(ops=None) -> int:
    """
    Update Celery beat_schedule for loan daily reports.

    - Enabled + times → one beat entry per HH:MM (IST / CELERY_TIMEZONE)
    - Disabled → remove all loan daily-report beat entries

    Returns number of active schedule entries.
    Note: Celery Beat must be restarted (or reloaded) to pick this up in workers.
    """
    try:
        from topteens.celery import app
    except Exception:
        logger.debug("Celery app unavailable; skip loan daily report beat sync")
        return 0

    sched = dict(app.conf.beat_schedule or {})
    for key in list(sched.keys()):
        if key == LOAN_DAILY_REPORT_PREFIX or str(key).startswith(
            LOAN_DAILY_REPORT_PREFIX + "-"
        ):
            del sched[key]

    enabled = True
    times: List[Tuple[int, int]] = [(9, 30)]
    try:
        if ops is None:
            from users.models import EducationLoanOpsSettings

            ops = EducationLoanOpsSettings.load()
        enabled = bool(getattr(ops, "daily_report_enabled", True))
        parsed = parse_daily_report_times(getattr(ops, "daily_report_times", "") or "")
        if parsed:
            times = parsed
    except Exception as exc:
        logger.debug("Loan ops settings unavailable for beat sync: %s", exc)

    count = 0
    if enabled:
        for hour, minute in times:
            key = f"{LOAN_DAILY_REPORT_PREFIX}-{hour:02d}{minute:02d}"
            sched[key] = {
                "task": LOAN_DAILY_REPORT_TASK,
                "schedule": crontab(minute=minute, hour=hour),
            }
            count += 1

    app.conf.beat_schedule = sched
    return count
