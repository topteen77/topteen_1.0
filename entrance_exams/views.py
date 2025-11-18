from unicodedata import name
from core.utils import build_breadcrumb,build_html_head
import random
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views.generic import TemplateView
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import EntranceExam
from .document_filters import EntranceExamDocumentFilter
from courses.models import Stream
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from core import choices
# Create your views here.

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class TestPrepDetail(TemplateView):
    template_name = "template20/testprep_detail.html"   
    def html_head(self,exam):
        t= exam.name 
        d = exam.about

        return build_html_head(title=t, description=d)
    
    def get_context(self,request,exam_slug,*args,**kwargs):
        ctx={}
        exam=EntranceExam.objects.get(slug=exam_slug)
        strem=exam.stream.all()
        related_exam=EntranceExam.objects.filter(stream__in=strem).exclude(name=exam.name)
        ctx['related_exam']=related_exam
        ctx['exam']=exam
        bread_crumb =self._breadcrumb(exam)
        ctx['breadcrumb']= bread_crumb[1]
        num_entities = EntranceExam.objects.all().exclude(name=exam.name).order_by('?')[:5]
        ctx['random_exam']=num_entities
        ctx["html_head"] = self.html_head(exam)
        
        return ctx
    
    def _breadcrumb(self,exam):
        from django.urls import reverse
        url=reverse('entrance_exams:testpreptenth')
        lst=[{'title':'Test Prep','text':'Test Prep','url':url},{'title':exam.name,'text':exam.name,'url':''}]
        return build_breadcrumb(lst)
    
    def get(self, request,exam_slug, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request,exam_slug,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')   
class TestPrepFilter(TemplateView):
    template_name = "topteenfrontend/testprepfilter.html"
    
    def html_head(self):
        name='TestPrepFilter'
        return build_html_head(title=name, description=name)

    def get_context(self,request,stream,*args, **kwargs):
        name=request.GET.get('search')
        
        entex=EntranceExamDocumentFilter()
        ctx=entex.get_entrance_exam_list_context(request,stream=stream,name=name)
        ctx["html_head"] = self.html_head()
        ctx['searchname']=name
        return ctx
    def _breadcrumb(self,exam):
        url=reverse_lazy('entrance_exams:testprepfilter')
        lst=[{'title':'{}'.format(exam.name),'text':'{}'.format("Exam"),'url':url}]
        return build_breadcrumb(lst)
    
    def get(self, request,stream=None,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,stream,args,kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class TestPreptenth(TemplateView):
    template_name = "template20/testprep_list.html"
    def html_head(self):
        name='Test Prep'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        stmcat3=[]
        stmcat2=[]
        stmcat1=[]
        tenthtag=[]
        twelthtag=[]
        collegetag=[]
        stm=EntranceExam.objects.all().values('stream')
        strm=Stream.objects.filter(id__in=stm)
        exmst=[]
        for examstr in strm:
            if examstr not in exmst:
                exmst.append(examstr)
        ctx['strm']=exmst
        tenthexam=EntranceExam.objects.filter(Q(category=choices.EntranceExamTypechoice.after_10_class)|Q(category=choices.EntranceExamTypechoice.BOTH))
        for exam in tenthexam:
            for tag in exam.examtags.all():
                if tag not in tenthtag:
                    tenthtag.append(tag)
            for stream in exam.stream.all():
                if stream not in stmcat1:
                    stmcat1.append(stream)
        ctx['tenthexamtag']=tenthtag  
        ctx['tenthstream']=stmcat1 
        ctx['tenthexam']=tenthexam
        twelexam=EntranceExam.objects.filter(Q(category=choices.EntranceExamTypechoice.after_12_class)|Q(category=choices.EntranceExamTypechoice.BOTH))
        for exam1 in twelexam:
            for tag in exam1.examtags.all():
                if tag not in twelthtag:
                    twelthtag.append(tag)
            for stream in exam1.stream.all():
                if stream not in stmcat2:
                    stmcat2.append(stream)
        ctx['twelthexamtag']=twelthtag   
        ctx['twelthstreams']=stmcat2 
        ctx['twelthexams']=twelexam
        collexam=EntranceExam.objects.filter(Q(category=choices.EntranceExamTypechoice.after_college))
        for exam2 in collexam:
            for tag in exam2.examtags.all():
                if tag not in collegetag:
                    collegetag.append(tag)
            for stream in exam2.stream.all():
                if stream not in stmcat3:
                    stmcat3.append(stream)
        ctx['collegeexamtag']=collegetag
        ctx['collegestreams']=stmcat3
        ctx['collegeexams']=collexam
        num_entities = EntranceExam.objects.all().order_by('?')[:5]
        ctx['related_exam']=num_entities
        ctx["html_head"] = self.html_head()
        ctx['entrance_exam_category']={'after10':"After 10th",'after12':"After 12th",'aftercollge':"After College"}
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'Test Prep', 'url': reverse('entrance_exams:testpreptenth')}
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

def shortlist_exam_view(request):
    id=request.GET.get("id")
    exam=get_object_or_404(EntranceExam,id=id)
    data=EntranceExam.objects.filter(id=id,shortlist=request.user).exists()
    if data:
        exam.shortlist.remove(request.user)
        return JsonResponse({'success':'false'})
    else:
        exam.shortlist.add(request.user)
        return JsonResponse({'success':'true'})