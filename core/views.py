import json
import re
import os
from multiprocessing import get_context
from .utils import build_breadcrumb,build_html_head
from django.db.models import Q
from xml.etree.ElementInclude import include
from django.shortcuts import render
from django.urls import reverse
from django.shortcuts import redirect
from blog.models import Blog
from careers.models import Career, CareerTags,Videos,CareerCluster
from core import choices
from django.views.generic import TemplateView
from core.models import CommonFAQ, Country, Review,Contact,Lead
from courses.models import Course
from colleges.models import College
from django.conf import settings
from .forms import ImageUploadModelForm
from django.core.paginator import Paginator
from django.http import HttpResponse,JsonResponse
from django.template.loader import render_to_string
from careers.document_filters import CareerDocumentFilter
from colleges.document_filters import CollegeDocumentFilter
from entrance_exams.document_filters import EntranceExamDocumentFilter
from courses.documents import CourseDocument
from careers.models import Videos,Career
from colleges.models import College
from .documents_filter import AllSearch
from entrance_exams.models import EntranceExam
from users.models import UserSearchHistory
from django.shortcuts import HttpResponse,HttpResponseRedirect
from skilllab.models import SkillLabCourse
from django.contrib import messages
from rest_framework.views import APIView
from django.http import JsonResponse

class Home(TemplateView):
    template_name ="template20/home_new.html"
    
    def html_head(self):
        name='Every Student, Career Ready'
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        tags=CareerTags.objects.all().order_by('priority')[:5]
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['careers'] = Career.get_all_careers()
        try:
            print(f"[HOME] Published careers count: {ctx['careers'].count()}")
        except Exception:
            pass
        ctx['videos'] = Videos.objects.all().order_by('?')
        ctx['careers_video']=Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).exclude(Q(video_url=""))
        ctx['courses'] = Course.get_all_courses()
        ctx['reviewers'] = Review.get_all_reviews()
        ctx['tags']=tags
        ctx['countries']=country
        ctx['body_css_class']='no-scrollbar overflow-x-hidden'
        ctx['comman_faq']=CommonFAQ.get_commonfaq_by_priority()
        ctx['parent_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.parent, is_featured=choices.FAQFeaturedType.HOME)[:10]
        ctx['student_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.student,is_featured=choices.FAQFeaturedType.HOME)[:10]
        ctx["html_head"] = self.html_head()
        ctx['skilllab_courses']=SkillLabCourse.all_objects()
        ctx['exams']=EntranceExam.objects.all().order_by('?')[:3]
        ctx['clusters']=CareerCluster.objects.filter(parent__isnull=True)
        return ctx
        
    def get(self, request,*args, **kwargs):
        print(f"[DEBUG] Rendering template: {self.template_name}")
        print(f"[DEBUG] Template file exists: {os.path.exists(os.path.join(settings.BASE_DIR, 'templates', self.template_name))}")
        return render(request, self.template_name,self.get_context(request,args, kwargs))


def privacy_policy(request):
    template_name='template20/privacy_policy.html'
    name="Privacy Policy"
    ctx={}
    ctx["html_head"]=build_html_head(title=name, description=name)
    from django.urls import reverse
    ctx['breadcrumb'] = {'text': 'Privacy Policy', 'url': reverse('core:privacypolicy')}
    return render(request,template_name,ctx)

def terms_and_condition(request):
    template_name='template20/terms_and_condition.html'
    name="Terms and Condition"
    ctx={}
    ctx["html_head"]=build_html_head(title=name, description=name)
    from django.urls import reverse
    ctx['breadcrumb'] = {'text': 'Terms and Condition', 'url': reverse('core:terms&condition')}
    return render(request,template_name,ctx)

def validation(request,mobile,email):
    mvalid = r'^\d{3}\d{3}\d{4}$'
    evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    phone=re.match(mvalid,mobile)
    em=re.match(evalid,email)
    if phone or em:
        if phone is None:
            messages.error(request,"Invalid phone number !!")
            return False
        if em is None:
            messages.error(request,"Invalid email !!")
            return False
        else:
            return True
    else:
        messages.error(request,"Invalid phone number and email !!")

def contact_us(request):
    template_name='template20/contact_us.html'
    name="Contact Us"
    from django.urls import reverse
    from django.middleware.csrf import get_token
    ctx={}
    ctx['breadcrumb'] = {'text': 'Contact Us', 'url': reverse('core:contactus')}
    ctx['csrf_token'] = get_token(request)
    if request.method=="POST":
        first_name=request.POST.get("first_name")
        last_name=request.POST.get("last_name")
        full_name="{} {}".format(first_name,last_name)
        mobile=request.POST.get("mobile")
        email=request.POST.get("email")
        message=request.POST.get("message")
        if full_name and message and validation(request,mobile,email):
            form=Contact(name=full_name,mobile=mobile,email=email,message=message)
            form.save()
            messages.success(request,"Thank you, Your response has been submitted!")
        else:
            messages.error(request,"")
    ctx["html_head"]=build_html_head(title=name, description=name)
    return render(request,template_name,ctx)

def upload(request):
    if request.method == "POST":
        form = ImageUploadModelForm(request.POST, request.FILES)
        if form.is_valid():
            obj=form.save()
            print(obj)
            # return HttpResponse(obj.upload.url)
            return HttpResponse(json.dumps({'success':True,'url':obj.upload.url}), content_type='application/json')
        print(form.errors)
    return HttpResponse('')


class AboutUsView(TemplateView):
    template_name ="template20/about_us.html"

    def html_head(self):
        name='About Us'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'About Us', 'url': reverse('core:aboutus')}
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

class AllFaqView(TemplateView):
    template_name ="template20/all_faq.html"
    
    def html_head(self):
        name='FAQ'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'FAQs', 'url': reverse('core:allfaq')}
        search_faq = request.GET.get('search')
        if search_faq:
            ctx['search_faq']=search_faq
            ctx['heading']=f"Results for '{search_faq}'"
            faq_question=CommonFAQ.get_commonfaq_by_priority().filter( Q(question__icontains=search_faq)).order_by('-modified') 
            ctx['faq_question']=faq_question
        else:
            ctx['search_faq']=""
            ctx['parent_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.parent)
            ctx['student_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.student)
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

class SearchItems(TemplateView):
    template_name="topteenfrontend/searchandexplore.html"
    def html_head(self):
        name='EXPLORE CAREER'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        careeritems=CareerDocumentFilter()
        examitems=EntranceExamDocumentFilter()
        total=careeritems.get_career_list_context(request)
        ctx['car']=careeritems.get_career_list_context(request)
        ctx['videoscount']=Videos.objects.all().count()
        ctx['col']=College.get_all_colleges().count()
        ctx['exm']=examitems.get_entrance_exam_list_context(request)
        ctx['coursecount']=Course.objects.all().count()
        ctx['most_searchcareers'] = Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).order_by('?')[:8]
        ctx['most_searchcolleges'] = College.objects.all().order_by('id')[:5]
        ctx['tranding_content']=Blog.objects.all()
        ctx["html_head"] = self.html_head()
        
        return ctx
    
    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))
    
class AjaxSearchResult(TemplateView):
    template_name="topteenfrontend/mainsearchresult.html"
    def html_head(self,request):
        name=request.GET.get('search')
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        ctx={} 
        input=request.GET.get('search')

        clf=AllSearch()
        ctx['allsearch']=clf.get_ajax_search_Item_list(request,input)
        ctx["html_head"] = self.html_head(request)
        ctx['searchname']=input
        
        ctx['user'] = request.user

        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

class AjaxRecommandedSearchCollege(TemplateView):
    template_name ="topteenfrontend/includes/recommendedsearch.html"

    def get_context(self,request,*args, **kwargs):
        ctx={} 
        clf=AllSearch()
        ctx['colleges']=clf.get_ajax_search_Item_list(request)
        ctx['user'] = request.user
        return ctx

    def get(self, request,*args, **kwargs):
        html = render_to_string(self.template_name,self.get_context(request, *args, **kwargs))
        return HttpResponse(html)
    
class LeadData(APIView):
    def post(self,request,*args,**kwargs):
        name=request.POST.get("lead_name")
        mobile=request.POST.get("lead_mobile")
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        phone=re.match(mvalid,mobile)
        lead_exist=Lead.objects.filter(mobile=mobile).exists()
        if name and phone and not lead_exist:
            lead_data=Lead(name=name,mobile=mobile)
            lead_data.save()
            response={"success":"true","message":"Thank you for connecting with us!"}
        else:
            if lead_exist:
                response={"success":"false","message":"Your phone number already exist!"}
            else:
                response={"success":"false","message":"Please Enter the Correct Phone number!"}
        return JsonResponse(response)

def deletehistory(request):
    clr=UserSearchHistory.objects.filter(user=request.user)
    clr.delete() 
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


def page404(request,exception):
    ctx={}
    ctx["html_head"] = build_html_head(title="404 | Error")
    return render(request,"topteenfrontend/404page.html",ctx)
