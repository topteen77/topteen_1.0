"""
Razorpay server-to-server webhooks.

Client-side flow alone cannot complete payment if the user closes the tab before the
browser POSTs gateway ids to our API. Register `payment.captured` in the Razorpay
dashboard pointing to this URL and set RAZORPAY_WEBHOOK_SECRET in .env.

ICICI EazyPay uses a separate push/notification URL: /payments/eazypay/webhook/
(see payments/eazypay_webhook.py and ICICI_EAZYPAY_WEBHOOK_SECRET).
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

import razorpay

from core import choices
from payments.models import Payment
from payments.payment.razorpay import RazorpayService
from payments.reconciliation import finalize_side_effects_after_gateway_success

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or ''
        if not secret.strip():
            logger.warning('Razorpay webhook rejected: RAZORPAY_WEBHOOK_SECRET is not set')
            return HttpResponse('Webhook not configured', status=503)

        body = request.body
        body_str = body.decode('utf-8') if isinstance(body, bytes) else body
        sig = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
            client.utility.verify_webhook_signature(body_str, sig, secret)
        except Exception as e:
            logger.warning('Razorpay webhook signature invalid: %s', e)
            return HttpResponse('Invalid signature', status=400)

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return HttpResponse('Invalid JSON', status=400)

        event = payload.get('event') or ''
        if event == 'payment.captured':
            return self._handle_payment_captured(payload)
        return HttpResponse(status=200)

    def _handle_payment_captured(self, payload):
        try:
            entity = payload['payload']['payment']['entity']
        except (KeyError, TypeError, IndexError):
            return HttpResponse(status=200)

        order_id = entity.get('order_id')
        rz_payment_id = entity.get('id')
        amount_paise = entity.get('amount')
        if not order_id or not rz_payment_id or amount_paise is None:
            return HttpResponse(status=200)

        payment = (
            Payment.objects.filter(
                gateway_order_id=order_id,
                is_success=choices.YesNoChoices.NO,
            )
            .exclude(gateway_order_id__isnull=True)
            .exclude(gateway_order_id='')
            .first()
        )
        if not payment:
            return HttpResponse(status=200)

        if int(amount_paise) != payment.get_gateway_amount():
            logger.warning(
                'Razorpay webhook amount mismatch payment_id=%s expected_paise=%s got=%s',
                payment.id,
                payment.get_gateway_amount(),
                amount_paise,
            )
            return HttpResponse(status=200)

        payment.gateway_payment_id = rz_payment_id
        rsvc = RazorpayService()
        if not rsvc.verify_payment_amount_status_and_order(payment):
            logger.warning('Razorpay API verify failed after webhook for payment %s', payment.id)
            return HttpResponse(status=200)

        payment.is_success = choices.YesNoChoices.YES
        payment.save(update_fields=['gateway_payment_id', 'is_success'])
        finalize_side_effects_after_gateway_success(payment)

        try:
            from invoices.models import PaymentGatewayHealth
            from invoices.utils import record_gateway_callback

            record_gateway_callback(
                PaymentGatewayHealth.RAZORPAY,
                success=True,
                callback_url='razorpay_webhook:payment.captured',
            )
        except Exception:
            pass

        return HttpResponse(status=200)
