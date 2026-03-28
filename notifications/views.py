from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Notification, NotificationTypeConfig
from .services import (
    check_notification_dependencies,
    detect_notification_environment,
    ensure_default_notification_message_templates,
    ensure_default_notification_types,
)


def _is_staff_or_superuser(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _request_notification_environment(request):
    host = ''
    try:
        host = request.get_host()
    except Exception:
        host = ''
    return detect_notification_environment(host)


def _api_payload_for_notification(row):
    """Expose safe JSON for the bell / list UI (retry link, amount summary)."""
    p = row.payload or {}
    if not isinstance(p, dict):
        return {}
    out = {}
    if p.get('retry_payment_path'):
        out['retry_payment_path'] = p['retry_payment_path']
    if p.get('retry_payment_label'):
        out['retry_payment_label'] = p['retry_payment_label']
    if p.get('show_retry_payment'):
        out['show_retry_payment'] = True
    if p.get('amount_display'):
        out['amount_display'] = p['amount_display']
    if p.get('currency_code'):
        out['currency_code'] = p['currency_code']
    return out


@login_required
def notifications_page(request):
    ensure_default_notification_types()
    ensure_default_notification_message_templates()
    template_name = 'notifications/notifications_admin.html' if request.user.is_staff else 'notifications/notifications_user.html'
    current_environment = _request_notification_environment(request)
    env_choices = list(Notification.Environment.CHOICES)
    environments_for_filter = (
        [('all', 'All environments')] + env_choices if request.user.is_staff else env_choices
    )
    list_environment_default = 'all' if request.user.is_staff else current_environment
    return render(
        request,
        template_name,
        {
            'page_title': 'Notifications',
            'type_configs': NotificationTypeConfig.objects.all(),
            'current_environment': current_environment,
            'environments': environments_for_filter,
            'list_environment_default': list_environment_default,
        },
    )


@login_required
@require_GET
def notifications_latest_api(request):
    # Show all notifications regardless of stored environment (dev / production / etc.).
    rows = Notification.objects.filter(recipient=request.user).order_by('-created')[:10]
    unread_count = Notification.objects.filter(recipient=request.user).count()
    return JsonResponse(
        {
            'success': True,
            'unread_count': unread_count,
            'notifications': [
                {
                    'id': r.id,
                    'title': r.title,
                    'body': (r.body or '')[:180],
                    'event_type': r.event_type,
                    'category': r.category,
                    'environment': r.environment,
                    'is_read': r.is_read,
                    'created': r.created.strftime('%Y-%m-%d %H:%M:%S'),
                    'payload': _api_payload_for_notification(r),
                }
                for r in rows
            ],
        }
    )


@login_required
@require_GET
def notifications_list_api(request):
    q = (request.GET.get('q') or '').strip()
    event_type = (request.GET.get('type') or '').strip()
    page = int(request.GET.get('page') or 1)
    current_environment = _request_notification_environment(request)
    if _is_staff_or_superuser(request.user):
        requested_environment = (request.GET.get('environment') or 'all').strip().lower()
        if requested_environment == 'all':
            qs = Notification.objects.filter(recipient=request.user).order_by('-created')
        elif requested_environment in dict(Notification.Environment.CHOICES):
            qs = Notification.objects.filter(recipient=request.user, environment=requested_environment).order_by('-created')
        else:
            requested_environment = 'all'
            qs = Notification.objects.filter(recipient=request.user).order_by('-created')
    else:
        requested_environment = 'all'
        qs = Notification.objects.filter(recipient=request.user).order_by('-created')
    if event_type:
        qs = qs.filter(event_type=event_type)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    pager = Paginator(qs, 20)
    pg = pager.get_page(page)
    return JsonResponse(
        {
            'success': True,
            'pagination': {
                'current_page': pg.number,
                'total_pages': pager.num_pages,
                'has_next': pg.has_next(),
                'has_previous': pg.has_previous(),
                'next_page': pg.next_page_number() if pg.has_next() else None,
                'previous_page': pg.previous_page_number() if pg.has_previous() else None,
            },
            'notifications': [
                {
                    'id': r.id,
                    'title': r.title,
                    'body': r.body,
                    'event_type': r.event_type,
                    'category': r.category,
                    'environment': r.environment,
                    'is_read': r.is_read,
                    'created': r.created.strftime('%Y-%m-%d %H:%M:%S'),
                    'payload': _api_payload_for_notification(r),
                }
                for r in pg.object_list
            ],
            'environment': requested_environment,
        }
    )


@csrf_exempt
@login_required
@require_POST
def notification_mark_read_api(request):
    nid = request.POST.get('id')
    if nid:
        row = Notification.objects.filter(id=nid, recipient=request.user).first()
        if row:
            row.mark_read()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
@require_POST
def notification_mark_all_read_api(request):
    Notification.objects.filter(recipient=request.user).delete()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
@require_POST
def notification_delete_api(request):
    """Hard-delete one notification row for the current user (SQL DELETE)."""
    nid = (request.POST.get('id') or '').strip()
    if not nid:
        return JsonResponse({'success': False, 'error': 'missing_id'}, status=400)
    deleted, _ = Notification.objects.filter(
        id=nid,
        recipient=request.user,
    ).delete()
    if not deleted:
        return JsonResponse({'success': False, 'error': 'not_found'}, status=404)
    return JsonResponse({'success': True, 'deleted': int(deleted)})


@login_required
@user_passes_test(_is_staff_or_superuser)
def notification_admin_settings(request):
    ensure_default_notification_types()
    ensure_default_notification_message_templates()
    health = check_notification_dependencies()
    configs = NotificationTypeConfig.objects.all().order_by('event_type')
    return render(
        request,
        'notifications/admin_settings.html',
        {
            'page_title': 'Notification settings',
            'configs': configs,
            'services': health,
            'services_ok': health.get('all_required_ok', False),
        },
    )


@csrf_exempt
@login_required
@user_passes_test(_is_staff_or_superuser)
@require_POST
def notification_toggle_type_api(request):
    health = check_notification_dependencies()
    if not health.get('all_required_ok', False):
        return JsonResponse({'success': False, 'error': 'services_unhealthy'}, status=409)
    event_type = (request.POST.get('event_type') or '').strip()
    enabled = (request.POST.get('enabled') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    cfg = NotificationTypeConfig.objects.filter(event_type=event_type).first()
    if not cfg:
        return JsonResponse({'success': False, 'error': 'event_type_not_found'}, status=404)
    cfg.enabled = enabled
    cfg.save(update_fields=['enabled', 'modified'])
    return JsonResponse({'success': True, 'enabled': cfg.enabled})


@csrf_exempt
@login_required
@user_passes_test(_is_staff_or_superuser)
@require_POST
def notification_admin_delete_all_api(request):
    """Delete all notifications in one environment, or every row if environment=all (staff)."""
    requested_environment = (request.POST.get('environment') or '').strip().lower()
    if requested_environment == 'all':
        deleted_count, _ = Notification.objects.all().delete()
        return JsonResponse({'success': True, 'deleted': deleted_count, 'environment': 'all'})
    if requested_environment not in dict(Notification.Environment.CHOICES):
        return JsonResponse({'success': False, 'error': 'invalid_environment'}, status=400)
    deleted_count, _ = Notification.objects.filter(environment=requested_environment).delete()
    return JsonResponse({'success': True, 'deleted': deleted_count, 'environment': requested_environment})


@csrf_exempt
@login_required
@user_passes_test(_is_staff_or_superuser)
@require_POST
def notification_admin_delete_for_user_api(request):
    """Hard-delete notifications for a single user (optional environment filter)."""
    from django.contrib.auth import get_user_model

    uid = (request.POST.get('user_id') or '').strip()
    if not uid:
        return JsonResponse({'success': False, 'error': 'missing_user_id'}, status=400)
    if not get_user_model().objects.filter(pk=uid).exists():
        return JsonResponse({'success': False, 'error': 'user_not_found'}, status=404)
    env = (request.POST.get('environment') or '').strip().lower()
    qs = Notification.objects.filter(recipient_id=uid)
    if env and env != 'all' and env in dict(Notification.Environment.CHOICES):
        qs = qs.filter(environment=env)
    deleted_count, _ = qs.delete()
    return JsonResponse({'success': True, 'deleted': deleted_count, 'user_id': uid})


@csrf_exempt
@login_required
@user_passes_test(_is_staff_or_superuser)
@require_POST
def notification_admin_purge_old_api(request):
    """Delete notifications with created date older than ``days`` (optional ``user_id``)."""
    try:
        days = int((request.POST.get('days') or '90').strip())
    except ValueError:
        return JsonResponse({'success': False, 'error': 'invalid_days'}, status=400)
    if days < 1 or days > 3650:
        return JsonResponse({'success': False, 'error': 'invalid_days'}, status=400)
    cutoff = timezone.now() - timedelta(days=days)
    uid = (request.POST.get('user_id') or '').strip()
    qs = Notification.objects.filter(created__lt=cutoff)
    if uid:
        qs = qs.filter(recipient_id=uid)
    deleted_count, _ = qs.delete()
    return JsonResponse(
        {
            'success': True,
            'deleted': deleted_count,
            'older_than_days': days,
            'user_id': uid or None,
        }
    )

