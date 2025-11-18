from asyncio import streams
from urllib import request
from django.shortcuts import render
from django.http import JsonResponse
from colleges.document_filters import CollegeDocumentFilter
from .models import College,CollegeShortlist
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from courses.models import Course
from courses.models import Stream
from core.models import Country
from entrance_exams.models import EntranceExam
from django.shortcuts import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from core.utils import build_breadcrumb,build_html_head
from html import unescape
# Create your views here.


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

class CollegeDetails(TemplateView):
    template_name = "template20/college_detail.html"
    
    def __html_head(self,college):
        name=college.name
        return build_html_head(title=name, description=name)

    def get_context(self, request,slug, *args, **kwargs):
        ctx={}
        college=get_object_or_404(College,slug=slug)
        ctx['college']=college
        bread_crumb =self._breadcrumb(ctx["college"])
        country=Country.objects.all()
        ctx['countries']=country
        courses=Course.objects.filter(college=college)
        ctx['colleges'] = College.get_all_colleges()
        ctx['courses']=courses
        streams=[]
        for course in courses:
            stream=course.stream
            if stream not in streams and stream is not None:
                streams.append(stream)
        ctx['streams']=streams
        ctx['breadcrumb']= bread_crumb[1]
        ctx['html_head'] = self.__html_head(ctx["college"])
        ctx['unescape']=unescape
        try:
            ctx['shortlisted_college']=CollegeShortlist.objects.filter(user=request.user,college__slug=ctx['college'].slug)
        except:
            ctx['shortlisted_college']=None
        return ctx

    def _breadcrumb(self,college):
        from django.urls import reverse
        url=reverse('colleges:college')
        lst=[{'title':'Colleges','text':'Colleges','url':url},{'title':college.name,'text':college.name,'url':''}]
        return build_breadcrumb(lst)

    def get(self, request,slug, *args, **kwargs):
        if is_ajax(request=request):
            clgd=CollegeDocumentFilter()
            ctx=clgd.college_detail(request,slug,is_ajax=True)
            html=render_to_string("topteenfrontend/includes/explore_college.html",ctx)
            return HttpResponse(html) 
        return render(request, self.template_name, self.get_context(request,slug,args, kwargs))

def explore_college(self,request):
    ctx={}
    country=Country.objects.all()
    ctx['colleges'] = College.get_all_colleges()
    ctx['countries']=country
    return ctx

class CollegeList(TemplateView):
    template_name = "template20/college_list.html"

    def __html_head(self):
        name="Colleges"
        return build_html_head(title=name, description=name)

    def get_context(self, request,state, *args, **kwargs):
        from django.urls import reverse
        clg=CollegeDocumentFilter()
        ctx=clg.get_college_list_context(request,state)
        ctx['html_head'] = self.__html_head()
        counrty=request.GET.getlist('country')
        state_list=request.GET.getlist('state')
        city=request.GET.getlist('city')
        counrty_list=["country={}".format(c) for c in counrty]
        state_list_str=["state={}".format(s) for s in state_list]
        city_list=["city={}".format(ci) for ci in city]
        query_list_all=counrty_list+state_list_str+city_list
        queries="&".join(query_list_all)
        ctx['query_list']=state_list+city
        ctx['get_updated_url']=queries
        ctx['breadcrumb'] = {'text': 'Colleges', 'url': reverse('colleges:college')}
        return ctx

    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))

def shortlist_college_view(request):
    id=request.GET.get("id")
    college=get_object_or_404(College,id=id)
    data=College.objects.filter(id=id,shortlist=request.user).exists()
    if data:
        college.shortlist.remove(request.user)
        return JsonResponse({'success':'false'})
    else:
        college.shortlist.add(request.user)
        return JsonResponse({'success':'true'})