"""
In-app notifications for Payment lifecycle (success, failure, recovery after non-success).

Called from ``post_save`` on ``Payment``; may also be invoked explicitly if a code path
bypasses signals (e.g. ``QuerySet.update``).
"""

from urllib.parse import quote

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


def payment_amount_is_positive(payment=None, amount=None):
    """True when the payable amount is strictly greater than zero."""
    raw = amount
    if raw is None and payment is not None:
        raw = payment_order_amount_decimal(payment)
    try:
        return float(raw or 0) > 0
    except (TypeError, ValueError):
        return False


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
        elif ot == choices.PaymentObjectType.INSTITUTE_TIEUP:
            inst = institute_from_tieup_payment(payment)
            name = (getattr(inst, 'name', None) or '').strip() if inst is not None else ''
            if name:
                return 'Institute tie-up · {}'.format(name)
            return 'Institute tie-up'
    except Exception:
        pass
    return fallback


def retry_payment_path_for_payment(payment):
    """Relative URL path to restart checkout for this payment's product, or '' if unknown."""
    if not payment_amount_is_positive(payment):
        return ''
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
        elif ot == choices.PaymentObjectType.INSTITUTE_TIEUP:
            inst = institute_from_tieup_payment(payment)
            slug = (getattr(inst, 'slug', None) or '').strip() if inst is not None else ''
            if slug:
                return reverse('institute:institute_tieup_pay', kwargs={'slug': slug}) + '?retry=1'
    except NoReverseMatch:
        return ''
    return ''


def is_institute_tieup_payment(payment):
    return getattr(payment, 'obj_type', None) == choices.PaymentObjectType.INSTITUTE_TIEUP


def institute_from_tieup_payment(payment):
    if not payment or not is_institute_tieup_payment(payment):
        return None
    oid = getattr(payment, 'obj_id', None)
    if not oid:
        return None
    try:
        from institute.models import InstituteTieUpOrder

        order = (
            InstituteTieUpOrder.objects.select_related('institute')
            .filter(pk=oid)
            .first()
        )
    except Exception:
        return None
    return getattr(order, 'institute', None) if order is not None else None


def payment_identity_payload(payment):
    """Institute + payer ids used for role routing and page identification."""
    inst = institute_from_tieup_payment(payment)
    payer = getattr(payment, 'user', None)
    return {
        'obj_type': getattr(payment, 'obj_type', None),
        'payer_id': getattr(payment, 'user_id', None),
        'payer_email': (getattr(payer, 'email', None) or '').strip(),
        'payer_name': (getattr(payer, 'name', None) or '').strip(),
        'institute_id': getattr(inst, 'id', None) if inst is not None else None,
        'institute_slug': (getattr(inst, 'slug', None) or '') if inst is not None else '',
        'institute_name': (getattr(inst, 'name', None) or '').strip() if inst is not None else '',
    }


def marketing_tieup_payments_url(institute_slug='', payment_id=None, failed=False):
    extra = []
    slug = (institute_slug or '').strip()
    if slug:
        extra.append('institute=' + quote(slug, safe=''))
    if payment_id:
        extra.append('payment_id=' + str(payment_id))
    extra.append('status=failed' if failed else 'status=received')
    try:
        url = reverse('institute:marketinggroupdashboard_page', args=['payments'])
    except Exception:
        return ''
    return url + (('?' + '&'.join(extra)) if extra else '')


def payment_capture_url(payment_id=None, event_id=None):
    extra = []
    if payment_id:
        extra.append('payment_id=' + str(payment_id))
    if event_id:
        extra.append('event_id=' + str(event_id))
    try:
        url = reverse('notifications:payment_capture')
    except Exception:
        return ''
    return url + (('?' + '&'.join(extra)) if extra else '')


def cancel_payment_path_for_user(user, payment):
    """Dashboard / payments page for the payer (Cancel on the payment-info screen)."""
    ut = getattr(user, 'user_type', None)
    inst = institute_from_tieup_payment(payment)
    slug = (getattr(inst, 'slug', None) or '').strip() if inst is not None else ''
    try:
        if ut == choices.UserType.INSTITUTE and slug:
            return reverse('institute:institutedashboard_page', args=[slug, 'payments'])
        if ut == choices.UserType.INSTITUTEGROUPADMIN:
            extra = ('?institute=' + quote(slug, safe='')) if slug else ''
            return reverse('institute:institutegroupdashboard_page', args=['payments']) + extra
        if ut == choices.UserType.COUNSELOR:
            from counselor.models import Counselor

            coun = Counselor.objects.filter(coun_user_id=getattr(user, 'id', None)).only('id').first()
            if coun:
                return reverse('counselor:CounselorDashboardView', args=[coun.id])
            return reverse('counselor:CounselorCoursepayment')
        if ut == choices.UserType.MARKETINGGROUPADMIN:
            return marketing_tieup_payments_url(slug, getattr(payment, 'id', None))
    except Exception:
        pass
    try:
        return reverse('notifications:page')
    except Exception:
        return ''


def split_ops_payment_recipients(ops_recipients, payment):
    """Marketing sees institute/group tie-up payments only; staff/admin see all."""
    marketing = []
    staff = []
    tieup = is_institute_tieup_payment(payment)
    for user in ops_recipients or []:
        ut = getattr(user, 'user_type', None)
        if ut == choices.UserType.MARKETINGGROUPADMIN:
            if tieup:
                marketing.append(user)
            continue
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            staff.append(user)
    return marketing, staff


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
    if not payment_amount_is_positive(payment):
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
    identity = payment_identity_payload(payment)
    payer_capture_url = payment_capture_url(payment.id)
    payer_cancel = cancel_payment_path_for_user(getattr(payment, 'user', None), payment)
    marketing_ops, staff_ops = split_ops_payment_recipients(ops_recipients, payment)
    marketing_item_url = marketing_tieup_payments_url(
        identity.get('institute_slug') or '',
        payment.id,
        failed=bool(became_failed),
    )
    staff_item_url = payer_capture_url

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
                    **identity,
                    'recovered_from_non_success': True,
                    'item_url': payer_capture_url,
                    'cancel_payment_path': payer_cancel,
                    'show_retry_payment': False,
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
                payload={
                    **_payment_context_base(payment, label, amt, cur_code),
                    **identity,
                    'item_url': payer_capture_url,
                    'cancel_payment_path': payer_cancel,
                    'show_retry_payment': False,
                },
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
        ops_payload = {
            'payment_id': payment.id,
            'status': 'success',
            'item': label,
            'amount_display': amt,
            'currency_code': cur_code,
            'amount': '{:.2f}'.format(payment_order_amount_decimal(payment)),
            'recovered_from_non_success': transitioned_from_non_success,
            'show_retry_payment': False,
            **identity,
        }
        if marketing_ops:
            emit_notification(
                event_type='payment.status_updated',
                title=title,
                body=body,
                recipients=marketing_ops,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={**ops_payload, 'item_url': marketing_item_url},
                dedupe_key='payment_status_updated_success_{}'.format(payment.id),
            )
        if staff_ops:
            emit_notification(
                event_type='payment.status_updated',
                title=title,
                body=body,
                recipients=staff_ops,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={**ops_payload, 'item_url': staff_item_url},
                dedupe_key='payment_status_updated_success_{}'.format(payment.id),
            )
    elif became_failed:
        ctx = _payment_context_base(payment, label, amt, cur_code, retry_path=retry_path)
        payer = getattr(payment, 'user', None)
        payer_email = (getattr(payer, 'email', None) or '').strip()
        payer_name = (getattr(payer, 'name', None) or '').strip()
        ctx['payer_email'] = payer_email
        ctx['payer_name'] = payer_name
        ctx['payer_id'] = getattr(payer, 'id', None)
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
        payer_ids = {getattr(u, 'id', None) for u in recipients}
        marketing_ops = [u for u in marketing_ops if getattr(u, 'id', None) not in payer_ids]
        staff_ops = [u for u in staff_ops if getattr(u, 'id', None) not in payer_ids]
        emit_notification(
            event_type='payment.failed',
            title=title,
            body=body,
            recipients=recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=payment,
            payload={
                **ctx,
                **identity,
                'item_url': payer_capture_url,
                'cancel_payment_path': payer_cancel,
                'show_retry_payment': bool(retry_path),
            },
            dedupe_key='payment_failed_{}'.format(payment.id),
        )
        ops_bits = [
            bit
            for bit in (amt, label, identity.get('institute_name'), payer_email or payer_name)
            if bit
        ]
        ops_body = ' · '.join(ops_bits) if ops_bits else 'A checkout could not be completed.'
        failed_ops_payload = {
            'payment_id': payment.id,
            'gateway_order_id': (payment.gateway_order_id or '') or '',
            'item': label,
            'amount_display': amt,
            'currency_code': cur_code,
            'amount': '{:.2f}'.format(payment_order_amount_decimal(payment)),
            'show_retry_payment': False,
            **identity,
        }
        if marketing_ops:
            emit_notification(
                event_type='payment.failed',
                title='Payment failed',
                body=ops_body,
                recipients=marketing_ops,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={**failed_ops_payload, 'item_url': marketing_item_url},
                dedupe_key='payment_failed_{}'.format(payment.id),
            )
        if staff_ops:
            emit_notification(
                event_type='payment.failed',
                title='Payment failed',
                body=ops_body,
                recipients=staff_ops,
                category=NotificationCategory.PAYMENT,
                source_obj=payment,
                payload={**failed_ops_payload, 'item_url': staff_item_url},
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
