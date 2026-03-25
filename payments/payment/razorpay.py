import logging
import razorpay
from django.conf import settings 
from datetime import datetime,timedelta
import json

logger = logging.getLogger(__name__)


class RazorpayService:

    def __init__(self):
        self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))

    def create_order(self,order_amount=0,order_receipt=""):
        order_currency = 'INR'
        data = {}
        data['amount'] = order_amount
        data['currency'] = order_currency
        data['receipt'] = order_receipt
        response = self.client.order.create(data)
        return response.get('id')

    def verify_payment(self,order_payment):
        try:
           
            signature_verified = self.get_signature_status(order_payment)  
            payment_status = self.get_payment_status(order_payment)         
            return signature_verified  and payment_status
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("asdfasd",e)
        return False

    def get_signature_status(self,order_payment):
        d={}
        d['razorpay_payment_id'] = order_payment.gateway_payment_id
        d['razorpay_order_id'] = order_payment.gateway_order_id
        d['razorpay_signature'] = order_payment.gateway_signature
        result = self.client.utility.verify_payment_signature(d)
        return result

    def get_payment_status(self,order_payment):
        payment_id,amount=order_payment.gateway_payment_id,order_payment.get_gateway_amount()
        payment_detail = self.get_payment_details(payment_id)
        return (payment_detail.get('status') == 'captured' or payment_detail.get('status') ==  'authorized') and int(payment_detail.get('amount')) == amount

    def verify_payment_amount_status_and_order(self, order_payment):
        """
        Confirm payment via Razorpay API (amount, status, order_id) without client signature.
        Used when payment.captured webhook already passed HMAC verification.
        """
        try:
            if not order_payment.gateway_payment_id or not order_payment.gateway_order_id:
                return False
            detail = self.get_payment_details(order_payment.gateway_payment_id)
            amount_ok = int(detail.get('amount')) == order_payment.get_gateway_amount()
            status_ok = detail.get('status') in ('captured', 'authorized')
            order_ok = (detail.get('order_id') or '') == (order_payment.gateway_order_id or '')
            return amount_ok and status_ok and order_ok
        except Exception:
            logger.exception('verify_payment_amount_status_and_order failed')
            return False

    def get_payment_details(self,payment_id):
        return self.client.payment.fetch(payment_id)
    
