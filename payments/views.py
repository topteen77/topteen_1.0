from django.shortcuts import get_object_or_404
from core import choices
from .models import Payment
from psychometric_tests.models import PsychometricTestPayment
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import redirect,HttpResponseRedirect
from skilllab.models import SkilllabCoursePayment
from skilllab.task import send_skillabcourse_payment_success_mail
from rest_framework import status

class UpdateEazyPayPayment(APIView):    
    def post(self, request,*args, **kwargs):   
        response_code=request.data.get("Response Code")
        unique_reference_no=request.data.get("Unique Ref Number")
        service_tax_amount=request.data.get("Service Tax Amount") 
        processing_fee_amount=request.data.get("Processing Fee Amount")
        total_amount=request.data.get("Total Amount")
        transaction_amount=request.data.get("Transaction Amount")
        transaction_date=request.data.get("Transaction Date")
        interchange_value=request.data.get("Interchange Value")
        tdr=request.data.get("TDR")
        payment_mode=request.data.get("Payment Mode")
        submerchantid=request.data.get("SubMerchantId")
        referenceno=request.data.get("ReferenceNo")
        rs=request.data.get("RS")
        tps=request.data.get("TPS")
        mandotry_fields=request.data.get("mandatory fields")
        optional_fields=request.data.get("optional fields")
        rsv=request.data.get("RSV")
        is_api=request.GET.get("is_api",None)
        print("#"*30)
        print(request.data)
        print("#"*30)
        payment=get_object_or_404(Payment,id=referenceno,user__id=submerchantid)
        payment_status=payment.update_eazypay_payment(response_code,unique_reference_no,service_tax_amount,processing_fee_amount,total_amount,transaction_amount,transaction_date,interchange_value,tdr,payment_mode,rs=rs,tps=tps,rsv=rsv)
        try:
            from invoices.utils import record_gateway_callback
            from invoices.models import PaymentGatewayHealth
            record_gateway_callback(
                PaymentGatewayHealth.ICICI_EAZYPAY,
                success=bool(payment_status),
                error_message=None if payment_status else 'Callback response code: {}'.format(response_code),
                callback_url=request.build_absolute_uri(request.path) if request else None,
            )
        except Exception:
            pass
        if payment.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
            test=get_object_or_404(PsychometricTestPayment,id=payment.obj_id,user__id=submerchantid)
            if payment_status==choices.YesNoChoices.YES:
                redirect_url=test.get_test_payment_success_fail_url().get("success_url")
                test.is_success=choices.YesNoChoices.YES
                test.save()
                # Send payment success email (central test no longer used)
                try:
                    from psychometric_tests.task import send_pychometric_test_payment_success_mail
                    send_pychometric_test_payment_success_mail.delay(test.id)
                except Exception as e:
                    import traceback
                    print(traceback.format_exc())
                    print("Error sending payment success email:", e)
            else:
                redirect_url=test.get_test_payment_success_fail_url().get("fail_url")
                
        elif payment.obj_type == choices.PaymentObjectType.SKILLLABCOURSE:
            sp=get_object_or_404(SkilllabCoursePayment,id=payment.obj_id,user__id=submerchantid)
            if payment_status==choices.YesNoChoices.YES:
                redirect_url=sp.get_payment_success_fail_url().get("success_url")
                sp.is_success=choices.YesNoChoices.YES
                sp.save()
                send_skillabcourse_payment_success_mail.delay(sp.id)
            else:
                redirect_url=sp.get_payment_success_fail_url().get("fail_url")
        if is_api:
            return Response(status=status.HTTP_200_OK)
        return HttpResponseRedirect(redirect_url)
        
        