from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core import choices
from institute.models import StudentManagement
from payments.models import Payment
from user_analytics.models import UserEvent
from user_analytics.models import Lead

from .models import NotificationCategory
from .payment_notifications import (
    _dedupe_recipients_by_id,
    format_currency_amount,
    notify_payment_transition,
    payment_amount_display,
    payment_currency_code,
    payment_order_amount_decimal,
    payment_purchase_label,
    retry_payment_path_for_payment,
)
from .services import (
    emit_notification,
    format_notification_message,
    get_business_dashboard_notification_recipients,
    get_parent_users_for_student,
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
    institute_user = getattr(instance.institute, 'created_by', None)
    recipients = [u for u in [institute_user] if getattr(u, 'id', None)]
    if recipients:
        emit_notification(
            event_type='institute.student_registered',
            title='New student registered',
            body='A student was registered under your institute.',
            recipients=recipients,
            category=NotificationCategory.INSTITUTE,
            source_obj=instance,
            payload={'student_id': instance.student_id, 'institute_id': instance.institute_id},
            dedupe_key='institute_student_registered_{}'.format(instance.id),
        )

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


@receiver(post_save, sender=Lead)
def marketing_lead_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    from users.models import User

    recipients = list(
        User.objects.filter(
            user_type=choices.UserType.MARKETINGGROUPADMIN,
            is_active=True,
        )
    )
    if not recipients:
        return
    emit_notification(
        event_type='marketing.new_lead',
        title='New lead captured',
        body='Lead {} ({}) captured from {}.'.format(instance.name or '-', instance.email, instance.source or 'unknown'),
        recipients=recipients,
        category=NotificationCategory.MARKETING,
        source_obj=instance,
        payload={'lead_id': instance.id, 'email': instance.email, 'source': instance.source},
        dedupe_key='marketing_new_lead_{}'.format(instance.id),
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

    recipients = _dedupe_recipients_by_id(
        [instance.user]
        + list(get_parent_users_for_student(instance.user_id))
        + get_business_dashboard_notification_recipients()
    )

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

    emit_notification(
        event_type='payment.failed',
        title=title,
        body=body,
        recipients=recipients,
        category=NotificationCategory.PAYMENT,
        source_obj=instance if instance.object_id else None,
        payload={
            'payment_id': payment_id or '',
            'gateway_order_id': gateway_order_id,
            'event_id': instance.id,
            'item': item,
            'currency_code': currency_code or '',
            'amount_display': amt,
            'retry_payment_path': retry_path,
            'retry_payment_label': ctx['retry_payment_label'],
            'show_retry_payment': bool(retry_path),
        },
        dedupe_key=dedupe_key,
    )

