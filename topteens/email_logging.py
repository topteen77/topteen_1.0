"""
Append-only JSONL log for outbound email (used by logging mail backends + Email logs admin page).
Each line: ts, subject, from_email, to, status, error.

Retention: drop entries older than 30 days, but always keep the newest 10 rows.
"""
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_MAX_FILE_LINES_SCAN = 40000
_RETENTION_DAYS = 30
_KEEP_MIN_ENTRIES = 10


def _log_path():
    raw = getattr(settings, 'EMAIL_SEND_LOG_PATH', None)
    if raw:
        return Path(raw)
    base = getattr(settings, 'BASE_DIR', None)
    if not base:
        return Path('logs') / 'email_send.jsonl'
    return Path(base) / 'logs' / 'email_send.jsonl'


def get_email_send_log_path():
    """Absolute path for display in admin UI."""
    return str(_log_path().resolve())


def _parse_ts(ts_iso):
    if not ts_iso:
        return None
    try:
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(str(ts_iso))
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _read_entries(path):
    if not path.is_file():
        return []
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
    except OSError:
        return []
    out = []
    for line in lines[-_MAX_FILE_LINES_SCAN:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _entries_newest_first(entries):
    return sorted(entries, key=lambda r: (r.get('ts') or ''), reverse=True)


def prune_email_send_log_entries(entries):
    """
    Keep entries newer than 30 days, and always keep the newest 10
    (even if those 10 are older than a month).
    Returns oldest-first list suitable for rewriting the JSONL file.
    """
    if not entries:
        return []
    newest_first = _entries_newest_first(entries)
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    kept = []
    for index, entry in enumerate(newest_first):
        if index < _KEEP_MIN_ENTRIES:
            kept.append(entry)
            continue
        ts = _parse_ts(entry.get('ts'))
        if ts is not None and ts >= cutoff:
            kept.append(entry)
    # Rewrite oldest-first so append order stays chronological.
    kept.reverse()
    return kept


def _rewrite_log_file(path, entries_oldest_first):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        for rec in entries_oldest_first:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    tmp.replace(path)


def append_email_send_log(*, to_emails, subject, from_email, status, error=None):
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'subject': (subject or '')[:2000],
            'from_email': (from_email or '')[:500],
            'to': list(to_emails) if to_emails else [],
            'status': status,
            'error': (error or '')[:4000] if error else '',
        }
        with _lock:
            entries = _read_entries(path)
            entries.append(rec)
            kept = prune_email_send_log_entries(entries)
            _rewrite_log_file(path, kept)
    except Exception as exc:
        logger.warning('email_send.jsonl append failed: %s', exc)


def _recipient_list(message):
    emails = []
    for attr in ('to', 'cc', 'bcc'):
        raw = getattr(message, attr, None) or []
        if isinstance(raw, (list, tuple)):
            emails.extend([str(x) for x in raw])
        elif raw:
            emails.append(str(raw))
    return emails


def log_from_email_message(message, status, error=None):
    subj = getattr(message, 'subject', '') or ''
    from_email = getattr(message, 'from_email', None) or ''
    if not (from_email or '').strip():
        from_email = str(getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '')
    append_email_send_log(
        to_emails=_recipient_list(message),
        subject=subj,
        from_email=str(from_email).strip(),
        status=status,
        error=error,
    )


def load_email_log_entries_newest_first():
    """Parse JSONL, prune retention, return list newest-first."""
    path = _log_path()
    with _lock:
        entries = _read_entries(path)
        kept = prune_email_send_log_entries(entries)
        if len(kept) != len(entries) and path.is_file():
            try:
                _rewrite_log_file(path, kept)
            except OSError as exc:
                logger.warning('email_send.jsonl prune rewrite failed: %s', exc)
        return _entries_newest_first(kept)


def format_ts_for_display(ts_iso):
    """Format stored UTC ISO string for staff UI (local timezone)."""
    if not ts_iso:
        return '—'
    try:
        from django.utils import timezone as dj_tz
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(ts_iso)
        if dt is None:
            return str(ts_iso)
        if dj_tz.is_naive(dt):
            dt = dj_tz.make_aware(dt, timezone.utc)
        return dj_tz.localtime(dt).strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        return str(ts_iso)
