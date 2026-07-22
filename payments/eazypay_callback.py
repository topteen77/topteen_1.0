"""
Shared ICICI EazyPay POST handling for the browser return URL and the server webhook.

Both paths receive the same field names from EazyPay (Response Code, ReferenceNo, SubMerchantId, …).
"""
import logging

from django.shortcuts import get_object_or_404

from core import choices
from payments.models import Payment
from payments.reconciliation import finalize_side_effects_after_gateway_success
from psychometric_tests.models import PsychometricTestPayment
from skilllab.models import SkilllabCoursePayment

logger = logging.getLogger(__name__)


def process_eazypay_callback(request):
    """
    Apply EazyPay POST fields to the matching Payment row and run success side effects.

    Returns:
        (payment, payment_status, redirect_url, error)
        error is None on success; otherwise a short machine-readable string.
    """
    data = request.data
    response_code = data.get('Response Code')
    unique_reference_no = data.get('Unique Ref Number')
    service_tax_amount = data.get('Service Tax Amount')
    processing_fee_amount = data.get('Processing Fee Amount')
    total_amount = data.get('Total Amount')
    transaction_amount = data.get('Transaction Amount')
    transaction_date = data.get('Transaction Date')
    interchange_value = data.get('Interchange Value')
    tdr = data.get('TDR')
    payment_mode = data.get('Payment Mode')
    submerchantid = data.get('SubMerchantId')
    referenceno = data.get('ReferenceNo')
    rs = data.get('RS')
    tps = data.get('TPS')
    rsv = data.get('RSV')

    if referenceno is None or submerchantid is None:
        return None, None, None, 'missing_reference_or_submerchant'

    try:
        ref = int(referenceno)
        uid = int(submerchantid)
    except (TypeError, ValueError):
        return None, None, None, 'invalid_reference_or_submerchant'

    payment = Payment.objects.filter(id=ref, user_id=uid).first()
    if not payment:
        return None, None, None, 'payment_not_found'

    payment_status = payment.update_eazypay_payment(
        response_code,
        unique_reference_no,
        service_tax_amount,
        processing_fee_amount,
        total_amount,
        transaction_amount,
        transaction_date,
        interchange_value,
        tdr,
        payment_mode,
        rs=rs,
        tps=tps,
        rsv=rsv,
    )

    try:
        from invoices.models import PaymentGatewayHealth
        from invoices.utils import record_gateway_callback

        record_gateway_callback(
            PaymentGatewayHealth.ICICI_EAZYPAY,
            success=bool(payment_status),
            error_message=None if payment_status else 'Callback response code: {}'.format(response_code),
            callback_url=request.build_absolute_uri(request.path) if request else None,
        )
    except Exception:
        pass

    if payment_status == choices.YesNoChoices.YES:
        finalize_side_effects_after_gateway_success(payment)

    redirect_url = _eazypay_redirect_url(payment, payment_status, uid)
    return payment, payment_status, redirect_url, None


def _eazypay_redirect_url(payment, payment_status, user_id):
    """Success/fail landing URL for browser return (Skilllab / Psychometric)."""
    if payment.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
        test = get_object_or_404(PsychometricTestPayment, id=payment.obj_id, user_id=user_id)
        urls = test.get_test_payment_success_fail_url()
        if payment_status == choices.YesNoChoices.YES:
            return urls.get('success_url')
        return urls.get('fail_url')
    if payment.obj_type == choices.PaymentObjectType.SKILLLABCOURSE:
        sp = get_object_or_404(SkilllabCoursePayment, id=payment.obj_id, user_id=user_id)
        urls = sp.get_payment_success_fail_url()
        if payment_status == choices.YesNoChoices.YES:
            return urls.get('success_url')
        return urls.get('fail_url')
    if payment.obj_type == choices.PaymentObjectType.INSTITUTE_TIEUP:
        from institute.tieup_billing import tieup_payment_result_url

        url = tieup_payment_result_url(payment)
        if url:
            return url
    if payment.obj_type == choices.PaymentObjectType.LLM_TOKEN_PACKAGE:
        from core.models import LLMTokenPackagePayment

        sp = get_object_or_404(LLMTokenPackagePayment, id=payment.obj_id, user_id=user_id)
        urls = sp.get_payment_success_fail_url()
        if payment_status == choices.YesNoChoices.YES:
            return urls.get('success_url')
        return urls.get('fail_url')
    return None
