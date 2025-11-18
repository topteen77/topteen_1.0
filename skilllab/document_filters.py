from re import T
from requests import request
from colleges.views import is_ajax
from .documents import SkillLabCourseDocument
from django.utils.functional import LazyObject
from django.core.paginator import Paginator
from elasticsearch_dsl import Q ,Nested
from django.core.paginator import Paginator
from .models import SkillLabCourse
from core.utils import build_breadcrumb
from django.urls import reverse_lazy


class SkillLabCourseDocumentFilter:
    def __init__(self):
        self.search=SkillLabCourseDocument.search()

    def get_elasticsearch_document_skilllab_all(self,request,is_ajax):
        return self.search
        
    def get_skilllab_list_context(self,request,is_ajax=False):
        ctx={}
        streams=[]
        search_results=SearchResults(self.get_elasticsearch_document_skilllab_all(request,is_ajax))
        paginator = Paginator(search_results,9)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['skilllab']=page_obj
        
        return ctx
    
    def _breadcrumb(self,skilllab):
        url=reverse_lazy('skilllab:skilllabcourselist')
        lst=[{'text':'{}'.format("skilllabcourse"),'url':url}]
        return build_breadcrumb(lst)
    

    def _skilllab_filter(self,search,request):
        
        return search

    def _parse_request_filters(self,request):
        pass

class SearchResults(LazyObject):
    def __init__(self, search_object):
        self._wrapped = search_object

