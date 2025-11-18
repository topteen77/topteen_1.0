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
from .task import send_skillabcourse_payment_success_mail
from rest_framework.views import APIView
from django.conf import settings
# Create your views here.

class SkillLabCourseList(TemplateView):
    template_name = "template20/skilllab_course_list.html"
    def html_head(self):
        name='Skill Lab Courses'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        from django.urls import reverse
        ctx={}
        skl=SkillLabCourseDocumentFilter()
        ctx=skl.get_skilllab_list_context(request)
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb'] = {'text': 'Skill Lab Courses', 'url': reverse('skilllabcourse:skilllabcourselist')}
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
        skillab=SkillLabCourse.objects.get(slug=skil_slug)
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
        skillab_course_chapter=SkillLabCourseChapter.objects.get(slug=chapter_slug)
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
        sklibactive=SkillLabCourseActivity.objects.get(slug=workactive_slug)
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
        gateway_receipt="Skilllab_course_receipt_user_id_{}_skillab_course_id_{}".format(request.user.id,skillab_course.id)
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
            # For Razorpay, redirect to payment page with payment info
            from django.http import JsonResponse
            import json
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
        purchase_item="Skilllab Course {}".format(skillab_course.name)
        order_no_1="x"
        order_no="x"
        upivpa="x"
        return ezypy.get_encrypt_payment_url(reference_no=reference_no,sub_merchant_id=sub_merchant_id,transaction_amount=transaction_amount,email=email,login_user_id=login_user_id,mobile_no=mobile_no,remarks=remarks,purchase_item=purchase_item,order_no_1=order_no_1,order_no=order_no,upivpa=upivpa)

    def get(self, request,slug,*args, **kwargs):      
        return redirect(self.get_payment_url(request,slug,args, kwargs))
    
class UpdateSkilllabCoursePaymentWithEazyPay(APIView):
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