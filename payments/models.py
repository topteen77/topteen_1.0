from django.db import models
from core.models import BaseModel,BaseMoneyModel, SeoModel,SlugModel,Configuration
from users.models import User
from core import choices
from core.utils import get_preferred_payment_gateway
import json
from django.conf import settings
from .payment.razorpay import RazorpayService
from django.utils.timezone import datetime

def get_default_gateway():
    """Callable function to get default gateway preference"""
    return get_preferred_payment_gateway()

class Payment(BaseModel,BaseMoneyModel):
    """Gateway payment record. Use is_test_payment=True for demo/test payments; only testing payments can be deleted in admin."""
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="payments")
    is_test_payment = models.BooleanField(
        default=False,
        help_text="If True, this is a testing/demo payment and can be hard-deleted by admin. Actual payments cannot be deleted.",
    )
    gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
    gateway = models.SmallIntegerField(choices=choices.GatewayChoices.CHOICES,default=get_default_gateway)
    gateway_order_id = models.CharField(max_length=120,blank=True,null=True)
    gateway_payment_id = models.CharField(max_length=120,blank=True,null=True)
    gateway_signature = models.CharField(help_text="The transaction signature",max_length=120,blank=True,null=True)
    is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)
    obj_id=models.IntegerField()
    obj_type=models.SmallIntegerField(choices=choices.PaymentObjectType.CHOICES)
    response_details=models.TextField(blank=True,null=True,default='')
    response_code=models.CharField(max_length=120,blank=True,null=True)
    service_tax_amount=models.CharField(max_length=120,blank=True,null=True)
    processing_fee_amount=models.CharField(max_length=120,blank=True,null=True)
    total_amount=models.CharField(max_length=120,blank=True,null=True)
    transaction_amount=models.CharField(max_length=120,blank=True,null=True)
    transaction_date=models.DateTimeField(null=True,blank=True)
    interchange_value=models.CharField(max_length=255,null=True,blank=True)
    tdr=models.CharField(max_length=255,null=True,blank=True)
    payment_mode=models.CharField(max_length=255,null=True,blank=True)
    rs=models.TextField(null=True,blank=True)
    tps=models.TextField(null=True,blank=True)
    rsv=models.TextField(null=True,blank=True)

    def is_admin_manual_cash(self):
        """Staff-recorded offline cash payment — hidden from user-facing pages."""
        return self.gateway == choices.GatewayChoices.MANUAL

    @classmethod
    def user_facing_queryset(cls, user):
        """Payments shown on the student/parent payment history page."""
        return cls.objects.filter(user=user).exclude(
            gateway=choices.GatewayChoices.MANUAL
        ).order_by('-created')

    def get_order_id(self):
        rsvc = RazorpayService()
        order_receipt = self.gateway_receipt
        return rsvc.create_order(order_amount=int(self.get_gateway_amount()),order_receipt = order_receipt)

    def get_gateway_amount(self):
        return int(self.amount)*100
    
    def get_payment_info(self):
        d={}
        d['key'] = settings.RAZORPAY_KEY
        d['amount'] = self.get_gateway_amount()
        d['currency'] = "INR"
        d['name'] = settings.SITE_NAME
        d['description'] = "{}_{}_payment_{} || user_{} ||email_{}".format(self.get_obj_type_display(),self.obj_id,self.id,self.user.id,self.user.email) 
        d['image'] = settings.LOGO_URL
        d['order_id'] = self.get_order_id()
        d['prefill'] = self.get_payment_user_info()
        d['notes']={'{}_{}_payment_id'.format(self.obj_type,self.obj_id):self.id,'user_id':self.user.id,'name':self.user.name}
        d["theme"]= {"color": "#3399cc"}
        return json.dumps(d)

    def get_payment_user_info(self):
        d={}
        d['name']=self.user.name
        d['email'] = self.user.email
        d['contact'] =self.user.mobile
        return d

    def update_payment(self,gateway_payment_id,gateway_order_id,gateway_signature):
        """
        Verify against Razorpay using in-memory fields, then persist once.

        A single ``save()`` avoids an extra post_save where gateway ids are set but
        ``is_success`` is still NO (which looked like a failure to notifications/analytics).
        """
        self.gateway_order_id = gateway_order_id
        self.gateway_payment_id = gateway_payment_id
        self.gateway_signature = gateway_signature
        status = self.verify_payment()
        if status:
            self.is_success = choices.YesNoChoices.YES
        self.save()
        return status

    def verify_payment(self):
        rsvc = RazorpayService()
        status = rsvc.verify_payment(self)
        return status


    def update_eazypay_payment(self,response_code,unique_ref_no,service_tax_amount,processing_fee_amount,total_amount,transaction_amount,transaction_date,interchange_value,tdr,payment_mode,rs=rs,tps=tps,rsv=rsv):
        if transaction_date:
            transaction_date=datetime.strptime(transaction_date, "%d-%m-%Y %H:%M:%S")
        self.response_code=response_code
        self.gateway_order_id=unique_ref_no
        self.service_tax_amount=service_tax_amount
        self.processing_fee_amount=processing_fee_amount
        self.total_amount=total_amount
        self.transaction_amount=transaction_amount
        self.transaction_date=transaction_date
        self.interchange_value=interchange_value
        self.tdr=tdr
        self.payment_mode=payment_mode
        self.rs=rs
        self.tps=tps
        self.rsv=rsv
        if response_code == settings.ICICI_EAZYPAY_PAYMENT_SUCESS_RESPONSE_CODE:
            self.is_success=choices.YesNoChoices.YES
        self.save()
        return self.is_success