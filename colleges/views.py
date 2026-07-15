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
from core.utils import build_html_head, date_format
from core.breadcrumbs import get_breadcrumb
from html import unescape
from core import choices
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
        # select_related the location FKs so college.get_location() below does not
        # trigger separate country/state/city queries; prefetch flat_texts so the
        # email/mobile/website getters share one query instead of three.
        college=get_object_or_404(
            College.objects.select_related('country', 'state', 'city').prefetch_related('flat_texts'),
            slug=slug,
        )
        ctx['college']=college
        country=Country.objects.all()
        ctx['countries']=country
        courses=Course.objects.filter(college=college).select_related('stream')
        # Related colleges: the template only renders colleges[:6]. get_all_colleges()
        # already select_related's location FKs, so get_location() adds no extra queries.
        all_colleges = College.get_all_colleges().exclude(id=college.id)[:12]
        if hasattr(all_colleges, '__iter__') and not isinstance(all_colleges, str):
            colleges_list = list(all_colleges)
        else:
            colleges_list = []
        ctx['courses']=list(courses)
        streams=[]
        for course in courses:
            stream=course.stream
            if stream not in streams and stream is not None:
                streams.append(stream)
        ctx['streams']=streams
        ctx['breadcrumb'] = self._breadcrumb(ctx["college"])
        ctx['html_head'] = self.__html_head(ctx["college"])
        ctx['unescape']=unescape
        ctx['date_format']=date_format
        
        # Pre-evaluate querysets for Jinja2 template
        ctx['college_texts'] = list(college.texts.all())
        college_facts_list = list(college.facts.all())
        # Pre-process facts to get display values - create dict with display values
        facts_with_display = []
        for fact in college_facts_list:
            facts_with_display.append({
                'fact': fact,
                'type_display': fact.get_type_display(),
                'value': fact.value
            })
        ctx['college_facts'] = facts_with_display
        ctx['college_facilities'] = list(college.facilities.all())
        ctx['college_images'] = list(college.college_images.all())
        
        # Pre-evaluate method calls for Jinja2 template
        ctx['college_location'] = college.get_location()
        ctx['college_email'] = college.get_email()
        ctx['college_mobile'] = college.get_mobile()
        ctx['college_website'] = college.get_website()
        
        # Pre-process related colleges - create list with location
        colleges_with_location = []
        for rel_college in colleges_list:
            colleges_with_location.append({
                'college': rel_college,
                'location': rel_college.get_location()
            })
        ctx['colleges'] = colleges_with_location
        
        # Parent->Student context for suggesting colleges
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(College)
                    ctx['is_bookmarked'] = ParentStudentBookmark.objects.filter(
                        parent=request.user, student_id=int(student_id), content_type=ct, object_id=college.id
                    ).exists()
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
                else:
                    ctx['is_bookmarked'] = False
                ctx['shortlisted_college'] = None
            else:
                if request.user.is_authenticated:
                    ctx['shortlisted_college']=CollegeShortlist.objects.filter(user=request.user,college__slug=ctx['college'].slug).first()
                    ctx['is_bookmarked'] = ctx['shortlisted_college'] is not None
                else:
                    ctx['shortlisted_college']=None
                    ctx['is_bookmarked'] = False
        except Exception:
            try:
                if request.user.is_authenticated:
                    ctx['shortlisted_college']=CollegeShortlist.objects.filter(user=request.user,college__slug=ctx['college'].slug).first()
                    ctx['is_bookmarked'] = ctx['shortlisted_college'] is not None
                else:
                    ctx['shortlisted_college']=None
                    ctx['is_bookmarked'] = False
            except Exception:
                ctx['shortlisted_college']=None
                ctx['is_bookmarked'] = False
        return ctx

    def _breadcrumb(self, college):
        from django.urls import reverse
        return get_breadcrumb([
            {'text': 'Colleges', 'url': reverse('colleges:college')},
            {'text': college.name, 'url': ''},
        ])

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
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Colleges', 'url': reverse('colleges:college')}])
        # Parent->Student context for suggesting colleges
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(College)
                    bookmarked_ids = list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user, student_id=int(student_id), content_type=ct
                        ).values_list("object_id", flat=True)
                    )
                    ctx['bookmarked_college_ids'] = bookmarked_ids
                    ctx['bookmarked_college_slugs'] = list(College.objects.filter(id__in=bookmarked_ids).values_list("slug", flat=True))
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
        except Exception:
            pass
        from users.parent_suggestions import apply_student_parent_suggestions_context, maybe_mark_parent_suggestions_seen
        apply_student_parent_suggestions_context(ctx, request, "colleges")
        maybe_mark_parent_suggestions_seen(
            request, "colleges", is_parent_student_context=ctx.get("is_parent_student_context", False)
        )
        return ctx

    def get_fallback_context(self, request, state):
        """Fallback method using Django ORM when Elasticsearch is unavailable"""
        from django.core.paginator import Paginator
        from django.db.models import Count
        from core.models import Country, State, City

        ctx = {}

        # Get bookmarked college IDs and slugs for authenticated users
        if request.user.is_authenticated:
            bookmarked_college_ids = list(CollegeShortlist.objects.filter(user=request.user).values_list('college_id', flat=True))
            bookmarked_college_slugs = list(CollegeShortlist.objects.filter(user=request.user).values_list('college__slug', flat=True))
            ctx['bookmarked_college_ids'] = bookmarked_college_ids
            ctx['bookmarked_college_slugs'] = bookmarked_college_slugs
        else:
            ctx['bookmarked_college_ids'] = []
            ctx['bookmarked_college_slugs'] = []

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
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'User not authenticated'}, status=401)
    
    id=request.GET.get("id")
    if not id:
        return JsonResponse({'success': False, 'error': 'College ID is required'}, status=400)
    
    try:
        college=get_object_or_404(College,id=id)
        # Check if user already shortlisted this college using ManyToMany relationship
        is_shortlisted = college.shortlist.filter(id=request.user.id).exists()
        if is_shortlisted:
            college.shortlist.remove(request.user)
            return JsonResponse({'success':'false'})
        else:
            college.shortlist.add(request.user)
            return JsonResponse({'success':'true'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)