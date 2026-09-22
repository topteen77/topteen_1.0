from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core import choices
from institute.models import StudentManagement
from payments.models import Payment
from user_analytics.models import UserEvent
from user_analytics.models import Lead as AnalyticsLead
from core.models import Lead as ContactLead

from .models import NotificationCategory
from .payment_notifications import (
    _dedupe_recipients_by_id,
    cancel_payment_path_for_user,
    format_currency_amount,
    marketing_tieup_payments_url,
    notify_payment_transition,
    payment_amount_display,
    payment_amount_is_positive,
    payment_capture_url,
    payment_currency_code,
    payment_identity_payload,
    payment_order_amount_decimal,
    payment_purchase_label,
    retry_payment_path_for_payment,
    split_ops_payment_recipients,
)
from .services import (
    emit_notification,
    format_notification_message,
    get_business_dashboard_notification_recipients,
    get_parent_users_for_student,
    phone_is_followable,
)


def _user_event_payment_label_and_amount(ev):
    """Item label + amount string + currency code for UserEvent(payment_failed) when Payment row may be missing."""
    meta = ev.metadata or {}
    amt_raw = meta.get('order_amount_rupees')
    if amt_raw is None and getattr(ev, 'event_value', None):
        amt_raw = ev.event_value
    amt_str = (
        format_currency_amount(amt_raw, 'INR')
        if amt_raw not in (None, '', 0, '0', 0.0)
        else ''
    )

    item = (meta.get('test_name') or meta.get('course_name') or '').strip()
    if not item:
        item = (meta.get('obj_type') or '').strip()

    p = None
    currency_code = ''
    pid = meta.get('payment_id') or ev.object_id
    if pid:
        p = Payment.objects.filter(pk=pid).only('obj_type', 'obj_id', 'amount', 'currency').first()
    if p is None:
        oid = (meta.get('gateway_order_id') or meta.get('order_id') or '').strip()
        if oid:
            p = Payment.objects.filter(gateway_order_id=oid).only('obj_type', 'obj_id', 'amount', 'currency').first()
    if p is not None:
        item = payment_purchase_label(p)
        if not amt_str:
            amt_str = payment_amount_display(p)
        currency_code = payment_currency_code(p)
    elif amt_str:
        currency_code = 'INR'
    if not item:
        item = 'your purchase'
    return item, amt_str, currency_code


@receiver(post_save, sender=Payment)
def payment_notifications(sender, instance, created, **kwargs):
    previous_is_success = getattr(instance, '_previous_is_success', None)
    notify_payment_transition(instance, previous_is_success=previous_is_success, created=created)


@receiver(pre_save, sender=Payment)
def payment_notification_state_cache(sender, instance, **kwargs):
    """
    Cache previous payment state to emit notifications only on status transition.
    """
    if not instance.pk:
        instance._previous_is_success = None
        return
    prev = sender.objects.filter(pk=instance.pk).values_list('is_success', flat=True).first()
    instance._previous_is_success = prev


@receiver(post_save, sender=StudentManagement)
def institute_student_notifications(sender, instance, created, **kwargs):
    if not created or not instance.institute_id:
        return
    try:
        from institute.models import Institute
        from notifications.institute_notifications import notify_student_registered

        institute = (
            Institute.objects.select_related(
                'created_by',
                'institute_group',
                'institute_group__institute_group_admin',
            )
            .filter(pk=instance.institute_id)
            .first()
        )
        if institute is not None:
            notify_student_registered(instance, institute)
    except Exception:
        pass

    # Marketing alerts for demo institutes (website + optional WhatsApp).
    if getattr(instance, '_skip_demo_mktg_student_added_notify', False):
        return
    try:
        institute = instance.institute
        if institute and getattr(institute, 'is_demo_institute', False):
            from institute.demo_institute_notifications import notify_demo_institute_students_added

            notify_demo_institute_students_added(
                institute,
                student=getattr(instance, 'student', None),
                source='enroll',
            )
    except Exception:
        pass


@receiver(post_save, sender=AnalyticsLead)
def marketing_lead_notifications(sender, instance, created, **kwargs):
    if not _analytics_lead_has_contact(instance):
        return
    _emit_marketing_new_lead(
        lead_id=instance.id,
        lead_kind='analytics',
        source_obj=instance,
        name=instance.name,
        email=instance.email,
        phone=instance.phone,
        source=instance.source,
    )


@receiver(post_save, sender=ContactLead)
def marketing_contact_lead_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    name = (instance.name or '').strip()
    phone = (instance.mobile or '').strip()
    if not phone_is_followable(phone):
        return
    _emit_marketing_new_lead(
        lead_id=instance.id,
        lead_kind='contact',
        source_obj=instance,
        name=name,
        email='',
        phone=phone,
        source='enquiry form',
    )


def _analytics_lead_has_contact(instance):
    """Only real follow-up leads: a callable phone. Session emails are tracking junk."""
    return phone_is_followable(getattr(instance, 'phone', None))


def _emit_marketing_new_lead(lead_id, lead_kind, source_obj, name, email, phone, source):
    from django.urls import reverse
    from users.models import User

    recipients = list(
        User.objects.filter(
            user_type=choices.UserType.MARKETINGGROUPADMIN,
            is_active=True,
        )
    )
    if not recipients:
        return
    item_url = ''
    try:
        if lead_kind == 'contact':
            item_url = reverse('notifications:lead_capture_contact', args=[lead_id])
        else:
            item_url = reverse('notifications:lead_capture', args=[lead_id])
    except Exception:
        item_url = ''
    display_name = (name or '').strip() or (phone or '').strip() or (email or '').strip() or 'New lead'
    body_bits = [bit for bit in ((phone or '').strip(), (email or '').strip(), (source or '').strip()) if bit]
    payload = {
        'lead_id': lead_id,
        'lead_kind': lead_kind,
        'name': (name or '').strip(),
        'email': (email or '').strip(),
        'phone': (phone or '').strip(),
        'source': (source or '').strip(),
    }
    if item_url:
        payload['item_url'] = item_url
    emit_notification(
        event_type='marketing.new_lead',
        title='New lead: {}'.format(display_name),
        body=' · '.join(body_bits) if body_bits else 'A new lead shared contact details.',
        recipients=recipients,
        category=NotificationCategory.MARKETING,
        source_obj=source_obj,
        payload=payload,
        dedupe_key='marketing_new_lead_{}_{}'.format(lead_kind, lead_id),
    )


def _notify_demo_result_for_user(user, result_kind='test'):
    if not user:
        return
    try:
        from institute.demo_institute_notifications import notify_demo_institute_test_result

        notify_demo_institute_test_result(user, result_kind=result_kind)
    except Exception:
        pass


@receiver(post_save, sender='app.Results')
def demo_institute_class10_result_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    _notify_demo_result_for_user(getattr(instance, 'user', None), result_kind='class10')


@receiver(post_save, sender='app_post_matric.TestResult')
def demo_institute_post_matric_result_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    session = getattr(instance, 'session', None)
    user = getattr(session, 'user', None) if session else None
    _notify_demo_result_for_user(user, result_kind='post_matric')


@receiver(post_save, sender='psychometric_tests.PsychometricTestResult')
def demo_institute_psychometric_result_notifications(sender, instance, created, **kwargs):
    # get_or_create may create an empty shell first; notify once when RIASEC scores appear.
    if not any(
        getattr(instance, f, None) is not None
        for f in ('realistic', 'investigative', 'artistic', 'social', 'entrepreneurial', 'conventional')
    ):
        return
    try:
        from institute.demo_institute_notifications import resolve_user_from_psychometric_result

        user = resolve_user_from_psychometric_result(instance)
    except Exception:
        user = None
    _notify_demo_result_for_user(user, result_kind='psychometric')


@receiver(post_save, sender=UserEvent)
def userevent_payment_failed_notifications(sender, instance, created, **kwargs):
    """
    Fallback path: some gateway failures are only tracked as UserEvent(payment_failed).
    Ensure student/parent still receive an in-app notification in those flows.
    """
    if not created or instance.event_type != 'payment_failed' or not instance.user_id:
        return

    payer_recipients = _dedupe_recipients_by_id(
        [instance.user] + list(get_parent_users_for_student(instance.user_id))
    )
    payer_ids = {getattr(u, 'id', None) for u in payer_recipients}
    ops_recipients = [
        u
        for u in get_business_dashboard_notification_recipients()
        if getattr(u, 'id', None) not in payer_ids
    ]

    metadata = instance.metadata or {}
    payment_id = metadata.get('payment_id') or instance.object_id
    gateway_order_id = metadata.get('gateway_order_id') or ''
    reason = (metadata.get('payment_stage') or metadata.get('error_message') or '').strip()
    item, amt, currency_code = _user_event_payment_label_and_amount(instance)

    # Do not notify if this event points at a Payment row that already succeeded (stale analytics events).
    # Match by payment id only — gateway_order_id can be reused or ambiguous across rows.
    if payment_id:
        pay_row = Payment.objects.filter(pk=payment_id).only('is_success').first()
        if pay_row and pay_row.is_success == choices.YesNoChoices.YES:
            return
    retry_path = ''
    p_obj = None
    if payment_id:
        p_obj = Payment.objects.filter(pk=payment_id).first()
    if p_obj is None and gateway_order_id:
        p_obj = Payment.objects.filter(gateway_order_id=gateway_order_id).first()
    if p_obj is not None:
        retry_path = retry_payment_path_for_payment(p_obj)
        if not payment_amount_is_positive(p_obj):
            return
    else:
        amt_raw = metadata.get('order_amount_rupees')
        if amt_raw is None:
            amt_raw = getattr(instance, 'event_value', None)
        if not payment_amount_is_positive(amount=amt_raw):
            return

    retry_hint = (
        'You can use Retry payment below or open the checkout again from the product page.'
        if retry_path
        else 'Please try again from the purchase page or contact support.'
    )
    amt_num = ''
    if p_obj is not None:
        amt_num = '{:.2f}'.format(payment_order_amount_decimal(p_obj))
    ctx = {
        'amount_display': amt,
        'amount': amt_num,
        'currency_code': currency_code or 'INR',
        'item': item,
        'payment_id': payment_id or '',
        'gateway_order_id': gateway_order_id,
        'retry_payment_path': retry_path,
        'retry_payment_label': 'Retry payment' if retry_path else '',
        'retry_payment_hint': retry_hint,
        'reason': reason,
    }
    if amt:
        default_title = 'Payment failed'
        default_body = (
            'We could not confirm your payment of {amount_display} for {item}. {retry_payment_hint}'
            + (' Reason: {reason}.' if reason else '')
        )
    else:
        default_title = 'Payment failed'
        default_body = (
            'We could not confirm your payment for {item}. {retry_payment_hint}'
            + (' Reason: {reason}.' if reason else '')
        )
    title, body = format_notification_message('payment.failed', ctx, default_title, default_body)

    dedupe_key = 'payment_failed_event_{}'.format(instance.id)
    if payment_id:
        # Keep same key shape as Payment signal to avoid duplicates for same payment.
        dedupe_key = 'payment_failed_{}'.format(payment_id)
    elif gateway_order_id:
        dedupe_key = 'payment_failed_order_{}'.format(gateway_order_id)

    payer_user = instance.user
    payer_email = (getattr(payer_user, 'email', None) or '').strip()
    payer_name = (getattr(payer_user, 'name', None) or '').strip()
    identity = payment_identity_payload(p_obj) if p_obj is not None else {
        'payer_id': getattr(payer_user, 'id', None),
        'payer_email': payer_email,
        'payer_name': payer_name,
        'obj_type': None,
        'institute_id': None,
        'institute_slug': '',
        'institute_name': '',
    }
    capture_url = payment_capture_url(payment_id, instance.id)
    payer_cancel = cancel_payment_path_for_user(payer_user, p_obj) if p_obj is not None else ''
    marketing_ops, staff_ops = split_ops_payment_recipients(ops_recipients, p_obj)
    marketing_item_url = marketing_tieup_payments_url(
        identity.get('institute_slug') or '',
        payment_id,
        failed=True,
    )
    shared_payload = {
        'payment_id': payment_id or '',
        'gateway_order_id': gateway_order_id,
        'event_id': instance.id,
        'item': item,
        'currency_code': currency_code or '',
        'amount_display': amt,
        **identity,
    }
    if payer_recipients:
        emit_notification(
            event_type='payment.failed',
            title=title,
            body=body,
            recipients=payer_recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=instance if instance.object_id else None,
            payload={
                **shared_payload,
                'retry_payment_path': retry_path,
                'retry_payment_label': ctx['retry_payment_label'],
                'show_retry_payment': bool(retry_path),
                'item_url': capture_url,
                'cancel_payment_path': payer_cancel,
            },
            dedupe_key=dedupe_key,
        )
    ops_bits = [
        bit
        for bit in (amt, item, identity.get('institute_name'), payer_email or payer_name)
        if bit
    ]
    ops_body = ' · '.join(ops_bits) if ops_bits else 'A checkout could not be completed.'
    failed_ops = {
        **shared_payload,
        'show_retry_payment': False,
    }
    if marketing_ops:
        emit_notification(
            event_type='payment.failed',
            title='Payment failed',
            body=ops_body,
            recipients=marketing_ops,
            category=NotificationCategory.PAYMENT,
            source_obj=instance if instance.object_id else None,
            payload={**failed_ops, 'item_url': marketing_item_url},
            dedupe_key=dedupe_key,
        )
    if staff_ops:
        emit_notification(
            event_type='payment.failed',
            title='Payment failed',
            body=ops_body,
            recipients=staff_ops,
            category=NotificationCategory.PAYMENT,
            source_obj=instance if instance.object_id else None,
            payload={**failed_ops, 'item_url': capture_url},
            dedupe_key=dedupe_key,
        )

