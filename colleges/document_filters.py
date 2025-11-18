from django.utils.functional import LazyObject
from colleges.documents import CollegeDocument
from core.models import Country
from colleges.models import College
from courses.documents import CourseDocument
from elasticsearch_dsl import Q
from .facets import CollegeFilterFacets
from django.core.paginator import Paginator
#from .views import explore_college

class CollegeDocumentFilter:
    def __init__(self):
        self.search=CollegeDocument.search()

    def college_detail(self,request,college_slug,is_ajax=False):
        streams=[]
        ctx = self.explore_colleges_details(request,is_ajax)
        # q = Q("match",slug=college_slug)
        college=self.search.query("match",slug=college_slug)
        filter_courses=CourseDocumentfilter()
        courses=filter_courses.get_college_courses(request,college_slug)
        country=Country.objects.all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['countries']=country
        ctx['college']=college.execute()[0]
        ctx['courses']=courses
        for course in courses:
            stream=course.stream
            if stream not in streams:
                streams.append(stream)
        ctx['streams']=streams
        return ctx
    
    def explore_colleges_details(self,request,is_ajax=False):
        ctx={}
        countys=[]
        streamlist=[]
        colleges = self.search.execute()
        for college in colleges:
            country = college.country
            countys.append(country)
            streamlist.append(college.stream)
        streams =  [i for n, i in enumerate(streamlist) if i not in streamlist[n + 1:]] 
        countries = [i for n, i in enumerate(countys) if i not in countys[n + 1:]]   
        # for country in countries:    
        #     country_name=country.name
        #     country_colleges=self.search.query("match",country__name=country_name)
        #     ctx['country_colleges']=country_colleges.execute()
        #     print(country_name)
        #     print(country_colleges.execute())
        if is_ajax:
            country_name=request.GET.get('country_name')    
            country_colleges=self.search.query("match",country__name=country_name)
            print(country_colleges.execute())

            ctx['country_colleges']=country_colleges.execute()
        else:
            country_colleges=self.search.query("match",country__name=countries[0]['name'])
            ctx['country_colleges']=country_colleges.execute()
        ctx['countries']=countries
        ctx['streams'] = streams
        return ctx

    def get_elasticsearch_document_college_all(self,request,state,is_ajax):
        if state is None :
            return self.search
        elif state:
            return self.search.filter("match",state__name=state)
        return self._college_filter(self.search,request)
    
    def _college_filter(self,search,request):
        selected_filters = self._parse_request_filters(request)
        if selected_filters.get('state'):
            search = search.filter("terms",state__name=selected_filters.get('state'))
        if selected_filters.get('city'):
            search = search.filter("terms",city__name=selected_filters.get('city'))
        if selected_filters.get('country'):
            search = search.filter("terms",country__name=selected_filters.get('country'))
       
        return search

    def _parse_request_filters(self,request):
        selected_filters={}
        state_filter=request.GET.getlist('state')
        city_filter=request.GET.getlist('city')
        country_filter=request.GET.getlist('country')
        if state_filter:
            selected_filters['state']=[item for item in state_filter if item != '']
        if city_filter:
            selected_filters['city']=[item for item in city_filter if item != '']
        if country_filter:
            selected_filters['country']=[item for item in country_filter if item != '']
        return selected_filters
    
    def get_facets_filter(self,request,filters={}):
        d=self._parse_request_filters(request)
        bs = CollegeFilterFacets(filters=d)
        return bs.execute()

    def get_college_list_context(self,request,state=None,is_ajax=False):
        ctx={}
        search_results=SearchResults(self.get_elasticsearch_document_college_all(request,state,is_ajax))
        paginator = Paginator(search_results,9)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['colleges']=page_obj
        if state:
            d={'state':state}
        else:
            d={}
        ctx['facets_filter']=self.get_facets_filter(request,filters=d)
        return ctx

class SearchResults(LazyObject):
    def __init__(self, search_object):
        self._wrapped = search_object

class CourseDocumentfilter:
    def __init__(self):
        self.search=CourseDocument.search()
    
    def get_college_courses(self,request,college_slug):
        courses=self.search.query("match",college__slug=college_slug)
        return courses.execute()