from re import T
from requests import request
from colleges.document_filters import CollegeDocumentFilter
from colleges.views import is_ajax
from .documents import CareerDocument
from django.utils.functional import LazyObject
from django.core.paginator import Paginator
from .facets import CareerFilterFacets
from core.models import Country
from colleges.models import College
from elasticsearch_dsl import Q ,Nested

class CareerDocumentFilter:
    def __init__(self):
        self.search=CareerDocument.search()

    def get_elasticsearch_document_career_all(self,request,tagslug):
        if tagslug is not None :
            # tagfilter=self._career_filter(self.search,request)
            return self._career_filter(self.search.filter("match",career_tags__slug=tagslug),request)
        return self._career_filter(self.search,request,tagslug)

    def _career_filter(self,search,request,tagslug=None):
        if request.GET.getlist('professions'):
            q = Q('nested',path='profession',ignore_unmapped= "true",query=Q('terms', profession__name=request.GET.getlist('professions')))
            search = search.query(q)
        if request.GET.getlist('skills'):
            search = search.filter("terms",skills__name=request.GET.getlist('skills'))
        if request.GET.getlist('courses'):
            search = search.filter("terms",courses__name=request.GET.getlist('courses'))
        return search
    def get_career_list_context(self,request,tagslug=None):
        ctx={}
        search_results=SearchResults(self.get_elasticsearch_document_career_all(request,tagslug))
        paginator = Paginator(search_results,15)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['careers']=page_obj
        
        ctx['facets_filter']=self.get_facets_filter(request,tagslug)
        
        # Get shortlisted career IDs for authenticated users
        shortlisted_career_ids = []
        if request.user.is_authenticated:
            from careers.models import CareerShortlist
            shortlisted_career_ids = list(CareerShortlist.objects.filter(
                user=request.user
            ).values_list('career_id', flat=True))
        ctx['shortlisted_career_ids'] = shortlisted_career_ids
        
        return ctx

    def get_facets_filter(self,request,tagslug=None):
        facets_filter={}
        d=self.get_filter_dict(request,tagslug)
        bs=CareerFilterFacets(filters=d)
        result=bs.execute()
        facets_filter["skill"] =sorted(result.facets.skill,key=lambda obj:obj[0].capitalize())
        facets_filter["profession"] =sorted(result.facets.profession,key=lambda obj:obj[0].capitalize())
        return facets_filter

    def get_filter_dict(self,request,tagslug=None):
        d={}
        if request.GET.getlist('professions') and len(request.GET.getlist('professions')) > 0:
            d['profession']=request.GET.getlist('professions')
            
        if request.GET.getlist('skills') and len(request.GET.getlist('skills')) >0:
            d['skill']=request.GET.getlist('skills')
            
        if request.GET.getlist('courses') and len(request.GET.getlist('courses')) >0:
            d['course']=request.GET.getlist('courses')

        if tagslug:
            d['career_tags']=tagslug
        return d

    def get_career_detail(self,request,slug,is_ajax=False):
        career=self.search.query("match",slug=slug)
        clgdf=CollegeDocumentFilter()
        ctx={}
        country=Country.objects.all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['countries']=country
        ctx['career'] = career.execute()[0]
        return ctx

class SearchResults(LazyObject):
    def __init__(self, search_object):
        self._wrapped = search_object

    def __len__(self):
        return self._wrapped.count()

    def __getitem__(self, index):
        search_results = self._wrapped[index]
        if isinstance(index, slice):
            search_results = list(search_results)
        return search_results