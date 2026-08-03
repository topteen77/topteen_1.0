from django.shortcuts import render
from django.views.generic import TemplateView,View
from django.urls import reverse_lazy
from core.utils import build_html_head, get_preferred_payment_gateway, is_gateway_available, ensure_user_pdf_folder
from core.breadcrumbs import get_breadcrumb
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from core import choices
from core.models import Configuration
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions,authentication
from rest_framework import status
import json
from payments.models import Payment
from .models import PsychometricTestPayment,CentralTestCandidate,CandidateTest,PsychometricTestResult,PsychometricFAQ
from .task import create_central_test_candidate,send_pychometric_test_payment_success_mail,create_pyschometric_assessment_result
from blog.models import Blog
from courses.models import Course
from skilllab.models import SkillLabCourse
from django.core.signing import Signer
from django.shortcuts import get_object_or_404
from careers.models import Career
from django.db.models import Q
from django.urls import reverse
from django.shortcuts import redirect,HttpResponseRedirect
from payments.payment.icicieazypay import IciciEazyPayService
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.conf import settings
from colleges.models import College
from core.models import Country
from users.models import User
from institute.models import StudentManagement
from django.http import JsonResponse


@method_decorator(never_cache, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class PsychometricTest(TemplateView):
    template_name = "template20/psychometric_test.html"
    def html_head(self):
        name='Psychometric Test'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        from django.urls import reverse
        ctx={}
        ctx["test_type"]={"basic_test_type":choices.PsychometricTestType.BASIC,"advanced_test_type":choices.PsychometricTestType.ADVANCED}
        # Stream Sorter uses BASIC test type
        ctx["test_type_id"] = choices.PsychometricTestType.BASIC
        ctx["html_head"] = self.html_head()
        ctx["faq"]=PsychometricFAQ.objects.all().order_by("priority")
        # Use Stream Sorter test amount from settings
        ctx['pyschometric_test_amount']=settings.STREAM_SORTER_TEST_AMOUNT
        ctx['psychometric_cross_test_amount']=2999
        ctx['user'] = request.user  # Add user to context for template
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Stream Sorter Psychometric Test', 'url': reverse('psychometrictests:psychometrictest')}])
        ctx['payment_update_url'] = reverse('psychometrictests:psychomerticttestpaymentupdate')
        
        # Check if user is authenticated before accessing user attributes
        if request.user.is_authenticated:
            sm=StudentManagement.objects.filter(student=request.user).exists()
            ctx['is_student']=sm
            if request.user.email in settings.DEMO_EMAIL:
                # Use API endpoint for payment creation (supports POST)
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=reverse('psychometrictests:deletedemopsychomerticttestpaymenteazypay')
            elif sm:
                # Use API endpoint for payment creation (supports POST)
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=False
            else:
                # Use API endpoint for payment creation
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=False
        else:
            ctx['is_student']=False
            # Use API endpoint for payment creation
            ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
            ctx['delete_demo_payment_url']=False
        ctx['is_authenticated'] = request.user.is_authenticated
        ctx['login_url'] = reverse('users:login')
        return ctx

    def get(self, request,*args, **kwargs):
        # Parent paying for a linked student
        for_student = request.GET.get("for_student")
        if for_student and request.user.is_authenticated:
            try:
                from users.parent_checkout import set_parent_checkout_student
                from core import choices as core_choices
                if getattr(request.user, "user_type", None) == core_choices.UserType.PARENT:
                    set_parent_checkout_student(request, int(for_student))
            except (TypeError, ValueError):
                pass
        # Redirect users who have already paid for Stream Sorter (BASIC) to their dashboard
        if request.user.is_authenticated:
            from users.parent_checkout import get_parent_checkout_student
            beneficiary = get_parent_checkout_student(request) or request.user
            has_paid = PsychometricTestPayment.objects.filter(
                user=beneficiary,
                test_type=choices.PsychometricTestType.BASIC,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if has_paid:
                return redirect(reverse('app:test_buttons'))
        return render(request, self.template_name, self.get_context(request,args, kwargs))



@method_decorator(never_cache, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class PsychometricTest12(TemplateView):
    template_name = "template20/psychometric_test_12.html"
    def html_head(self):
        name='Psychometric Test'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        from django.urls import reverse
        ctx={}
        ctx["test_type"]={"basic_test_type":choices.PsychometricTestType.BASIC,"advanced_test_type":choices.PsychometricTestType.ADVANCED}
        # Career Direction uses ADVANCED test type
        ctx["test_type_id"] = choices.PsychometricTestType.ADVANCED
        ctx["html_head"] = self.html_head()
        ctx["faq"]=PsychometricFAQ.objects.all().order_by("priority")
        # Use Career Direction test amount from settings
        ctx['pyschometric_test_amount']=settings.CAREER_DIRECTION_TEST_AMOUNT
        ctx['psychometric_cross_test_amount']=2999
        ctx['user'] = request.user  # Add user to context for template
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Career Direction Psychometric Test', 'url': reverse('psychometrictests:PsychometricTest12')}])
        ctx['payment_update_url'] = reverse('psychometrictests:psychomerticttestpaymentupdate')
        
        # Check if user is authenticated before accessing user attributes
        if request.user.is_authenticated:
            sm=StudentManagement.objects.filter(student=request.user).exists()
            ctx['is_student']=sm
            if request.user.email in settings.DEMO_EMAIL:
                # Use API endpoint for payment creation (supports POST)
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=reverse('psychometrictests:deletedemopsychomerticttestpaymenteazypay')
            elif sm:
                # Use API endpoint for payment creation (supports POST)
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=False
            else:
                # Use API endpoint for payment creation
                ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
                ctx['delete_demo_payment_url']=False
        else:
            ctx['is_student']=False
            # Use API endpoint for payment creation
            ctx["psychometric_test_payment_url"]=reverse('psychometrictests:createpsychomerticttestpayment')
            ctx['delete_demo_payment_url']=False
        ctx['is_authenticated'] = request.user.is_authenticated
        ctx['login_url'] = reverse('users:login')
        return ctx

    def get(self, request,*args, **kwargs):
        for_student = request.GET.get("for_student")
        if for_student and request.user.is_authenticated:
            try:
                from users.parent_checkout import set_parent_checkout_student
                from core import choices as core_choices
                if getattr(request.user, "user_type", None) == core_choices.UserType.PARENT:
                    set_parent_checkout_student(request, int(for_student))
            except (TypeError, ValueError):
                pass
        # Redirect users who have already paid for Career Direction (ADVANCED) to their dashboard
        if request.user.is_authenticated:
            from users.parent_checkout import get_parent_checkout_student
            beneficiary = get_parent_checkout_student(request) or request.user
            has_paid = PsychometricTestPayment.objects.filter(
                user=beneficiary,
                test_type=choices.PsychometricTestType.ADVANCED,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if has_paid:
                return redirect(reverse('post_matric:tests'))
        return render(request, self.template_name, self.get_context(request,args, kwargs))




class CreatePsychometricTestPayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            from users.parent_checkout import resolve_payment_users

            payer, user = resolve_payment_users(
                request,
                student_id=request.data.get("student_id") or request.POST.get("student_id"),
            )
            psychometric_test_type = request.data.get('test_type', False)

            if not user:
                return Response({"error": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

            if not psychometric_test_type:
                return Response({"error": "Test type is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Institute students are exempt from payment: allow direct access to test dashboard.
            try:
                if StudentManagement.objects.filter(student=user).exists():
                    # Keep a payment record for audit/consistency, but mark as success (free access).
                    try:
                        ptype_int = int(psychometric_test_type)
                    except (ValueError, TypeError):
                        ptype_int = None
                    if ptype_int == choices.PsychometricTestType.BASIC:
                        gateway_receipt = "Student_Psychometric_test_receipt_{}".format(user.id)
                        amount = settings.STREAM_SORTER_TEST_AMOUNT
                        test_type = choices.PsychometricTestType.BASIC
                    elif ptype_int == choices.PsychometricTestType.ADVANCED:
                        gateway_receipt = "Student_Psychometric_test_receipt_{}".format(user.id)
                        amount = settings.CAREER_DIRECTION_TEST_AMOUNT
                        test_type = choices.PsychometricTestType.ADVANCED
                    else:
                        # Default to BASIC for safety
                        gateway_receipt = "Student_Psychometric_test_receipt_{}".format(user.id)
                        amount = settings.STREAM_SORTER_TEST_AMOUNT
                        test_type = choices.PsychometricTestType.BASIC

                    test, _ = PsychometricTestPayment.objects.get_or_create(
                        user=user,
                        gateway_receipt=gateway_receipt,
                        test_type=test_type,
                        is_success=choices.YesNoChoices.NO,
                        amount=amount,
                        currency=choices.Currency.IND,
                    )
                    test.is_success = choices.YesNoChoices.YES
                    test.save()

                    return Response(
                        {
                            "free_access": True,
                            "test_type": test.test_type,
                            "redirect_url": request.build_absolute_uri(reverse("app:test_buttons")),
                        },
                        status=status.HTTP_200_OK,
                    )
            except Exception:
                # If exemption logic fails for any reason, fall back to normal payment flow
                pass

            try:
                psychometric_test_type = int(psychometric_test_type)
            except (ValueError, TypeError):
                return Response({"error": "Invalid test type"}, status=status.HTTP_400_BAD_REQUEST)
            
            if choices.PsychometricTestType.BASIC == psychometric_test_type:
                test_type=choices.PsychometricTestType.BASIC
                gateway_receipt="B_psy_test_receipt_{}".format(request.user.id)
                # Use Stream Sorter test amount from settings
                amount=settings.STREAM_SORTER_TEST_AMOUNT
            elif choices.PsychometricTestType.ADVANCED == psychometric_test_type:
                test_type=choices.PsychometricTestType.ADVANCED
                gateway_receipt="A_psy_test_receipt_{}".format(request.user.id)
                # Use Career Direction test amount from settings
                amount=settings.CAREER_DIRECTION_TEST_AMOUNT
            else:
                return Response({"error": "Invalid test type. Use 10 for BASIC or 20 for ADVANCED"}, status=status.HTTP_400_BAD_REQUEST)

            # Prevent duplicate payment: if user has already paid for this test type, redirect to dashboard
            existing_payment = PsychometricTestPayment.objects.filter(
                user=user,
                test_type=test_type,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if existing_payment:
                redirect_url = (
                    reverse("app:test_buttons")
                    if test_type == choices.PsychometricTestType.BASIC
                    else reverse("post_matric:tests")
                )
                return Response(
                    {
                        "already_paid": True,
                        "redirect_url": request.build_absolute_uri(redirect_url),
                    },
                    status=status.HTTP_200_OK,
                )
            
            test,_=PsychometricTestPayment.objects.get_or_create(user=user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
            
            # Get preferred gateway with fallback logic
            preferred_gateway = get_preferred_payment_gateway()
            
            # Log gateway selection
            gateway_name = 'RAZORPAY' if preferred_gateway == choices.GatewayChoices.RAZORPAY else 'ICICI EAZYPAY'
            print(f"[Payment Gateway] Preferred gateway from settings: {gateway_name} (value: {preferred_gateway})")
            print(f"[Payment Gateway] PAYMENT_GATEWAY_PREFERENCE setting: {settings.PAYMENT_GATEWAY_PREFERENCE}")
            
            payment,_=Payment.objects.get_or_create(
                user=payer,
                gateway_receipt=test.gateway_receipt,
                gateway=preferred_gateway,
                is_success=choices.YesNoChoices.NO,
                obj_id=test.id,
                obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,
                amount=test.amount,
                currency=test.currency
            )
            
            # If ICICI Eazypay is selected but not available, fallback to Razorpay
            if payment.gateway == choices.GatewayChoices.ICICIEAZYPAY and not is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY):
                print("[Payment Gateway] ICICI Eazypay not available, falling back to Razorpay")
                payment.gateway = choices.GatewayChoices.RAZORPAY
                payment.save()
            
            # Log final gateway selection
            final_gateway_name = 'RAZORPAY' if payment.gateway == choices.GatewayChoices.RAZORPAY else 'ICICI EAZYPAY'
            print(f"[Payment Gateway] Final selected gateway: {final_gateway_name} (value: {payment.gateway})")
            
            url=test.get_test_payment_success_fail_url()
            data={}
            data['test_id'] = test.id
            data['pay_id'] = payment.id
            
            # Return payment info based on gateway
            if payment.gateway == choices.GatewayChoices.RAZORPAY:
                try:
                    payment_info_str = payment.get_payment_info()
                    if payment_info_str:
                        data['payment_info'] = json.loads(payment_info_str)
                    else:
                        return Response({"error": "Failed to generate Razorpay payment info"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                except (json.JSONDecodeError, Exception) as e:
                    import traceback
                    print(traceback.format_exc())
                    return Response({"error": "Failed to process Razorpay payment: " + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # For ICICI Eazypay, return redirect URL
                try:
                    ezypy = IciciEazyPayService()
                    reference_no = str(payment.id)
                    sub_merchant_id = str(user.id)
                    transaction_amount = str(amount)
                    email = user.email
                    login_user_id = str(user.id)
                    mobile_no = user.mobile if user.mobile else "1111111111"
                    remarks = gateway_receipt
                    purchase_item = "Psychometric test"
                    eazypay_url = ezypy.get_encrypt_payment_url(
                        reference_no=reference_no,
                        sub_merchant_id=sub_merchant_id,
                        transaction_amount=transaction_amount,
                        email=email,
                        login_user_id=login_user_id,
                        mobile_no=mobile_no,
                        remarks=remarks,
                        purchase_item=purchase_item
                    )
                    if not eazypay_url:
                        return Response({"error": "Failed to generate ICICI Eazypay payment URL"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    data['payment_url'] = eazypay_url
                except Exception as e:
                    import traceback
                    print(traceback.format_exc())
                    return Response({"error": "Failed to process ICICI Eazypay payment: " + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            data['test_type'] = test.test_type
            data['gateway'] = payment.gateway
            data['success_url']=url.get("success_url")
            data['fail_url']=url.get("fail_url")
            return Response(data, status=status.HTTP_200_OK)   
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"error": "An unexpected error occurred: " + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreatePsychometricTestPaymentWithEazyPay(View):
    def get_payment_url(self,request,*args, **kwargs):
        user=request.user
        # Institute students are exempt from payment: redirect directly to test dashboard.
        try:
            if StudentManagement.objects.filter(student=user).exists():
                return reverse("app:test_buttons")
        except Exception:
            pass
        gateway_receipt="Psychometric_test_receipt_{}".format(user.id)
        amount=Configuration.get('EAZYPAY_PSYCHOMETRIC_TEST_AMOUNT',999,editable=True)
        test_type=choices.PsychometricTestType.BASIC
        test,_=PsychometricTestPayment.objects.get_or_create(user=user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
        
        # Get preferred gateway with fallback
        preferred_gateway = get_preferred_payment_gateway()
        payment,_=Payment.objects.get_or_create(
            user=user,
            gateway_receipt=test.gateway_receipt,
            gateway=preferred_gateway,
            is_success=choices.YesNoChoices.NO,
            obj_id=test.id,
            obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,
            amount=test.amount,
            currency=test.currency
        )
        
        # If ICICI Eazypay is not available, fallback to Razorpay
        if payment.gateway == choices.GatewayChoices.ICICIEAZYPAY and not is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY):
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save()
            # Redirect to Razorpay payment page
            from django.http import JsonResponse
            return JsonResponse({
                'payment_info': json.loads(payment.get_payment_info()),
                'gateway': 'razorpay'
            })
        
        # Use ICICI Eazypay
        ezypy=IciciEazyPayService()

        reference_no=str(payment.id)
        sub_merchant_id=str(user.id)
        transaction_amount=str(amount)
        email = user.email
        login_user_id=str(user.id)
        mobile_no = user.mobile if user.mobile else "1111111111"
        remarks=gateway_receipt
        purchase_item="Psychometric test"
        order_no_1="x"
        order_no="x"
        upivpa="x"
        a= ezypy.get_encrypt_payment_url(reference_no=reference_no,sub_merchant_id=sub_merchant_id,transaction_amount=transaction_amount,email=email,login_user_id=login_user_id,mobile_no=mobile_no,remarks=remarks,purchase_item=purchase_item,order_no_1=order_no_1,order_no=order_no,upivpa=upivpa)
        print("#"*30)
        print(a)
        print("#"*30)
        return a
    def get(self, request,*args, **kwargs):      
        return redirect(self.get_payment_url(request,args, kwargs))
    
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreateDemoPsychometricTestPaymentWithEazyPay(View):
    def create_demo_psychometric_test(self,request,*args, **kwargs):
        user=request.user
        sm=StudentManagement.objects.filter(student=user).exists()
        if (request.user.email in settings.DEMO_EMAIL) or sm:
            if sm:
                gateway_receipt="Student_Psychometric_test_receipt_{}".format(user.id)
            else:
                gateway_receipt="Demo_Psychometric_test_receipt_{}".format(user.id)
            amount=Configuration.get('EAZYPAY_PSYCHOMETRIC_TEST_AMOUNT',10,editable=True)
            test_type=choices.PsychometricTestType.BASIC
            test,_test=PsychometricTestPayment.objects.get_or_create(user=user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
            test.is_success=choices.YesNoChoices.YES
            test.save()
            # Send payment success email
            try:
                from .task import send_pychometric_test_payment_success_mail
                send_pychometric_test_payment_success_mail.delay(test.id)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                print("Error sending payment success email:", e)
            return test
        return None

    def get(self, request,*args, **kwargs):      
        test = self.create_demo_psychometric_test(request,args, kwargs)
        if test:
            # Redirect to payment success page
            sign = Signer()
            enc_id = sign.sign_object(({"enc_id": test.id}))
            return redirect(reverse('psychometrictests:pyschometrictestpaymentsuccess', kwargs={'enc_id': enc_id}))
        else:
            # If not demo/student, redirect to dashboard
            return redirect(reverse('users:userdashboard'))

class DeleteDemoPsychometricTestPaymentWithEazyPay(APIView):
    def post(self, request,*args, **kwargs):      
        data={}
        if request.user.email in settings.DEMO_EMAIL:
            # Delete demo psychometric test payments (central test no longer used)
            test_payments=PsychometricTestPayment.objects.filter(
                user=request.user,
                gateway_receipt__startswith="Demo_Psychometric_test_receipt_"
            )
            if test_payments.exists():
                test_payments.delete()
                data['message']="Deleted"
                data['success']=True
            else:
                data['message']="Not Exist" 
                data['success']=False
            return Response(data, status=status.HTTP_200_OK)

    
class UpdatePsychometricTestPaymentWithEazyPay(APIView):
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
        
        payment=get_object_or_404(Payment,id=referenceno,user__id=submerchantid)
        test=get_object_or_404(PsychometricTestPayment,id=payment.obj_id,user__id=submerchantid)
            
        payment_status=payment.update_eazypay_payment(response_code,unique_reference_no,service_tax_amount,processing_fee_amount,total_amount,transaction_amount,transaction_date,interchange_value,tdr,payment_mode,rs=rs,tps=tps,rsv=rsv)
        
        if payment_status==choices.YesNoChoices.YES:
            redirect_url=test.get_test_payment_success_fail_url().get("success_url")
            test.is_success=choices.YesNoChoices.YES
            test.save()
            # Send payment success email (central test no longer used)
            try:
                from .task import send_pychometric_test_payment_success_mail
                send_pychometric_test_payment_success_mail.delay(test.id)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                print("Error sending payment success email:", e)
        else:
            redirect_url=test.get_test_payment_success_fail_url().get("fail_url")
            
        return HttpResponseRedirect(redirect_url)
        

class UpdatePsychometricTestPayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            test_id = request.data.get('test_id',False)
            payment_id=request.data.get('payment_id',False)
            psychometric_test_type = request.data.get('test_type',False)
            try:
                psychometric_test_type = int(psychometric_test_type)
            except (TypeError, ValueError):
                pass
            gateway_order_id = request.data.get('gateway_order_id',False)
            gateway_payment_id = request.data.get('gateway_payment_id',False)
            gateway_signature = request.data.get('gateway_signature',False)
            if choices.PsychometricTestType.BASIC == psychometric_test_type:
                test_type=choices.PsychometricTestType.BASIC
                gateway_receipt="B_psy_test_receipt_{}".format(request.user.id)
            elif choices.PsychometricTestType.ADVANCED == psychometric_test_type:
                test_type=choices.PsychometricTestType.ADVANCED
                gateway_receipt="A_psy_test_receipt_{}".format(request.user.id)
            else:
                return Response({"success": False, "message": "Payment Failed."}, status=status.HTTP_400_BAD_REQUEST)
            
            test = PsychometricTestPayment.objects.filter(id=test_id,user=request.user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,currency=choices.Currency.IND).last()

            if test and gateway_payment_id and gateway_order_id and gateway_signature and payment_id:
                payment = Payment.objects.filter(id=payment_id,user=request.user,gateway_receipt=test.gateway_receipt,is_success=choices.YesNoChoices.NO,obj_id=test.id,obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,amount=test.amount,currency=test.currency).last()
                if payment:
                    print(f"[Payment Update] Updating payment ID: {payment.id} for test ID: {test.id}")
                    print(f"[Payment Update] Gateway Payment ID: {gateway_payment_id}")
                    print(f"[Payment Update] Gateway Order ID: {gateway_order_id}")
                    
                    payment_status=payment.update_payment(gateway_payment_id,gateway_order_id,gateway_signature)
                    try:
                        from invoices.utils import record_gateway_callback
                        from invoices.models import PaymentGatewayHealth
                        record_gateway_callback(
                            PaymentGatewayHealth.RAZORPAY,
                            success=bool(payment_status),
                            callback_url=request.build_absolute_uri(request.path) if request else None,
                        )
                    except Exception:
                        pass
                    print(f"[Payment Update] Payment verification status: {payment_status}")
                    print(f"[Payment Update] Payment is_success after update: {payment.is_success}")
                    
                    if payment_status:
                        test.is_success=choices.YesNoChoices.YES
                        test.save()
                        print(f"[Payment Update] Test payment ID {test.id} marked as SUCCESS")
                        print(f"[Payment Update] Test payment is_success: {test.is_success}")
                        
                        # Send payment success email (central test no longer used)
                        try:
                            from .task import send_pychometric_test_payment_success_mail
                            send_pychometric_test_payment_success_mail.delay(test.id)
                            print(f"[Payment Update] Payment success email queued for test ID: {test.id}")
                        except Exception as e:
                            import traceback
                            print(traceback.format_exc())
                            print("Error sending payment success email:", e)
                        
                        return Response(
                            {"success": True, "message": "Psychometric test payment successful."},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        print(f"[Payment Update] Payment verification FAILED for payment ID: {payment.id}")
                        return Response({"success": False, "message": "Payment Failed."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"success": False, "message": "Payment Failed."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"success": False, "message": "Payment Failed."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response({"success": False, "message": "Request rejected."}, status=status.HTTP_400_BAD_REQUEST)

class CreateCentralTestCandidate(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            test_id = request.data.get('test_id',False)
            psychometric_test_type = request.data.get('test_type',False)
            if choices.PsychometricTestType.BASIC == psychometric_test_type:
                test_type=choices.PsychometricTestType.BASIC
                gateway_receipt="B_psy_test_receipt_{}".format(request.user.id)
            elif choices.PsychometricTestType.ADVANCED == psychometric_test_type:
                test_type=choices.PsychometricTestType.ADVANCED
                gateway_receipt="A_psy_test_receipt_{}".format(request.user.id)
            else:
                return Response("Something went wrong.Please contact to support", status=status.HTTP_400_BAD_REQUEST) 
            
            test = PsychometricTestPayment.objects.filter(id=test_id,user=request.user,gateway_receipt=gateway_receipt,test_type=test_type).last()

            if test and test.is_success == choices.YesNoChoices.YES:
                test.create_central_test_candidate()                   
                return Response("Pyschometric test create successfully", status=status.HTTP_200_OK)
            else:
                return Response("Something went wrong.Please contact to support", status=status.HTTP_400_BAD_REQUEST)      
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserPyschometricTestPaymentSuccess(TemplateView):
    template_name ="topteenfrontend/psychometricpaymentsuccess.html"

    def html_head(self):
        name='Psychometric Test Payment Success'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        test_payment = get_object_or_404(PsychometricTestPayment, id=id)
        ctx['test_payment'] = test_payment
        # Payment record for order id, transaction id and invoice/receipt
        payment = Payment.objects.filter(
            user=request.user,
            obj_id=test_payment.id,
            obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,
            is_success=choices.YesNoChoices.YES,
        ).order_by('-created').first()
        ctx['payment'] = payment
        try:
            ctx['invoice_id'] = payment.invoice.id if payment else None
        except Exception:
            ctx['invoice_id'] = None
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['skilllab_courses']=SkillLabCourse.all_objects()
        ctx["test_type"]={"basic_test_type":choices.PsychometricTestType.BASIC,"advanced_test_type":choices.PsychometricTestType.ADVANCED}
        ctx["test_name"] = ctx['test_payment'].get_test_name()
        ctx["html_head"] = self.html_head()
        ctx["fetch_test_link"]=reverse('psychometrictests:fetchcandidatetestlink',kwargs={'enc_id':enc_id})
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserPyschometricTestPaymentFail(TemplateView):
    template_name ="topteenfrontend/psychometricpaymentfail.html"

    def html_head(self):
        name='Psychometric Test Payment Fail'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        test_payment = get_object_or_404(PsychometricTestPayment,id=id)
        ctx['test_payment'] = test_payment
        payment = Payment.objects.filter(
            user=request.user,
            obj_id=test_payment.id,
            obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,
        ).order_by('-created').first()
        ctx['payment'] = payment
        ctx['order_id'] = (
            (payment.gateway_order_id if payment else None)
            or (payment.gateway_receipt if payment else None)
            or 'N/A'
        )
        ctx["test_type"]={"basic_test_type":choices.PsychometricTestType.BASIC,"advanced_test_type":choices.PsychometricTestType.ADVANCED}
        ctx["test_name"] = test_payment.get_test_name()
        ctx["payment_api_url"] = reverse('psychometrictests:createpsychomerticttestpayment')
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class PyschometricTestResult(TemplateView):
    template_name ="template20/psychometric/pyschometrictestresult.html"

    def html_head(self):
        name='Psychometric Test Report'
        return build_html_head(title=name, description=name)

    def get_context(self,request,id,*args,**kwargs):
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['result']=get_object_or_404(PsychometricTestResult,id=id)
        key=ctx['result'].get_sort_form_riasec()
        ctx['careers']=Career.objects.filter(riasec_career__key=key).exclude(publish_status=choices.PublishStatus.DRAFT)
        ctx['lead_action']={"lead_psychometriccounsling":choices.LeadAction.PSYCHOMETRICTESTCOUNSLING}
        ctx['skilllab_courses']=SkillLabCourse.all_objects()
        ctx['colleges'] = College.get_all_colleges()
        ctx['countries']=country
        return ctx


    def get(self, request,id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,id,*args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ModernTestTemplatePreview(TemplateView):
    template_name = "template20/psychometric/test_modern_template.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        sample_questions = [
            {
                "id": 101,
                "title": "Visual matching puzzle",
                "description": "Choose the figure that completes the series by rotating the base cube mentally.",
                "category": "Spatial Visualization",
                "difficulty": "Medium",
                "estimated_time": "45 sec",
                "input_type": "radio",
                "option_layout": "two-column",
                "options": [
                    {"value": "A", "label": "Rotate shape A", "hint": "45° clockwise"},
                    {"value": "B", "label": "Rotate shape B", "hint": "Mirror along Y"},
                    {"value": "C", "label": "Shift depth", "hint": "Move to front"},
                    {"value": "D", "label": "Flip horizontal", "hint": "Mirror along X"},
                ],
            },
            {
                "id": 102,
                "title": "Choose the unfolded net",
                "description": "Which net forms the 3D object shown here?",
                "category": "Mental Rotation",
                "difficulty": "Easy",
                "estimated_time": "35 sec",
                "input_type": "radio",
                "option_layout": "two-column",
                "image": "images_new/icons/info-tree.svg",
                "options": [
                    {"value": "A", "label": "Net A", "hint": "Opposite faces match"},
                    {"value": "B", "label": "Net B", "hint": "Adjacent faces differ"},
                    {"value": "C", "label": "Net C", "hint": "Symmetry mismatch"},
                    {"value": "D", "label": "Net D", "hint": "Edge sequence correct"},
                ],
            },
            {
                "id": 103,
                "title": "Logical sequencing",
                "description": "Arrange the segments so that arrows align and form a continuous path.",
                "category": "Critical Reasoning",
                "difficulty": "Medium",
                "estimated_time": "50 sec",
                "input_type": "radio",
                "option_layout": "two-column",
                "options": [
                    {"value": "A", "label": "Segment order 1-3-2-4"},
                    {"value": "B", "label": "Segment order 2-4-1-3"},
                    {"value": "C", "label": "Segment order 3-1-4-2"},
                    {"value": "D", "label": "Segment order 4-2-3-1"},
                ],
            },
        ]

        ctx["questions"] = sample_questions
        ctx["total_questions"] = len(sample_questions)
        ctx["time_limit_seconds"] = 20 * 60
        ctx["submit_url"] = "#"
        ctx["test_meta"] = {
            "pill": "Preview Mode",
            "title": "Stream Sorter • Modern Test Template",
            "subtitle": "Experience the refreshed interface with all existing capabilities intact.",
            "class_label": "Class 10",
            "estimated_time": "20 min",
            "attempts_allowed": "01",
        }
        return ctx

class UpdateCentralTest(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            candidate_id=request.data.get("candidate_id")
            assessment_id=request.data.get("assessment_id")
            test=CandidateTest.objects.filter(assessment_id=assessment_id,central_test_candidate__candidate_id=candidate_id).last()
            test.is_success=choices.YesNoChoices.YES
            test.save()
            create_pyschometric_assessment_result.delay(test.id)
            return Response("Psychometric test update successfully", status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  
    
class FetchCandidateTestLink(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def get(self,request,enc_id,*args,**kwargs):
        try:
            data={}
            data["success"]=False
            sign=Signer()
            signobj=sign.unsign_object(enc_id)
            id=signobj.get('enc_id')
            text_payment=get_object_or_404(PsychometricTestPayment,id=id)

            # Ensure user PDF folder exists before starting test (e.g. class 10 psychometric)
            ensure_user_pdf_folder(request.user.id)

            candidate_test=text_payment.candidate_test.last()
            if candidate_test:
                data["testlink"]=candidate_test.test_link
                data["success"]=True
            return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 