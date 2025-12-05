from django.shortcuts import render
from .models import SkillLabCourse,SkillLabCourseActivity,SkillLabCourseChapter
from django.views.generic import TemplateView,View
from django.urls import reverse_lazy
from core.utils import build_breadcrumb,build_html_head,get_preferred_payment_gateway,is_gateway_available
from .document_filters import SkillLabCourseDocumentFilter
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.signing import Signer
from django.shortcuts import get_object_or_404
from .models import SkilllabCoursePayment
from django.http import Http404
import re
from payments.payment.icicieazypay import IciciEazyPayService
from payments.models import Payment
from core import choices
from django.shortcuts import redirect,HttpResponseRedirect
from django.urls import reverse
from .task import send_skillabcourse_payment_success_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
# Create your views here.

class SkillLabCourseList(TemplateView):
    template_name = "template20/skilllab_course_list.html"
    def html_head(self):
        name='Skill Lab Courses'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        from django.urls import reverse
        from django.core.paginator import Paginator
        
        try:
            skl=SkillLabCourseDocumentFilter()
            ctx=skl.get_skilllab_list_context(request)
        except (KeyError, Exception) as e:
            # Fallback to Django ORM when Elasticsearch is not available
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
            ctx = self.get_fallback_context(request)
        
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb'] = {'text': 'Skill Lab Courses', 'url': reverse('skilllabcourse:skilllabcourselist')}
        return ctx
    
    def get_fallback_context(self, request):
        """Fallback method using Django ORM when Elasticsearch is unavailable"""
        from django.core.paginator import Paginator
        
        ctx = {}
        
        # Get all skilllab courses ordered by modified date (newest first)
        courses = SkillLabCourse.objects.all().order_by('-modified')
        
        # Pagination
        paginator = Paginator(courses, 9)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['skilllab'] = page_obj
        
        return ctx
    
    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))
             
class SkillLabCourseDetail(TemplateView):
    template_name = "template20/skilllab_course_detail.html"
    def html_head(self,skilllab):
        clean=re.compile('<.*?>')
        t= skilllab.name 
        des = skilllab.description
        d=re.sub(clean,'',des)
        return build_html_head(title=t, description=d)
    
    def get_context(self,request,skil_slug,*args,**kwargs):
        ctx={}
        skillab=get_object_or_404(SkillLabCourse, slug=skil_slug)
        ctx['skilllab']=skillab
        ctx['activecourses']=SkillLabCourse.objects.filter(category=skillab.category).exclude(id=skillab.id)
        bread_crumb =self._breadcrumb(skillab)
        ctx['breadcrumb']= bread_crumb[1]
        ctx["html_head"] = self.html_head(skillab)
        
        return ctx
    
    def _breadcrumb(self,skilllab):
        from django.urls import reverse
        url=reverse('skilllabcourse:skilllabcourselist')
        lst=[{'title':'Skill Lab Courses','text':'Skill Lab Courses','url':url},{'title':skilllab.name,'text':skilllab.name,'url':''}]
        return build_breadcrumb(lst)
    
    def get(self, request,skilllab_slug, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request,skilllab_slug,*args, **kwargs))

class SkillLabCourseChapterDetail(TemplateView):
    template_name = "topteenfrontend/skillabcoursechapter.html"

    def html_head(self,skilllab):
        t= skilllab.chapter_name 
        d = skilllab.content

        return build_html_head(title=t, description=d)
    
    def get_context(self,request,chapter_slug,*args,**kwargs):
        ctx={}
        skillab_course_chapter=get_object_or_404(SkillLabCourseChapter, slug=chapter_slug)
        ctx['skilllab_course_chapter']=skillab_course_chapter
        ctx['breadcrumb']=self._breadcrumb(skillab_course_chapter)
        ctx["html_head"] = self.html_head(skillab_course_chapter)
        
        return ctx
    
    def _breadcrumb(self,skilllab_course_chapter):
        lst=[
            {'title':"SkilllabCourse",'text':"SkilllabCourse","url":reverse_lazy('skilllab:skilllabcourselist')},
            {'title':'{}'.format(skilllab_course_chapter.skilllab.name),'text':'{}'.format("skilllabcourse"),'url':reverse_lazy('skilllab:skilllabcoursedetail',args=[skilllab_course_chapter.skilllab.slug])},
            {'title':skilllab_course_chapter.chapter_name,"text":skilllab_course_chapter.chapter_name,"url":""},
            ]
        return build_breadcrumb(lst)
    
    def get(self, request,chapter_slug, *args, **kwargs):
        ctx=self.get_context(request,chapter_slug,*args, **kwargs)
        course_payment_status=ctx['skilllab_course_chapter'].skilllab.is_user_vissible(request)
        if not course_payment_status:
            raise Http404
        return render(request, self.template_name, ctx)

class SkillLabCourseActivityDetail(TemplateView):
    template_name="topteenfrontend/skilllabactivityworksheet.html"

    def _breadcrumb(self,skilllab_activity):
        lst=[
            {'title':"SkilllabCourse",'text':"SkilllabCourse","url":reverse_lazy('skilllab:skilllabcourselist')},
            {'title':'{}'.format(skilllab_activity.skilllab_chapter.skilllab.name),'text':'{}'.format(skilllab_activity.skilllab_chapter.skilllab.name),'url':reverse_lazy('skilllab:skilllabcoursedetail',args=[skilllab_activity.skilllab_chapter.skilllab.slug])},
            {'title':'{}'.format(skilllab_activity.skilllab_chapter.chapter_name),'text':'{}'.format(skilllab_activity.skilllab_chapter.chapter_name),'url':reverse_lazy('skilllab:skilllabcoursechapterdetail',args=[skilllab_activity.skilllab_chapter.slug])},
            {'title':skilllab_activity.name,"text":skilllab_activity.name,"url":""},
            ]
        return build_breadcrumb(lst)

    def html_head(self,skillactive):
        t= skillactive.name 
        return build_html_head(title=t, description=t)

    def get_context(self,request,workactive_slug,*args,**kwargs):
        ctx={}
        sklibactive=get_object_or_404(SkillLabCourseActivity, slug=workactive_slug)
        ctx['activityworksheet']=sklibactive
        ctx["html_head"] = self.html_head(sklibactive)
        ctx['breadcrumb'] =self._breadcrumb(sklibactive)
        return ctx

    def get(self, request,workactive_slug, *args, **kwargs):
        ctx=self.get_context(request,workactive_slug,*args, **kwargs)
        course_payment_status=ctx['activityworksheet'].skilllab_chapter.skilllab.is_user_vissible(request)
        if not course_payment_status:
            raise Http404
        return render(request, self.template_name,ctx)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SkilllabCoursePaymentSuccess(TemplateView):
    template_name ="topteenfrontend/skilllabcoursepaymentsuccess.html"

    def html_head(self):
        name='Skilllab Course Payment Success'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        ctx['skilllab_payment']=get_object_or_404(SkilllabCoursePayment,id=id)
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SkilllabCoursePaymentFail(TemplateView):
    template_name ="topteenfrontend/skilllabcoursepaymentfail.html"

    def html_head(self):
        name='Skilllab Course Payment Fail'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        ctx['skilllab_payment']=get_object_or_404(SkilllabCoursePayment,id=id)
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreateSkilllabCoursePaymentWithEazyPay(View):
    def get_payment_url(self,request,slug,*args, **kwargs):
        skillab_course=get_object_or_404(SkillLabCourse,slug=slug)
        user=request.user
        # Create a shorter receipt format (Razorpay requires max 40 characters)
        # Format: SL{user_id}_{course_id} (e.g., "SL123_456")
        gateway_receipt="SL{}_{}".format(request.user.id, skillab_course.id)
        amount=skillab_course.amount
        sp,_=SkilllabCoursePayment.objects.get_or_create(user=user,skilllab_course=skillab_course,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
        
        # Get preferred gateway with fallback
        preferred_gateway = get_preferred_payment_gateway()
        payment,_=Payment.objects.get_or_create(
            user=user,
            gateway_receipt=sp.gateway_receipt,
            gateway=preferred_gateway,
            is_success=choices.YesNoChoices.NO,
            obj_id=sp.id,
            obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
            amount=sp.amount,
            currency=sp.currency
        )
        
        # If ICICI Eazypay is not available, fallback to Razorpay
        if payment.gateway == choices.GatewayChoices.ICICIEAZYPAY and not is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY):
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save()
        
        # If gateway is Razorpay, return payment info
        if payment.gateway == choices.GatewayChoices.RAZORPAY:
            # For Razorpay, return payment info (will be handled in get method)
            from django.http import JsonResponse
            import json
            try:
                payment_info_str = payment.get_payment_info()
                # get_payment_info() returns JSON string, parse it to dict
                payment_info_dict = json.loads(payment_info_str) if isinstance(payment_info_str, str) else payment_info_str
                return {
                    'type': 'json',
                    'data': {
                        'payment_info': payment_info_dict,
                        'gateway': 'razorpay'
                    }
                }
            except Exception as e:
                import traceback
                print(f"[Payment Error] Failed to get payment info: {str(e)}")
                print(traceback.format_exc())
                # Fallback: return error message
                from django.http import HttpResponse
                return HttpResponse(f"Error preparing payment: {str(e)}", status=500)
        
        # Use ICICI Eazypay - wrap in try-except to handle encryption errors
        try:
            ezypy=IciciEazyPayService()
            reference_no=str(payment.id)
            sub_merchant_id=str(user.id)
            transaction_amount=str(amount)
            email = user.email
            login_user_id=str(user.id)
            mobile_no = user.mobile if user.mobile else "1111111111"
            remarks=gateway_receipt
            purchase_item="Skilllab Course {}".format(skillab_course.name)
            order_no_1="x"
            order_no="x"
            upivpa="x"
            payment_url = ezypy.get_encrypt_payment_url(reference_no=reference_no,sub_merchant_id=sub_merchant_id,transaction_amount=transaction_amount,email=email,login_user_id=login_user_id,mobile_no=mobile_no,remarks=remarks,purchase_item=purchase_item,order_no_1=order_no_1,order_no=order_no,upivpa=upivpa)
            return {
                'type': 'redirect',
                'url': payment_url
            }
        except (ValueError, AttributeError, Exception) as e:
            # If ICICI Eazypay fails (e.g., missing/empty encryption key), fallback to Razorpay
            import traceback
            print(f"[Payment] ICICI Eazypay failed: {str(e)}")
            print(traceback.format_exc())
            
            # Update payment gateway to Razorpay
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save()
            
            # Return Razorpay payment info
            from django.http import JsonResponse
            import json
            try:
                payment_info_str = payment.get_payment_info()
                # get_payment_info() returns JSON string, parse it to dict
                payment_info_dict = json.loads(payment_info_str) if isinstance(payment_info_str, str) else payment_info_str
                return {
                    'type': 'json',
                    'data': {
                        'payment_info': payment_info_dict,
                        'gateway': 'razorpay'
                    }
                }
            except Exception as e2:
                import traceback
                print(f"[Payment Error] Failed to get Razorpay payment info: {str(e2)}")
                print(traceback.format_exc())
                # Fallback: return error message
                from django.http import HttpResponse
                return HttpResponse(f"Error preparing Razorpay payment: {str(e2)}", status=500)

    def get(self, request,slug,*args, **kwargs):
        from django.http import JsonResponse
        skillab_course=get_object_or_404(SkillLabCourse,slug=slug)
        result = self.get_payment_url(request,slug,*args, **kwargs)
        
        # Get success/fail URLs
        user=request.user
        gateway_receipt="SL{}_{}".format(request.user.id, skillab_course.id)
        sp,_=SkilllabCoursePayment.objects.get_or_create(user=user,skilllab_course=skillab_course,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,amount=skillab_course.amount,currency=choices.Currency.IND)
        url_info = sp.get_payment_success_fail_url()
        
        # Handle different return types
        if isinstance(result, dict):
            if result.get('type') == 'json':
                # Render payment template with Razorpay data
                try:
                    payment_info = result.get('data', {}).get('payment_info', {})
                    if isinstance(payment_info, str):
                        import json
                        payment_info = json.loads(payment_info)
                    
                    if not payment_info:
                        raise ValueError("Payment info is empty")
                    
                    # Convert payment_info dict to JSON string for template
                    import json
                    payment_info_json = json.dumps(payment_info)
                    
                    ctx = {
                        'skilllab': skillab_course,
                        'payment_info_json': payment_info_json,
                        'payment_info': payment_info,  # Keep dict version too
                        'gateway': result.get('data', {}).get('gateway', 'razorpay'),
                        'success_url': url_info['success_url'],
                        'fail_url': url_info['fail_url'],
                        'payment_id': sp.id,
                    }
                    return render(request, 'template20/skilllab/payment.html', ctx)
                except Exception as e:
                    import traceback
                    print(f"[Template Render Error] {str(e)}")
                    print(traceback.format_exc())
                    from django.http import HttpResponse
                    return HttpResponse(f"Error rendering payment page: {str(e)}", status=500)
            elif result.get('type') == 'redirect':
                return redirect(result['url'])
        
        # Fallback: assume it's a URL string (for backward compatibility)
        if isinstance(result, str):
            return redirect(result)
        
        # If we get here, something went wrong
        from django.http import HttpResponse
        return HttpResponse("Unable to process payment. Please try again.", status=500)
    
class UpdateSkilllabCoursePaymentWithEazyPay(APIView):
    def post(self, request,*args, **kwargs):
        # Check if this is a Razorpay payment (has gateway_order_id, gateway_payment_id, gateway_signature)
        gateway_order_id = request.data.get('gateway_order_id')
        gateway_payment_id = request.data.get('gateway_payment_id')
        gateway_signature = request.data.get('gateway_signature')
        payment_id = request.data.get('payment_id')
        
        if gateway_order_id and gateway_payment_id and gateway_signature and payment_id:
            # Razorpay payment update
            try:
                sp = get_object_or_404(SkilllabCoursePayment, id=payment_id, user=request.user)
                payment = get_object_or_404(Payment, obj_id=sp.id, obj_type=choices.PaymentObjectType.SKILLLABCOURSE, user=request.user)
                
                # Update payment with Razorpay details
                # update_payment signature: (gateway_payment_id, gateway_order_id, gateway_signature)
                payment_status = payment.update_payment(gateway_payment_id, gateway_order_id, gateway_signature)
                
                if payment_status:
                    redirect_url = sp.get_payment_success_fail_url().get("success_url")
                    sp.is_success = choices.YesNoChoices.YES
                    sp.save()
                    send_skillabcourse_payment_success_mail.delay(sp.id)
                    return Response({'success': True, 'redirect_url': redirect_url}, status=status.HTTP_200_OK)
                else:
                    redirect_url = sp.get_payment_success_fail_url().get("fail_url")
                    return Response({'success': False, 'redirect_url': redirect_url}, status=status.HTTP_200_OK)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                print(f"[Payment Update Error] {str(e)}")
                # Try to get fail URL
                try:
                    sp = get_object_or_404(SkilllabCoursePayment, id=payment_id, user=request.user)
                    redirect_url = sp.get_payment_success_fail_url().get("fail_url")
                except:
                    redirect_url = reverse('skilllab:skilllabcourselist')
                return HttpResponseRedirect(redirect_url)
        
        # ICICI Eazypay payment update (original logic)
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
        sp=get_object_or_404(SkilllabCoursePayment,id=payment.obj_id,user__id=submerchantid)
            
        payment_status=payment.update_eazypay_payment(response_code,unique_reference_no,service_tax_amount,processing_fee_amount,total_amount,transaction_amount,transaction_date,interchange_value,tdr,payment_mode,rs=rs,tps=tps,rsv=rsv)
        
        if payment_status==choices.YesNoChoices.YES:
            redirect_url=sp.get_payment_success_fail_url().get("success_url")
            sp.is_success=choices.YesNoChoices.YES
            sp.save()
            send_skillabcourse_payment_success_mail.delay(sp.id)
        else:
            redirect_url=sp.get_payment_success_fail_url().get("fail_url")
            
        return HttpResponseRedirect(redirect_url)