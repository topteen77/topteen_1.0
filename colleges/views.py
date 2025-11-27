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
            try:
                clgd=CollegeDocumentFilter()
                ctx=clgd.college_detail(request,slug,is_ajax=True)
            except (KeyError, Exception) as e:
                # Fallback to regular context when Elasticsearch is not available
                print(f"Elasticsearch not available, using Django ORM fallback: {e}")
                ctx = self.get_context(request, slug, args, kwargs)
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
        from django.core.paginator import Paginator
        from django.db.models import Q
        
        try:
            clg=CollegeDocumentFilter()
            ctx=clg.get_college_list_context(request,state)
        except (KeyError, Exception) as e:
            # Fallback to Django ORM when Elasticsearch is not available
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
            ctx = self.get_fallback_context(request, state)
        
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
    
    def get_fallback_context(self, request, state=None):
        """Fallback method using Django ORM when Elasticsearch is unavailable"""
        from django.core.paginator import Paginator
        from django.db.models import Q, Count
        from core.models import Country, State, City
        
        ctx = {}
        
        # Get base queryset
        colleges = College.objects.filter(publish_status=1).select_related('country', 'state', 'city', 'category')
        
        # Apply filters from request
        country_filter = request.GET.getlist('country')
        state_filter = request.GET.getlist('state')
        city_filter = request.GET.getlist('city')
        
        if state:
            colleges = colleges.filter(state__name=state)
        elif state_filter:
            colleges = colleges.filter(state__name__in=state_filter)
        
        if country_filter:
            colleges = colleges.filter(country__name__in=country_filter)
        
        if city_filter:
            colleges = colleges.filter(city__name__in=city_filter)
        
        # Order by name
        colleges = colleges.order_by('name')
        
        # Pagination
        paginator = Paginator(colleges, 9)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['colleges'] = page_obj
        
        # Create facets structure compatible with template expectations
        # Get all available countries with counts
        all_countries = Country.objects.filter(
            college__publish_status=1
        ).annotate(
            count=Count('college', distinct=True)
        ).distinct().order_by('name')
        
        # Get all available states with counts
        all_states = State.objects.filter(
            college__publish_status=1
        ).annotate(
            count=Count('college', distinct=True)
        ).distinct().order_by('name')
        
        # Get all available cities with counts
        all_cities = City.objects.filter(
            college__publish_status=1
        ).annotate(
            count=Count('college', distinct=True)
        ).distinct().order_by('name')
        
        # Create facets structure matching Elasticsearch FacetedResponse format
        # The template expects facets_filter.facets.state, facets_filter.facets.city, facets_filter.facets.country
        # Each should be a list of tuples: (tag, count, selected)
        class FacetsWrapper:
            def __init__(self):
                self.facets = type('Facets', (), {
                    'country': [(c.name, c.count, c.name in country_filter) for c in all_countries],
                    'state': [(s.name, s.count, s.name in state_filter) for s in all_states],
                    'city': [(c.name, c.count, c.name in city_filter) for c in all_cities],
                })()
        
        ctx['facets_filter'] = FacetsWrapper()
        
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