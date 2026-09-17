from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import HttpResponseRedirect, JsonResponse
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
    email_is_placeholder,
    ensure_default_notification_message_templates,
    ensure_default_notification_types,
    lead_payload_is_followable,
    phone_is_followable,
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
    ('payment.failed', 'Payment failed'),
    ('payment.success', 'Payment received'),
)

DEMO_INSTITUTE_EVENT_TYPES = (
    'marketing.demo_institute_students_added',
    'marketing.demo_institute_test_result',
    'marketing.demo_institute_all_demos_completed',
    'marketing.demo_institute_report_viewed',
)

PINNED_NOTIFICATION_EVENT_TYPES = (
    'accounts.new_registration',
    'marketing.new_lead',
    'institute.student_registered',
    'institute.student_assigned',
    'payment.success',
    'payment.failed',
    'payment.resolved',
    'payment.status_updated',
) + DEMO_INSTITUTE_EVENT_TYPES

OPS_VISIBLE_EVENT_TYPES = (
    'marketing.new_lead',
    'accounts.new_registration',
    'institute.student_registered',
    'payment.success',
    'payment.failed',
    'payment.resolved',
    'payment.status_updated',
    'llm.recharge_reminder',
) + DEMO_INSTITUTE_EVENT_TYPES

INSTITUTE_PORTAL_VISIBLE_EVENT_TYPES = (
    'institute.student_registered',
    'institute.student_assigned',
    'payment.success',
    'payment.failed',
    'payment.resolved',
    'llm.recharge_reminder',
)

COUNSELOR_VISIBLE_EVENT_TYPES = (
    'institute.student_assigned',
    'payment.success',
    'payment.failed',
    'payment.resolved',
    'llm.recharge_reminder',
)

_PAYMENT_EVENT_TYPES = (
    'payment.success',
    'payment.failed',
    'payment.resolved',
    'payment.status_updated',
)

_STUDENT_SCOPE_EVENT_TYPES = (
    'institute.student_registered',
    'institute.student_assigned',
)

_MARKETING_REGISTRATION_USER_TYPES = (
    choices.UserType.INSTITUTE,
    choices.UserType.INSTITUTEGROUPADMIN,
    choices.UserType.COUNSELOR,
)


def _order_notifications_new_first(qs):
    """Unread first, then new registration / new activity, then newest created."""
    return qs.annotate(
        _pin_rank=Case(
            When(event_type__in=PINNED_NOTIFICATION_EVENT_TYPES, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by('is_read', '_pin_rank', '-created')

OPS_NOTIFICATION_BUCKET_KEYS = frozenset(
    ('lead', 'registration', 'payment_done', 'payment_failed', 'demo_institute')
)

OPS_BUCKET_LABELS = {
    'lead': 'New lead capture',
    'registration': 'New registration',
    'payment_done': 'New payment done',
    'payment_failed': 'Payment failed',
    'demo_institute': 'Demo institute activity',
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


def _is_ops_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return getattr(user, 'user_type', None) == choices.UserType.MARKETINGGROUPADMIN


def _is_marketing_user(user):
    return bool(user) and getattr(user, 'user_type', None) == choices.UserType.MARKETINGGROUPADMIN


def _is_platform_admin(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if _is_marketing_user(user):
        return False
    ut = getattr(user, 'user_type', None)
    if ut in (
        choices.UserType.INSTITUTE,
        choices.UserType.INSTITUTEGROUPADMIN,
        choices.UserType.COUNSELOR,
    ):
        return False
    return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))


def _visible_event_types_for_user(user):
    """Whitelist by role so leads/payments/student alerts stay on the right dashboards."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    ut = getattr(user, 'user_type', None)
    if ut == choices.UserType.COUNSELOR:
        return COUNSELOR_VISIBLE_EVENT_TYPES
    if ut in (choices.UserType.INSTITUTE, choices.UserType.INSTITUTEGROUPADMIN):
        return INSTITUTE_PORTAL_VISIBLE_EVENT_TYPES
    if ut == choices.UserType.MARKETINGGROUPADMIN or user.is_staff or user.is_superuser:
        return OPS_VISIBLE_EVENT_TYPES
    return None


def _scoped_notifications_qs(user, qs=None):
    if qs is None:
        qs = Notification.objects.filter(recipient=user)
    try:
        qs = qs.select_related('recipient')
    except Exception:
        pass
    types = _visible_event_types_for_user(user)
    if types is not None:
        qs = qs.filter(event_type__in=types)
    qs = _apply_role_payload_filters(user, qs)
    return _exclude_zero_amount_payment_notifications(
        _exclude_placeholder_lead_notifications(qs)
    )


def _apply_role_payload_filters(user, qs):
    """Keep marketing / admin / payer lists aligned with role-specific payment and registration rules."""
    if _is_marketing_user(user):
        qs = qs.exclude(
            Q(event_type='accounts.new_registration')
            & ~Q(payload__user_type__in=_MARKETING_REGISTRATION_USER_TYPES)
        )
        qs = qs.exclude(
            Q(event_type__in=_PAYMENT_EVENT_TYPES)
            & ~Q(payload__obj_type=choices.PaymentObjectType.INSTITUTE_TIEUP)
        )
        qs = qs.exclude(event_type='institute.student_registered')
        return qs
    if _is_platform_admin(user):
        qs = qs.exclude(
            Q(event_type='accounts.new_registration')
            & ~Q(payload__user_type=choices.UserType.STUDENT)
        )
        return qs
    ut = getattr(user, 'user_type', None)
    if ut in (
        choices.UserType.INSTITUTE,
        choices.UserType.INSTITUTEGROUPADMIN,
        choices.UserType.COUNSELOR,
    ):
        uid = getattr(user, 'id', None)
        if uid:
            qs = qs.exclude(
                Q(event_type__in=_PAYMENT_EVENT_TYPES)
                & ~Q(payload__payer_id=uid)
            )
        qs = _restrict_student_notifications_to_scope(user, qs)
    return qs


def _accessible_institute_ids(user):
    """Schools this institute / group / counselor login is allowed to see."""
    from institute.models import Institute

    ut = getattr(user, 'user_type', None)
    uid = getattr(user, 'id', None)
    if not uid:
        return set()
    if ut == choices.UserType.INSTITUTE:
        return set(Institute.objects.filter(created_by_id=uid).values_list('id', flat=True))
    if ut == choices.UserType.INSTITUTEGROUPADMIN:
        return set(
            Institute.objects.filter(
                institute_group__institute_group_admin_id=uid
            ).values_list('id', flat=True)
        )
    if ut == choices.UserType.COUNSELOR:
        from counselor.models import Counselor

        coun = Counselor.objects.filter(coun_user_id=uid).only('id', 'counselor_admin_id').first()
        if coun is None:
            return set()
        ids = set()
        if coun.counselor_admin_id:
            ids.add(coun.counselor_admin_id)
        ids.update(coun.institute_placements.values_list('id', flat=True))
        return ids
    return set()


def _payload_int_value(payload, key):
    if not isinstance(payload, dict):
        return None
    raw = payload.get(key)
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _restrict_student_notifications_to_scope(user, qs):
    """Hide student roster alerts that are not for this user's institute / group / counselor."""
    ut = getattr(user, 'user_type', None)
    if ut not in (
        choices.UserType.INSTITUTE,
        choices.UserType.INSTITUTEGROUPADMIN,
        choices.UserType.COUNSELOR,
    ):
        return qs
    from institute.models import Institute, StudentManagement
    from counselor.models import Counselor

    allowed_ids = _accessible_institute_ids(user)
    allowed_slugs = set()
    allowed_student_ids = set()
    if allowed_ids:
        allowed_slugs = set(
            Institute.objects.filter(id__in=allowed_ids)
            .exclude(slug='')
            .exclude(slug__isnull=True)
            .values_list('slug', flat=True)
        )
        allowed_student_ids = set(
            StudentManagement.objects.filter(institute_id__in=allowed_ids)
            .exclude(student_id__isnull=True)
            .values_list('student_id', flat=True)
        )
    counselor_id = None
    if ut == choices.UserType.COUNSELOR:
        counselor_id = (
            Counselor.objects.filter(coun_user_id=getattr(user, 'id', None))
            .values_list('id', flat=True)
            .first()
        )
    try:
        rows = list(qs.filter(event_type__in=_STUDENT_SCOPE_EVENT_TYPES)[:4000])
    except Exception:
        return qs.exclude(event_type__in=_STUDENT_SCOPE_EVENT_TYPES)
    keep = []
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        if ut == choices.UserType.COUNSELOR:
            cid = _payload_int_value(payload, 'counselor_id')
            if counselor_id and cid == counselor_id:
                keep.append(row.id)
            continue
        iid = _payload_int_value(payload, 'institute_id')
        slug = (payload.get('institute_slug') or '').strip()
        in_scope = (iid is not None and iid in allowed_ids) or (
            bool(slug) and slug in allowed_slugs
        )
        if not in_scope:
            continue
        sid = _payload_int_value(payload, 'student_id')
        if sid is not None and allowed_student_ids and sid not in allowed_student_ids:
            continue
        keep.append(row.id)
    drop_ids = [row.id for row in rows if row.id not in set(keep)]
    if not drop_ids:
        return qs
    return qs.exclude(id__in=drop_ids)


def _institute_event_type_count(user, event_type):
    """Row count for bell badge; ``institute.student_assigned`` dedupes per student."""
    qs = _scoped_notifications_qs(user).filter(event_type=event_type, is_read=False)
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


def _exclude_zero_amount_payment_notifications(qs):
    """Hide payment alerts when the order total is zero (demo credits, free packages)."""
    # Match zeros with .filter() first. .exclude() on JSON lookups treats NULL as
    # unknown and would hide legitimate ₹1.00 rows that omit payload.amount.
    try:
        zero_ids = qs.filter(event_type__in=_PAYMENT_EVENT_TYPES).filter(
            Q(payload__amount_display__istartswith='₹0.00')
            | Q(payload__amount_display__istartswith='$0.00')
            | Q(body__contains='₹0.00')
            | Q(body__contains='$0.00')
            | (
                Q(payload__has_key='amount')
                & Q(payload__amount__in=['0', '0.0', '0.00'])
            )
        ).values_list('id', flat=True)
        return qs.exclude(id__in=zero_ids)
    except Exception:
        return qs


def _exclude_placeholder_lead_notifications(qs):
    """Session/bot rows cannot be followed up. Keep only leads with a real phone."""
    junk = Q(event_type='marketing.new_lead') & (
        Q(payload__email__icontains='temp.topteen.in')
        | Q(title__icontains='temp.topteen.in')
        | Q(title__icontains='session_')
        | Q(body__icontains='temp.topteen.in')
        | Q(title='New lead captured')
        | ~Q(payload__phone__regex=r'[0-9]{8,}')
    )
    try:
        return qs.exclude(junk)
    except Exception:
        try:
            return qs.exclude(
                event_type='marketing.new_lead',
                payload__email__icontains='temp.topteen.in',
            )
        except Exception:
            return qs


_BELL_RESTORE_CACHE_KEY = 'notif_restore_unopened_v1:{0}'


def _skip_unopened_bell_restore(user):
    if not user or not getattr(user, 'id', None):
        return
    cache.set(_BELL_RESTORE_CACHE_KEY.format(user.id), 1, 60 * 60 * 24 * 45)


def _restore_unopened_bell_notifications(user):
    """
    The notifications page used to mark every visible row read on load, which
    emptied the bell while the list still showed items. Restore those until
    the user actually opens a destination or clicks Mark all read.
    """
    if not user or not getattr(user, 'id', None):
        return
    key = _BELL_RESTORE_CACHE_KEY.format(user.id)
    if cache.get(key):
        return
    cutoff = timezone.now() - timedelta(days=60)
    qs = _scoped_notifications_qs(user).filter(is_read=True, created__gte=cutoff)
    try:
        qs = qs.exclude(payload__opened=True)
    except Exception:
        pass
    qs.update(is_read=False, read_at=None)
    cache.set(key, 1, 60 * 60 * 24 * 45)


def _notification_bucket_queryset(user, bucket_key):
    """
    Notifications grouped for the bell summary and for mark-bucket-dismiss.
    ``payment_done`` includes payer-facing success events plus staff ops ``payment.status_updated`` (success).
    """
    qs = _scoped_notifications_qs(user).filter(is_read=False)
    if bucket_key == 'lead':
        return _exclude_placeholder_lead_notifications(qs.filter(event_type='marketing.new_lead'))
    if bucket_key == 'registration':
        if _is_platform_admin(user):
            return qs.filter(
                event_type__in=('accounts.new_registration', 'institute.student_registered')
            )
        return qs.filter(event_type='accounts.new_registration')
    if bucket_key == 'payment_done':
        return qs.filter(
            Q(event_type__in=('payment.success', 'payment.resolved'))
            | Q(event_type='payment.status_updated', payload__status='success')
        )
    if bucket_key == 'payment_failed':
        return qs.filter(event_type='payment.failed')
    if bucket_key == 'demo_institute':
        return qs.filter(event_type__in=DEMO_INSTITUTE_EVENT_TYPES)
    return qs.none()


def _ops_user_has_analytics_access(user):
    """Staff/superuser may open user-analytics detail pages from the bell."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _ops_bucket_destination_url(request, bucket_key):
    """
    Marketing group admins use the in-app notifications list (no user-analytics ACL).
    Staff keep deep links into user-analytics business reports except payments
    (payment rows open payment info, not retry).
    """
    if bucket_key == 'demo_institute':
        page_base = reverse('notifications:page')
        return '{}?bucket={}'.format(page_base, quote(bucket_key, safe=''))
    if _is_marketing_user(request.user) and bucket_key in ('payment_done', 'payment_failed'):
        extra = '?status=failed' if bucket_key == 'payment_failed' else '?status=received'
        dest = _safe_reverse('institute:marketinggroupdashboard_page', ['payments'], extra=extra)
        if dest:
            return dest
    if bucket_key in ('payment_done', 'payment_failed', 'registration'):
        page_base = reverse('notifications:page')
        return '{}?bucket={}'.format(page_base, quote(bucket_key, safe=''))
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
    for key in ('lead', 'registration', 'payment_done', 'payment_failed', 'demo_institute'):
        count = _notification_bucket_queryset(user, key).count()
        buckets.append(
            {
                'key': key,
                'label': OPS_BUCKET_LABELS.get(key, key),
                'count': count,
                'url': _ops_bucket_destination_url(request, key),
                'clear_on_click': False,
            }
        )
    buckets.sort(key=lambda b: (0 if b['count'] else 1, 0 if b['key'] in ('registration', 'lead') else 1))
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


def _payload_amount_positive(payload):
    if not isinstance(payload, dict):
        return False
    raw = payload.get('amount')
    if raw in (None, ''):
        display = (payload.get('amount_display') or '').replace(',', '')
        for token in ('₹', '$', 'INR', 'USD', ' '):
            display = display.replace(token, '')
        raw = display.strip()
    try:
        return float(raw or 0) > 0
    except (TypeError, ValueError):
        return False


def _api_payload_for_notification(row):
    """Expose safe JSON for the bell / list UI (retry link, amount summary, navigation)."""
    p = row.payload or {}
    if not isinstance(p, dict):
        return {}
    out = {}
    ops = _is_ops_user(getattr(row, 'recipient', None))
    if p.get('retry_payment_path') and not ops and _payload_amount_positive(p):
        out['retry_payment_path'] = p['retry_payment_path']
    if p.get('retry_payment_label') and not ops and _payload_amount_positive(p):
        out['retry_payment_label'] = p['retry_payment_label']
    if p.get('show_retry_payment') and not ops and _payload_amount_positive(p):
        out['show_retry_payment'] = True
    if p.get('cancel_payment_path') and not ops:
        out['cancel_payment_path'] = p['cancel_payment_path']
    if p.get('amount_display'):
        out['amount_display'] = p['amount_display']
    if p.get('currency_code'):
        out['currency_code'] = p['currency_code']
    item_url = (p.get('item_url') or '').strip()
    if item_url and item_url != '#':
        out['item_url'] = item_url
    return out


def _notification_public_copy(row):
    """Prefer name/phone in the list; never surface session placeholder emails."""
    title = row.title or ''
    body = row.body or ''
    event_type = (row.event_type or '').strip()
    p = row.payload or {}
    if not isinstance(p, dict):
        p = {}
    if event_type == 'marketing.new_lead':
        name = (p.get('name') or '').strip()
        phone = (p.get('phone') or '').strip()
        email = (p.get('email') or '').strip()
        if _is_placeholder_email(email):
            email = ''
        if not phone_is_followable(phone):
            source = _source_display(p.get('source') or '')
            title = 'Waiting for a phone number'
            body = 'This visitor has not shared a number to call or WhatsApp yet.'
            if source:
                body = 'Visitor from {} has not shared a phone number yet.'.format(source)
            return title, body
        if name or phone or email:
            headline = name or phone or email
            title = 'New lead: {}'.format(headline)
            bits = [bit for bit in (phone, email) if bit and bit != headline]
            source = _source_display(p.get('source') or '')
            if source:
                bits.append(source)
            body = ' · '.join(bits) if bits else 'New enquiry'
            return title, body
        source = _source_display(p.get('source') or '')
        title = 'Waiting for name & phone'
        body = 'Visitor{} has not shared contact details yet.'.format(
            ' from {}'.format(source) if source else ''
        )
        return title, body
    if event_type == 'accounts.new_registration':
        name = (p.get('name') or '').strip()
        email = (p.get('email') or '').strip()
        who = name or email or 'A user'
        kind = (p.get('registration_kind') or '').strip()
        ut_raw = p.get('user_type')
        try:
            ut_val = int(ut_raw) if ut_raw not in (None, '') else None
        except (TypeError, ValueError):
            ut_val = None
        if kind == 'direct' or ut_val == choices.UserType.STUDENT:
            title = 'Direct student registration'
            body = '{0} registered directly.'.format(who)
            return title, body
        if ut_val == choices.UserType.COUNSELOR:
            title = 'New counselor registration'
        elif ut_val == choices.UserType.INSTITUTEGROUPADMIN:
            title = 'New institute group registration'
        elif ut_val == choices.UserType.INSTITUTE:
            title = 'New institute registration'
        else:
            title = 'New registration'
        if email and email != who:
            body = '{0} ({1}) registered.'.format(who, email)
        else:
            body = '{0} registered.'.format(who)
        return title, body
    if event_type in ('institute.student_registered', 'institute.student_assigned'):
        search = _student_search_term(p, row)
        inst = (p.get('institute_name') or '').strip()
        if not inst:
            institute = _institute_from_payload(p, row)
            inst = (getattr(institute, 'name', None) or '').strip()
        if event_type == 'institute.student_registered':
            if _is_platform_admin(getattr(row, 'recipient', None)) or (
                p.get('registration_kind') or ''
            ) == 'indirect':
                title = 'Indirect student registration'
            else:
                title = 'New student registered'
            if search and inst:
                body = '{0} registered via {1}.'.format(search, inst) if title.startswith('Indirect') else '{0} registered at {1}.'.format(search, inst)
            elif search:
                body = '{0} registered at your institute.'.format(search)
        else:
            title = 'New student assigned'
            counselor_name = (p.get('counselor_name') or '').strip()
            if search and counselor_name:
                body = '{0} was assigned to {1}.'.format(search, counselor_name)
            elif search:
                body = '{0} was assigned to a counselor.'.format(search)
        return title, body
    if event_type.startswith('payment.') and _is_ops_user(getattr(row, 'recipient', None)):
        name, email = _payer_contact_from_payload(p, row)
        item = (p.get('item') or '').strip()
        amt = (p.get('amount_display') or '').strip()
        who = name or email
        inst = (p.get('institute_name') or '').strip()
        bits = [bit for bit in (amt, item, inst, who) if bit]
        if event_type == 'payment.failed':
            title = 'Payment failed'
        elif event_type == 'payment.resolved':
            title = 'Payment issue resolved'
        else:
            title = 'Payment received'
        if bits:
            body = ' · '.join(bits)
        return title, body
    return title, body


def _notification_json(row, body_limit=None):
    title, body = _notification_public_copy(row)
    if body_limit is not None:
        body = (body or '')[:body_limit]
    try:
        destination_url = _notification_destination_url(row)
    except Exception:
        destination_url = ''
    try:
        payload = _api_payload_for_notification(row)
    except Exception:
        payload = {}
    created = ''
    try:
        created = row.created.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        created = ''
    return {
        'id': row.id,
        'title': title,
        'body': body,
        'event_type': row.event_type,
        'category': row.category,
        'environment': row.environment,
        'is_read': row.is_read,
        'created': created,
        'payload': payload,
        'destination_url': destination_url,
    }


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


def _registration_destination_url(row, payload):
    """Open the registered user/institute/counselor detail from a new-registration alert."""
    from counselor.models import Counselor
    from institute.models import Institute
    from users.models import User

    user = getattr(row, 'content_object', None)
    if not isinstance(user, User):
        user = None
    uid = payload.get('user_id') or getattr(row, 'object_id', None)
    email = (payload.get('email') or '').strip()
    if user is None and uid:
        try:
            user = User.objects.filter(id=int(uid)).first()
        except (TypeError, ValueError):
            user = None
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()

    if user is None:
        if _is_platform_admin(getattr(row, 'recipient', None)):
            return _safe_reverse('notifications:page', extra='?bucket=registration')
        return _safe_reverse('institute:marketinggroupdashboard_page', ['institutes'])

    ut = getattr(user, 'user_type', None)
    if ut in (choices.UserType.STUDENT, choices.UserType.PARENT):
        extra = ('?period=alltime&search=' + quote(user.email, safe='')) if user.email else ''
        if _is_platform_admin(getattr(row, 'recipient', None)):
            dest = _safe_reverse('user_analytics:registrations_detail', extra=extra)
            if dest:
                return dest
            return _safe_reverse(
                'notifications:page',
                extra='?bucket=registration'
                + ('&q=' + quote(user.email, safe='') if user.email else ''),
            )
        extra = ('?student_name=' + quote(user.email, safe='')) if user.email else ''
        return _safe_reverse('institute:marketinggroupdashboard_page', ['students'], extra=extra)
    if ut == choices.UserType.INSTITUTE:
        inst = (
            Institute.objects.filter(created_by_id=user.id)
            .order_by('-id')
            .only('slug')
            .first()
        )
        if inst and inst.slug:
            return _safe_reverse('institute:institute_masterdashboard', [inst.slug])
        return _safe_reverse(
            'institute:marketinggroupdashboard_page',
            ['institutes'],
            extra='?status=pending',
        )
    if ut == choices.UserType.COUNSELOR:
        coun = Counselor.objects.filter(coun_user_id=user.id).order_by('id').only('id').first()
        if coun:
            return _safe_reverse('counselor:CounselorDashboardView', [coun.id])
        return _safe_reverse('institute:marketinggroupdashboard_page', ['counselors'])
    if ut == choices.UserType.INSTITUTEGROUPADMIN:
        return _safe_reverse('institute:institutegroupdashboard')
    return _safe_reverse('institute:marketinggroupdashboard_page', ['institutes'])


def _safe_reverse(name, args=None, extra=''):
    try:
        url = reverse(name, args=args or [])
    except Exception:
        return ''
    return url + extra if extra else url


def _lead_destination_url(row, payload):
    """Open the captured lead detail from a new-lead alert."""
    from core.models import Lead as ContactLead
    from user_analytics.models import Lead as AnalyticsLead

    if not lead_payload_is_followable(payload) and not phone_is_followable(
        (payload or {}).get('phone') or (payload or {}).get('mobile')
    ):
        kind = (payload.get('lead_kind') or '').strip() if isinstance(payload, dict) else ''
        lid = (payload or {}).get('lead_id') if isinstance(payload, dict) else None
        obj = getattr(row, 'content_object', None)
        phone = ''
        if isinstance(obj, ContactLead):
            phone = getattr(obj, 'mobile', None) or ''
        elif isinstance(obj, AnalyticsLead):
            phone = getattr(obj, 'phone', None) or ''
        if not phone_is_followable(phone):
            return _safe_reverse('notifications:page', extra='?bucket=lead')

    kind = (payload.get('lead_kind') or '').strip()
    lid = payload.get('lead_id') or getattr(row, 'object_id', None)
    obj = getattr(row, 'content_object', None)

    if kind == 'contact' or isinstance(obj, ContactLead):
        cid = getattr(obj, 'id', None) if isinstance(obj, ContactLead) else lid
        phone = (payload.get('phone') or payload.get('mobile') or getattr(obj, 'mobile', None) or '')
        if not phone_is_followable(phone):
            return _safe_reverse('notifications:page', extra='?bucket=lead')
        try:
            dest = _safe_reverse('notifications:lead_capture_contact', [int(cid)])
        except (TypeError, ValueError):
            dest = ''
        if dest:
            return dest

    lead = obj if isinstance(obj, AnalyticsLead) else None
    email = (payload.get('email') or '').strip()
    if lead is None and lid:
        try:
            lead = AnalyticsLead.objects.filter(id=int(lid)).only('id', 'phone', 'email', 'name').first()
        except Exception:
            lead = None
    if lead is None and email and not email_is_placeholder(email):
        try:
            lead = AnalyticsLead.objects.filter(email__iexact=email).order_by('-id').only('id', 'phone', 'email', 'name').first()
        except Exception:
            lead = None

    if lead:
        phone = payload.get('phone') or getattr(lead, 'phone', None) or ''
        if not phone_is_followable(phone):
            return _safe_reverse('notifications:page', extra='?bucket=lead')
        dest = _safe_reverse('notifications:lead_capture', [lead.id])
        if dest:
            return dest

    if email and not email_is_placeholder(email) and phone_is_followable(payload.get('phone')):
        extra = '?period=alltime&search=' + quote(email, safe='')
        dest = _safe_reverse('user_analytics:prospects_detail', extra=extra)
        if dest:
            return dest
    return _safe_reverse('notifications:page', extra='?bucket=lead')


def _payload_int(payload, *keys):
    for key in keys:
        raw = payload.get(key)
        if raw in (None, ''):
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _institute_from_payload(payload, row=None):
    from institute.models import Institute, StudentManagement

    obj = getattr(row, 'content_object', None) if row is not None else None
    if isinstance(obj, Institute) and getattr(obj, 'slug', None):
        return obj
    if isinstance(obj, StudentManagement):
        inst = getattr(obj, 'institute', None)
        if inst is not None:
            return inst
    slug = (payload.get('institute_slug') or '').strip()
    iid = _payload_int(payload, 'institute_id')
    try:
        if slug:
            inst = Institute.objects.filter(slug=slug).only('id', 'slug', 'name').first()
            if inst:
                return inst
        if iid:
            inst = Institute.objects.filter(id=iid).only('id', 'slug', 'name').first()
            if inst:
                return inst
    except Exception:
        pass
    if slug:
        return type('InstituteStub', (), {'id': iid, 'slug': slug, 'name': (payload.get('institute_name') or '')})()
    return None


def _student_from_payload(payload, row=None):
    from institute.models import StudentManagement
    from users.models import User

    obj = getattr(row, 'content_object', None) if row is not None else None
    if isinstance(obj, StudentManagement):
        student = getattr(obj, 'student', None)
        if student is not None:
            return student
    if isinstance(obj, User) and getattr(obj, 'user_type', None) == choices.UserType.STUDENT:
        return obj
    sid = _payload_int(payload, 'student_id', 'payer_id', 'user_id')
    if sid:
        try:
            found = User.objects.filter(id=sid).only('id', 'name', 'email', 'mobile', 'user_type').first()
        except Exception:
            found = None
        if found:
            return found
    email = (payload.get('student_email') or payload.get('payer_email') or payload.get('email') or '').strip()
    if email and not _is_placeholder_email(email):
        try:
            return User.objects.filter(email__iexact=email).only('id', 'name', 'email', 'mobile', 'user_type').first()
        except Exception:
            return None
    return None


def _student_search_term(payload, row=None):
    name = (payload.get('student_name') or payload.get('payer_name') or payload.get('name') or '').strip()
    email = (payload.get('student_email') or payload.get('payer_email') or payload.get('email') or '').strip()
    if _is_placeholder_email(email):
        email = ''
    if name:
        return name
    if email:
        return email
    student = _student_from_payload(payload, row)
    if student is None:
        return ''
    return (student.name or student.email or '').strip()


def _students_page_url_for_recipient(recipient, institute=None, search=''):
    extra = ('?student_name=' + quote(search, safe='')) if search else ''
    ut = getattr(recipient, 'user_type', None)
    slug = getattr(institute, 'slug', None) or ''
    if ut == choices.UserType.INSTITUTEGROUPADMIN:
        if slug:
            extra += ('&' if extra else '?') + 'institute_slug=' + quote(slug, safe='')
        return _safe_reverse('institute:institutegroupdashboard_page', ['students'], extra=extra)
    if ut == choices.UserType.MARKETINGGROUPADMIN:
        if slug:
            extra += ('&' if extra else '?') + 'institute_slug=' + quote(slug, safe='')
        return _safe_reverse('institute:marketinggroupdashboard_page', ['students'], extra=extra)
    if ut == choices.UserType.INSTITUTE and slug:
        return _safe_reverse('institute:institutedashboard_page', [slug, 'students'], extra=extra)
    if ut == choices.UserType.COUNSELOR:
        from counselor.models import Counselor

        cid = None
        try:
            coun = Counselor.objects.filter(coun_user_id=getattr(recipient, 'id', None)).only('id').first()
            if coun:
                cid = coun.id
        except Exception:
            cid = None
        if cid:
            return _safe_reverse('counselor:CounselorDashboardSection', [cid, 'students'], extra=extra)
    if _is_platform_admin(recipient):
        extra_a = ('?period=alltime&search=' + quote(search, safe='')) if search else ''
        dest = _safe_reverse('user_analytics:registrations_detail', extra=extra_a)
        if dest:
            return dest
    if slug:
        return _safe_reverse('institute:institute_masterdashboard', [slug])
    return ''


def _student_roster_destination_url(row, payload):
    institute = _institute_from_payload(payload, row)
    search = _student_search_term(payload, row)
    dest = _students_page_url_for_recipient(row.recipient, institute, search)
    if dest:
        return dest
    return _safe_reverse('notifications:page')


def _student_assigned_destination_url(row, payload):
    recipient = row.recipient
    ut = getattr(recipient, 'user_type', None)
    search = _student_search_term(payload, row)
    extra = ('?student_name=' + quote(search, safe='')) if search else ''
    if ut == choices.UserType.COUNSELOR:
        from counselor.models import Counselor

        cid = _payload_int(payload, 'counselor_id')
        if not cid:
            try:
                coun = Counselor.objects.filter(coun_user_id=recipient.id).only('id').first()
                cid = getattr(coun, 'id', None)
            except Exception:
                cid = None
        if cid:
            dest = _safe_reverse('counselor:CounselorDashboardSection', [cid, 'students'], extra=extra)
            if dest:
                return dest
    return _student_roster_destination_url(row, payload)


def _demo_institute_destination_url(row, payload):
    institute = _institute_from_payload(payload, row)
    search = _student_search_term(payload, row)
    if payload.get('student_id') or search:
        dest = _students_page_url_for_recipient(row.recipient, institute, search)
        if dest:
            return dest
    slug = getattr(institute, 'slug', None) or ''
    if slug:
        dest = _safe_reverse('institute:institute_masterdashboard', [slug])
        if dest:
            return dest
    return _safe_reverse('institute:marketinggroupdashboard_page', ['institutes'])


def _payer_contact_from_payload(payload, row=None):
    email = (payload.get('payer_email') or payload.get('email') or '').strip()
    name = (payload.get('payer_name') or payload.get('name') or '').strip()
    if _is_placeholder_email(email):
        email = ''
    if email or name:
        return name, email
    student = _student_from_payload(payload, row)
    if student is not None:
        return (student.name or '').strip(), (student.email or '').strip()
    pid = _payload_int(payload, 'payment_id')
    if pid:
        try:
            from payments.models import Payment

            pay = Payment.objects.select_related('user').filter(id=pid).first()
        except Exception:
            pay = None
        user = getattr(pay, 'user', None) if pay is not None else None
        if user is not None:
            return (user.name or '').strip(), (user.email or '').strip()
    return name, email


def _payment_destination_url(row, payload):
    recipient = row.recipient
    event_type = (row.event_type or '').strip()
    pid = _payload_int(payload, 'payment_id')
    eid = _payload_int(payload, 'event_id')
    slug = (payload.get('institute_slug') or '').strip()
    extra_bits = []
    if pid:
        extra_bits.append('payment_id=' + str(pid))
    if eid:
        extra_bits.append('event_id=' + str(eid))
    capture_extra = ('?' + '&'.join(extra_bits)) if extra_bits else ''

    if _is_marketing_user(recipient):
        extra = []
        if slug:
            extra.append('institute=' + quote(slug, safe=''))
        if pid:
            extra.append('payment_id=' + str(pid))
        extra.append('status=failed' if event_type == 'payment.failed' else 'status=received')
        dest = _safe_reverse(
            'institute:marketinggroupdashboard_page',
            ['payments'],
            extra=('?' + '&'.join(extra)) if extra else '',
        )
        if dest:
            return dest
    dest = _safe_reverse('notifications:payment_capture', extra=capture_extra)
    if dest:
        return dest
    if _is_ops_user(recipient):
        return _safe_reverse(
            'notifications:page',
            extra='?bucket=payment_failed' if event_type == 'payment.failed' else '?bucket=payment_done',
        )
    return _safe_reverse('notifications:page')


def _notification_destination_url(row):
    """Best-effort link when the user opens a notification row."""
    p = row.payload or {}
    if not isinstance(p, dict):
        p = {}

    item_url = (p.get('item_url') or '').strip()
    if item_url and item_url != '#':
        return item_url

    event_type = (row.event_type or '').strip()

    if event_type == 'parent.suggestion_added':
        return _parent_suggestion_destination_url(row, p)
    if event_type in ('parent.suggestion_liked', 'parent.suggestion_disliked'):
        return _parent_reaction_destination_url(p)
    if event_type == 'accounts.new_registration':
        return _registration_destination_url(row, p)
    if event_type == 'marketing.new_lead':
        return _lead_destination_url(row, p)
    if event_type == 'institute.student_registered':
        return _student_roster_destination_url(row, p)
    if event_type == 'institute.student_assigned':
        return _student_assigned_destination_url(row, p)
    if event_type in DEMO_INSTITUTE_EVENT_TYPES:
        return _demo_institute_destination_url(row, p)
    if event_type.startswith('payment.'):
        return _payment_destination_url(row, p)

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
    _restore_unopened_bell_notifications(user)
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
    other = _scoped_notifications_qs(user).filter(is_read=False).exclude(
        event_type='institute.student_assigned'
    ).count()
    assign_qs = (
        _scoped_notifications_qs(user).filter(
            is_read=False, event_type='institute.student_assigned'
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


def _can_open_lead_capture(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return getattr(user, 'user_type', None) == choices.UserType.MARKETINGGROUPADMIN


def _user_is_parent_of(user, student_id):
    if not user or not student_id:
        return False
    try:
        from users.models import ParentStudentLink

        return ParentStudentLink.objects.filter(parent_id=user.id, student_id=student_id).exists()
    except Exception:
        return False


def _can_open_payment_capture(user, payment=None, event=None):
    if not user or not user.is_authenticated:
        return False
    if _can_open_lead_capture(user):
        return True
    payer_id = None
    if payment is not None:
        payer_id = getattr(payment, 'user_id', None)
    elif event is not None:
        payer_id = getattr(event, 'user_id', None)
    if payer_id and int(payer_id) == int(user.id):
        return True
    if payer_id and _user_is_parent_of(user, payer_id):
        return True
    return False


def _is_placeholder_email(email):
    return email_is_placeholder(email)


def _source_display(source, referrer=''):
    raw = (source or '').strip()
    key = raw.lower()
    mapping = {
        'google': 'Google',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'internal': 'TopTeen',
        'direct': 'Direct visit',
        'enquiry form': 'Enquiry form',
    }
    if key in mapping:
        return mapping[key]
    if raw:
        return raw
    ref = (referrer or '').lower()
    if 'google.' in ref:
        return 'Google'
    if 'facebook' in ref:
        return 'Facebook'
    if 'instagram' in ref:
        return 'Instagram'
    return ''


def _phone_digits(phone):
    return ''.join(ch for ch in (phone or '') if ch.isdigit())


def _phone_tel(phone):
    digits = _phone_digits(phone)
    if len(digits) == 10:
        return '+91' + digits
    if len(digits) == 11 and digits.startswith('0'):
        return '+91' + digits[1:]
    if len(digits) >= 12 and digits.startswith('91'):
        return '+' + digits
    if digits:
        return '+' + digits
    return ''


def _phone_whatsapp(phone):
    tel = _phone_tel(phone)
    return tel.replace('+', '') if tel else ''


def _lead_initials(name, phone=''):
    parts = [p for p in (name or '').split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        word = parts[0]
        return word[:2].upper() if len(word) >= 2 else (word[0] + 'L').upper()
    digits = _phone_digits(phone)
    if len(digits) >= 2:
        return digits[-2:]
    return '?'


def _fmt_when(dt):
    if not dt:
        return ''
    try:
        local = timezone.localtime(dt)
        return local.strftime('%b %d, %Y · %I:%M %p').replace(' 0', ' ')
    except Exception:
        return ''


def _build_lead_card(name='', email='', phone='', source='', referrer='', captured_at=None, is_converted=False):
    name = (name or '').strip()
    phone = (phone or '').strip()
    email = (email or '').strip()
    if name and _is_placeholder_email(name):
        name = ''
    if _is_placeholder_email(email):
        email = ''
    followable = phone_is_followable(phone)
    source_label = _source_display(source, referrer)
    display_name = name or (phone if followable else '') or 'No phone to follow up'
    return {
        'has_contact': followable,
        'display_name': display_name,
        'initials': _lead_initials(name, phone),
        'name': name,
        'phone': phone if followable else '',
        'phone_tel': _phone_tel(phone) if followable else '',
        'phone_whatsapp': _phone_whatsapp(phone) if followable else '',
        'email': email,
        'source_label': source_label,
        'captured_at': _fmt_when(captured_at),
        'status_label': 'Converted' if is_converted else 'Ready to call',
        'waiting_message': (
            'This visitor{} has not shared a phone number yet, so there is nothing to follow up.'
            .format(' from {}'.format(source_label) if source_label else '')
        ),
    }


def _render_lead_capture(request, card, account_url='', analytics_url=''):
    return render(
        request,
        'notifications/lead_capture_detail.html',
        {
            'page_title': card.get('display_name') or 'Lead capture',
            'card': card,
            'account_url': account_url,
            'analytics_url': analytics_url,
        },
    )


@login_required
def lead_capture_detail(request, lead_id):
    """Detail page for an analytics lead notification click."""
    from user_analytics.models import Lead
    from users.models import User

    if not _can_open_lead_capture(request.user):
        return HttpResponseRedirect(reverse('notifications:page'))

    lead = Lead.objects.filter(id=lead_id).first()
    if lead is None:
        return HttpResponseRedirect(reverse('notifications:page') + '?bucket=lead')

    linked_user = getattr(lead, 'user', None)
    if linked_user is None and lead.email and not _is_placeholder_email(lead.email):
        linked_user = User.objects.filter(email__iexact=lead.email).first()

    name = lead.name or ''
    phone = lead.phone or ''
    email = lead.email or ''
    if linked_user is not None:
        name = name or (linked_user.name or '')
        phone = phone or (linked_user.mobile or '')
        if linked_user.email and not _is_placeholder_email(linked_user.email):
            email = linked_user.email

    account_url = ''
    if linked_user is not None:
        fake_row = type('R', (), {'content_object': linked_user, 'object_id': linked_user.id})()
        account_url = _registration_destination_url(
            fake_row,
            {'user_id': linked_user.id, 'email': linked_user.email or email},
        )

    analytics_url = ''
    if _ops_user_has_analytics_access(request.user) and email and not _is_placeholder_email(email):
        extra = '?period=alltime&search=' + quote(email, safe='')
        analytics_url = _safe_reverse('user_analytics:prospects_detail', extra=extra)

    card = _build_lead_card(
        name=name,
        email=email,
        phone=phone,
        source=lead.source,
        referrer=lead.referrer,
        captured_at=lead.first_visit or lead.created,
        is_converted=bool(lead.is_converted),
    )
    if not card.get('has_contact'):
        return HttpResponseRedirect(reverse('notifications:page') + '?bucket=lead')
    return _render_lead_capture(request, card, account_url=account_url, analytics_url=analytics_url)


@login_required
def lead_capture_contact_detail(request, lead_id):
    """Detail page for an enquiry-form lead (name + phone)."""
    from core.models import Lead as ContactLead

    if not _can_open_lead_capture(request.user):
        return HttpResponseRedirect(reverse('notifications:page'))

    lead = ContactLead.objects.filter(id=lead_id).first()
    if lead is None:
        return HttpResponseRedirect(reverse('notifications:page') + '?bucket=lead')

    card = _build_lead_card(
        name=lead.name,
        email='',
        phone=lead.mobile,
        source='enquiry form',
        captured_at=getattr(lead, 'created', None),
        is_converted=False,
    )
    if not card.get('has_contact'):
        return HttpResponseRedirect(reverse('notifications:page') + '?bucket=lead')
    return _render_lead_capture(request, card)


@login_required
def payment_capture_detail(request):
    """Payment info for ops (view only) and the paying role (retry/cancel)."""
    from payments.models import Payment
    from user_analytics.models import UserEvent

    payment_id = request.GET.get('payment_id') or ''
    event_id = request.GET.get('event_id') or ''
    payment = None
    event = None
    try:
        if payment_id:
            payment = Payment.objects.select_related('user').filter(id=int(payment_id)).first()
    except (TypeError, ValueError):
        payment = None
    try:
        if event_id:
            event = UserEvent.objects.select_related('user').filter(id=int(event_id)).first()
    except (TypeError, ValueError):
        event = None

    if not _can_open_payment_capture(request.user, payment, event):
        return HttpResponseRedirect(reverse('notifications:page'))

    payer = None
    item = ''
    amount = ''
    status_label = 'Payment'
    gateway_order_id = ''
    captured_at = None
    institute_name = ''
    institute_slug = ''
    retry_url = ''
    cancel_url = reverse('notifications:page')
    amount_positive = False
    if payment is not None:
        payer = getattr(payment, 'user', None)
        try:
            from notifications.payment_notifications import (
                cancel_payment_path_for_user,
                institute_from_tieup_payment,
                payment_amount_display,
                payment_amount_is_positive,
                payment_purchase_label,
                retry_payment_path_for_payment,
            )

            item = payment_purchase_label(payment)
            amount = payment_amount_display(payment)
            amount_positive = payment_amount_is_positive(payment)
            inst = institute_from_tieup_payment(payment)
            if inst is not None:
                institute_name = (getattr(inst, 'name', None) or '').strip()
                institute_slug = (getattr(inst, 'slug', None) or '').strip()
            if getattr(payment, 'is_success', None) != choices.YesNoChoices.YES:
                retry_url = retry_payment_path_for_payment(payment) or ''
            cancel_url = cancel_payment_path_for_user(request.user, payment) or cancel_url
        except Exception:
            item = ''
            amount = str(getattr(payment, 'amount', '') or '')
        if getattr(payment, 'is_success', None) == choices.YesNoChoices.YES:
            status_label = 'Successful'
        else:
            status_label = 'Failed / pending'
        gateway_order_id = (getattr(payment, 'gateway_order_id', None) or '') or ''
        captured_at = getattr(payment, 'modified', None) or getattr(payment, 'created', None)
    elif event is not None:
        payer = getattr(event, 'user', None)
        meta = event.metadata or {}
        item = (meta.get('item') or event.event_name or '').strip()
        amount = str(meta.get('order_amount_rupees') or event.event_value or '')
        status_label = 'Failed' if event.event_type == 'payment_failed' else (event.event_type or 'Payment')
        gateway_order_id = (meta.get('gateway_order_id') or '') or ''
        captured_at = getattr(event, 'created', None)
        if payment is None:
            pid = meta.get('payment_id') or event.object_id
            if pid:
                payment = Payment.objects.select_related('user').filter(id=pid).first()
                if payment is not None and payer is None:
                    payer = getattr(payment, 'user', None)

    if payer is None and payment is None and event is None:
        return HttpResponseRedirect(reverse('notifications:page') + '?bucket=payment_failed')

    name = (getattr(payer, 'name', None) or '').strip()
    email = (getattr(payer, 'email', None) or '').strip()
    phone = (getattr(payer, 'mobile', None) or '').strip()
    if _is_placeholder_email(email):
        email = ''

    concerned_payer = bool(
        payer
        and (
            getattr(payer, 'id', None) == request.user.id
            or _user_is_parent_of(request.user, getattr(payer, 'id', None))
        )
    )
    if not amount_positive:
        amount_positive = _payload_amount_positive({'amount_display': amount})
    show_retry = bool(
        concerned_payer
        and retry_url
        and amount_positive
        and status_label != 'Successful'
        and not _is_ops_user(request.user)
    )
    show_cancel = bool(concerned_payer and not _is_ops_user(request.user) and status_label != 'Successful')

    card = _build_lead_card(
        name=name or institute_name or 'Payer',
        email=email,
        phone=phone,
        source=item or 'Payment',
        captured_at=captured_at,
        is_converted=status_label == 'Successful',
    )
    card['status_label'] = status_label
    card['amount_display'] = amount
    card['item'] = item
    card['gateway_order_id'] = gateway_order_id
    card['payment_id'] = getattr(payment, 'id', None) or payment_id
    card['institute_name'] = institute_name
    card['institute_slug'] = institute_slug
    return render(
        request,
        'notifications/payment_capture_detail.html',
        {
            'page_title': card.get('display_name') or 'Payment',
            'card': card,
            'account_url': '',
            'analytics_url': '',
            'retry_url': retry_url if show_retry else '',
            'cancel_url': cancel_url if show_cancel else '',
            'show_retry': show_retry,
            'show_cancel': show_cancel,
        },
    )


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
    unread_rows = _dedupe_assignment_notifications(
        list(
            _order_notifications_new_first(
                _scoped_notifications_qs(request.user).filter(is_read=False)
            )[:40]
        )
    )[:10]
    unread_json = [_notification_json(r, body_limit=180) for r in unread_rows]
    if summary_profile:
        payload = {
            'success': True,
            'summary_mode': True,
            'summary_profile': summary_profile,
            'unread_count': unread_count,
            'notifications': unread_json,
            'buckets': _notification_summary_buckets_for_request(request),
        }
        cache.set(cache_key, payload, 5)
        return JsonResponse(payload)
    # Show all notifications regardless of stored environment (dev / production / etc.).
    raw = list(
        _order_notifications_new_first(
            _scoped_notifications_qs(request.user)
        )[:80]
    )
    rows = _dedupe_assignment_notifications(raw)[:10]
    payload = {
        'success': True,
        'summary_mode': False,
        'unread_count': unread_count,
        'notifications': [_notification_json(r, body_limit=180) for r in rows],
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
            qs = Notification.objects.filter(recipient=request.user)
        elif requested_environment in dict(Notification.Environment.CHOICES):
            qs = Notification.objects.filter(recipient=request.user, environment=requested_environment)
        else:
            requested_environment = 'all'
            qs = Notification.objects.filter(recipient=request.user)
    else:
        requested_environment = 'all'
        qs = Notification.objects.filter(recipient=request.user)
    qs = _scoped_notifications_qs(request.user, qs)
    if bucket_key in OPS_NOTIFICATION_BUCKET_KEYS:
        qs = _notification_bucket_queryset(request.user, bucket_key)
    elif bucket_key in FAMILY_STUDENT_BUCKET_KEYS and _notification_summary_profile(request.user) == 'family_student':
        qs = _family_student_bucket_queryset(request.user, bucket_key)
    elif bucket_key in FAMILY_PARENT_BUCKET_KEYS and _notification_summary_profile(request.user) == 'family_parent':
        qs = _family_parent_bucket_queryset(request.user, bucket_key)
    elif event_type:
        qs = qs.filter(event_type=event_type)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    qs = _order_notifications_new_first(qs)
    if event_type == 'institute.student_assigned':
        rows = _dedupe_assignment_notifications(list(qs[:2000]))
        pager = Paginator(rows, 20)
    else:
        pager = Paginator(qs, 20)
    pg = pager.get_page(page)
    notifications = []
    for row in pg.object_list:
        try:
            notifications.append(_notification_json(row))
        except Exception:
            continue
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
            'notifications': notifications,
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
    opened = (request.POST.get('opened') or '').strip().lower() in ('1', 'true', 'yes')
    if nid:
        row = Notification.objects.filter(id=nid, recipient=request.user).first()
        if row:
            row.mark_read(opened=opened)
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
    _skip_unopened_bell_restore(request.user)
    _scoped_notifications_qs(request.user).filter(is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
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

