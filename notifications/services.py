import glob
import logging
import os
import subprocess
from collections import deque

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from core import choices
from users.models import ParentStudentLink

from .models import (
    Notification,
    NotificationCategory,
    NotificationRoleHint,
    NotificationTypeConfig,
)

logger = logging.getLogger(__name__)
User = get_user_model()


DEFAULT_TYPE_CONFIGS = {
    'payment.success': dict(category=NotificationCategory.PAYMENT, description='Payment successful', requires_celery=False, requires_email=False),
    'payment.failed': dict(category=NotificationCategory.PAYMENT, description='Payment failed', requires_celery=False, requires_email=False),
    'payment.status_updated': dict(category=NotificationCategory.PAYMENT, description='Payment status updated', requires_celery=False, requires_email=False),
    'course.allocated': dict(category=NotificationCategory.COURSE, description='Course allocated', requires_celery=False, requires_email=False),
    'institute.student_registered': dict(category=NotificationCategory.INSTITUTE, description='Institute student registration', requires_celery=False, requires_email=False),
    'marketing.new_lead': dict(category=NotificationCategory.MARKETING, description='New lead for marketing team', requires_celery=False, requires_email=False),
}


def ensure_default_notification_types():
    for event_type, cfg in DEFAULT_TYPE_CONFIGS.items():
        NotificationTypeConfig.objects.get_or_create(
            event_type=event_type,
            defaults={
                'category': cfg.get('category', NotificationCategory.SYSTEM),
                'description': cfg.get('description', ''),
                'enabled': True,
                'requires_celery': cfg.get('requires_celery', False),
                'requires_email': cfg.get('requires_email', False),
                'requires_redis': cfg.get('requires_redis', False),
            },
        )


def _check_celery_ok():
    if not getattr(settings, 'ENABLE_CELERY', False):
        return True
    try:
        from user_analytics.tasks import _check_celery_workers_active

        return bool(_check_celery_workers_active())
    except Exception:
        return False


def _check_email_ok():
    host = (getattr(settings, 'EMAIL_HOST', '') or '').strip()
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()
    return bool(host and from_email)


def _check_redis_ok():
    if not getattr(settings, 'ENABLE_REDIS', False):
        return True
    try:
        import redis

        url = getattr(settings, 'CELERY_BROKER_URL', '') or getattr(settings, 'REDIS_URL', '')
        if not url:
            return False
        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def _is_process_running(pattern):
    try:
        result = subprocess.run(
            ['pgrep', '-f', pattern],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        return result.returncode == 0 and bool((result.stdout or '').strip())
    except Exception:
        return False


def _tail_file(path, lines=40, max_chars=12000):
    if not path or not os.path.exists(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            dq = deque(fh, maxlen=lines)
        text = ''.join(dq).strip()
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text
    except Exception:
        return ''


def _service_log_candidates():
    log_dir = getattr(settings, 'LOG_DIR', '') or ''
    candidates = {
        'django': [
            os.path.join(log_dir, 'django_error.log') if log_dir else '',
            os.path.join(log_dir, 'django_app.log') if log_dir else '',
        ],
        'celery': [
            os.path.join(log_dir, 'celery.log') if log_dir else '',
            '/var/log/celery/worker.log',
            '/var/log/celery/celery.log',
            '/var/log/supervisor/celery.log',
            '/var/log/supervisor/celery-worker.log',
        ],
        'gunicorn': [
            os.path.join(log_dir, 'gunicorn_error.log') if log_dir else '',
            os.path.join(log_dir, 'gunicorn.log') if log_dir else '',
            '/var/log/gunicorn/error.log',
            '/var/log/gunicorn/gunicorn.log',
            '/var/log/supervisor/gunicorn.log',
        ],
    }

    # Optional overrides from env for custom deployments.
    env_map = {
        'django': getattr(settings, 'SERVICE_LOG_DJANGO', ''),
        'celery': getattr(settings, 'SERVICE_LOG_CELERY', ''),
        'gunicorn': getattr(settings, 'SERVICE_LOG_GUNICORN', ''),
    }
    for service_name, custom_path in env_map.items():
        if custom_path:
            candidates[service_name].insert(0, custom_path)
    return candidates


def _existing_paths_with_glob(paths):
    out = []
    for p in paths:
        if not p:
            continue
        matched = glob.glob(p)
        if matched:
            for m in matched:
                if os.path.isfile(m):
                    out.append(m)
            continue
        if os.path.isfile(p):
            out.append(p)
    return out


def get_runtime_service_status():
    celery_ok = _check_celery_ok()
    redis_ok = _check_redis_ok()
    email_ok = _check_email_ok()
    gunicorn_ok = _is_process_running('gunicorn')
    celery_proc_ok = _is_process_running('celery')

    service_rows = [
        {'key': 'db', 'label': 'Database', 'ok': True, 'detail': 'Django DB is reachable through request flow.', 'required': True},
        {'key': 'redis', 'label': 'Redis', 'ok': redis_ok, 'detail': 'Used by Celery broker/cache when enabled.', 'required': bool(getattr(settings, 'ENABLE_REDIS', False))},
        {'key': 'celery', 'label': 'Celery Worker', 'ok': celery_ok and celery_proc_ok, 'detail': 'Worker heartbeat and process check.', 'required': bool(getattr(settings, 'ENABLE_CELERY', False))},
        {'key': 'gunicorn', 'label': 'Gunicorn', 'ok': gunicorn_ok, 'detail': 'OS process availability check.', 'required': True},
        {'key': 'email', 'label': 'Email config', 'ok': email_ok, 'detail': 'SMTP host/from-email present.', 'required': True},
    ]

    logs = {}
    for service_name, paths in _service_log_candidates().items():
        existing = _existing_paths_with_glob(paths)
        selected = existing[0] if existing else ''
        logs[service_name] = {
            'path': selected,
            'tail': _tail_file(selected),
        }

    all_required_ok = True
    for row in service_rows:
        if row['required'] and not row['ok']:
            all_required_ok = False
            break

    return {
        'all_required_ok': all_required_ok,
        'services': service_rows,
        'logs': logs,
    }


def check_notification_dependencies():
    runtime_status = get_runtime_service_status()
    statuses = {
        row['key']: bool(row['ok'])
        for row in runtime_status['services']
    }
    statuses['all_required_ok'] = bool(runtime_status['all_required_ok'])
    statuses['service_rows'] = runtime_status['services']
    statuses['logs'] = runtime_status['logs']
    return statuses


def notification_role_hint_for_user(user):
    if not user:
        return NotificationRoleHint.UNKNOWN
    if user.is_superuser:
        return NotificationRoleHint.ADMIN
    if user.is_staff and user.groups.filter(Q(name__iexact='Accounts') | Q(name__iexact='Accounts staff')).exists():
        return NotificationRoleHint.ACCOUNTS
    if user.user_type == choices.UserType.STUDENT:
        return NotificationRoleHint.STUDENT
    if user.user_type == choices.UserType.PARENT:
        return NotificationRoleHint.PARENT
    if user.user_type in (choices.UserType.INSTITUTE, choices.UserType.INSTITUTEGROUPADMIN):
        return NotificationRoleHint.INSTITUTE
    if user.user_type == choices.UserType.MARKETINGGROUPADMIN:
        return NotificationRoleHint.MARKETING
    if user.is_staff:
        return NotificationRoleHint.ADMIN
    return NotificationRoleHint.UNKNOWN


def get_admin_and_accounts_users():
    return User.objects.filter(
        is_active=True,
    ).filter(
        Q(is_superuser=True) | Q(is_staff=True, groups__name__in=['Accounts', 'Accounts staff'])
    ).distinct()


def get_parent_users_for_student(student_user_id):
    parent_ids = ParentStudentLink.objects.filter(student_id=student_user_id).values_list('parent_id', flat=True)
    return User.objects.filter(id__in=parent_ids, is_active=True)


def _event_enabled(event_type):
    ensure_default_notification_types()
    cfg = NotificationTypeConfig.objects.filter(event_type=event_type).first()
    if not cfg:
        return False, None
    return bool(cfg.enabled), cfg


def emit_notification(
    *,
    event_type,
    title,
    body='',
    recipients,
    category=NotificationCategory.SYSTEM,
    payload=None,
    source_obj=None,
    dedupe_key='',
):
    enabled, _cfg = _event_enabled(event_type)
    if not enabled:
        return []
    deps = check_notification_dependencies()
    if not deps.get('all_required_ok', False):
        logger.warning('Notification emit skipped (deps unhealthy) event=%s deps=%s', event_type, deps)
        return []

    payload = payload or {}
    recipients = [u for u in recipients if getattr(u, 'id', None)]
    if not recipients:
        return []

    content_type = None
    object_id = None
    if source_obj is not None and getattr(source_obj, 'id', None):
        content_type = ContentType.objects.get_for_model(source_obj)
        object_id = source_obj.id

    created_rows = []

    def _create():
        nonlocal created_rows
        for user in recipients:
            row = Notification(
                recipient=user,
                role_hint=notification_role_hint_for_user(user),
                category=category,
                event_type=event_type,
                title=title[:255],
                body=body or '',
                payload=payload,
                content_type=content_type,
                object_id=object_id,
                dedupe_key=(dedupe_key or '')[:255],
            )
            try:
                row.save()
                created_rows.append(row)
            except Exception:
                # Unique dedupe collision is expected for retries.
                continue

    transaction.on_commit(_create)
    return created_rows

