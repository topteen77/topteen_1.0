from re import T
from requests import request
from colleges.views import is_ajax
from .documents import SkillLabCourseDocument
from django.utils.functional import LazyObject
from django.core.paginator import Paginator
from elasticsearch_dsl import Q ,Nested
from django.core.paginator import Paginator
from .models import SkillLabCourse
from core.breadcrumbs import get_breadcrumb
from django.urls import reverse_lazy


class SkillLabCourseDocumentFilter:
    def __init__(self):
        try:
            self.search=SkillLabCourseDocument.search()
        except (KeyError, Exception) as e:
            # Elasticsearch connection not available
            self.search = None
            raise e

    def get_elasticsearch_document_skilllab_all(self,request,is_ajax):
        return self.search
        
    def get_skilllab_list_context(self,request,is_ajax=False):
        if self.search is None:
            raise KeyError("Elasticsearch connection not available")
        ctx={}
        streams=[]
        search_results=SearchResults(self.get_elasticsearch_document_skilllab_all(request,is_ajax))
        paginator = Paginator(search_results,9)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['skilllab']=page_obj
        
        return ctx
    
    def _breadcrumb(self, skilllab):
        url = reverse_lazy('skilllabcourse:skilllabcourselist')
        return get_breadcrumb([{'text': 'skilllabcourse', 'url': url}])
    

    def _skilllab_filter(self,search,request):
        
        return search

    def _parse_request_filters(self,request):
        pass

class SearchResults(LazyObject):
    def __init__(self, search_object):
        self._wrapped = search_object

