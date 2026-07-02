from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core import choices

from .models import Notification, NotificationTypeConfig
from .services import (
    check_notification_dependencies,
    detect_notification_environment,
    ensure_default_notification_message_templates,
    ensure_default_notification_types,
)


def _is_staff_or_superuser(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


_INSTITUTE_PORTAL_USER_TYPES = (
    choices.UserType.INSTITUTE,
    choices.UserType.INSTITUTEGROUPADMIN,
    choices.UserType.COUNSELOR,
)

INSTITUTE_BELL_EVENT_TYPES = (
    ('institute.student_registered', 'New student registered'),
    ('institute.student_assigned', 'New student assigned'),
)

OPS_NOTIFICATION_BUCKET_KEYS = frozenset(
    ('lead', 'registration', 'payment_done', 'payment_failed')
)

OPS_BUCKET_LABELS = {
    'lead': 'New lead capture',
    'registration': 'New registration',
    'payment_done': 'New payment done',
    'payment_failed': 'Payment failed',
}

_OPS_BUCKET_ANALYTICS_ROUTES = {
    'lead': 'user_analytics:prospects_detail',
    'registration': 'user_analytics:registrations_detail',
    'payment_done': 'user_analytics:successful_payments_detail',
    'payment_failed': 'user_analytics:failed_payments_detail',
}

FAMILY_STUDENT_BUCKET_KEYS = frozenset(('careers', 'blogs', 'videos', 'colleges'))
FAMILY_PARENT_BUCKET_KEYS = frozenset(('student_liked', 'student_disliked'))

FAMILY_STUDENT_BUCKET_LABELS = {
    'careers': 'Career suggestions',
    'blogs': 'Blog suggestions',
    'videos': 'Video suggestions',
    'colleges': 'College suggestions',
}

FAMILY_PARENT_BUCKET_LABELS = {
    'student_liked': 'Student liked',
    'student_disliked': 'Student disliked',
}

FAMILY_BUCKET_KEYS = FAMILY_STUDENT_BUCKET_KEYS | FAMILY_PARENT_BUCKET_KEYS


def _notification_summary_profile(user):
    """
    ``institute`` — institute / group institute / counselor bell (grouped by event, link to notifications page).
    ``ops`` — marketing / staff analytics bell (grouped buckets, dismiss on navigate).
    ``family_student`` / ``family_parent`` — student/parent scrapbook suggestion & reaction groups.
    """
    if not user.is_authenticated:
        return None
    ut = getattr(user, 'user_type', None)
    if ut in _INSTITUTE_PORTAL_USER_TYPES:
        return 'institute'
    if user.is_staff or user.is_superuser or ut == choices.UserType.MARKETINGGROUPADMIN:
        return 'ops'
    if ut == choices.UserType.STUDENT:
        return 'family_student'
    if ut == choices.UserType.PARENT:
        return 'family_parent'
    return None


def _notification_summary_eligible(user):
    return _notification_summary_profile(user) is not None


def _institute_event_type_count(user, event_type):
    """Row count for bell badge; ``institute.student_assigned`` dedupes per student."""
    qs = Notification.objects.filter(recipient=user, event_type=event_type)
    if event_type != 'institute.student_assigned':
        return qs.count()
    seen = set()
    n = 0
    for row in qs.order_by('-created')[:2000]:
        dk = _student_assignment_dedupe_key(row.payload)
        if dk is not None:
            if dk in seen:
                continue
            seen.add(dk)
        n += 1
    return n


def _institute_notification_summary_buckets(request):
    """One bell row per institute event type (count); opens notifications page filtered by ``type``."""
    user = request.user
    page_base = reverse('notifications:page')
    buckets = []
    for event_type, label in INSTITUTE_BELL_EVENT_TYPES:
        count = _institute_event_type_count(user, event_type)
        if count < 1:
            continue
        buckets.append(
            {
                'key': event_type,
                'label': label,
                'count': count,
                'url': '{}?type={}'.format(page_base, quote(event_type, safe='')),
                'clear_on_click': False,
            }
        )
    return buckets


def _notification_bucket_queryset(user, bucket_key):
    """
    Notifications grouped for the bell summary and for mark-bucket-dismiss.
    ``payment_done`` includes payer-facing success events plus staff ops ``payment.status_updated`` (success).
    """
    qs = Notification.objects.filter(recipient=user)
    if bucket_key == 'lead':
        return qs.filter(event_type='marketing.new_lead')
    if bucket_key == 'registration':
        return qs.filter(event_type='accounts.new_registration')
    if bucket_key == 'payment_done':
        return qs.filter(
            Q(event_type__in=('payment.success', 'payment.resolved'))
            | Q(event_type='payment.status_updated', payload__status='success')
        )
    if bucket_key == 'payment_failed':
        return qs.filter(event_type='payment.failed')
    return qs.none()


def _ops_user_has_analytics_access(user):
    """Staff/superuser may open user-analytics detail pages from the bell."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _ops_bucket_destination_url(request, bucket_key):
    """
    Marketing group admins use the in-app notifications list (no user-analytics ACL).
    Staff keep deep links into user-analytics business reports.
    """
    if _ops_user_has_analytics_access(request.user):
        route = _OPS_BUCKET_ANALYTICS_ROUTES.get(bucket_key)
        if route:
            try:
                return reverse(route)
            except Exception:
                pass
    page_base = reverse('notifications:page')
    return '{}?bucket={}'.format(page_base, quote(bucket_key, safe=''))


def _notification_summary_buckets(request):
    """``key``, ``label``, ``count``, ``url`` for each summary row."""
    user = request.user
    buckets = []
    for key in ('lead', 'registration', 'payment_done', 'payment_failed'):
        count = _notification_bucket_queryset(user, key).count()
        buckets.append(
            {
                'key': key,
                'label': OPS_BUCKET_LABELS.get(key, key),
                'count': count,
                'url': _ops_bucket_destination_url(request, key),
                'clear_on_click': True,
            }
        )
    return buckets


def _family_student_bucket_queryset(user, bucket_key):
    return Notification.objects.filter(
        recipient=user,
        is_read=False,
        event_type='parent.suggestion_added',
        payload__kind=bucket_key,
    )


def _family_parent_bucket_queryset(user, bucket_key):
    if bucket_key == 'student_liked':
        return Notification.objects.filter(
            recipient=user,
            is_read=False,
            event_type='parent.suggestion_liked',
        )
    if bucket_key == 'student_disliked':
        return Notification.objects.filter(
            recipient=user,
            is_read=False,
            event_type='parent.suggestion_disliked',
        )
    return Notification.objects.none()


def _family_student_notification_summary_buckets(request):
    user = request.user
    page_base = reverse('notifications:page')
    buckets = []
    for key, label in FAMILY_STUDENT_BUCKET_LABELS.items():
        count = _family_student_bucket_queryset(user, key).count()
        if count < 1:
            continue
        buckets.append(
            {
                'key': key,
                'label': label,
                'count': count,
                'url': '{}?bucket={}'.format(page_base, quote(key, safe='')),
                'clear_on_click': False,
            }
        )
    return buckets


def _family_parent_notification_summary_buckets(request):
    user = request.user
    page_base = reverse('notifications:page')
    buckets = []
    for key, label in FAMILY_PARENT_BUCKET_LABELS.items():
        count = _family_parent_bucket_queryset(user, key).count()
        if count < 1:
            continue
        buckets.append(
            {
                'key': key,
                'label': label,
                'count': count,
                'url': '{}?bucket={}'.format(page_base, quote(key, safe='')),
                'clear_on_click': False,
            }
        )
    return buckets


def _notification_summary_buckets_for_request(request):
    profile = _notification_summary_profile(request.user)
    if profile == 'institute':
        return _institute_notification_summary_buckets(request)
    if profile == 'ops':
        return _notification_summary_buckets(request)
    if profile == 'family_student':
        return _family_student_notification_summary_buckets(request)
    if profile == 'family_parent':
        return _family_parent_notification_summary_buckets(request)
    return []


def _request_notification_environment(request):
    host = ''
    try:
        host = request.get_host()
    except Exception:
        host = ''
    return detect_notification_environment(host)


def _api_payload_for_notification(row):
    """Expose safe JSON for the bell / list UI (retry link, amount summary, navigation)."""
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
    item_url = (p.get('item_url') or '').strip()
    if item_url and item_url != '#':
        out['item_url'] = item_url
    return out


def _parent_suggestion_destination_url(row, payload):
    """Resolve detail page for parent shortlist notifications."""
    item_url = (payload.get('item_url') or '').strip()
    if item_url and item_url != '#':
        return item_url
    kind = (payload.get('kind') or '').lower()
    try:
        bookmark = row.content_object
        if bookmark is not None and hasattr(bookmark, 'object_id'):
            from users.parent_suggestions import (
                _bookmark_object,
                _item_payload,
                _kind_for_content_type_id,
            )

            if not kind and getattr(bookmark, 'content_type_id', None):
                kind = _kind_for_content_type_id(bookmark.content_type_id)
            target = _bookmark_object(bookmark, kind)
            if target:
                return (_item_payload(kind, target).get('url') or '').strip()
    except Exception:
        pass
    return ''


def _parent_reaction_destination_url(payload):
    """Parent-facing like/dislike alerts open the career or student suggestions list."""
    career_id = payload.get('career_id')
    if career_id:
        try:
            from careers.models import Career

            career = Career.objects.filter(id=career_id).only('id', 'slug').first()
            if career:
                return career.url()
        except Exception:
            pass
    student_id = payload.get('student_id')
    if student_id:
        try:
            return reverse('parents_student_suggestions', args=[int(student_id), 'careers'])
        except Exception:
            pass
    return ''


def _notification_destination_url(row):
    """Best-effort link when the user opens a notification row."""
    p = row.payload or {}
    if not isinstance(p, dict):
        p = {}

    item_url = (p.get('item_url') or '').strip()
    if item_url and item_url != '#':
        return item_url

    if p.get('retry_payment_path') and p.get('show_retry_payment'):
        return (p.get('retry_payment_path') or '').strip()

    event_type = (row.event_type or '').strip()
    if event_type == 'parent.suggestion_added':
        return _parent_suggestion_destination_url(row, p)
    if event_type in ('parent.suggestion_liked', 'parent.suggestion_disliked'):
        return _parent_reaction_destination_url(p)

    return ''


def _student_assignment_dedupe_key(payload):
    """Collapse duplicate institute.student_assigned alerts for the same student."""
    if not isinstance(payload, dict):
        return None
    smid = payload.get('student_management_id')
    if smid is not None:
        try:
            return ('sm', int(smid))
        except Exception:
            return None
    sid = payload.get('student_id')
    if sid is not None:
        try:
            return ('stu', int(sid))
        except Exception:
            return None
    return None


def _dedupe_assignment_notifications(rows):
    """Keep the newest row per student for institute.student_assigned (ordered newest first)."""
    seen = set()
    out = []
    for r in rows:
        if r.event_type == 'institute.student_assigned':
            dk = _student_assignment_dedupe_key(r.payload)
            if dk is not None:
                if dk in seen:
                    continue
                seen.add(dk)
        out.append(r)
    return out


def _invalidate_user_notification_cache(user):
    if not user or not getattr(user, 'id', None):
        return
    try:
        cache.delete(f'notif_latest:{user.id}')
    except Exception:
        pass


def _unread_count_for_user(user):
    """
    Unread total; institute.student_assigned counts once per student (payload), not per duplicate row.
    Student/parent bells use grouped bucket totals so the badge matches the dropdown.
    """
    profile = _notification_summary_profile(user)
    if profile == 'family_student':
        return sum(
            _family_student_bucket_queryset(user, key).count()
            for key in FAMILY_STUDENT_BUCKET_LABELS
        )
    if profile == 'family_parent':
        return sum(
            _family_parent_bucket_queryset(user, key).count()
            for key in FAMILY_PARENT_BUCKET_LABELS
        )
    other = Notification.objects.filter(recipient=user, is_read=False).exclude(
        event_type='institute.student_assigned'
    ).count()
    assign_qs = (
        Notification.objects.filter(
            recipient=user, is_read=False, event_type='institute.student_assigned'
        )
        .order_by('-created')[:2000]
    )
    seen = set()
    n_assign = 0
    for r in assign_qs:
        dk = _student_assignment_dedupe_key(r.payload)
        if dk is not None:
            if dk in seen:
                continue
            seen.add(dk)
        n_assign += 1
    return int(other) + int(n_assign)


_PORTAL_NOTIFICATION_PAGE_USER_TYPES = _INSTITUTE_PORTAL_USER_TYPES + (
    choices.UserType.MARKETINGGROUPADMIN,
)


def _notifications_page_template(user):
    """
    Role-appropriate shell: portal v2 (institute / group / counselor / marketing),
    student/parent user dashboard, or staff analytics admin page.
    """
    ut = getattr(user, 'user_type', None)
    if ut in _PORTAL_NOTIFICATION_PAGE_USER_TYPES:
        return 'notifications/notifications_portal.html'
    if ut in (choices.UserType.STUDENT, choices.UserType.PARENT):
        return 'notifications/notifications_user.html'
    if user.is_staff or user.is_superuser:
        return 'notifications/notifications_admin.html'
    return 'notifications/notifications_user.html'


@login_required
def notifications_page(request):
    ensure_default_notification_types()
    ensure_default_notification_message_templates()
    template_name = _notifications_page_template(request.user)
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
            'is_parent_view': getattr(request.user, 'user_type', None) == choices.UserType.PARENT,
            'type_configs': NotificationTypeConfig.objects.all(),
            'current_environment': current_environment,
            'environments': environments_for_filter,
            'list_environment_default': list_environment_default,
            'initial_notification_type': (request.GET.get('type') or '').strip(),
            'initial_notification_bucket': (request.GET.get('bucket') or '').strip(),
        },
    )


@login_required
@require_GET
def notifications_latest_api(request):
    cache_key = f'notif_latest:{request.user.id}'
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    unread_count = _unread_count_for_user(request.user)
    summary_profile = _notification_summary_profile(request.user)
    if summary_profile:
        payload = {
            'success': True,
            'summary_mode': True,
            'summary_profile': summary_profile,
            'unread_count': unread_count,
            'notifications': [],
            'buckets': _notification_summary_buckets_for_request(request),
        }
        cache.set(cache_key, payload, 5)
        return JsonResponse(payload)
    # Show all notifications regardless of stored environment (dev / production / etc.).
    raw = list(
        Notification.objects.filter(recipient=request.user).order_by('-created')[:80]
    )
    rows = _dedupe_assignment_notifications(raw)[:10]
    payload = {
        'success': True,
        'summary_mode': False,
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
                'destination_url': _notification_destination_url(r),
            }
            for r in rows
        ],
    }
    cache.set(cache_key, payload, 5)
    return JsonResponse(payload)


@login_required
@require_GET
def notifications_list_api(request):
    q = (request.GET.get('q') or '').strip()
    event_type = (request.GET.get('type') or '').strip()
    bucket_key = (request.GET.get('bucket') or '').strip()
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
    if bucket_key in OPS_NOTIFICATION_BUCKET_KEYS:
        qs = _notification_bucket_queryset(request.user, bucket_key).order_by('-created')
    elif bucket_key in FAMILY_STUDENT_BUCKET_KEYS and _notification_summary_profile(request.user) == 'family_student':
        qs = _family_student_bucket_queryset(request.user, bucket_key).order_by('-created')
    elif bucket_key in FAMILY_PARENT_BUCKET_KEYS and _notification_summary_profile(request.user) == 'family_parent':
        qs = _family_parent_bucket_queryset(request.user, bucket_key).order_by('-created')
    elif event_type:
        qs = qs.filter(event_type=event_type)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    if event_type == 'institute.student_assigned':
        rows = _dedupe_assignment_notifications(list(qs.order_by('-created')[:2000]))
        pager = Paginator(rows, 20)
    else:
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
                    'destination_url': _notification_destination_url(r),
                }
                for r in pg.object_list
            ],
            'environment': requested_environment,
            'filtered_type': event_type or None,
            'filtered_bucket': bucket_key if bucket_key in (OPS_NOTIFICATION_BUCKET_KEYS | FAMILY_BUCKET_KEYS) else None,
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
    _invalidate_user_notification_cache(request.user)
    unread_count = _unread_count_for_user(request.user)
    return JsonResponse(
        {
            'success': True,
            'unread_count': unread_count,
            'buckets': _notification_summary_buckets_for_request(request),
        }
    )


@csrf_exempt
@login_required
@require_POST
def notification_mark_bucket_read_api(request):
    """
    Dismiss notifications in a summary bucket, then the client navigates to the filtered list.
    Ops, student, and parent family buckets clear on click; institute buckets do not.
    """
    profile = _notification_summary_profile(request.user)
    bucket_key = (request.POST.get('bucket') or '').strip()
    if profile == 'ops':
        if bucket_key not in OPS_NOTIFICATION_BUCKET_KEYS:
            return JsonResponse({'success': False, 'error': 'invalid_bucket'}, status=400)
        deleted, _ = _notification_bucket_queryset(request.user, bucket_key).delete()
    elif profile == 'family_student':
        if bucket_key not in FAMILY_STUDENT_BUCKET_KEYS:
            return JsonResponse({'success': False, 'error': 'invalid_bucket'}, status=400)
        deleted, _ = _family_student_bucket_queryset(request.user, bucket_key).delete()
    elif profile == 'family_parent':
        if bucket_key not in FAMILY_PARENT_BUCKET_KEYS:
            return JsonResponse({'success': False, 'error': 'invalid_bucket'}, status=400)
        deleted, _ = _family_parent_bucket_queryset(request.user, bucket_key).delete()
    else:
        return JsonResponse({'success': False, 'error': 'not_allowed'}, status=403)
    _invalidate_user_notification_cache(request.user)
    unread_count = _unread_count_for_user(request.user)
    return JsonResponse(
        {
            'success': True,
            'deleted': int(deleted),
            'unread_count': unread_count,
            'buckets': _notification_summary_buckets_for_request(request),
        }
    )


@csrf_exempt
@login_required
@require_POST
def notification_mark_all_read_api(request):
    Notification.objects.filter(recipient=request.user).delete()
    _invalidate_user_notification_cache(request.user)
    unread_count = _unread_count_for_user(request.user)
    return JsonResponse(
        {
            'success': True,
            'unread_count': unread_count,
            'buckets': _notification_summary_buckets_for_request(request),
        }
    )


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
    _invalidate_user_notification_cache(request.user)
    return JsonResponse(
        {
            'success': True,
            'deleted': int(deleted),
            'unread_count': _unread_count_for_user(request.user),
            'buckets': _notification_summary_buckets_for_request(request),
        }
    )


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

