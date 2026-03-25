"""
Shared logic to complete payment + product side effects after gateway confirms success.
Used by Razorpay webhooks and staff manual reconciliation.
"""
import logging

from core import choices

logger = logging.getLogger(__name__)


def finalize_side_effects_after_gateway_success(payment):
    """Mirror client-side success handling in skilllab/psychometric views."""
    if payment.obj_type == choices.PaymentObjectType.SKILLLABCOURSE:
        from skilllab.models import SkilllabCoursePayment
        from skilllab.task import send_skillabcourse_payment_success_mail

        sp = SkilllabCoursePayment.objects.filter(id=payment.obj_id, user_id=payment.user_id).first()
        if sp and sp.is_success != choices.YesNoChoices.YES:
            sp.is_success = choices.YesNoChoices.YES
            sp.save(update_fields=['is_success'])
            send_skillabcourse_payment_success_mail.delay(sp.id)
    elif payment.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
        from psychometric_tests.models import PsychometricTestPayment
        from psychometric_tests.task import send_pychometric_test_payment_success_mail

        test = PsychometricTestPayment.objects.filter(id=payment.obj_id, user_id=payment.user_id).first()
        if test and test.is_success != choices.YesNoChoices.YES:
            test.is_success = choices.YesNoChoices.YES
            test.save(update_fields=['is_success'])
            try:
                send_pychometric_test_payment_success_mail.delay(test.id)
            except Exception:
                logger.exception('Psychometric success mail failed (reconciliation)')
    # COUNSELOR: invoice + analytics from Payment signals only.
