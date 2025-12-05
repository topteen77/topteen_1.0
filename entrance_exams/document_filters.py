from re import T
from requests import request
from colleges.views import is_ajax
# Import EntranceExamDocument lazily to avoid errors if Elasticsearch is not available
# from .documents import EntranceExamDocument
from django.utils.functional import LazyObject
from django.core.paginator import Paginator
from elasticsearch_dsl import Q ,Nested
from django.core.paginator import Paginator
from .facets import EntranceExamFilterFacets
from .models import EntranceExam
from core.utils import build_breadcrumb
from django.urls import reverse_lazy
from careers.document_filters import SearchResults
from dataclasses import dataclass,field
from core import choices

class EntranceExamDocumentFilter:
    def __init__(self):
        self.search = None
        self.elasticsearch_available = False
        try:
            # Try to import and initialize Elasticsearch search
            from .documents import EntranceExamDocument
            self.search = EntranceExamDocument.search()
            self.elasticsearch_available = True
        except (Exception, AttributeError, TypeError, ImportError) as e:
            import traceback
            print(f"Elasticsearch not available: {e}")
            traceback.print_exc()
            self.search = None
            self.elasticsearch_available = False

    def get_elasticsearch_document_entrance_exam_all(self,request,stream,name,is_ajax):
        if not self.elasticsearch_available or self.search is None:
            raise Exception("Elasticsearch not available")
        # if name:
        #     return self.search.filter("match",name=name)
        return self._entrance_exam_filter(self.search,request)
   
    def get_entrance_exam_list_context(self,request,stream=None,name=None,is_ajax=False):
        ctx={}
        streams=[]
        try:
            search_results=self.get_elasticsearch_document_entrance_exam_all(request,stream,name,is_ajax)
            exams=SearchResults(search_results)
            paginator = Paginator(exams,10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            ctx['exams']=page_obj
            try:
                executed_results = search_results.execute()
                if executed_results:
                    for exam in executed_results[0:]:
                        try:
                            exam_stream = exam.stream
                            if exam_stream:
                                for ste in exam_stream:
                                    # Handle both dict and object formats
                                    stream_name = ste['name'] if isinstance(ste, dict) else getattr(ste, 'name', None)
                                    if stream_name and stream_name not in streams:
                                        streams.append(stream_name)
                        except (KeyError, AttributeError, TypeError) as e:
                            # Skip this exam if stream parsing fails
                            continue
            except (KeyError, AttributeError, TypeError, IndexError) as e:
                # If Elasticsearch structure is different, fallback to empty streams list
                print(f"Warning: Could not parse streams from Elasticsearch: {e}")
                streams = []
        except Exception as e:
            # Fallback to Django ORM if Elasticsearch fails
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
            import traceback
            traceback.print_exc()
            from django.core.paginator import Paginator
            exams = EntranceExam.objects.all()
            paginator = Paginator(exams, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            ctx['exams'] = page_obj
            # Get streams from Django ORM
            from courses.models import Stream
            streams = list(Stream.objects.filter(entranceexam__isnull=False).distinct().values_list('name', flat=True))
        ctx['streams']=streams   
        try:
            ctx['facets_filter']=self.get_facets_filter(request)
        except Exception as e:
            print(f"Warning: Could not get facets filter: {e}")
            ctx['facets_filter'] = {
                'category': [],
                'examtags_slug': [],
                'stream_slug': []
            }
        
        en_exam=EntranceExam.objects.all()
        exam_count = en_exam.count()
        ctx['exam_count']=exam_count        
        ctx['related_exam']=en_exam.order_by('?')[:5]
        bread_crumb =self._breadcrumb()
        ctx['breadcrumb']=bread_crumb[1]
        return ctx
    
    def _breadcrumb(self):
        url=reverse_lazy('entrance_exams:testprepfilter')
        lst=[{'text':'{}'.format("Exam"),'url':url}]
        return build_breadcrumb(lst)
   

    def _entrance_exam_filter(self,search,request):
        selected_filters = self._parse_request_filters(request)
        if selected_filters.get('stream_slug'):
            search = search.filter("terms",stream__slug=selected_filters.get('stream_slug'))
        if selected_filters.get('category'):
            both_category=selected_filters['category'].copy()
            if  choices.EntranceExamTypechoice.get_choice_string(choices.EntranceExamTypechoice.BOTH) not in  both_category:
                both_category.append("After 10th or 12th") 
            search = search.filter("terms",category=both_category)
        if selected_filters.get('examtags_slug'):
            search = search.filter("terms",examtags__slug=selected_filters.get('examtags_slug'))
        if request.GET.get('search'):
            search = search.query(Q("match_phrase", name=request.GET.get('search')) ) 
        return search

    def _parse_request_filters(self,request):
        selected_filters={}
        stream_filter=request.GET.getlist('stream')
        category_filter=request.GET.getlist('category')
        tags_filter=request.GET.getlist('tags')
        
        if tags_filter:
            selected_filters['examtags_slug']=[item for item in tags_filter if item != '']
        
        if stream_filter:
            selected_filters['stream_slug']=[item for item in stream_filter if item != '']
        
        if category_filter:
            selected_filters['category']=[item for item in category_filter if item != '']  
        return selected_filters
    
    def get_facets_filter(self,request,filters={}):
        facets_filters={}
        try:
            d=self._parse_request_filters(request)
            bs = EntranceExamFilterFacets(filters=d)
            result=bs.execute()
            facets_filters["category"]=result.facets.category if hasattr(result.facets, 'category') else []
            facets_filters["examtags_slug"]=sorted(result.facets.examtags_slug,key=lambda obj:obj[0].capitalize()) if hasattr(result.facets, 'examtags_slug') else []
            facets_filters["stream_slug"]=sorted(result.facets.stream_slug,key=lambda obj:obj[0].capitalize()) if hasattr(result.facets, 'stream_slug') else []
        except Exception as e:
            print(f"Warning: Elasticsearch facets not available: {e}")
            facets_filters["category"]=[]
            facets_filters["examtags_slug"]=[]
            facets_filters["stream_slug"]=[]
        return facets_filters
    
    def get_facets_search(self,request,filters={}):
        bs = EntranceExamFilterFacets(filters=filters)
        return bs.execute()

