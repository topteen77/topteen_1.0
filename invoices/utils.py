"""Track payment gateway callback health for Accounts red alert."""
from django.utils import timezone
from .models import PaymentGatewayHealth
from core import choices


def record_gateway_callback(gateway, success, error_message=None, callback_url=None):
    """
    Call from payment callback views (Razorpay verify, EazyPay webhook) to update health.
    gateway: PaymentGatewayHealth.RAZORPAY or PaymentGatewayHealth.ICICI_EAZYPAY
    """
    try:
        health, _ = PaymentGatewayHealth.objects.get_or_create(
            gateway=gateway,
            defaults={
                'last_callback_at': timezone.now(),
                'last_callback_success': success,
                'last_error_message': error_message or '',
                'callback_url': callback_url or '',
            },
        )
        health.last_callback_at = timezone.now()
        health.last_callback_success = success
        health.last_error_message = error_message or ''
        if callback_url:
            health.callback_url = callback_url
        health.save(update_fields=['last_callback_at', 'last_callback_success', 'last_error_message', 'callback_url', 'modified'])
    except Exception as e:
        import traceback
        print('invoices.utils.record_gateway_callback failed:', e)
        traceback.print_exc()
