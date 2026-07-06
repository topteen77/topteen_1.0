"""
Signal: create Invoice only when Payment becomes successful. No invoice for failed payments.
No invoice for institute-registered free students.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from core import choices
from payments.models import Payment


def _is_institute_free_student_payment(payment):
    """True if this payment is for an institute-registered free student (no invoice should be generated)."""
    from institute.models import StudentManagement
    if not payment.user_id:
        return False
    if payment.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
        if StudentManagement.objects.filter(student_id=payment.user_id).exists():
            return True
    if getattr(payment, 'gateway_receipt', None) and str(payment.gateway_receipt or '').startswith('Student_Psychometric'):
        return True
    return False


@receiver(post_save, sender=Payment)
def on_payment_success_create_invoice(sender, instance, created, **kwargs):
    """Create invoice only when payment is successful. Never for failed payments. Institute free students skipped unless config allows."""
    if instance.is_success != choices.YesNoChoices.YES:
        return
    if instance.gateway == choices.GatewayChoices.MANUAL:
        return
    if _is_institute_free_student_payment(instance):
        from invoices.services import get_config
        if not get_config().generate_invoice_for_institute_students:
            return
    from invoices.models import Invoice
    if Invoice.objects.filter(payment=instance).exists():
        return
    # Build and save invoice with basic fields; task will generate PDF and send emails
    from invoices.services import create_invoice_for_payment
    create_invoice_for_payment(instance)
