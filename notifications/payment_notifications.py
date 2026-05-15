"""
In-app notifications for Payment lifecycle (success, failure, recovery after non-success).

Called from ``post_save`` on ``Payment``; may also be invoked explicitly if a code path
bypasses signals (e.g. ``QuerySet.update``).
"""

from django.urls import NoReverseMatch, reverse

from core import choices

from .models import NotificationCategory
from .services import (
    emit_notification,
    format_notification_message,
    get_business_dashboard_notification_recipients,
    get_parent_users_for_student,
)


def _dedupe_recipients_by_id(users):
    seen = set()
    out = []
    for u in users:
        uid = getattr(u, 'id', None)
        if not uid or uid in seen:
            continue
        seen.add(uid)
        out.append(u)
    return out


def payment_currency_code(payment):
    """ISO-style code for display (Payment.currency is a small int). Defaults to INR."""
    cur = getattr(payment, 'currency', None)
    if cur is None:
        return 'INR'
    if cur == choices.Currency.USD:
        return 'USD'
    return 'INR'


def payment_order_amount_decimal(payment):
    """
    Amount for display: prefer gateway-settled fields (order / callback),
    then ``Payment.amount`` (in major units for INR/USD in this app).
    """
    for attr in ('transaction_amount', 'total_amount'):
        raw = getattr(payment, attr, None)
        if raw in (None, ''):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    try:
        return float(payment.amount or 0)
    except (TypeError, ValueError):
        return 0.0


def format_currency_amount(amount, currency_code='INR'):
    """
    Amount with symbol and ISO currency label, e.g. ``₹500.00 INR`` or ``$10.00 USD``.
    ``amount`` may be int/float/str from DB or metadata.
    """
    code = (currency_code or 'INR').upper()
    if code not in ('USD', 'INR'):
        code = 'INR'
    try:
        if amount is None or amount == '':
            return ''
        val = float(amount)
        if code == 'USD':
            return '${:.2f} USD'.format(val)
        return '₹{:.2f} INR'.format(val)
    except (TypeError, ValueError):
        return ''


def payment_amount_display(payment):
    """Formatted money line using order/callback amount and payment currency."""
    amt = payment_order_amount_decimal(payment)
    cur = payment_currency_code(payment)
    return format_currency_amount(amt, cur)


def payment_purchase_label(payment):
    """Course / test / counselor title for a Payment row."""
    ot = getattr(payment, 'obj_type', None)
    oid = getattr(payment, 'obj_id', None)
    fallback = dict(choices.PaymentObjectType.CHOICES).get(ot, 'your purchase')
    if not oid:
        return fallback
    try:
        if ot == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
            from psychometric_tests.models import PsychometricTestPayment

            p = PsychometricTestPayment.objects.filter(pk=oid).only('test_type').first()
            if p:
                return p.get_test_name()
        elif ot == choices.PaymentObjectType.SKILLLABCOURSE:
            from skilllab.models import SkilllabCoursePayment

            sp = SkilllabCoursePayment.objects.filter(pk=oid).select_related('skilllab_course').first()
            if sp and sp.skilllab_course and sp.skilllab_course.name:
                return (sp.skilllab_course.name or '').strip() or fallback
        elif ot == choices.PaymentObjectType.COUNSELOR:
            from counselor.models import CounselorCourse

            c = CounselorCourse.objects.filter(pk=oid).only('title').first()
            if c and c.title:
                return (c.title or '').strip() or fallback
    except Exception:
        pass
    return fallback


def retry_payment_path_for_payment(payment):
    """Relative URL path to restart checkout for this payment's product, or '' if unknown."""
    ot = getattr(payment, 'obj_type', None)
    oid = getattr(payment, 'obj_id', None)
    if not oid:
        return ''
    try:
        if ot == choices.PaymentObjectType.SKILLLABCOURSE:
            from skilllab.models import SkilllabCoursePayment

            sp = SkilllabCoursePayment.objects.filter(pk=oid).select_related('skilllab_course').first()
            if sp and getattr(sp, 'skilllab_course', None) and sp.skilllab_course.slug:
                return reverse(
                    'skilllabcourse:createskilllabcoursepayment',
                    kwargs={'slug': sp.skilllab_course.slug},
                )
        elif ot == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
            from psychometric_tests.models import PsychometricTestPayment

            tp = PsychometricTestPayment.objects.filter(pk=oid).only('test_type').first()
            if tp:
                if tp.test_type == choices.PsychometricTestType.BASIC:
                    return reverse('psychometrictests:psychometrictest')
                if tp.test_type == choices.PsychometricTestType.ADVANCED:
                    return reverse('psychometrictests:PsychometricTest12')
            return reverse('psychometrictests:psychometrictest')
        elif ot == choices.PaymentObjectType.COUNSELOR:
            return reverse('counselor:CounselorCoursepayment')
    except NoReverseMatch:
        return ''
    return ''


def _payment_indicates_completed_gateway_attempt(payment):
    """
    True after a gateway callback / verification attempt (not merely a Razorpay order created).

    Avoids treating a newly created unpaid ``Payment`` row as a failed payment.
    """
    if (getattr(payment, 'gateway_payment_id', None) or '').strip():
        return True
    if (getattr(payment, 'response_code', None) or '').strip():
        return True
    return False


def _payment_context_base(payment, label, amt_display, cur_code, retry_path=''):
    retry_hint = (
        'You can use Retry payment below or open the checkout again from the product page.'
        if retry_path
        else 'Please try again from the purchase page or contact support.'
    )
    return {
        'amount_display': amt_display,
        'amount': '{:.2f}'.format(payment_order_amount_decimal(payment)),
        'currency_code': cur_code,
        'item': label,
        'payment_id': payment.id,
        'gateway_order_id': (payment.gateway_order_id or '') or '',
        'retry_payment_path': retry_path,
        'retry_payment_label': 'Retry payment' if retry_path else '',
        'retry_payment_hint': retry_hint,
    }


def notify_payment_transition(payment, previous_is_success, created):
    """
    Emit user/parent/staff notifications when Payment status changes.

    ``previous_is_success`` is the value before this save (from pre_save cache), or None for new rows.

    Normal checkout (pending → success) uses ``payment.success``. Set ``payment._notify_payment_resolved =
    True`` on the instance before ``save()`` only for rare recovery cases (e.g. staff reconciliation after
    a failed or stuck payment) so users get the ``payment.resolved`` copy instead.
    """
    if not payment.user_id:
        return

    recipients = [payment.user]
    recipients.extend(list(get_parent_users_for_student(payment.user_id)))
    ops_recipients = get_business_dashboard_notification_recipients()

    became_success = payment.is_success == choices.YesNoChoices.YES and (
        created or previous_is_success != choices.YesNoChoices.YES
    )
    became_failed = (
        payment.is_success != choices.YesNoChoices.YES
        and not created
        and (
            previous_is_success == choices.YesNoChoices.YES
            or (
                previous_is_success != choices.YesNoChoices.YES
                and _payment_indicates_completed_gateway_attempt(payment)
            )
        )
    )

    label = payment_purchase_label(payment)
    amt = payment_amount_display(payment)
    cur_code = payment_currency_code(payment)
    retry_path = retry_payment_path_for_payment(payment) if became_failed else ''

    if became_success:
        # Do not treat "was pending (NO) → success" as "resolved"; that is the normal gateway path.
        transitioned_from_non_success = (
            not created
            and previous_is_success != choices.YesNoChoices.YES
            and bool(getattr(payment, '_notify_payment_resolved', False))
        )

        if transitioned_from_non_success:
            if amt:
                default_title = 'Payment issue resolved'
                default_body = (
                    'Your payment of {amount_display} for {item} is now successful. '
                    'If you saw an error or pending status earlier, that issue is resolved.'
                )
            else:
                default_title = 'Payment issue resolved'
                default_body = (
                    'Your payment for {item} is now successful. '
                    'If you saw an error or pending status earlier, that issue is resolved.'
                )
            title, body = format_notification_message(
                'payment.resolved',
                _payment_context_base(payment, label, amt, cur_code),
                default_title,
                default_body,
            )
            emit_notification(
                event_type='payment.resolved',
                title=title,
                body=body,
                recipients=recipients,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={
                    **_payment_context_base(payment, label, amt, cur_code),
                    'recovered_from_non_success': True,
                },
                dedupe_key='payment_resolved_{}'.format(payment.id),
            )
        else:
            if amt:
                default_title = 'Payment successful'
                default_body = 'Your payment of {amount_display} for {item} was received successfully.'
            else:
                default_title = 'Payment successful'
                default_body = 'Your payment for {item} was received successfully.'
            title, body = format_notification_message(
                'payment.success',
                _payment_context_base(payment, label, amt, cur_code),
                default_title,
                default_body,
            )
            emit_notification(
                event_type='payment.success',
                title=title,
                body=body,
                recipients=recipients,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload=_payment_context_base(payment, label, amt, cur_code),
                dedupe_key='payment_success_{}'.format(payment.id),
            )

        if transitioned_from_non_success:
            staff_extra = (
                '(was not successful before; e.g. gateway callback or manual reconciliation).'
            )
            default_title = 'Payment status updated'
            default_body = (
                'Payment {payment_id} for {item} ({amount_display}) marked successful. {extra}'
            )
            ctx = _payment_context_base(payment, label, amt, cur_code)
            ctx['status'] = 'success'
            ctx['extra'] = staff_extra
            title, body = format_notification_message(
                'payment.status_updated',
                ctx,
                default_title,
                default_body,
            )
        else:
            staff_extra = ''
            default_title = 'Payment status updated'
            default_body = 'Payment {payment_id} for {item} ({amount_display}) marked successful. {extra}'
            ctx = _payment_context_base(payment, label, amt, cur_code)
            ctx['status'] = 'success'
            ctx['extra'] = staff_extra
            title, body = format_notification_message(
                'payment.status_updated',
                ctx,
                default_title,
                default_body,
            )
        emit_notification(
            event_type='payment.status_updated',
            title=title,
            body=body,
            recipients=ops_recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=payment,
            payload={
                'payment_id': payment.id,
                'status': 'success',
                'item': label,
                'amount_display': amt,
                'currency_code': cur_code,
                'amount': '{:.2f}'.format(payment_order_amount_decimal(payment)),
                'recovered_from_non_success': transitioned_from_non_success,
            },
            dedupe_key='payment_status_updated_success_{}'.format(payment.id),
        )
    elif became_failed:
        ctx = _payment_context_base(payment, label, amt, cur_code, retry_path=retry_path)
        if amt:
            default_title = 'Payment failed'
            default_body = (
                'We could not confirm your payment of {amount_display} for {item}. '
                '{retry_payment_hint}'
            )
        else:
            default_title = 'Payment failed'
            default_body = (
                'We could not confirm your payment for {item}. {retry_payment_hint}'
            )
        title, body = format_notification_message(
            'payment.failed',
            ctx,
            default_title,
            default_body,
        )
        emit_notification(
            event_type='payment.failed',
            title=title,
            body=body,
            recipients=_dedupe_recipients_by_id(list(recipients) + ops_recipients),
            category=NotificationCategory.PAYMENT,
            source_obj=payment,
            payload={
                **ctx,
                'show_retry_payment': bool(retry_path),
            },
            dedupe_key='payment_failed_{}'.format(payment.id),
        )


def notify_payment_now_successful(payment, previous_is_success, notify_resolved=False):
    """
    Call after saving a Payment as successful when signals did not run (e.g. ``QuerySet.update``).

    Pass ``previous_is_success`` from the row state *before* the update (typically ``YesNoChoices.NO``).
    Set ``notify_resolved=True`` only for recovery-after-failure style updates.
    """
    if notify_resolved:
        payment._notify_payment_resolved = True
    notify_payment_transition(payment, previous_is_success=previous_is_success, created=False)
