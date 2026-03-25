from django.urls import path
from . import views
from .eazypay_webhook import IciciEazyPayWebhookView
from .razorpay_webhook import RazorpayWebhookView

app_name = "payments"
urlpatterns = [
    path("payment-success-v2/", views.UpdateEazyPayPayment.as_view(), name="updateeazypaypayment"),
    path("eazypay/webhook/", IciciEazyPayWebhookView.as_view(), name="eazypay_webhook"),
    path("razorpay/webhook/", RazorpayWebhookView.as_view(), name="razorpay_webhook"),
]