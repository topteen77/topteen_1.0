"""
In-app notifications for Payment lifecycle (success, failure, recovery after non-success).

Called from ``post_save`` on ``Payment``; may also be invoked explicitly if a code path
bypasses signals (e.g. ``QuerySet.update``).
"""

from core import choices

from .models import NotificationCategory
from .services import emit_notification, get_admin_and_accounts_users, get_parent_users_for_student


def payment_currency_code(payment):
    """ISO-style code for display (Payment.currency is a small int)."""
    if getattr(payment, 'currency', None) == choices.Currency.USD:
        return 'USD'
    return 'INR'


def format_currency_amount(amount, currency_code='INR'):
    """
    Amount with symbol and ISO currency label, e.g. ``₹500.00 INR`` or ``$10.00 USD``.
    ``amount`` may be int/float/str from DB or metadata.
    """
    try:
        if amount is None or amount == '':
            return ''
        val = float(amount)
        if currency_code == 'USD':
            return '${:.2f} USD'.format(val)
        return '₹{:.2f} INR'.format(val)
    except (TypeError, ValueError):
        return ''


def payment_amount_display(payment):
    """Formatted money line for a Payment row (uses ``payment.currency`` + ``payment.amount``)."""
    return format_currency_amount(getattr(payment, 'amount', None), payment_currency_code(payment))


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
            from skilllab.models import SkillLabCourse

            c = SkillLabCourse.objects.filter(pk=oid).only('name').first()
            if c and c.name:
                return (c.name or '').strip() or fallback
        elif ot == choices.PaymentObjectType.COUNSELOR:
            from counselor.models import CounselorCourse

            c = CounselorCourse.objects.filter(pk=oid).only('title').first()
            if c and c.title:
                return (c.title or '').strip() or fallback
    except Exception:
        pass
    return fallback


def notify_payment_transition(payment, previous_is_success, created):
    """
    Emit user/parent/staff notifications when Payment status changes.

    ``previous_is_success`` is the value before this save (from pre_save cache), or None for new rows.
    """
    if not payment.user_id:
        return

    recipients = [payment.user]
    recipients.extend(list(get_parent_users_for_student(payment.user_id)))
    staff = list(get_admin_and_accounts_users())

    became_success = payment.is_success == choices.YesNoChoices.YES and (
        created or previous_is_success != choices.YesNoChoices.YES
    )
    became_failed = payment.is_success != choices.YesNoChoices.YES and (
        created or previous_is_success == choices.YesNoChoices.YES
    )

    if became_success:
        label = payment_purchase_label(payment)
        amt = payment_amount_display(payment)
        cur_code = payment_currency_code(payment)
        transitioned_from_non_success = not created and previous_is_success != choices.YesNoChoices.YES

        if transitioned_from_non_success:
            if amt:
                body_ok = (
                    'Your payment of {} for {} is now successful. '
                    'If you saw an error or pending status earlier, that issue is resolved.'
                ).format(amt, label)
            else:
                body_ok = (
                    'Your payment for {} is now successful. '
                    'If you saw an error or pending status earlier, that issue is resolved.'
                ).format(label)
            emit_notification(
                event_type='payment.resolved',
                title='Payment issue resolved',
                body=body_ok,
                recipients=recipients,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={
                    'payment_id': payment.id,
                    'gateway_order_id': payment.gateway_order_id or '',
                    'item': label,
                    'currency_code': cur_code,
                    'amount_rupees': float(payment.amount or 0),
                    'amount_display': amt,
                    'recovered_from_non_success': True,
                },
                dedupe_key='payment_resolved_{}'.format(payment.id),
            )
        else:
            if amt:
                body_ok = 'Your payment of {} for {} was received successfully.'.format(amt, label)
            else:
                body_ok = 'Your payment for {} was received successfully.'.format(label)
            emit_notification(
                event_type='payment.success',
                title='Payment successful',
                body=body_ok,
                recipients=recipients,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={
                    'payment_id': payment.id,
                    'gateway_order_id': payment.gateway_order_id or '',
                    'item': label,
                    'currency_code': cur_code,
                    'amount_rupees': float(payment.amount or 0),
                    'amount_display': amt,
                },
                dedupe_key='payment_success_{}'.format(payment.id),
            )

        if transitioned_from_non_success:
            staff_body = 'Payment {} for {} ({}) marked successful (was not successful before; e.g. gateway callback or manual reconciliation).'.format(
                payment.id, label, amt or '—'
            )
        else:
            staff_body = 'Payment {} for {} ({}) marked successful.'.format(payment.id, label, amt or '—')
        emit_notification(
            event_type='payment.status_updated',
            title='Payment status updated',
            body=staff_body,
            recipients=staff,
            category=NotificationCategory.PAYMENT,
            source_obj=payment,
            payload={
                'payment_id': payment.id,
                'status': 'success',
                'item': label,
                'amount_rupees': float(payment.amount or 0),
                'recovered_from_non_success': transitioned_from_non_success,
            },
            dedupe_key='payment_status_updated_success_{}'.format(payment.id),
        )
    elif became_failed:
        label = payment_purchase_label(payment)
        amt = payment_amount_display(payment)
        cur_code = payment_currency_code(payment)
        if amt:
            body_fail = 'We could not confirm your payment of {} for {}. Please retry or contact support.'.format(
                amt, label
            )
        else:
            body_fail = 'We could not confirm your payment for {}. Please retry or contact support.'.format(label)
        emit_notification(
            event_type='payment.failed',
            title='Payment failed',
            body=body_fail,
            recipients=recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=payment,
            payload={
                'payment_id': payment.id,
                'gateway_order_id': payment.gateway_order_id or '',
                'item': label,
                'currency_code': cur_code,
                'amount_rupees': float(payment.amount or 0),
                'amount_display': amt,
            },
            dedupe_key='payment_failed_{}'.format(payment.id),
        )


def notify_payment_now_successful(payment, previous_is_success):
    """
    Call after saving a Payment as successful when signals did not run (e.g. ``QuerySet.update``).

    Pass ``previous_is_success`` from the row state *before* the update (typically ``YesNoChoices.NO``).
    """
    notify_payment_transition(payment, previous_is_success=previous_is_success, created=False)
