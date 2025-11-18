from django.urls import path,include
from . import views

app_name="payments"
urlpatterns = [   
    path("payment-success-v2/",views.UpdateEazyPayPayment.as_view(),name="updateeazypaypayment") 
]