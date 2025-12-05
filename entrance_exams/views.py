from unicodedata import name
from core.utils import build_breadcrumb,build_html_head
import random
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views.generic import TemplateView
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.template.loader import render_to_string
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
        
        try:
            entex=EntranceExamDocumentFilter()
            ctx=entex.get_entrance_exam_list_context(request,stream=stream,name=name)
        except Exception as e:
            # Fallback to Django ORM if filter fails
            import traceback
            print(f"EntranceExamDocumentFilter failed: {e}")
            traceback.print_exc()
            from django.core.paginator import Paginator
            from .models import EntranceExam
            from courses.models import Stream
            
            exams = EntranceExam.objects.all()
            paginator = Paginator(exams, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            
            from core.utils import build_breadcrumb
            breadcrumb_url = reverse_lazy('entrance_exams:testprepfilter')
            breadcrumb_list = [{'text': 'Exam', 'url': breadcrumb_url}]
            breadcrumb_result = build_breadcrumb(breadcrumb_list)
            
            ctx = {
                'exams': page_obj,
                'streams': list(Stream.objects.filter(entranceexam__isnull=False).distinct().values_list('name', flat=True)),
                'exam_count': exams.count(),
                'related_exam': exams.order_by('?')[:5],
                'facets_filter': {
                    'category': [],
                    'examtags_slug': [],
                    'stream_slug': []
                },
                'breadcrumb': breadcrumb_result[1] if isinstance(breadcrumb_result, tuple) else breadcrumb_result
            }
        
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
        # Only load initial tab (After 10th) data - other tabs loaded via AJAX
        from django.db.models import Prefetch
        
        # Optimize queries with prefetch_related to avoid N+1 queries
        tenthexam = EntranceExam.objects.filter(
            Q(category=choices.EntranceExamTypechoice.after_10_class) | 
            Q(category=choices.EntranceExamTypechoice.BOTH)
        ).prefetch_related('examtags', 'stream', 'shortlist')[:50]  # Limit initial load
        
        # Get unique streams efficiently
        stmcat1 = list(Stream.objects.filter(
            entranceexam__category__in=[choices.EntranceExamTypechoice.after_10_class, choices.EntranceExamTypechoice.BOTH]
        ).distinct()[:10])
        
        # Get unique tags efficiently - limit to first 20 exams to avoid heavy processing
        tenthtag = []
        seen_tags = set()
        for exam in tenthexam[:20]:
            for tag in exam.examtags.all()[:5]:
                if tag.id not in seen_tags:
                    tenthtag.append(tag)
                    seen_tags.add(tag.id)
                    if len(tenthtag) >= 10:
                        break
            if len(tenthtag) >= 10:
                break
        
        # Pre-compute bookmarked exams to avoid N+1 queries in template
        bookmarked_exam_ids = set()
        if request.user.is_authenticated:
            bookmarked_exam_ids = set(
                EntranceExam.objects.filter(
                    Q(category=choices.EntranceExamTypechoice.after_10_class) | 
                    Q(category=choices.EntranceExamTypechoice.BOTH),
                    shortlist=request.user
                ).values_list('id', flat=True)
            )
        
        ctx['tenthexamtag'] = tenthtag  
        ctx['tenthstream'] = stmcat1 
        ctx['tenthexam'] = tenthexam
        ctx['bookmarked_exam_ids'] = bookmarked_exam_ids
        
        # Don't load other tabs initially - load via AJAX
        ctx['twelthexamtag'] = []
        ctx['twelthstreams'] = []
        ctx['twelthexams'] = EntranceExam.objects.none()
        ctx['collegeexamtag'] = []
        ctx['collegestreams'] = []
        ctx['collegeexams'] = EntranceExam.objects.none()
        
        # Only load related exams (lightweight)
        num_entities = EntranceExam.objects.all().order_by('?')[:5]
        ctx['related_exam'] = num_entities
        ctx["html_head"] = self.html_head()
        ctx['entrance_exam_category'] = {'after10':"After 10th",'after12':"After 12th",'aftercollge':"After College"}
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'Test Prep', 'url': reverse('entrance_exams:testpreptenth')}
        return ctx

    def get(self, request,*args, **kwargs):
        # Handle AJAX requests for tab content
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            tab = request.GET.get('tab', 'tenth')
            return self.get_tab_content(request, tab)
        return render(request, self.template_name, self.get_context(request,args,kwargs))
    
    def get_tab_content(self, request, tab):
        """Load tab content via AJAX"""
        from django.db.models import Prefetch
        
        if tab == 'twelfth':
            twelexam = EntranceExam.objects.filter(
                Q(category=choices.EntranceExamTypechoice.after_12_class) | 
                Q(category=choices.EntranceExamTypechoice.BOTH)
            ).prefetch_related('examtags', 'stream', 'shortlist')[:50]
            
            stmcat2 = list(Stream.objects.filter(
                entranceexam__category__in=[choices.EntranceExamTypechoice.after_12_class, choices.EntranceExamTypechoice.BOTH]
            ).distinct()[:10])
            
            # Get unique tags efficiently
            twelthtag = []
            seen_tags = set()
            for exam in twelexam[:20]:
                for tag in exam.examtags.all()[:5]:
                    if tag.id not in seen_tags:
                        twelthtag.append(tag)
                        seen_tags.add(tag.id)
                        if len(twelthtag) >= 10:
                            break
                if len(twelthtag) >= 10:
                    break
            
            # Pre-compute bookmarked exams
            bookmarked_exam_ids = set()
            if request.user.is_authenticated:
                bookmarked_exam_ids = set(
                    EntranceExam.objects.filter(
                        Q(category=choices.EntranceExamTypechoice.after_12_class) | 
                        Q(category=choices.EntranceExamTypechoice.BOTH),
                        shortlist=request.user
                    ).values_list('id', flat=True)
                )
            
            ctx = {
                'twelthexamtag': twelthtag,
                'twelthstreams': stmcat2,
                'twelthexams': twelexam,
                'entrance_exam_category': {'after12':"After 12th"},
                'bookmarked_exam_ids': bookmarked_exam_ids,
            }
            html = render_to_string('template20/testprep_list_tab_content.html', ctx, request=request)
            return JsonResponse({'html': html})
            
        elif tab == 'college':
            collexam = EntranceExam.objects.filter(
                Q(category=choices.EntranceExamTypechoice.after_college)
            ).prefetch_related('examtags', 'stream', 'shortlist')[:50]
            
            stmcat3 = list(Stream.objects.filter(
                entranceexam__category=choices.EntranceExamTypechoice.after_college
            ).distinct()[:10])
            
            # Get unique tags efficiently
            collegetag = []
            seen_tags = set()
            for exam in collexam[:20]:
                for tag in exam.examtags.all()[:5]:
                    if tag.id not in seen_tags:
                        collegetag.append(tag)
                        seen_tags.add(tag.id)
                        if len(collegetag) >= 10:
                            break
                if len(collegetag) >= 10:
                    break
            
            # Pre-compute bookmarked exams
            bookmarked_exam_ids = set()
            if request.user.is_authenticated:
                bookmarked_exam_ids = set(
                    EntranceExam.objects.filter(
                        Q(category=choices.EntranceExamTypechoice.after_college),
                        shortlist=request.user
                    ).values_list('id', flat=True)
                )
            
            ctx = {
                'collegeexamtag': collegetag,
                'collegestreams': stmcat3,
                'collegeexams': collexam,
                'entrance_exam_category': {'aftercollge':"After College"},
                'bookmarked_exam_ids': bookmarked_exam_ids,
            }
            html = render_to_string('template20/testprep_list_tab_content.html', ctx, request=request)
            return JsonResponse({'html': html})
        
        return JsonResponse({'html': ''})

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