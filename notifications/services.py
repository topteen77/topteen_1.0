import glob
import logging
import os
import re
import subprocess
from collections import deque
from urllib.parse import urlparse

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
    NotificationMessageTemplate,
    NotificationRoleHint,
    NotificationTypeConfig,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def detect_notification_environment(host=''):
    h = (host or '').lower().strip()
    if h:
        if h.startswith('localhost') or h.startswith('127.0.0.1') or h.startswith('0.0.0.0') or h.endswith('.local'):
            return Notification.Environment.DEVELOPMENT
        return Notification.Environment.PRODUCTION
    if getattr(settings, 'DEBUG', False):
        return Notification.Environment.DEVELOPMENT
    return Notification.Environment.PRODUCTION


DEFAULT_TYPE_CONFIGS = {
    'payment.success': dict(category=NotificationCategory.PAYMENT, description='Payment successful', requires_celery=False, requires_email=False),
    'payment.resolved': dict(
        category=NotificationCategory.PAYMENT,
        description='Payment succeeded after prior non-success (callback or reconciliation)',
        requires_celery=False,
        requires_email=False,
    ),
    'payment.failed': dict(category=NotificationCategory.PAYMENT, description='Payment failed', requires_celery=False, requires_email=False),
    'payment.status_updated': dict(category=NotificationCategory.PAYMENT, description='Payment status updated', requires_celery=False, requires_email=False),
    'course.allocated': dict(category=NotificationCategory.COURSE, description='Course allocated', requires_celery=False, requires_email=False),
    'institute.student_registered': dict(category=NotificationCategory.INSTITUTE, description='Institute student registration', requires_celery=False, requires_email=False),
    'marketing.new_lead': dict(category=NotificationCategory.MARKETING, description='New lead for marketing team', requires_celery=False, requires_email=False),
    'accounts.new_registration': dict(
        category=NotificationCategory.MARKETING,
        description='New end-user registration (analytics)',
        requires_celery=False,
        requires_email=False,
    ),
    'institute.student_assigned': dict(
        category=NotificationCategory.INSTITUTE,
        description='Student assigned to counselor',
        requires_celery=False,
        requires_email=False,
    ),
    'parent.suggestion_added': dict(
        category=NotificationCategory.SYSTEM,
        description='Parent shortlisted career/video/blog/college for linked student',
        requires_celery=False,
        requires_email=False,
    ),
    'parent.suggestion_disliked': dict(
        category=NotificationCategory.SYSTEM,
        description='Student disliked a parent career recommendation',
        requires_celery=False,
        requires_email=False,
    ),
    'parent.suggestion_liked': dict(
        category=NotificationCategory.SYSTEM,
        description='Student liked a parent career recommendation',
        requires_celery=False,
        requires_email=False,
    ),
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


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return ''


DEFAULT_NOTIFICATION_MESSAGE_TEMPLATES = {
    'payment.success': {
        'title': 'Payment successful',
        'body': 'Your payment of {amount_display} for {item} was received successfully.',
    },
    'payment.resolved': {
        'title': 'Payment issue resolved',
        'body': (
            'Your payment of {amount_display} for {item} is now successful. '
            'If you saw an error or pending status earlier, that issue is resolved.'
        ),
    },
    'payment.failed': {
        'title': 'Payment failed',
        'body': (
            'We could not confirm your payment of {amount_display} for {item}. '
            '{retry_payment_hint}'
        ),
    },
    'payment.status_updated': {
        'title': 'Payment status updated',
        'body': 'Payment {payment_id} for {item} ({amount_display}) marked {status}. {extra}',
    },
    'institute.student_assigned': {
        'title': 'New student assigned',
        'body': 'A new student {student_name} ({student_email}) was assigned to you by {institute_name}.',
    },
    'parent.suggestion_added': {
        'title': 'New {item_kind} suggestion from {parent_name}',
        'body': '{parent_name} shortlisted "{item_title}" for you. Open it from your dashboard or the relevant page.',
    },
    'parent.suggestion_disliked': {
        'title': '{student_name} disliked your career suggestion',
        'body': '{student_name} is not interested in "{career_name}" that you recommended.',
    },
    'parent.suggestion_liked': {
        'title': '{student_name} liked your career suggestion',
        'body': '{student_name} is interested in "{career_name}" that you recommended.',
    },
}


def ensure_default_notification_message_templates():
    """Seed DB rows so Django admin can edit copy; empty template fields mean built-in defaults apply."""
    ensure_default_notification_types()
    for event_type, defaults in DEFAULT_NOTIFICATION_MESSAGE_TEMPLATES.items():
        NotificationMessageTemplate.objects.get_or_create(
            event_type=event_type,
            defaults={
                'title_template': '',
                'body_template': '',
                'is_active': True,
            },
        )


def format_notification_message(event_type, context, default_title, default_body):
    """
    Apply optional admin ``NotificationMessageTemplate`` overrides.

    ``default_title`` / ``default_body`` may contain ``{placeholders}``; ``context`` supplies values.
    """
    ensure_default_notification_message_templates()
    ctx = _SafeFormatDict(context or {})
    try:
        title = (default_title or '').format_map(ctx)[:255]
    except Exception:
        title = (default_title or '')[:255]
    try:
        body = (default_body or '').format_map(ctx)
    except Exception:
        body = default_body or ''

    tpl = NotificationMessageTemplate.objects.filter(event_type=event_type, is_active=True).first()
    if tpl:
        if (tpl.title_template or '').strip():
            try:
                title = (tpl.title_template or '').strip().format_map(ctx)[:255]
            except Exception:
                pass
        if (tpl.body_template or '').strip():
            try:
                body = (tpl.body_template or '').strip().format_map(ctx)
            except Exception:
                pass
    return title, body


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


def _run_command(cmd, timeout=2):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=timeout,
        )
        return (result.returncode == 0, (result.stdout or '').strip(), (result.stderr or '').strip())
    except Exception as exc:
        return (False, '', str(exc))


def _looks_local_host(host):
    h = (host or '').strip().lower()
    return h in ('localhost', '127.0.0.1', '0.0.0.0', '::1', '')


def _source_from_host(host):
    if _looks_local_host(host):
        return ('local', 'Local host')
    return ('remote', f'Remote ({host})')


def _source_from_url(url):
    if not url:
        return ('unknown', 'Unknown')
    parsed = urlparse(url)
    host = (parsed.hostname or '').strip()
    if _looks_local_host(host):
        return ('local', 'Local host')
    if host:
        return ('remote', f'Remote ({host})')
    return ('unknown', 'Unknown')


def _running_inside_docker():
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/1/cgroup', 'r', encoding='utf-8', errors='ignore') as fh:
            text = fh.read().lower()
            return ('docker' in text) or ('containerd' in text) or ('kubepods' in text)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Runtime identity: THIS TopTeen stack (compose project / image / ports / CLI app)
# vs other apps on the same host (apravas, indo-israel, olympiad, …).
# ---------------------------------------------------------------------------

def _csv_setting(name, default=''):
    raw = getattr(settings, name, default) or default
    return [p.strip() for p in str(raw).split(',') if p.strip()]


def _project_identity():
    """Expected Docker/env fingerprints for this deployment (from settings /.env)."""
    project = (getattr(settings, 'COMPOSE_PROJECT_NAME', None) or 'topteens').strip() or 'topteens'
    celery_app = (getattr(settings, 'SERVICE_MONITOR_CELERY_APP', None) or 'topteens').strip() or 'topteens'
    guni_mod = (getattr(settings, 'SERVICE_MONITOR_GUNICORN_MODULE', None) or 'topteens.wsgi').strip()
    image = (getattr(settings, 'DOCKER_IMAGE', None) or 'developertopteen/demotopteen').strip()
    image_nginx = (getattr(settings, 'DOCKER_IMAGE_NGINX', None) or f'{image}-nginx').strip()
    app_port = str(getattr(settings, 'APP_PORT', None) or '80').strip()
    https_port = str(getattr(settings, 'HTTPS_PORT', None) or '443').strip()
    # Compose v2 names: {project}-{service}-1
    expected = {
        'web': f'{project}-web-1',
        'nginx': f'{project}-nginx-1',
        'celery': f'{project}-celery-1',
        'celery_beat': f'{project}-celery_beat-1',
        'redis': f'{project}-redis-1',
    }
    # Also accept underscore form from older compose
    expected_alt = {k: v.replace('-', '_', 1) if '-' in v else v for k, v in expected.items()}
    return {
        'project': project,
        'celery_app': celery_app,
        'gunicorn_module': guni_mod,
        'image': image,
        'image_nginx': image_nginx,
        'app_port': app_port,
        'https_port': https_port,
        'expected_containers': expected,
        'expected_containers_alt': expected_alt,
        'supervisor_celery': _csv_setting(
            'SERVICE_MONITOR_SUPERVISOR_CELERY', 'celery_worker,celery_beat'
        ),
        'supervisor_gunicorn': _csv_setting(
            'SERVICE_MONITOR_SUPERVISOR_GUNICORN', 'gunicorn,gunicorn_topteen,topteens_gunicorn'
        ),
    }


def _port_is_listening(port):
    """True if something is listening on TCP port (host)."""
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False
    ok, out, _ = _run_command(['ss', '-ltn'], timeout=2)
    if ok and out:
        needle = f':{port} '
        # ss shows *:8005 or 0.0.0.0:8005 or [::]:8005
        for line in out.splitlines():
            if f':{port}' in line and 'LISTEN' in line.upper():
                return True
            if needle in line or line.rstrip().endswith(f':{port}'):
                return True
    ok2, out2, _ = _run_command(['netstat', '-ltn'], timeout=2)
    if ok2 and out2:
        for line in out2.splitlines():
            if f':{port}' in line and 'LISTEN' in line.upper():
                return True
    return False


def _supervisor_programs_running(program_names):
    """Return list of program names reported RUNNING by supervisorctl."""
    if not program_names:
        return []
    ok, out, _ = _run_command(['supervisorctl', 'status'], timeout=3)
    if not ok or not out:
        # try sudo-less failure; don't require sudo in web process
        return []
    running = []
    wanted = {n.lower() for n in program_names}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, state = parts[0], parts[1]
        if name.lower() in wanted and state.upper() == 'RUNNING':
            running.append(name)
    return running


def _docker_ps_rows():
    """
    List running containers: name, image, ports, command, compose project, compose service.
    """
    fmt = (
        '{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Command}}\t'
        '{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}'
    )
    ok, out, _ = _run_command(['docker', 'ps', '--format', fmt], timeout=3)
    if not ok or not out:
        return []
    rows = []
    for line in out.splitlines():
        parts = (line or '').split('\t')
        while len(parts) < 6:
            parts.append('')
        rows.append(
            {
                'name': parts[0].strip(),
                'image': parts[1].strip(),
                'ports': parts[2].strip(),
                'command': parts[3].strip(),
                'compose_project': parts[4].strip(),
                'compose_service': parts[5].strip(),
            }
        )
    return rows


def _container_matches_project(row, ident):
    """True if this container belongs to THIS TopTeen compose stack."""
    name = (row.get('name') or '').lower()
    image = (row.get('image') or '').lower()
    project = (ident['project'] or '').lower()
    compose_project = (row.get('compose_project') or '').lower()
    img_base = (ident['image'] or '').lower().split(':')[0]
    img_nginx = (ident['image_nginx'] or '').lower().split(':')[0]

    if compose_project and compose_project == project:
        return True
    if name.startswith(f'{project}-') or name.startswith(f'{project}_'):
        return True
    if img_base and img_base in image:
        return True
    if img_nginx and img_nginx in image:
        return True
    return False


def _is_topteen_celery_cmdline(text, celery_app=None):
    t = (text or '').lower()
    app = (celery_app or _project_identity()['celery_app']).lower()
    if 'celery' not in t:
        return False
    if 'app.tasks.celery_app' in t:
        return False
    return (
        f'-a {app}' in t
        or f'--app={app}' in t
        or f'--app {app}' in t
    )


def _is_topteen_gunicorn_cmdline(text, guni_mod=None):
    t = (text or '').lower()
    mod = (guni_mod or _project_identity()['gunicorn_module']).lower()
    if 'gunicorn' not in t:
        return False
    return mod in t or mod.split('.')[0] in t


def _topteen_celery_on_host():
    ident = _project_identity()
    app = ident['celery_app']
    if _is_process_running(rf'celery +(-A|--app[= ]) *{re.escape(app)}'):
        return True
    # Supervisor programs for this project
    if _supervisor_programs_running(ident['supervisor_celery']):
        return True
    ok, out, _ = _run_command(['pgrep', '-af', 'celery'], timeout=2)
    if not ok or not out:
        return False
    for line in out.splitlines():
        if _is_topteen_celery_cmdline(line, app):
            return True
    return False


def _topteen_gunicorn_on_host():
    ident = _project_identity()
    mod = ident['gunicorn_module']
    if _is_process_running(rf'gunicorn.*{re.escape(mod)}'):
        return True
    if _supervisor_programs_running(ident['supervisor_gunicorn']):
        return True
    ok, out, _ = _run_command(['pgrep', '-af', 'gunicorn'], timeout=2)
    if not ok or not out:
        return False
    for line in out.splitlines():
        if _is_topteen_gunicorn_cmdline(line, mod):
            return True
    return False


def _find_project_docker_services():
    """
    Map compose service -> container name for THIS project only.
    Keys: web, nginx, celery, celery_beat, redis (and unknowns by service label).
    """
    ident = _project_identity()
    found = {}
    for row in _docker_ps_rows():
        if not _container_matches_project(row, ident):
            continue
        svc = (row.get('compose_service') or '').strip().lower().replace('-', '_')
        name = row['name']
        cmd = row.get('command') or ''
        name_l = name.lower()

        if not svc:
            if 'celery_beat' in name_l or 'celery-beat' in name_l or 'beat' in name_l and 'celery' in name_l:
                svc = 'celery_beat'
            elif 'celery' in name_l:
                svc = 'celery'
            elif 'nginx' in name_l:
                svc = 'nginx'
            elif 'redis' in name_l:
                svc = 'redis'
            elif 'web' in name_l or 'django' in name_l or 'gunicorn' in (cmd or '').lower():
                svc = 'web'

        # Celery must be topteens app if we can read the command
        if svc in ('celery', 'celery_beat') and cmd and not _is_topteen_celery_cmdline(cmd, ident['celery_app']):
            # Name/project matched but foreign celery cmdline — skip
            if 'app.tasks' in cmd.lower():
                continue

        if svc and svc not in found:
            found[svc] = {
                'name': name,
                'image': row.get('image') or '',
                'ports': row.get('ports') or '',
                'command': cmd,
                'compose_project': row.get('compose_project') or '',
                'compose_service': row.get('compose_service') or svc,
            }
    return found


def _docker_container_for_topteen_service(service_key):
    """Return running container name for a TopTeen service key (celery, web/gunicorn, redis, nginx)."""
    found = _find_project_docker_services()
    key = service_key
    if key == 'gunicorn':
        key = 'web'
    if key == 'celery':
        # Prefer worker over beat for "celery" label
        if 'celery' in found:
            return found['celery']['name']
        if 'celery_beat' in found:
            return found['celery_beat']['name']
        return ''
    return (found.get(key) or {}).get('name') or ''


def _docker_container_for_pattern(pattern):
    """Legacy name-substring match (prefer _docker_container_for_topteen_service)."""
    ok, out, _ = _run_command(['docker', 'ps', '--format', '{{.Names}}'], timeout=2)
    if not ok or not out:
        return ''
    names = [n.strip() for n in out.splitlines() if n.strip()]
    lowered = pattern.lower()
    for name in names:
        if lowered in name.lower():
            return name
    return ''


def _runtime_identity_payload(service_key):
    """Extra fields for service monitor UI: expected names, ports, matched containers."""
    ident = _project_identity()
    found = _find_project_docker_services()
    app_port = ident['app_port']
    https_port = ident['https_port']
    port_http_ok = _port_is_listening(app_port)
    port_https_ok = _port_is_listening(https_port) if https_port and https_port != '0' else False

    expected_for_key = []
    if service_key == 'celery':
        expected_for_key = [
            ident['expected_containers']['celery'],
            ident['expected_containers']['celery_beat'],
        ]
        matched = [found[k]['name'] for k in ('celery', 'celery_beat') if k in found]
        host_ok = _topteen_celery_on_host()
        supervisor = _supervisor_programs_running(ident['supervisor_celery'])
    elif service_key == 'gunicorn':
        expected_for_key = [ident['expected_containers']['web'], ident['expected_containers']['nginx']]
        matched = [found[k]['name'] for k in ('web', 'nginx') if k in found]
        host_ok = _topteen_gunicorn_on_host()
        supervisor = _supervisor_programs_running(ident['supervisor_gunicorn'])
    elif service_key == 'redis':
        expected_for_key = [ident['expected_containers']['redis']]
        matched = [found['redis']['name']] if 'redis' in found else []
        host_ok = _is_process_running('redis-server')
        supervisor = []
    else:
        expected_for_key = list(ident['expected_containers'].values())
        matched = [v['name'] for v in found.values()]
        host_ok = False
        supervisor = []

    return {
        'compose_project': ident['project'],
        'docker_image': ident['image'],
        'expected_containers': expected_for_key,
        'matched_containers': matched,
        'app_port': app_port,
        'https_port': https_port,
        'app_port_listening': port_http_ok,
        'https_port_listening': port_https_ok,
        'host_process_ok': host_ok,
        'supervisor_running': supervisor,
        'celery_app': ident['celery_app'],
        'all_project_containers': {k: v['name'] for k, v in found.items()},
    }


def _resolve_runtime_source(service_key):
    ident = _project_identity()
    payload = _runtime_identity_payload(service_key)

    # Prefer explicit config endpoints when available.
    if service_key == 'redis':
        redis_url = (getattr(settings, 'CELERY_BROKER_URL', '') or getattr(settings, 'REDIS_URL', '') or '').strip()
        src, label = _source_from_url(redis_url)
        docker_redis = _docker_container_for_topteen_service('redis')
        if docker_redis:
            return {
                'type': 'docker',
                'label': f'Docker ({docker_redis})',
                'via': redis_url or docker_redis,
                **{k: payload[k] for k in payload},
            }
        if src != 'unknown':
            return {'type': src, 'label': label, 'via': redis_url, **payload}
        return {'type': 'local', 'label': 'Local host', 'via': redis_url, **payload}

    if service_key == 'email':
        email_host = (getattr(settings, 'EMAIL_HOST', '') or '').strip()
        src, label = _source_from_host(email_host)
        if src != 'unknown':
            return {'type': src, 'label': label, 'via': email_host}
        return {'type': 'unknown', 'label': 'Unknown', 'via': email_host}

    if service_key == 'db':
        db_host = (settings.DATABASES.get('default', {}).get('HOST', '') or '').strip() if hasattr(settings, 'DATABASES') else ''
        src, label = _source_from_host(db_host)
        return {'type': src, 'label': label, 'via': db_host}

    # Celery: host env/supervisor first, else this project's Docker celery
    if service_key == 'celery':
        if _topteen_celery_on_host():
            via = 'celery -A %s' % ident['celery_app']
            if payload['supervisor_running']:
                via = 'supervisor: ' + ', '.join(payload['supervisor_running'])
            return {
                'type': 'local',
                'label': 'Local host (env / supervisor)',
                'via': via,
                **payload,
            }
        docker_name = _docker_container_for_topteen_service('celery')
        if docker_name:
            return {
                'type': 'docker',
                'label': f'Docker ({docker_name})',
                'via': docker_name,
                **payload,
            }
        if _running_inside_docker():
            return {'type': 'docker', 'label': 'Docker container', 'via': '', **payload}
        return {
            'type': 'local',
            'label': 'Local host (not detected)',
            'via': f"expected {', '.join(payload['expected_containers'])}",
            **payload,
        }

    if service_key == 'gunicorn':
        if _topteen_gunicorn_on_host():
            via = 'gunicorn %s' % ident['gunicorn_module']
            if payload['supervisor_running']:
                via = 'supervisor: ' + ', '.join(payload['supervisor_running'])
            elif payload['app_port_listening']:
                via = f"{via}; APP_PORT={payload['app_port']} listening"
            return {
                'type': 'local',
                'label': 'Local host (env / supervisor)',
                'via': via,
                **payload,
            }
        docker_name = _docker_container_for_topteen_service('gunicorn')
        if docker_name:
            port_note = ''
            if payload['app_port_listening']:
                port_note = f" APP_PORT={payload['app_port']} OK"
            return {
                'type': 'docker',
                'label': f'Docker ({docker_name})',
                'via': f'{docker_name}{port_note}',
                **payload,
            }
        if _running_inside_docker():
            return {'type': 'docker', 'label': 'Docker container', 'via': '', **payload}
        return {
            'type': 'local',
            'label': 'Local host (not detected)',
            'via': f"expected {', '.join(payload['expected_containers'])}; APP_PORT={payload['app_port']}",
            **payload,
        }

    if _running_inside_docker():
        return {'type': 'docker', 'label': 'Docker container', 'via': ''}
    return {'type': 'local', 'label': 'Local host', 'via': ''}


def _get_process_details(pattern, limit=4, cmdline_filter=None):
    """
    List matching processes. Optional cmdline_filter(str)->bool keeps only this app's rows.
    """
    ok, out, _err = _run_command(['pgrep', '-f', pattern], timeout=1)
    if not ok or not out:
        return []
    pids = [pid.strip() for pid in out.splitlines() if pid.strip()]
    details = []
    for pid in pids:
        if len(details) >= limit:
            break
        ps_ok, ps_out, _ = _run_command(
            ['ps', '-p', pid, '-o', 'pid,ppid,%cpu,%mem,rss,etime,comm,args'],
            timeout=1,
        )
        if not ps_ok or not ps_out:
            continue
        lines = [line for line in ps_out.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        row = lines[-1].strip()
        if cmdline_filter and not cmdline_filter(row):
            continue
        details.append(row)
    return details


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


def _extract_error_highlights(log_text, max_items=8):
    if not log_text:
        return []
    pattern = re.compile(r'(error|exception|traceback|critical|fatal|oom|out of memory|killed)', re.IGNORECASE)
    items = []
    for line in reversed(log_text.splitlines()):
        if pattern.search(line):
            cleaned = line.strip()
            if cleaned:
                items.append(cleaned[:400])
            if len(items) >= max_items:
                break
    return list(reversed(items))


def _detect_failure_hints(log_text):
    text = (log_text or '').lower()
    hints = []
    if 'out of memory' in text or 'oom' in text or 'killed process' in text:
        hints.append('Possible memory pressure / OOM kill detected in logs.')
    if 'connection refused' in text or 'temporarily unavailable' in text:
        hints.append('Dependency connection issue detected (service may be down or blocked).')
    if 'traceback' in text:
        hints.append('Python traceback found; inspect the stack trace in log tail.')
    if 'worker lost' in text or 'worker exited' in text:
        hints.append('Worker instability detected (unexpected worker exits).')
    return hints


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


def _celery_truncate(value, max_len=120):
    text = repr(value) if not isinstance(value, str) else value
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + '…'


def _celery_format_started(time_start):
    """Celery time_start is epoch seconds (float); return short local display or ''."""
    if time_start is None:
        return ''
    try:
        from datetime import datetime

        from django.utils import timezone as dj_tz

        ts = float(time_start)
        dt = datetime.fromtimestamp(ts)
        if getattr(settings, 'USE_TZ', False):
            dt = dj_tz.make_aware(dt, dj_tz.get_current_timezone())
            return dj_tz.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError, OSError):
        return str(time_start)


def _normalize_celery_task_rows(bucket, state):
    """Flatten inspect active/reserved/scheduled maps into display rows."""
    rows = []
    if not bucket:
        return rows
    for worker, tasks in bucket.items():
        for item in tasks or []:
            req = item.get('request') if isinstance(item, dict) and state == 'scheduled' else item
            if not isinstance(req, dict):
                continue
            args = req.get('args', ())
            kwargs = req.get('kwargs', {})
            rows.append(
                {
                    'state': state,
                    'worker': worker or req.get('hostname') or '—',
                    'id': req.get('id') or '',
                    'name': req.get('name') or req.get('type') or '—',
                    'args': _celery_truncate(args),
                    'kwargs': _celery_truncate(kwargs),
                    'started': _celery_format_started(req.get('time_start')),
                    'eta': (item.get('eta') if state == 'scheduled' else '') or '',
                }
            )
    return rows


def _get_celery_runtime_diagnostics():
    diag = {
        'workers_up': 0,
        'open_tasks': 0,
        'active_tasks': 0,
        'reserved_tasks': 0,
        'scheduled_tasks': 0,
        'task_rows': [],
        'inspect_ok': False,
        'inspect_error': '',
    }
    if not getattr(settings, 'ENABLE_CELERY', False):
        return diag
    try:
        from topteens.celery import app as celery_app

        insp = celery_app.control.inspect(timeout=1.5)
        ping = insp.ping() or {}
        active = insp.active() or {}
        reserved = insp.reserved() or {}
        scheduled = insp.scheduled() or {}
        diag['workers_up'] = len(ping)
        diag['active_tasks'] = sum(len(v or []) for v in active.values())
        diag['reserved_tasks'] = sum(len(v or []) for v in reserved.values())
        diag['scheduled_tasks'] = sum(len(v or []) for v in scheduled.values())
        diag['open_tasks'] = diag['active_tasks'] + diag['reserved_tasks'] + diag['scheduled_tasks']
        diag['task_rows'] = (
            _normalize_celery_task_rows(active, 'active')
            + _normalize_celery_task_rows(reserved, 'reserved')
            + _normalize_celery_task_rows(scheduled, 'scheduled')
        )
        diag['inspect_ok'] = True
    except Exception as exc:
        diag['inspect_error'] = str(exc)
    return diag


_CELERY_TASK_ID_RE = re.compile(r'^[a-zA-Z0-9_.:-]{8,255}$')


def get_celery_open_tasks():
    """
    Public helper: return Celery inspect snapshot for UI (service monitor, demo admin).
    Keys: workers_up, open_tasks, active_tasks, reserved_tasks, scheduled_tasks,
    task_rows, inspect_ok, inspect_error.
    """
    return _get_celery_runtime_diagnostics()


def revoke_celery_task(task_id, terminate=True, signal='SIGTERM'):
    """
    Revoke a Celery task by id.

    terminate=True sends signal to the worker child for active tasks.
    Returns a dict: ok, message, task_id.
    """
    task_id = (task_id or '').strip()
    if not task_id or not _CELERY_TASK_ID_RE.match(task_id):
        return {'ok': False, 'message': 'Invalid Celery task id.', 'task_id': task_id}
    if not getattr(settings, 'ENABLE_CELERY', False):
        return {'ok': False, 'message': 'Celery is disabled (ENABLE_CELERY=False).', 'task_id': task_id}
    try:
        from topteens.celery import app as celery_app

        celery_app.control.revoke(task_id, terminate=bool(terminate), signal=signal)
        action = 'terminated' if terminate else 'revoked'
        return {
            'ok': True,
            'message': f'Task {task_id} {action}. Refresh to confirm it left the list.',
            'task_id': task_id,
        }
    except Exception as exc:
        return {'ok': False, 'message': f'Could not revoke task: {exc}', 'task_id': task_id}


def revoke_celery_tasks(task_ids, terminate=True, signal='SIGTERM'):
    """Revoke multiple Celery task ids. Returns summary dict with results list."""
    results = []
    for tid in task_ids or []:
        results.append(revoke_celery_task(tid, terminate=terminate, signal=signal))
    ok_count = sum(1 for r in results if r.get('ok'))
    fail_count = len(results) - ok_count
    return {
        'ok': fail_count == 0 and ok_count > 0,
        'ok_count': ok_count,
        'fail_count': fail_count,
        'results': results,
    }


def get_runtime_service_status():
    celery_ok = _check_celery_ok()
    redis_ok = _check_redis_ok()
    email_ok = _check_email_ok()
    gunicorn_ok = _topteen_gunicorn_on_host() or _is_process_running('gunicorn')
    celery_proc_ok = _topteen_celery_on_host()
    celery_diag = _get_celery_runtime_diagnostics()

    service_rows = [
        {'key': 'db', 'label': 'Database', 'ok': True, 'detail': 'Django DB is reachable through request flow.', 'required': True, 'enabled': True},
        {'key': 'redis', 'label': 'Redis', 'ok': redis_ok, 'detail': 'Used by Celery broker/cache when enabled.', 'required': bool(getattr(settings, 'ENABLE_REDIS', False)), 'enabled': bool(getattr(settings, 'ENABLE_REDIS', False))},
        {'key': 'celery', 'label': 'Celery Worker', 'ok': celery_ok and (celery_proc_ok or bool(celery_diag.get('workers_up'))), 'detail': 'Worker heartbeat and process check (celery -A topteens).', 'required': bool(getattr(settings, 'ENABLE_CELERY', False)), 'enabled': bool(getattr(settings, 'ENABLE_CELERY', False))},
        {'key': 'gunicorn', 'label': 'Gunicorn', 'ok': gunicorn_ok, 'detail': 'OS process availability check.', 'required': True, 'enabled': True},
        {'key': 'email', 'label': 'Email config', 'ok': email_ok, 'detail': 'SMTP host/from-email present.', 'required': True, 'enabled': True},
    ]

    logs = {}
    for service_name, paths in _service_log_candidates().items():
        existing = _existing_paths_with_glob(paths)
        selected = existing[0] if existing else ''
        tail_text = _tail_file(selected)
        logs[service_name] = {
            'path': selected,
            'tail': tail_text,
            'error_highlights': _extract_error_highlights(tail_text),
            'failure_hints': _detect_failure_hints(tail_text),
        }

    service_map = {row['key']: row for row in service_rows}
    service_map['redis']['anchor'] = 'service-redis'
    service_map['redis']['process_details'] = _get_process_details('redis-server')
    service_map['redis']['clickable'] = True
    service_map['redis']['log_key'] = 'django'
    service_map['redis']['runtime_source'] = _resolve_runtime_source('redis')

    service_map['celery']['anchor'] = 'service-celery'
    service_map['celery']['process_details'] = _get_process_details(
        'celery',
        limit=8,
        cmdline_filter=lambda row: _is_topteen_celery_cmdline(row),
    )
    service_map['celery']['clickable'] = True
    service_map['celery']['log_key'] = 'celery'
    service_map['celery']['runtime_source'] = _resolve_runtime_source('celery')
    service_map['celery']['open_tasks'] = celery_diag['open_tasks']
    service_map['celery']['workers_up'] = celery_diag['workers_up']
    service_map['celery']['active_tasks'] = celery_diag['active_tasks']
    service_map['celery']['reserved_tasks'] = celery_diag['reserved_tasks']
    service_map['celery']['scheduled_tasks'] = celery_diag['scheduled_tasks']
    service_map['celery']['task_rows'] = celery_diag.get('task_rows') or []
    service_map['celery']['inspect_ok'] = celery_diag['inspect_ok']
    service_map['celery']['inspect_error'] = celery_diag['inspect_error']

    service_map['gunicorn']['anchor'] = 'service-gunicorn'
    guni_details = _get_process_details(
        'gunicorn',
        limit=6,
        cmdline_filter=lambda row: _is_topteen_gunicorn_cmdline(row),
    )
    if not guni_details:
        guni_details = _get_process_details('gunicorn', limit=4)
    service_map['gunicorn']['process_details'] = guni_details
    service_map['gunicorn']['clickable'] = True
    service_map['gunicorn']['log_key'] = 'gunicorn'
    service_map['gunicorn']['runtime_source'] = _resolve_runtime_source('gunicorn')

    service_map['email']['anchor'] = 'service-email'
    service_map['email']['process_details'] = []
    service_map['email']['clickable'] = True
    service_map['email']['log_key'] = 'django'
    service_map['email']['runtime_source'] = _resolve_runtime_source('email')

    service_map['db']['anchor'] = 'service-db'
    service_map['db']['process_details'] = []
    service_map['db']['clickable'] = False
    service_map['db']['log_key'] = 'django'
    service_map['db']['runtime_source'] = _resolve_runtime_source('db')

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


def _realpath_safe_prefix(path):
    try:
        return os.path.realpath(path)
    except Exception:
        return ''


def clear_service_monitor_tail_logs():
    """
    Truncate log files used for Service monitor tails (django / celery / gunicorn candidates).
    Only files under LOG_DIR or under BASE_DIR/logs are cleared (never /var/log/...).
    Returns {'cleared': [paths], 'errors': [str], 'skipped': [str]}.
    """
    cleared = []
    errors = []
    skipped = []
    log_dir = getattr(settings, 'LOG_DIR', '') or ''
    base_dir = getattr(settings, 'BASE_DIR', '') or ''
    allowed_roots = []
    for root in (log_dir, os.path.join(base_dir, 'logs') if base_dir else ''):
        root = (root or '').strip()
        if not root:
            continue
        try:
            if os.path.isdir(root):
                allowed_roots.append(_realpath_safe_prefix(root))
        except Exception:
            pass
    if not allowed_roots:
        skipped.append('No LOG_DIR or BASE_DIR/logs directory')
        return {'cleared': cleared, 'errors': errors, 'skipped': skipped}

    to_clear = set()
    for _service_name, paths in _service_log_candidates().items():
        existing = _existing_paths_with_glob(paths)
        if not existing:
            continue
        path = existing[0]
        try:
            rp = _realpath_safe_prefix(path)
        except Exception:
            skipped.append(path)
            continue
        if not os.path.isfile(path):
            continue
        allowed = any(
            rp == root or rp.startswith(root + os.sep)
            for root in allowed_roots
        )
        if not allowed:
            skipped.append(path)
            continue
        to_clear.add(path)

    for path in sorted(to_clear):
        try:
            with open(path, 'w', encoding='utf-8'):
                pass
            cleared.append(path)
        except Exception as exc:
            errors.append(f'{path}: {exc}')
    return {'cleared': cleared, 'errors': errors, 'skipped': skipped}


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


def get_business_dashboard_notification_recipients():
    """
    Users who should see business payment / ops alerts and bell summary counts:
    superuser, Accounts (staff) group, and marketing dashboard admins.
    """
    return list(
        User.objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(is_staff=True, groups__name__in=['Accounts', 'Accounts staff'])
            | Q(user_type=choices.UserType.MARKETINGGROUPADMIN)
        )
        .distinct()
    )


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
    environment='',
):
    enabled, _cfg = _event_enabled(event_type)
    if not enabled:
        return []
    # Dependency gating: only enforce runtime health for services the event actually requires.
    # Many in-app notifications should work even when celery/redis/gunicorn/email monitors are "unhealthy"
    # in development environments.
    try:
        requires_celery = bool(getattr(_cfg, 'requires_celery', False))
        requires_email = bool(getattr(_cfg, 'requires_email', False))
        requires_redis = bool(getattr(_cfg, 'requires_redis', False))
    except Exception:
        requires_celery = requires_email = requires_redis = False

    if requires_celery or requires_email or requires_redis:
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
        row_environment = environment or detect_notification_environment()
        recipient_ids = []
        for user in recipients:
            row = Notification(
                recipient=user,
                role_hint=notification_role_hint_for_user(user),
                category=category,
                environment=row_environment,
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
                recipient_ids.append(user.id)
            except Exception:
                # Unique dedupe collision is expected for retries.
                continue
        if recipient_ids:
            try:
                from django.core.cache import cache

                for uid in recipient_ids:
                    cache.delete(f'notif_latest:{uid}')
            except Exception:
                pass

    transaction.on_commit(_create)
    return created_rows

