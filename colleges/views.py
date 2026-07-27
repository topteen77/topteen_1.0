from asyncio import streams
from urllib import request
from django.shortcuts import render
from django.http import JsonResponse
from colleges.document_filters import CollegeDocumentFilter
from .models import College, CollegeShortlist, IndianCollegeShortlist
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
        from django.conf import settings
        from django.urls import reverse

        if getattr(settings, "USE_INDIAN_COLLEGES_API", False):
            return self.get_indian_api_context(request)

        try:
            clg=CollegeDocumentFilter()
            ctx=clg.get_college_list_context(request,state)
        except (KeyError, Exception) as e:
            # Fallback to Django ORM when Elasticsearch is not available
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
            ctx = self.get_fallback_context(request, state)
        
        ctx['html_head'] = self.__html_head()
        ctx['use_indian_colleges_api'] = False
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

    def get_indian_api_context(self, request):
        from django.urls import reverse
        from colleges.external_api import get_college_list_context_from_api

        try:
            ctx = get_college_list_context_from_api(request)
        except Exception as e:
            print(f"Indian colleges API unavailable, falling back to local colleges: {e}")
            ctx = self.get_fallback_context(request, None)
            ctx['use_indian_colleges_api'] = False
            ctx['api_error'] = str(e)
            country = request.GET.getlist('country')
            state_list = request.GET.getlist('state')
            city = request.GET.getlist('city')
            ctx['query_list'] = state_list + city
            ctx['get_updated_url'] = "&".join(
                [f"country={c}" for c in country]
                + [f"state={s}" for s in state_list]
                + [f"city={ci}" for ci in city]
            )

        ctx['html_head'] = self.__html_head()
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Colleges', 'url': reverse('colleges:college')}])
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        ctx['indian_shortlisted_ids'] = []
        ctx['psychometric_match'] = None
        ctx['psychometric_match_courses'] = []
        if request.user.is_authenticated:
            ctx['indian_shortlisted_ids'] = list(
                IndianCollegeShortlist.objects.filter(user_id=request.user.id)
                .values_list('external_college_id', flat=True)
            )
            try:
                from colleges.psychometric_match import (
                    get_matched_courses,
                    get_psychometric_match_profile,
                )

                # Local DB + short cache only — no upstream on list SSR.
                profile = get_psychometric_match_profile(request.user)
                ctx['psychometric_match'] = profile
                if profile:
                    # Cache-only preview so list page stays fast.
                    ctx['psychometric_match_courses'] = get_matched_courses(
                        profile['stream_id'],
                        stream_name=profile.get('stream_name') or '',
                        limit=6,
                        cache_only=True,
                    )
            except Exception:
                ctx['psychometric_match'] = None
                ctx['psychometric_match_courses'] = []
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


class IndianCollegeDetails(TemplateView):
    """College detail page backed by the Indian colleges API."""

    template_name = "template20/indian_college_detail.html"

    def get(self, request, college_id, tab=None, *args, **kwargs):
        from django.http import Http404
        from django.shortcuts import redirect
        from django.urls import reverse
        from colleges.external_api import (
            CollegeContentDisabled,
            get_college_detail_context_from_api,
            resolve_detail_tab,
        )

        active = resolve_detail_tab(tab)
        # Canonicalize aliases like cut_off -> cut-off
        if tab and tab != active["path"]:
            url = reverse(
                "colleges:indian_collegedetail_tab",
                kwargs={"college_id": college_id, "tab": active["path"]},
            )
            stream = request.GET.get("stream")
            course = request.GET.get("course")
            qs = []
            if stream:
                qs.append(f"stream={stream}")
            if course:
                qs.append(f"course={course}")
            if qs:
                url = f"{url}?{'&'.join(qs)}"
            return redirect(url)

        try:
            ctx = get_college_detail_context_from_api(
                college_id=college_id,
                tab=active["path"],
                stream_slug=request.GET.get("stream"),
                highlight_course_slug=request.GET.get("course"),
            )
            ctx["api_error"] = None
        except CollegeContentDisabled:
            raise Http404("College details are not available yet.")
        except Exception as e:
            print(f"Indian college detail API error: {e}")
            raise Http404("Unable to load college details right now.")

        ctx["is_indian_shortlisted"] = False
        if request.user.is_authenticated:
            ctx["is_indian_shortlisted"] = IndianCollegeShortlist.objects.filter(
                user_id=request.user.id,
                external_college_id=int(college_id),
            ).exists()

        redirect_tab = ctx.get("redirect_tab")
        if redirect_tab and redirect_tab != active["path"]:
            url = reverse(
                "colleges:indian_collegedetail_tab",
                kwargs={"college_id": college_id, "tab": redirect_tab},
            )
            stream = request.GET.get("stream")
            course = request.GET.get("course")
            qs = []
            if stream:
                qs.append(f"stream={stream}")
            if course:
                qs.append(f"course={course}")
            if qs:
                url = f"{url}?{'&'.join(qs)}"
            return redirect(url)

        ctx["html_head"] = build_html_head(
            title=ctx.get("college_name") or "College",
            description=ctx.get("college_location") or "College details",
        )
        ctx["breadcrumb"] = get_breadcrumb(
            [
                {"text": "Colleges", "url": reverse("colleges:college")},
                {"text": ctx.get("college_name") or "Details", "url": ""},
            ]
        )
        return render(request, self.template_name, ctx)


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


def shortlist_indian_college_view(request):
    """Toggle shortlist for an external Indian college (student dashboard scrapbook)."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "User not authenticated"},
            status=401,
        )

    college_id = request.POST.get("college_id") or request.GET.get("college_id")
    if not college_id:
        return JsonResponse(
            {"success": False, "error": "College ID is required"},
            status=400,
        )
    try:
        college_id = int(college_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Invalid college ID"},
            status=400,
        )

    name = (request.POST.get("name") or request.GET.get("name") or "").strip()
    city_name = (request.POST.get("city_name") or "").strip()
    state_name = (request.POST.get("state_name") or "").strip()
    college_type = (request.POST.get("college_type") or "").strip()
    avg_fees = (request.POST.get("avg_fees") or "").strip()

    existing = IndianCollegeShortlist.objects.filter(
        user=request.user,
        external_college_id=college_id,
    ).first()
    if existing and existing.object_status == 1:
        existing.delete(hard_delete=True)
        return JsonResponse(
            {
                "success": True,
                "message": "Removed Shortlisted",
                "shortlisted": False,
            }
        )

    if existing:
        existing.object_status = 1
        existing.name = name or existing.name or f"College {college_id}"
        existing.city_name = city_name or existing.city_name
        existing.state_name = state_name or existing.state_name
        existing.college_type = college_type or existing.college_type
        existing.avg_fees = avg_fees or existing.avg_fees
        existing.save()
    else:
        IndianCollegeShortlist.objects.create(
            user=request.user,
            external_college_id=college_id,
            name=name or f"College {college_id}",
            city_name=city_name,
            state_name=state_name,
            college_type=college_type,
            avg_fees=avg_fees,
        )
    return JsonResponse(
        {
            "success": True,
            "message": "College Shortlisted",
            "shortlisted": True,
        }
    )


class MatchedCoursesView(TemplateView):
    """Dedicated page: psychometric-matched courses (one cached filters call)."""

    template_name = "template20/matched_courses.html"

    def get(self, request, *args, **kwargs):
        from django.urls import reverse
        from colleges.psychometric_match import (
            get_matched_courses,
            get_psychometric_match_profile,
            resolve_stream_for_user,
        )

        profile = None
        if request.user.is_authenticated:
            try:
                profile = get_psychometric_match_profile(request.user)
            except Exception:
                profile = None

        stream_param = request.GET.get("stream")
        stream_id = None
        try:
            if stream_param:
                stream_id = int(stream_param)
        except (TypeError, ValueError):
            stream_id = None

        search_query = (request.GET.get("q") or "").strip()
        active = None
        courses = []
        if profile and request.user.is_authenticated:
            active = resolve_stream_for_user(request.user, stream_id=stream_id)
            if active:
                courses = get_matched_courses(
                    active["stream_id"],
                    stream_name=active.get("stream_name") or "",
                    q=search_query,
                    limit=200,
                )

        ctx = {
            "html_head": build_html_head(
                title="Matched Courses",
                description="Courses matched to your psychometric profile",
            ),
            "breadcrumb": get_breadcrumb(
                [
                    {"text": "Colleges", "url": reverse("colleges:college")},
                    {"text": "Matched Courses", "url": ""},
                ]
            ),
            "psychometric_match": profile,
            "courses": courses,
            "search_query": search_query,
            "active_stream_id": active["stream_id"] if active else None,
            "active_stream_name": active["stream_name"] if active else "",
            "active_stream_query": (
                f"stream={active['stream_id']}" if active else ""
            ),
        }
        return render(request, self.template_name, ctx)


def psychometric_match_courses_api(request):
    """Async JSON preview of matched courses (cached filters; list-page safe)."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth"}, status=401)
    try:
        from colleges.psychometric_match import (
            get_matched_courses,
            get_psychometric_match_profile,
            resolve_stream_for_user,
        )

        stream_param = request.GET.get("stream")
        stream_id = None
        try:
            if stream_param:
                stream_id = int(stream_param)
        except (TypeError, ValueError):
            stream_id = None

        active = resolve_stream_for_user(request.user, stream_id=stream_id)
        if not active:
            return JsonResponse({"ok": False, "reason": "no_profile"})

        courses = get_matched_courses(
            active["stream_id"],
            stream_name=active.get("stream_name") or "",
            limit=8,
            cache_only=False,
        )
        return JsonResponse(
            {
                "ok": True,
                "stream_id": active["stream_id"],
                "stream_name": active["stream_name"],
                "courses": courses,
                "matched_courses_url": (
                    f"/colleges/matched-courses/?stream={active['stream_id']}"
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "reason": "error", "error": str(e)})


class IndianCourseDetailView(TemplateView):
    """Separate course page linked from college Courses & Fees table."""

    template_name = "template20/indian_course_detail.html"

    def get(self, request, course_id, *args, **kwargs):
        from django.urls import reverse
        from colleges.course_pages import get_colleges_for_course
        from colleges.external_api import find_course_overview_html

        course_name = (request.GET.get("name") or f"Course {course_id}").strip()
        degree_level = (request.GET.get("degree") or "").strip()
        stream_name = (request.GET.get("stream") or "").strip()
        stream_slug = (request.GET.get("stream_slug") or "").strip()
        course_slug = (request.GET.get("course_slug") or "").strip()
        stream_id = request.GET.get("stream_id")
        from_college_id = request.GET.get("from_college")
        try:
            from_college_id = int(from_college_id) if from_college_id else None
        except (TypeError, ValueError):
            from_college_id = None
        try:
            stream_id = int(stream_id) if stream_id else None
        except (TypeError, ValueError):
            stream_id = None

        try:
            course_id_int = int(course_id)
        except (TypeError, ValueError):
            course_id_int = 0

        # Map stream label → id for matched-course links that only send the name.
        if stream_id is None and stream_name:
            from colleges.psychometric_match import RIASEC_TO_STREAMS

            want = stream_name.strip().lower()
            for rows in RIASEC_TO_STREAMS.values():
                for row in rows:
                    if (row.get("name") or "").strip().lower() == want:
                        stream_id = int(row["id"])
                        break
                if stream_id is not None:
                    break

        payload = get_colleges_for_course(
            course_name,
            stream_name=stream_name,
            stream_slug=stream_slug,
            course_slug=course_slug,
            limit=12,
        )
        colleges = payload.get("colleges") or []

        college_ids = []
        if from_college_id:
            college_ids.append(from_college_id)
        for row in colleges:
            try:
                college_ids.append(int(row.get("id")))
            except (TypeError, ValueError, AttributeError):
                continue

        overview = find_course_overview_html(
            course_name=course_name,
            course_id=course_id_int,
            course_slug=course_slug,
            stream_name=stream_name,
            stream_slug=stream_slug,
            stream_id=stream_id,
            college_ids=college_ids,
            max_colleges=10,
        )
        course_html = overview.get("html") or ""
        if course_html and not str(course_html).strip():
            course_html = ""
        course_slug = overview.get("course_slug") or course_slug
        # Keep the page title as the matched/filter course name; overview may
        # resolve to a closely related published course at a content-ready college.
        degree_level = overview.get("degree_level") or degree_level
        if overview.get("stream_name"):
            stream_name = overview.get("stream_name") or stream_name
        stream_slug = overview.get("stream_slug") or stream_slug
        overview_college_id = overview.get("college_id") or from_college_id
        overview_college_name = (overview.get("college_name") or "").strip()
        overview_college_city = (overview.get("college_city") or "").strip()
        overview_college_state = (overview.get("college_state") or "").strip()
        if not overview_college_name and overview_college_id:
            for row in colleges:
                try:
                    if int(row.get("id")) == int(overview_college_id):
                        overview_college_name = (row.get("name") or "").strip()
                        overview_college_city = (row.get("city") or "").strip()
                        overview_college_state = (row.get("state") or "").strip()
                        break
                except (TypeError, ValueError, AttributeError):
                    continue

        crumbs = [{"text": "Colleges", "url": reverse("colleges:college")}]
        if from_college_id:
            crumbs.append(
                {
                    "text": overview_college_name or "College",
                    "url": reverse(
                        "colleges:indian_collegedetail_tab",
                        kwargs={"college_id": from_college_id, "tab": "courses"},
                    ),
                }
            )
        elif overview_college_id and overview_college_name:
            crumbs.append(
                {
                    "text": overview_college_name,
                    "url": reverse(
                        "colleges:indian_collegedetail_tab",
                        kwargs={
                            "college_id": overview_college_id,
                            "tab": "courses",
                        },
                    ),
                }
            )
        crumbs.append({"text": course_name, "url": ""})

        ctx = {
            "html_head": build_html_head(
                title=course_name,
                description=f"{course_name} colleges and course details",
            ),
            "breadcrumb": get_breadcrumb(crumbs),
            "course_id": course_id_int,
            "course_name": course_name,
            "degree_level": degree_level,
            "stream_name": stream_name,
            "stream_slug": stream_slug,
            "course_slug": course_slug,
            "from_college_id": from_college_id,
            "overview_college_id": overview_college_id,
            "overview_college_name": overview_college_name,
            "overview_college_city": overview_college_city,
            "overview_college_state": overview_college_state,
            "course_html": course_html,
            "has_course_html": bool(str(course_html or "").strip()),
            "colleges": colleges,
            "filter_query": payload.get("filter_query") or "",
        }
        return render(request, self.template_name, ctx)