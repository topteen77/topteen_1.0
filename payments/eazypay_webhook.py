"""
ICICI EazyPay server-to-server / push notification URL.

Configure the same POST field names as the browser return URL (`payment-success-v2/`).
If `ICICI_EAZYPAY_WEBHOOK_SECRET` is set in settings, require it via header
`X-Eazypay-Webhook-Secret` or query `?secret=` (or POST field `webhook_secret`).
"""
import hmac
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from payments.eazypay_callback import process_eazypay_callback

logger = logging.getLogger(__name__)


def _webhook_secret_ok(request) -> bool:
    expected = (getattr(settings, 'ICICI_EAZYPAY_WEBHOOK_SECRET', '') or '').strip()
    if not expected:
        return True
    provided = (
        request.META.get('HTTP_X_EAZYPAY_WEBHOOK_SECRET')
        or request.META.get('HTTP_X_ICICI_EAZYPAY_WEBHOOK_SECRET')
        or request.GET.get('secret')
        or (request.data.get('webhook_secret') if hasattr(request, 'data') else None)
        or ''
    )
    provided = (provided or '').strip()
    return hmac.compare_digest(provided, expected)


@method_decorator(csrf_exempt, name='dispatch')
class IciciEazyPayWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        if not _webhook_secret_ok(request):
            logger.warning('ICICI EazyPay webhook rejected: secret mismatch or missing')
            return JsonResponse({'ok': False, 'error': 'invalid_secret'}, status=403)

        payment, _payment_status, _redirect_url, err = process_eazypay_callback(request)
        if err:
            # 200 avoids some gateways retry-storming on unknown references; ops can log body.
            return JsonResponse({'ok': False, 'error': err}, status=200)
        return JsonResponse(
            {
                'ok': True,
                'payment_id': payment.id,
                'is_success': payment.is_success,
            },
            status=200,
        )
