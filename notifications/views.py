from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Notification, NotificationTypeConfig
from .services import check_notification_dependencies, ensure_default_notification_types


def _is_staff_or_superuser(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
def notifications_page(request):
    ensure_default_notification_types()
    template_name = 'notifications/notifications_admin.html' if request.user.is_staff else 'notifications/notifications_user.html'
    return render(
        request,
        template_name,
        {
            'page_title': 'Notifications',
            'type_configs': NotificationTypeConfig.objects.all(),
        },
    )


@login_required
@require_GET
def notifications_latest_api(request):
    rows = Notification.objects.filter(recipient=request.user).order_by('-created')[:10]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
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
                    'is_read': r.is_read,
                    'created': r.created.strftime('%Y-%m-%d %H:%M:%S'),
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
                    'is_read': r.is_read,
                    'created': r.created.strftime('%Y-%m-%d %H:%M:%S'),
                }
                for r in pg.object_list
            ],
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
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
@user_passes_test(_is_staff_or_superuser)
def notification_admin_settings(request):
    ensure_default_notification_types()
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

