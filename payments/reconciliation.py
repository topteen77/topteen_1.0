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
        from notifications.models import NotificationCategory
        from notifications.services import emit_notification, get_parent_users_for_student

        sp = SkilllabCoursePayment.objects.filter(id=payment.obj_id, user_id=payment.user_id).first()
        if sp and sp.is_success != choices.YesNoChoices.YES:
            sp.is_success = choices.YesNoChoices.YES
            sp.save(update_fields=['is_success'])
            send_skillabcourse_payment_success_mail.delay(sp.id)
            recipients = [payment.user]
            recipients.extend(list(get_parent_users_for_student(payment.user_id)))
            emit_notification(
                event_type='course.allocated',
                title='Course allocated',
                body='Your course access is now active.',
                recipients=recipients,
                category=NotificationCategory.COURSE,
                source_obj=sp,
                payload={'payment_id': payment.id, 'course_payment_id': sp.id},
                dedupe_key='course_allocated_{}'.format(sp.id),
            )
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
    elif payment.obj_type == choices.PaymentObjectType.INSTITUTE_TIEUP:
        from institute.tieup_billing import finalize_tieup_payment

        finalize_tieup_payment(payment)
    elif payment.obj_type == choices.PaymentObjectType.LLM_TOKEN_PACKAGE:
        from core.llm_quota import fulfill_package_payment
        from core.models import LLMTokenPackagePayment

        sp = LLMTokenPackagePayment.objects.filter(id=payment.obj_id).first()
        if sp:
            # Beneficiary is domain payment user (may differ if we later allow parent pay)
            fulfill_package_payment(sp)
    # COUNSELOR: invoice + analytics from Payment signals only.
