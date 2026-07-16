import json
import logging
import random
import re
import os
import time
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)
from multiprocessing import get_context
from .utils import build_html_head, clean_html, expand_eq_band_percentile, get_static_page, get_static_page_html_head, get_page_seo_html_head
from .breadcrumbs import get_breadcrumb
from django.db import connection
from django.db.models import Q
from django.db.utils import ProgrammingError
from xml.etree.ElementInclude import include
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from blog.models import Blog
from careers.models import Career, CareerTags,Videos,CareerCluster
from core import choices
from django.views.generic import TemplateView
from core.models import CommonFAQ, Country, Review, Contact, Lead, Ebook, FourPillarsAssessmentResult, FourPillarsAssessment, MIAssessmentResult, EQAssessmentResult, CareerBattleFight, GeneratedPage
from courses.models import Course
from colleges.models import College
from django.conf import settings
from django.core.cache import cache
from .forms import ImageUploadModelForm
from django.core.paginator import Paginator
from django.http import HttpResponse,JsonResponse
from django.template.loader import render_to_string
from careers.document_filters import CareerDocumentFilter
from colleges.document_filters import CollegeDocumentFilter
from entrance_exams.document_filters import EntranceExamDocumentFilter
from courses.documents import CourseDocument
from careers.models import Videos,Career
from colleges.models import College
from .documents_filter import AllSearch
from core.models import EntranceTestPrepExam
from users.models import UserSearchHistory
from django.shortcuts import HttpResponse,HttpResponseRedirect
from skilllab.models import SkillLabCourse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from rest_framework.views import APIView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from pathlib import Path

# Anonymous homepage HTML is shared across all visitors (cookie-independent).
# Django's cache_page keys on Vary: Cookie, so Locust/session cookies bust it under load.
HOME_ANON_HTML_CACHE_KEY = 'home:anon:html:v1'
HOME_ANON_HTML_CACHE_TTL = 900  # 15 minutes
HOME_ANON_HTML_LOCK_KEY = 'home:anon:html:lock'
HOME_ANON_HTML_LOCK_TTL = 45

User = get_user_model()


class FreetrailContentMixin:
    """
    Mixin for views that show content with freetrail: guest sees content for
    FREETRAIL_TIME_SECONDS (from .env), then login popup; on popup close without
    login, redirect to back_url. Use for all logged-in content (ebook/vocational/
    extracurricular detail and any other gated content).
    Set freetrail_back_url to a URL name (e.g. 'core:ebook_list') or override
    get_freetrail_back_url(request). In template: wrap main content in
    <div id="freetrail-content-wrap"> and include freetrail_content_gate.html when
    show_freetrail_popup is true.
    """
    freetrail_back_url = None  # e.g. 'core:ebook_list' or reverse result

    def get_freetrail_back_url(self, request):
        if self.freetrail_back_url:
            url = self.freetrail_back_url
            if isinstance(url, str) and (url.startswith('http') or url.startswith('/')):
                return request.build_absolute_uri(url) if url.startswith('/') else url
            return request.build_absolute_uri(reverse(url))
        return request.META.get('HTTP_REFERER') or '/'

    def inject_freetrail_context(self, request, ctx):
        ctx['show_freetrail_popup'] = not request.user.is_authenticated
        ctx['freetrail_seconds'] = getattr(settings, 'FREETRAIL_TIME_SECONDS', 5)
        ctx['back_url'] = self.get_freetrail_back_url(request)
        return ctx


class Home(TemplateView):
    template_name = "template20/home_new.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Cache full HTML for anonymous users with a single shared Redis key.
        Avoids Django cache_page cookie-vary stampede under concurrent load.
        Authenticated users always get a fresh render (header login state).
        """
        if request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        cached_html = cache.get(HOME_ANON_HTML_CACHE_KEY)
        if cached_html is not None:
            response = HttpResponse(cached_html, content_type='text/html; charset=utf-8')
            response['X-Cache'] = 'HIT'
            return response

        got_lock = cache.add(HOME_ANON_HTML_LOCK_KEY, '1', HOME_ANON_HTML_LOCK_TTL)
        if not got_lock:
            # Another worker is rebuilding; wait briefly for shared HTML.
            for _ in range(40):
                time.sleep(0.25)
                cached_html = cache.get(HOME_ANON_HTML_CACHE_KEY)
                if cached_html is not None:
                    response = HttpResponse(cached_html, content_type='text/html; charset=utf-8')
                    response['X-Cache'] = 'HIT-WAIT'
                    return response

        response = super().dispatch(request, *args, **kwargs)
        try:
            if response.status_code == 200 and hasattr(response, 'content'):
                cache.set(HOME_ANON_HTML_CACHE_KEY, response.content, HOME_ANON_HTML_CACHE_TTL)
                response['X-Cache'] = 'MISS'
        except Exception:
            logger.exception('Failed to cache anonymous homepage HTML')
        finally:
            cache.delete(HOME_ANON_HTML_LOCK_KEY)
        return response

    def html_head(self):
        name = 'Every Student, Career Ready'
        return build_html_head(title=name, description=name)

    def _skilllab_featured_courses(self):
        """One query for after-10 / after-12 / after-college cards (BOTH as fallback).

        After-college courses are rare in the catalog (legacy category often unset).
        Fall back to the Career Planning course by slug/name so the third homepage
        card opens a real course detail page instead of the listing.
        """
        cat_10 = choices.SkillLabCourseTypeChoice.after_10_class
        cat_12 = choices.SkillLabCourseTypeChoice.after_12_class
        cat_college = choices.SkillLabCourseTypeChoice.after_college
        cat_both = choices.SkillLabCourseTypeChoice.BOTH
        qs = (
            SkillLabCourse.objects.all()
            .select_related('topic_category')
            .prefetch_related('grades')
            .order_by('id')
        )
        by_cat = {}
        by_slug = {}
        career_planning = None
        for course in qs.filter(category__in=[cat_10, cat_12, cat_college, cat_both]):
            by_cat.setdefault(course.category, course)
            if course.slug:
                by_slug[course.slug] = course
            name_l = (course.name or '').lower()
            if career_planning is None and 'career planning' in name_l:
                career_planning = course

        # Also resolve Career Planning if it was tagged outside the audience set above.
        if career_planning is None:
            career_planning = (
                qs.filter(slug='career-planning').first()
                or qs.filter(name__icontains='career planning').first()
            )

        both = by_cat.get(cat_both)
        after_10 = by_cat.get(cat_10) or both
        after_12 = by_cat.get(cat_12) or both
        after_college = by_cat.get(cat_college)
        if after_college is None:
            # Prefer dedicated Career Planning course for the After College card.
            after_college = by_slug.get('career-planning') or career_planning
        # Avoid showing the same course on two cards when possible.
        used_ids = {c.id for c in (after_10, after_12) if c is not None}
        if after_college is not None and after_college.id in used_ids:
            after_college = (
                qs.exclude(id__in=used_ids)
                .filter(name__icontains='career planning')
                .first()
                or after_college
            )
        return {
            'after_10_course': after_10,
            'after_12_course': after_12,
            'after_college_course': after_college,
        }

    def _career_track_cards(self):
        from django.templatetags.static import static

        clusters = CareerCluster.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE
        ).order_by('name')
        careers_base_url = reverse('careers:career')
        default_svg_icon_url = (
            static('images_new/careers/career-tracks/stem-icon.svg')
            or '/static/images_new/careers/career-tracks/stem-icon.svg'
        )
        career_track_cards = []
        for c in clusters:
            if not c.name:
                continue
            icon_url = (
                getattr(c, 'career_track_icon_s3_url', None)
                or (c.career_track_icon.url if (c.career_track_icon and c.career_track_icon.name) else None)
                or default_svg_icon_url
            )
            career_track_cards.append({
                'label': (c.name or '').strip(),
                'icon_url': icon_url,
                'url': f"{careers_base_url}?mode=view-mode&cluster={c.id}",
            })
        if career_track_cards:
            return career_track_cards

        career_track_specs = [
            ("Agriculture & Environmental Sciences", "agriculture-icon.svg"),
            ("Architecture & Constructions", "architecture-icon.svg"),
            ("Arts, Media & Mass Communication", "avtechnology.svg"),
            ("Business, Management & Administration", "businessmanage-icon.svg"),
            ("Finance, Economics and Statistics", "finance-icon.svg"),
            ("Education And Training", "educationtraining.svg"),
            ("Government Sector, Pub Adm. & Int. Relations", "government-services.svg"),
            ("Engineering & Technology", "eit-icon.svg"),
            ("Information Technology (IT)", "it-icon.svg"),
            ("STEM", "stem-icon.svg"),
            ("Health Science & Medical Services", "health-services.svg"),
            ("Hospitality and Tourism", "tourism-icon.svg"),
            ("Humanities, Social Work & Psychology", "humanities-icon.svg"),
            ("Law and Public Safety", "law-icon.svg"),
            ("Distribution, Transportation & Logistics", "transport.svg"),
            ("Marketing & Sales", "marketing-icon.svg"),
            ("Scientific Research, R & D", "scientific-research.svg"),
            ("Sports, Fitness & Wellness", "sports-icon.svg"),
            ("Fashion, Design & Creativity", "faishion-icon.svg"),
        ]
        for label, icon_name in career_track_specs:
            icon_url = (
                static(f"images_new/careers/career-tracks/{icon_name}")
                or f"/static/images_new/careers/career-tracks/{icon_name}"
            )
            career_track_cards.append({
                'label': label,
                'icon_url': icon_url,
                'url': f"{careers_base_url}?mode=view-mode",
            })
        return career_track_cards

    def _home_video_context(self):
        from core.models import Configuration

        default_home_video = 'https://topteenc.s3.ap-northeast-1.amazonaws.com/media/TopTeen_1080P.mp4'
        home_video_url = (
            Configuration.get('HOME_VIDEO_URL', default=default_home_video, editable=True)
            or default_home_video
            or ''
        ).strip()
        home_video_thumbnail_url = (
            Configuration.get('HOME_VIDEO_THUMBNAIL', default='', editable=True) or ''
        ).strip()
        home_video_embed_url = home_video_url
        home_video_yt_id = ''
        if home_video_url:
            yt_match = re.search(
                r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
                home_video_url,
            )
            if yt_match:
                home_video_yt_id = yt_match.group(1)
                home_video_embed_url = (
                    'https://www.youtube.com/embed/' + home_video_yt_id + '?autoplay=1'
                )
                if not home_video_thumbnail_url:
                    home_video_thumbnail_url = (
                        'https://img.youtube.com/vi/' + home_video_yt_id + '/maxresdefault.jpg'
                    )
        return {
            'home_video_url': home_video_url,
            'home_video_thumbnail_url': home_video_thumbnail_url,
            'home_video_embed_url': home_video_embed_url,
            'home_video_yt_id': home_video_yt_id,
        }

    def get_context(self, request, *args, **kwargs):
        # Only load data used by template20/home_new.html (+ html_head for base).
        ctx = {
            'html_head': self.html_head(),
            'blogs': Blog.get_published_objects()
            .select_related('author', 'category')
            .order_by('-modified')[:3],
            'reviewers': Review.get_published_objects()[:6],
            'career_track_cards': self._career_track_cards(),
        }
        ctx.update(self._skilllab_featured_courses())
        ctx.update(self._home_video_context())
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, args, kwargs))


def privacy_policy(request):
    template_name = 'template20/privacy_policy.html'
    url_key = 'privacy'
    static_page = get_static_page(url_key)
    ctx = {
        'static_page': static_page,
        'html_head': get_static_page_html_head(url_key, 'Privacy Policy', 'Privacy Policy for TopTeen.', request=request),
    }
    from django.urls import reverse
    ctx['breadcrumb'] = get_breadcrumb([{'text': 'Privacy Policy', 'url': reverse('core:privacypolicy')}])
    return render(request, template_name, ctx)

def terms_and_condition(request):
    template_name = 'template20/terms_and_condition.html'
    url_key = 'terms'
    static_page = get_static_page(url_key)
    ctx = {
        'static_page': static_page,
        'html_head': get_static_page_html_head(url_key, 'Terms and Condition', 'Terms and Conditions for TopTeen.', request=request),
    }
    from django.urls import reverse
    ctx['breadcrumb'] = get_breadcrumb([{'text': 'Terms and Condition', 'url': reverse('core:terms&condition')}])
    return render(request, template_name, ctx)


@require_GET
def ref_landing(request):
    """
    Public page that always returns 200. Use with ?ref=TOKEN to test enquiry-source tracking:
    visits here are counted in Page views and Sessions for that EnquirySource.
    """
    return HttpResponse('OK', content_type='text/plain')


@require_GET
def topteen_guide(request):
    """Standalone student platform reference guide (no site header/footer)."""
    ctx = {
        "html_head": build_html_head(
            title="TopTeen Student Platform Reference Guide | Classes 9–12",
            description=(
                "A complete walkthrough of www.topteen.in for Indian school students — "
                "career discovery, assessments, college research, and AI counselling."
            ),
            request=request,
        ),
    }
    return render(request, "template20/topteen_guide.html", ctx)

def validation(request,mobile,email):
    mvalid = r'^\d{3}\d{3}\d{4}$'
    evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    phone=re.match(mvalid,mobile)
    em=re.match(evalid,email)
    if phone or em:
        if phone is None:
            messages.error(request,"Invalid phone number !!")
            return False
        if em is None:
            messages.error(request,"Invalid email !!")
            return False
        else:
            return True
    else:
        messages.error(request,"Invalid phone number and email !!")

def contact_us(request):
    template_name = 'template20/contact_us.html'
    url_key = 'contact'
    static_page = get_static_page(url_key)
    from django.urls import reverse
    from django.middleware.csrf import get_token
    ctx = {'static_page': static_page}
    ctx['breadcrumb'] = get_breadcrumb([{'text': 'Contact Us', 'url': reverse('core:contactus')}])
    ctx['csrf_token'] = get_token(request)
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        full_name = "{} {}".format(first_name, last_name)
        mobile = request.POST.get("mobile")
        email = request.POST.get("email")
        message = request.POST.get("message")
        if full_name and message and validation(request, mobile, email):
            form = Contact(name=full_name, mobile=mobile, email=email, message=message)
            form.save()
            messages.success(request, "Thank you, Your response has been submitted!")
        else:
            messages.error(request, "")
    ctx["html_head"] = get_static_page_html_head(url_key, 'Contact Us', 'Contact TopTeen for career guidance and support.', request=request)
    return render(request, template_name, ctx)


def generated_page_view(request, slug):
    """Serve a GeneratedPage by slug: HTML + CSS + JS in the page div."""
    page = get_object_or_404(GeneratedPage, slug=slug, is_active=True)
    ctx = {
        "page": page,
        "html_head": build_html_head(title=page.title, description=page.title[:160] if page.title else ""),
        "breadcrumb": get_breadcrumb([{"text": page.title, "url": request.path}]),
    }
    return render(request, "template20/generated_page.html", ctx)


def upload(request):
    if request.method == "POST":
        form = ImageUploadModelForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            return HttpResponse(json.dumps({'success': True, 'url': obj.upload.url}), content_type='application/json')
        logger.debug("Upload form errors: %s", form.errors)
    return HttpResponse('')


class AboutUsView(TemplateView):
    template_name = "template20/about_us.html"
    url_key = 'about'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['static_page'] = get_static_page(self.url_key)
        ctx['html_head'] = get_static_page_html_head(
            self.url_key, 'About Us', 'About TopTeen career guidance for students in India.', request=self.request
        )
        from django.urls import reverse
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'About Us', 'url': reverse('core:aboutus')}])
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data(**kwargs))

class AllFaqView(TemplateView):
    template_name ="template20/all_faq.html"
    
    def html_head(self):
        name='FAQ'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        from django.urls import reverse
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'FAQs', 'url': reverse('core:allfaq')}])
        search_faq = request.GET.get('search')
        if search_faq:
            ctx['search_faq']=search_faq
            ctx['heading']=f"Results for '{search_faq}'"
            faq_question=CommonFAQ.get_commonfaq_by_priority().filter( Q(question__icontains=search_faq)).order_by('-modified') 
            ctx['faq_question']=faq_question
        else:
            ctx['search_faq']=""
            ctx['parent_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.parent)
            ctx['student_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.student)
            # SEO: FAQPage schema (all FAQs when not searching)
            all_faqs = list(ctx['parent_faq']) + list(ctx['student_faq'])
            seen = set()
            unique_faqs = []
            for faq in all_faqs:
                if faq.question and faq.question not in seen:
                    seen.add(faq.question)
                    unique_faqs.append({
                        'question': faq.question,
                        'answer': clean_html(faq.answer or '')[:500] or faq.question,
                    })
            ctx['seo_faq_items'] = unique_faqs[:50]  # cap for schema size
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))


class ExtracurricularActivitiesView(TemplateView):
    template_name = "template20/extracurricular_activities.html"
    url_key = "extracurricular-activities"

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = get_page_seo_html_head(
            self.url_key,
            "Extracurricular Activities",
            "Unlock your potential through diverse extracurricular activities that enhance your skills, build character, and create memorable experiences.",
            request=request,
        )
        ctx["breadcrumb"] = get_breadcrumb([{'text': 'Extracurricular Activities', 'url': reverse('core:extracurricular_activities')}])
        # Dynamic categories + activities (admin-managed)
        try:
            from django.db.models import Prefetch
            from core.models import ExtracurricularActivityCategory, ExtracurricularActivity
            from core import choices
            categories = ExtracurricularActivityCategory.objects.filter(
                object_status=choices.ObjectStatus.ACTIVE
            ).order_by("priority", "name").prefetch_related(
                Prefetch(
                    "activities",
                    queryset=ExtracurricularActivity.objects.filter(
                        object_status=choices.ObjectStatus.ACTIVE
                    ).order_by("priority", "name"),
                )
            )
            # Only show categories with at least 1 active activity
            categories = [c for c in categories if c.activities.all()]
            ctx["activity_categories"] = categories
        except Exception:
            ctx["activity_categories"] = []
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class VocationalCoursesView(TemplateView):
    """
    Combined page with tabs for After 10 / After 12.
    """
    template_name = "template20/vocational_courses.html"

    def html_head(self):
        name = "Vocational Courses & Career Tracks"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        from django.db.models import Prefetch
        from core import choices
        from core.models import VocationalCourseCategory, VocationalCourse

        from core.choices import ReasoningArea
        from app.vocational_recommendations import (
            course_ids_for_reasoning_area,
            normalize_reasoning_area_code,
            vocational_level_tab_for_user,
        )

        reasoning_area_code = normalize_reasoning_area_code(request.GET.get('reasoning_area'))
        reasoning_filter_active = False
        reasoning_filter_label = ''
        reasoning_filter_ids_by_tab = {}
        if reasoning_area_code:
            reasoning_filter_active = True
            reasoning_filter_label = ReasoningArea.label(reasoning_area_code)
            for level_slug in ('after-10', 'after-12'):
                reasoning_filter_ids_by_tab[level_slug] = course_ids_for_reasoning_area(
                    reasoning_area_code, level_slug
                )

        default_tab = request.GET.get('tab')
        if default_tab not in ('after-10', 'after-12'):
            default_tab = (
                vocational_level_tab_for_user(request.user)
                if request.user.is_authenticated
                else 'after-10'
            )

        # Subcategory display names and order (tab order: Integrated, B.Voc, Diploma, Certificate)
        VOC_SUBCAT_DISPLAY = {
            "integrated programs": ("Integrated Degree Programs", 1),
            "b.voc programs": ("Bachelor of Vocational Programs", 2),
            "diploma courses": ("Diploma", 3),
            "certificate courses for skill enhancement": ("Certificate", 4),
        }

        def ordered_children_with_display(children_queryset):
            children_list = list(children_queryset)
            used_ids = set()
            out = []
            for _key, (display_name, _order) in VOC_SUBCAT_DISPLAY.items():
                for sub in children_list:
                    if sub.id in used_ids:
                        continue
                    name_lower = sub.name.strip().lower()
                    if _key in name_lower or name_lower in _key:
                        out.append({"sub": sub, "display_name": display_name})
                        used_ids.add(sub.id)
                        break
            for sub in children_list:
                if sub.id not in used_ids:
                    out.append({"sub": sub, "display_name": sub.name})
            return out

        # Load both levels in a single query (with a shared child -> course
        # prefetch) instead of one query per tab, to avoid duplicate
        # category/course queries.
        levels_data = {}
        subcategories_display = {}
        try:
            levels_by_slug = {
                cat.slug: cat
                for cat in VocationalCourseCategory.objects.filter(
                    slug__in=['after-10', 'after-12'],
                    parent__isnull=True,
                    object_status=choices.ObjectStatus.ACTIVE,
                ).prefetch_related(
                    Prefetch(
                        "children",
                        queryset=VocationalCourseCategory.objects.filter(
                            object_status=choices.ObjectStatus.ACTIVE
                        ).order_by("priority", "name").prefetch_related(
                            Prefetch(
                                "courses",
                                queryset=VocationalCourse.objects.filter(
                                    object_status=choices.ObjectStatus.ACTIVE
                                ).order_by("priority", "name"),
                            )
                        ),
                    )
                )
            }
        except Exception:
            levels_by_slug = {}

        for level_slug in ['after-10', 'after-12']:
            level = levels_by_slug.get(level_slug)
            if level:
                levels_data[level_slug] = level
                subcategories_display[level_slug] = ordered_children_with_display(level.children.all())
            else:
                levels_data[level_slug] = None
                subcategories_display[level_slug] = []

        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{'text': 'Vocational Courses', 'url': reverse('core:vocational_courses')}])
        ctx["levels_data"] = levels_data
        ctx["subcategories_display"] = subcategories_display
        ctx["default_tab"] = default_tab
        ctx["active_level"] = levels_data.get(default_tab)
        reasoning_filter_course_ids = []
        if reasoning_filter_active:
            reasoning_filter_course_ids = reasoning_filter_ids_by_tab.get(default_tab, [])

        ctx["reasoning_filter_active"] = reasoning_filter_active
        ctx["reasoning_filter_course_ids"] = reasoning_filter_course_ids
        ctx["reasoning_filter_ids_by_tab"] = reasoning_filter_ids_by_tab
        ctx["reasoning_filter_label"] = reasoning_filter_label
        ctx["reasoning_filter_area"] = reasoning_area_code or ''
        ctx["reasoning_filter_count"] = len(reasoning_filter_course_ids)
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class VocationalCoursesLevelView(TemplateView):
    """
    Redirect to main vocational courses page with appropriate tab selected.
    """
    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        level_slug = kwargs.get("level_slug")
        # Redirect to main page with tab parameter
        return redirect(f"{reverse('core:vocational_courses')}?tab={level_slug}")


class VocationalCourseDetailView(FreetrailContentMixin, TemplateView):
    template_name = "template20/vocational_course_detail.html"
    freetrail_back_url = "core:vocational_courses"

    def get_context(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from core.models import VocationalCourse
        from blog.models import Blog

        from core.accordion_utils import (
            build_vocational_accordion_sections,
            content_json_from_html,
            toc_from_sections,
        )

        course = get_object_or_404(VocationalCourse, pk=kwargs.get("pk"))
        # determine top-level (After 10 / After 12) for back link/breadcrumb
        level = None
        try:
            cat = course.category
            while cat and cat.parent_id:
                cat = cat.parent
            level = cat
        except Exception:
            level = None
        ctx = {}
        ctx["course"] = course
        ctx["level"] = level
        ctx["html_head"] = build_html_head(title=course.name, description=course.name)

        from core import choices as core_choices
        from core.choices import ReasoningArea
        ctx["reasoning_area_labels"] = [
            ReasoningArea.label(area)
            for area in course.reasoning_mappings.filter(
                object_status=core_choices.ObjectStatus.ACTIVE,
            ).order_by("reasoning_area").values_list("reasoning_area", flat=True)
        ]

        content_json = course.content_json if isinstance(course.content_json, dict) else {}
        if not content_json.get("overview") and course.content_html:
            content_json = content_json_from_html(course.content_html, program_title=course.name)

        accordion_sections = build_vocational_accordion_sections(
            course.content_html or "",
            json_sections=content_json.get("sections"),
            section_order=content_json.get("section_order"),
        )
        ctx["course_content_json"] = content_json
        ctx["accordion_sections"] = accordion_sections
        ctx["accordion_toc"] = toc_from_sections(accordion_sections)
        
        # Add latest blogs for the blog section
        try:
            ctx["blogs"] = Blog.get_published_objects().order_by('-created')[:3]
        except Exception:
            ctx["blogs"] = []
        
        def breadcrumb_level_label(name):
            if not name:
                return name
            n = (name or "").strip().lower()
            if n in ("after 10", "after-10"):
                return "After 10th"
            if n in ("after 12", "after-12"):
                return "After 12th"
            return (name or "").strip().title()

        def breadcrumb_text_caps(text):
            if not text:
                return text
            return (text or "").strip().title()

        if level:
            level_label = breadcrumb_level_label(level.name)
            course_label = breadcrumb_text_caps(course.name)
            ctx["breadcrumb"] = get_breadcrumb([
                {"text": "Vocational Courses", "url": reverse("core:vocational_courses")},
                {"text": level_label, "url": f"/vocational-courses/{level.slug}/"},
                {"text": course_label, "url": reverse("core:vocational_course_detail", args=[course.pk])},
            ])
        else:
            course_label = breadcrumb_text_caps(course.name)
            ctx["breadcrumb"] = get_breadcrumb([
                {"text": "Vocational Courses", "url": reverse("core:vocational_courses")},
                {"text": course_label, "url": reverse("core:vocational_course_detail", args=[course.pk])},
            ])
        return self.inject_freetrail_context(request, ctx)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class ExtracurricularActivityDetailView(FreetrailContentMixin, TemplateView):
    template_name = "template20/extracurricular_activity_detail.html"
    freetrail_back_url = "core:extracurricular_activities"

    def get_context(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from core.models import ExtracurricularActivity
        from blog.models import Blog

        activity = get_object_or_404(ExtracurricularActivity, pk=kwargs.get("pk"))
        
        # Get latest blogs for the blog section
        blogs = Blog.get_published_objects().order_by('-created')[:3]
        
        ctx = {}
        ctx["activity"] = activity
        ctx["blogs"] = blogs
        ctx["html_head"] = build_html_head(title=activity.name, description=activity.name)
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Extracurricular Activities", "url": reverse("core:extracurricular_activities")},
            {"text": activity.name, "url": reverse("core:extracurricular_activity_detail", kwargs={"pk": activity.pk})},
        ])
        return self.inject_freetrail_context(request, ctx)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


# Category name (lowercase, normalized) -> entrance-exam icon filename (from reference HTML)
ENTRANCE_TEST_PREP_CATEGORY_IMAGE_MAP = {
    "defence": "defence-icon.png",
    "government job": "govt-job-icon.png",
    "govt. school entrance & scholarship exams": "govt-school-exam.png",
    "independent olympiads": "india-olympiad.png",
    "polytechnic exams": "polytech-exam.png",
    "school admission tests": "school-adm-test.png",
    "agriculture": "Agriculture.png",
    "architecture": "Architecture.png",
    "arts, media and communication": "media-communication.png",
    "business and management": "business-and-management.png",
    "commerce": "Commerce.png",
    "computer applications": "computer-applications.png",
    "defence exams": "defence-exams.png",
    "design": "design.png",
    "education": "education.png",
    "engineering": "engineering.png",
    "finance": "finance.png",
    "government jobs": "government-jobs.png",
    "medicine and health sciences": "medicine-and-health-sciences.png",
    "law": "law.png",
    "marketing and sales": "marketing-and-sales.png",
    "hospitality and tourism": "hospitality-and-tourism.png",
    "olympiads": "olympiads.png",
    "scolarships and fellowships": "scolarships-and-fellowships.png",
    "banking and financial sector exams": "govt-job-icon.png",
    "central government exams": "govt-job-icon.png",
    "design, architecture and fine arts": "india-olympiad.png",
    "education and research sector": "polytech-exam.png",
    "engineering technology and science": "school-adm-test.png",
    "international entrance exams": "school-adm-test.png",
    "management- integrated programs": "school-adm-test.png",
    "medical- pg": "school-adm-test.png",
    "other government exams": "school-adm-test.png",
    "post-graduate law programs": "school-adm-test.png",
    "research and phd programs": "school-adm-test.png",
    "ssc and psc exams": "school-adm-test.png",
}


class EntranceTestPrepListView(TemplateView):
    """Main entrance test prep page: tabs After 10th / After 12th / After Graduation, category cards per tab."""
    template_name = "template20/entrance_test_prep.html"
    url_key = "entrance-test-prep"

    def get_context(self, request, *args, **kwargs):
        from django.db.models import Prefetch
        from core.models import EntranceTestPrepCategory, EntranceTestPrepExam
        ctx = {}
        ctx["html_head"] = get_page_seo_html_head(
            self.url_key,
            "Entrance Exam | Top Teen",
            "Expert guidance and trusted resources to help you confidently prepare for entrance exams after 10th, 12th, or graduation.",
            request=request,
        )
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Home", "url": reverse("core:home")},
            {"text": "Entrance Exam", "url": reverse("core:entrance_test_prep")},
        ])
        ctx["category_image_map"] = ENTRANCE_TEST_PREP_CATEGORY_IMAGE_MAP
        try:
            levels = EntranceTestPrepCategory.objects.filter(
                parent__isnull=True,
                object_status=choices.ObjectStatus.ACTIVE,
            ).order_by("priority", "name").prefetch_related(
                Prefetch(
                    "children",
                    queryset=EntranceTestPrepCategory.objects.filter(
                        object_status=choices.ObjectStatus.ACTIVE
                    ).order_by("priority", "name").prefetch_related(
                        Prefetch(
                            "exams",
                            queryset=EntranceTestPrepExam.objects.filter(
                                object_status=choices.ObjectStatus.ACTIVE
                            ).order_by("priority", "name"),
                        )
                    ),
                )
            )
            ctx["levels"] = list(levels)
            # #region agent log
            try:
                _log_path = "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/.cursor/debug-0cd1d7.log"
                import json
                _per_level = [(getattr(l, "name", ""), l.children.count() if hasattr(l.children, "count") else len(list(l.children.all()))) for l in ctx["levels"]]
                _total_cards = sum(c for _, c in _per_level)
                with open(_log_path, "a") as _f:
                    _f.write(json.dumps({"hypothesisId": "A", "message": "entrance_test_prep cards", "data": {"per_level": _per_level, "total_cards_expected": _total_cards}, "timestamp": __import__("time").time() * 1000}) + "\n")
            except Exception:
                pass
            # #endregion
        except Exception:
            ctx["levels"] = []
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class EntranceTestPrepCategoryView(TemplateView):
    """Exams listing under one category (e.g. After 10 / Defence Related)."""
    template_name = "template20/entrance_test_prep_category.html"

    def get_context(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from core.models import EntranceTestPrepCategory, EntranceTestPrepExam
        level_slug = kwargs.get("level_slug")
        category_slug = kwargs.get("category_slug")
        category = get_object_or_404(
            EntranceTestPrepCategory,
            slug=category_slug,
            parent__slug=level_slug,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        level = category.parent
        exams = EntranceTestPrepExam.objects.filter(
            category=category,
            object_status=choices.ObjectStatus.ACTIVE,
        ).order_by("priority", "name")
        ctx = {}
        ctx["category"] = category
        ctx["level"] = level
        ctx["exams"] = exams
        ctx["html_head"] = build_html_head(
            title=f"{category.name} | Entrance Exam",
            description=f"Comprehensive guidance for {category.name} entrance exams.",
        )
        # Breadcrumb: Home > Entrance Exam > Level (After 10 / After 12 / Graduation) > Category
        _level_tab = {"after-10": "a", "after-12": "b", "graduation": "c"}.get((level.slug or "").lower(), "a")
        _level_url = reverse("core:entrance_test_prep") + "#pills-foundation-" + _level_tab
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Home", "url": reverse("core:home")},
            {"text": "Entrance Exam", "url": reverse("core:entrance_test_prep")},
            {"text": level.name, "url": _level_url},
            {"text": category.name, "url": reverse("core:entrance_test_prep_category", kwargs={"level_slug": level.slug, "category_slug": category.slug})},
        ])
        bookmarked_exam_ids = set()
        if request.user.is_authenticated:
            bookmarked_exam_ids = set(
                EntranceTestPrepExam.objects.filter(
                    shortlist=request.user,
                    object_status=choices.ObjectStatus.ACTIVE,
                ).values_list("id", flat=True)
            )
        ctx["bookmarked_exam_ids"] = bookmarked_exam_ids
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


from core.accordion_utils import (
    count_h2_in_html as _count_h2_in_html,
    filter_blank_sections as _filter_blank_sections,
    icon_for_heading as _icon_for_heading,
    normalize_entrance_exam_sections as _normalize_entrance_exam_sections,
    section_html_is_blank as _section_html_is_blank,
    sections_from_html as _sections_from_content_html,
    strip_heading_numbers as _strip_heading_numbers,
)


def _toc_from_content_html(html_content):
    """Extract h1/h2/h3 from HTML for Quick links sidebar. Returns (toc_list, html_with_ids).
    toc_list: [{"id": str, "text": str, "level": 1|2|3, "icon": str}, ...]
    """
    if not html_content or not html_content.strip():
        return [], html_content
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        toc = []
        used = set()
        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(strip=True)
            if not text:
                continue
            level = int(tag.name[1])
            existing_id = tag.get("id", "").strip()
            if existing_id and existing_id not in used:
                sid = existing_id
            else:
                sid = re.sub(r"[^a-z0-9]+", "-", text.lower())[:80].strip("-") or "section"
                base, c = sid, 1
                while sid in used:
                    sid = f"{base}-{c}"
                    c += 1
            used.add(sid)
            tag["id"] = sid
            toc.append({
                "id": sid,
                "text": text,
                "level": level,
                "icon": _icon_for_heading(text),
            })
        return toc, str(soup)
    except Exception:
        return [], html_content


def build_entrance_test_prep_exam_sections_raw(exam):
    """
    Build accordion section dicts the same way as the public detail view, *before*
    intro-merge and blank filtering. Includes blank content_json rows so admin validation
    can report them.
    """
    sections = []
    if getattr(exam, "content_json", None) and isinstance(exam.content_json, dict):
        raw_sections = exam.content_json.get("sections") or {}
        ordered_keys = exam.content_json.get("section_order") if isinstance(exam.content_json.get("section_order"), list) else []
        iter_keys = []
        for key in ordered_keys:
            if key in raw_sections and key not in iter_keys:
                iter_keys.append(key)
        for key in raw_sections.keys():
            if key not in iter_keys:
                iter_keys.append(key)

        for key in iter_keys:
            data = raw_sections.get(key)
            if not isinstance(data, dict):
                continue
            title = data.get("title") or key.replace("_", " ").title()
            html = data.get("html") or data.get("content") or data.get("body") or ""
            section_id = key.replace(" ", "-").lower()[:80]
            sections.append({
                "section_id": section_id,
                "title": title,
                "content_html": html,
                "icon": _icon_for_heading(title),
            })
    if not sections:
        section_objs = list(exam.sections.order_by("order", "section_id"))
        sections = [
            {
                "section_id": getattr(s, "section_id", f"section-{i}"),
                "title": getattr(s, "title", "Section"),
                "content_html": getattr(s, "content_html", "") or "",
                "icon": _icon_for_heading(getattr(s, "title", "")),
            }
            for i, s in enumerate(section_objs)
        ]
    if not sections and exam.content_html:
        sections = _sections_from_content_html(exam.content_html)
    return sections


class EntranceTestPrepExamDetailView(FreetrailContentMixin, TemplateView):
    """Single exam detail: Quick links sidebar + accordion (sections or single Overview from content_html)."""
    template_name = "template20/entrance_test_prep_exam_detail.html"
    freetrail_back_url = "core:entrance_test_prep"

    def get_context(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from core.models import EntranceTestPrepExam
        exam = get_object_or_404(
            EntranceTestPrepExam,
            slug=kwargs.get("slug"),
            object_status=choices.ObjectStatus.ACTIVE,
        )
        exam = EntranceTestPrepExam.objects.prefetch_related("sections").get(pk=exam.pk)
        category = exam.category
        level = category.parent if category else None
        sections = build_entrance_test_prep_exam_sections_raw(exam)
        sections = _normalize_entrance_exam_sections(sections)
        # Defensive: never render accordion rows with no visible body (merge/edge cases, CKEditor junk)
        sections = [s for s in sections if not _section_html_is_blank(s.get("content_html"))]
        for s in sections:
            s["display_title"] = _strip_heading_numbers(s.get("title") or "")
        toc = [{"id": s["section_id"], "text": s.get("display_title", s.get("title", "")), "level": 2, "icon": s.get("icon", "bx-info-circle")} for s in sections]
        ctx = {}
        ctx["exam"] = exam
        ctx["category"] = category
        ctx["level"] = level
        ctx["sections"] = sections
        ctx["toc"] = toc
        ctx["html_head"] = build_html_head(title=exam.name, description=exam.name)
        # Breadcrumb: Home > Entrance Exam > Level (After 10 / After 12 / Graduation) > Category > Exam
        breadcrumb = [
            {"text": "Home", "url": reverse("core:home")},
            {"text": "Entrance Exam", "url": reverse("core:entrance_test_prep")},
        ]
        if level:
            _level_tab = {"after-10": "a", "after-12": "b", "graduation": "c"}.get((level.slug or "").lower(), "a")
            breadcrumb.append({"text": level.name, "url": reverse("core:entrance_test_prep") + "#pills-foundation-" + _level_tab})
        if level and category:
            breadcrumb.append({"text": category.name, "url": reverse("core:entrance_test_prep_category", kwargs={"level_slug": level.slug, "category_slug": category.slug})})
        breadcrumb.append({"text": exam.name, "url": reverse("core:entrance_test_prep_exam_detail", kwargs={"slug": exam.slug})})
        ctx["breadcrumb"] = get_breadcrumb(breadcrumb)
        ctx["is_exam_bookmarked"] = (
            request.user.is_authenticated
            and exam.shortlist.filter(id=request.user.id).exists()
        )
        return self.inject_freetrail_context(request, ctx)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class CareerPlanningView(TemplateView):
    template_name = "template20/career_planning.html"

    def html_head(self):
        name = "Career Planning Hub"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{"text": "Career Planning", "url": ""}])
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class CareerPlanning4YearView(TemplateView):
    template_name = "template20/career_planning_4_year.html"

    def html_head(self):
        return build_html_head(title="4 Year Course Plan", description="Four-Year Success Plan for Classes 9–12")

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Career Planning", "url": reverse("core:career_planning")},
            {"text": "4 Year Course Plan", "url": ""},
        ])
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class _CareerPlanningClassYearView(TemplateView):
    """Base for class-year career planning pages."""
    year_number = 1
    class_label = "Class 9"
    page_title = "Year 1 - Class 9"
    template_name = "template20/career_planning_class_9.html"

    def html_head(self):
        return build_html_head(title=self.page_title, description="Career planning for " + self.class_label)

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Career Planning", "url": reverse("core:career_planning")},
            {"text": self.page_title, "url": ""},
        ])
        ctx["class_label"] = self.class_label
        ctx["year_number"] = self.year_number
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class CareerPlanningClass9View(_CareerPlanningClassYearView):
    year_number = 1
    class_label = "Class 9"
    page_title = "Year 1 - Class 9"
    template_name = "template20/career_planning_class_9.html"


class CareerPlanningClass10View(_CareerPlanningClassYearView):
    year_number = 2
    class_label = "Class 10"
    page_title = "Year 2 - Class 10"
    template_name = "template20/career_planning_class_10.html"


class CareerPlanningClass11View(_CareerPlanningClassYearView):
    year_number = 3
    class_label = "Class 11"
    page_title = "Year 3 - Class 11"
    template_name = "template20/career_planning_class_11.html"


class CareerPlanningClass12View(_CareerPlanningClassYearView):
    year_number = 4
    class_label = "Class 12"
    page_title = "Year 4 - Class 12"
    template_name = "template20/career_planning_class_12.html"


class EmotionalIntelligencesView(TemplateView):
    """Emotional Intelligences (EQ) landing page. Images from S3 via S3_EQ_IMAGES_BASE_URL or static fallback."""
    template_name = "template20/emotional_intelligences.html"

    def html_head(self):
        return build_html_head(
            title="Emotional Intelligences",
            description="Discover your Emotional Intelligences. EQ shapes relationships, choices, and real-life success—often more than IQ."
        )

    def get_context(self, request, *args, **kwargs):
        from django.templatetags.static import static
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{"text": "Emotional Intelligences", "url": reverse("core:emotional_intelligences")}])
        ctx["login_to_take_url"] = reverse("users:login") + "?next=" + quote(reverse("core:emotional_intelligences_assessment"))
        base = getattr(settings, "S3_EQ_IMAGES_BASE_URL", None)
        if base:
            ctx["eq_images_base"] = base.rstrip("/") + "/"
        else:
            ctx["eq_images_base"] = static("images_new/eq/")  # Add eq assets to static/images_new/eq/ or set S3_EQ_IMAGES_BASE_URL
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class EmotionalIntelligencesAssessmentView(LoginRequiredMixin, TemplateView):
    """Emotional Intelligences (EQ) assessment – 6 levels, 36 statements. Requires login."""
    template_name = "template20/emotional_intelligences_assessment.html"
    login_url = reverse_lazy("users:login")

    def get_back_url(self, request):
        from django.utils.http import url_has_allowed_host_and_scheme

        referer = (request.META.get("HTTP_REFERER") or "").strip()
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            if urlparse(referer).path.rstrip("/") != request.path.rstrip("/"):
                return referer
        return reverse("users:userdashboard")

    def html_head(self):
        return build_html_head(
            title="Emotional Intelligence Assessment",
            description="Take the Emotional Intelligence assessment to understand and strengthen key emotional intelligence skills."
        )

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["back_url"] = self.get_back_url(request)
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Emotional Intelligences", "url": reverse("core:emotional_intelligences")},
            {"text": "Assessment", "url": reverse("core:emotional_intelligences_assessment")},
        ])
        ctx["save_eq_url"] = reverse("core:save_eq_assessment")
        ctx["eq_report_pdf_url"] = reverse("core:eq_report_pdf")
        if getattr(request, "user", None) and request.user.is_authenticated:
            latest = EQAssessmentResult.objects.filter(user=request.user).order_by("-updated_at").first()
            if latest:
                ctx["saved_eq_responses"] = json.dumps(latest.responses)
                from core.eq_scoring import calculate_eq_result, get_subscale_band
                recalc = calculate_eq_result(latest.responses or {})
                subscale_bands = recalc.get("subscale_bands") or {
                    code: get_subscale_band((latest.subscale_scores or {}).get(code, 0))
                    for code in ("SA", "SC", "EM", "CR", "SM", "AC")
                }
                ctx["saved_eq_result"] = json.dumps({
                    "subscale_scores": recalc["subscale_scores"],
                    "subscale_bands": subscale_bands,
                    "ei_total": recalc["ei_total"],
                    "band_label": recalc["band_label"],
                    "band_description": recalc["band_description"],
                    "low_areas": recalc["low_areas"],
                })
        if not ctx.get("saved_eq_responses"):
            ctx["saved_eq_responses"] = "null"
            ctx["saved_eq_result"] = "null"
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class MultipleIntelligencesView(TemplateView):
    """Multiple Intelligences (MI) landing page. Images from S3 via S3_MI_IMAGES_BASE_URL or static fallback."""
    template_name = "template20/multiple_intelligences.html"

    def html_head(self):
        return build_html_head(
            title="Multiple Intelligences",
            description="Discover your Multiple Intelligences. Your learning success comes from understanding the distinct intelligences that shape how your mind thinks and excels."
        )

    def get_context(self, request, *args, **kwargs):
        from django.templatetags.static import static
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{"text": "Multiple Intelligences", "url": reverse("core:multiple_intelligences")}])
        # Login required before starting test: send unauthenticated users to login with next=assessment URL
        ctx["login_to_take_url"] = reverse("users:login") + "?next=" + quote(reverse("core:multiple_intelligences_assessment"))
        # S3 base URL for MI images (upload MI images to this folder in S3). Fallback: static/images_new/mi/
        base = getattr(settings, "S3_MI_IMAGES_BASE_URL", None)
        if base:
            ctx["mi_images_base"] = base.rstrip("/") + "/"
        else:
            ctx["mi_images_base"] = static("images_new/mi/")
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class MultipleIntelligencesAssessmentView(LoginRequiredMixin, TemplateView):
    """Multiple Intelligences / Learning Style Discovery Test (assessment). Requires login."""
    template_name = "template20/multiple_intelligences_assessment.html"
    login_url = reverse_lazy("users:login")

    def get_back_url(self, request):
        from django.utils.http import url_has_allowed_host_and_scheme

        referer = (request.META.get("HTTP_REFERER") or "").strip()
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            if urlparse(referer).path.rstrip("/") != request.path.rstrip("/"):
                return referer
        return reverse("users:userdashboard")

    def html_head(self):
        return build_html_head(
            title="Multiple Intelligences Assessment",
            description="Take the Multiple Intelligences (Learning Style Discovery) assessment to discover how you learn best."
        )

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["back_url"] = self.get_back_url(request)
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Multiple Intelligences", "url": reverse("core:multiple_intelligences")},
            {"text": "Assessment", "url": reverse("core:multiple_intelligences_assessment")},
        ])
        ctx["save_mi_url"] = reverse("core:save_mi_assessment")
        ctx["mi_report_pdf_url"] = reverse("core:mi_report_pdf")
        if getattr(request, "user", None) and request.user.is_authenticated:
            latest = MIAssessmentResult.objects.filter(user=request.user).order_by("-updated_at").first()
            if latest:
                ctx["saved_mi_answers"] = json.dumps(latest.answers)
                ctx["saved_mi_result"] = json.dumps({
                    "counts": latest.counts,
                    "primary_style": latest.primary_style,
                    "style_name": latest.style_name,
                    "style_summary": latest.style_summary,
                })
        if not ctx.get("saved_mi_answers"):
            ctx["saved_mi_answers"] = "null"
            ctx["saved_mi_result"] = "null"
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class FourPillarsOfLearningView(TemplateView):
    template_name = "template20/four_pillars_of_learning.html"

    def html_head(self):
        return build_html_head(
            title="Four Pillars of Learning",
            description="Discover your learning profile with the Four Pillars framework: Learning Preferences, Natural Abilities, Engagement Patterns, and Interest Drivers."
        )

    def get_context(self, request, *args, **kwargs):
        from django.core.files.storage import default_storage
        folder = getattr(settings, 'S3_FOUR_PILLARS_FOLDER', 'four_pillars')
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{"text": "Four Pillars of Learning", "url": ""}])
        # Four Pillars images from S3 bucket (folder in bucket / storage)
        ctx["four_pillar_hero_banner_url"] = default_storage.url(f"{folder}/four-pillar-hero-banner.png")
        ctx["four_pillar_visual_url"] = default_storage.url(f"{folder}/fou-pillar-image.png")
        ctx["four_pillar_icon_1_url"] = default_storage.url(f"{folder}/four-pillar-icon-1.png")
        ctx["four_pillar_icon_2_url"] = default_storage.url(f"{folder}/four-pillar-icon-2.png")
        ctx["four_pillar_icon_3_url"] = default_storage.url(f"{folder}/four-pillar-icon-3.png")
        ctx["four_pillar_icon_4_url"] = default_storage.url(f"{folder}/four-pillar-icon-4.png")
        ctx["four_pillar_success_url"] = default_storage.url(f"{folder}/four-pillar-success.png")
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


# Pillar detail pages (static content from pillar-1.html ... pillar-4.html)
FOUR_PILLARS_PILLAR_CONFIG = {
    1: {
        "title": "Learning Preferences",
        "subtitle_before": "Your ",
        "subtitle_highlight": "Information",
        "subtitle_after": " Processing Blueprint",
        "description": "Your Learning Preferences Pillar reveals how your brain naturally receives, processes, and retains information. Understanding this pillar helps you choose study methods that work WITH your brain, not against it.",
        "assessment_slug": "learning-preferences",
    },
    2: {
        "title": "Natural Abilities",
        "subtitle_before": "Your ",
        "subtitle_highlight": "Talent",
        "subtitle_after": " Foundation",
        "description": "Your Natural Abilities Pillar identifies the subjects and skills where you demonstrate inherent strengths and rapid learning capacity. These are areas where you naturally excel and could potentially build a career.",
        "assessment_slug": "natural-abilities",
    },
    3: {
        "title": "Engagement Patterns",
        "subtitle_before": "Your ",
        "subtitle_highlight": "Motivation and Energy",
        "subtitle_after": " Foundation",
        "description": "Your Engagement Patterns Pillar examines how you naturally combine theoretical learning with practical application. This pillar reveals your optimal approach to skill development and sustained motivation.",
        "assessment_slug": "engagement-patterns",
    },
    4: {
        "title": "Interest Drivers",
        "subtitle_before": "Your ",
        "subtitle_highlight": "Passion and Curiosity",
        "subtitle_after": " Foundation",
        "description": "Your Interest Drivers Pillar identifies the specific areas that naturally energize you and sustain your long-term engagement. These are the topics and activities that make you lose track of time because you're so absorbed in them.",
        "assessment_slug": "interest-drivers",
    },
}


class FourPillarsPillarDetailView(TemplateView):
    """Static pillar detail page (content from pillar-1.html ... pillar-4.html)."""

    def get_template_names(self):
        pillar_number = self.kwargs.get("pillar_number")
        if pillar_number not in FOUR_PILLARS_PILLAR_CONFIG:
            return ["template20/404.html"]
        return [f"template20/four_pillars_pillar_{pillar_number}.html"]

    def get_context_data(self, **kwargs):
        from django.core.files.storage import default_storage
        pillar_number = kwargs.get("pillar_number") or self.kwargs.get("pillar_number")
        if pillar_number not in FOUR_PILLARS_PILLAR_CONFIG:
            return {}
        config = FOUR_PILLARS_PILLAR_CONFIG[pillar_number]
        folder = getattr(settings, 'S3_FOUR_PILLARS_FOLDER', 'four_pillars')
        ctx = super().get_context_data(**kwargs)
        ctx["pillar_number"] = pillar_number
        ctx["pillar_title"] = config["title"]
        ctx["pillar_subtitle_before"] = config.get("subtitle_before", "")
        ctx["pillar_subtitle_highlight"] = config.get("subtitle_highlight", "")
        ctx["pillar_subtitle_after"] = config.get("subtitle_after", "")
        ctx["pillar_description"] = config["description"]
        ctx["assessment_slug"] = config["assessment_slug"]
        ctx["html_head"] = build_html_head(title=config["title"], description=config["description"])
        ctx["breadcrumb"] = get_breadcrumb([
            {"text": "Four Pillars of Learning", "url": reverse("core:four_pillars")},
            {"text": f"Pillar {pillar_number}", "url": ""},
        ])
        # ctx["pillar_icon_url"] = default_storage.url(f"{folder}/four-pillar-icon-{pillar_number}.png")
        ctx["pillar_icon_url"] = default_storage.url(f"{folder}/pillar-one-icon.png")

        hero_name = f"pillar-{pillar_number}-herobanner.png"
        try:
            ctx["pillar_hero_url"] = default_storage.url(f"{folder}/{hero_name}")
        except Exception:
            ctx["pillar_hero_url"] = default_storage.url(f"{folder}/four-pillar-hero-banner.png")
        return ctx

    def get(self, request, *args, **kwargs):
        if self.kwargs.get("pillar_number") not in FOUR_PILLARS_PILLAR_CONFIG:
            from django.http import Http404
            raise Http404("Pillar not found")
        return super().get(request, *args, **kwargs)


FOUR_PILLARS_ASSESSMENT_SLUGS = {
    "learning-preferences": ("Learning Preferences Assessment", "Answer 20 short questions to discover how you learn best. Then view your personalised learning style profile."),
    "natural-abilities": ("Natural Abilities Assessment", "Answer 20 short questions to discover your inherent talents and strengths. Then view your personalised natural abilities profile."),
    "engagement-patterns": ("Engagement Patterns Assessment", "Answer 20 short questions to discover your motivation and energy styles. Then view your personalised engagement profile."),
    "interest-drivers": ("Interest Drivers Assessment", "Answer 20 short questions to discover what captivates your curiosity. Then view your personalised interest profile."),
}

# Per-pillar copy for placeholder, tab label, scoring intro, mixed note, and style card tags (aligned with reference HTML in topteenhtml/html/a/)
FOUR_PILLARS_ASSESSMENT_COPY = {
    "learning-preferences": {
        "lp_placeholder_text": "learning style summary here.",
        "lp_profile_tab_label": "Your Learning Profile Guide",
        "lp_scoring_intro": "Count your responses for each letter:",
        "lp_mixed_note": "Mixed Results: Many learners have a combination of preferences. Look at your top two categories to understand your primary and secondary learning styles.",
        "lp_style_card_tags": {"A": "Deep reading & research", "B": "Hands-on & practical", "C": "Discussion & collaboration", "D": "Organised & visual"},
    },
    "natural-abilities": {
        "lp_placeholder_text": "natural abilities summary here.",
        "lp_profile_tab_label": "Your Natural Abilities Profile Guide",
        "lp_scoring_intro": "Step 1: Count your responses for each letter (A, B, C, D). Step 2: Use the ranges below to determine your profile.",
        "lp_mixed_note": "Dual Profile: 8–12 in two categories = combination (e.g. A+B Strategic Implementer, C+D Inspirational Leader). Balanced: 6–10 across three or more = Adaptive Multi-Talent. See combination profiles below.",
        "lp_style_card_tags": {"A": "Logical & systematic", "B": "Efficient & results-focused", "C": "Interpersonal & emotional intelligence", "D": "Innovative & conceptual"},
    },
    "engagement-patterns": {
        "lp_placeholder_text": "engagement pattern summary and complete results here.",
        "lp_profile_tab_label": "Complete Results Report",
        "lp_scoring_intro": "Step 1: Count your responses for each letter: A (Achievement-Driven), B (Mastery-Oriented), C (Purpose-Driven), D (Variety-Seeking). Step 2: Determine your engagement pattern from the ranges below.",
        "lp_mixed_note": "Dual Engagement Pattern: 8–12 in two categories (e.g. A+B Expert Achiever, C+D Flexible Contributor). Balanced: 6–10 across three or more = combination pattern. Multi-Modal: 5–8 in each = balanced across all four. See combination profiles below.",
        "lp_style_card_tags": {"A": "Results & goal orientation", "B": "Learning & expertise development", "C": "Meaning & impact orientation", "D": "Stimulation & change orientation"},
    },
    "interest-drivers": {
        "lp_placeholder_text": "interest drivers summary and complete results here.",
        "lp_profile_tab_label": "Complete Results Report",
        "lp_scoring_intro": "Step 1: Count your responses for each letter: A (Analytical Interest), B (Technical Interest), C (People Interest), D (Creative Interest). Step 2: Determine your interest driver pattern from the ranges below.",
        "lp_mixed_note": "Dual Interest Driver: 8–12 in two categories (e.g. A+B Research Engineer, C+D Social Innovator). Balanced: 6–10 across three or more = combination pattern. Multi-Domain Curiosity: 5–8 in each = balanced across all four. See combination profiles below.",
        "lp_style_card_tags": {"A": "Data & research curiosity", "B": "Systems & process curiosity", "C": "Human & social curiosity", "D": "Innovation & possibility curiosity"},
    },
}


class FourPillarsAssessmentView(LoginRequiredMixin, TemplateView):
    """Serve one of the four pillar assessments (login required). Option A: one template per pillar."""
    login_url = reverse_lazy("users:login")

    def get_template_names(self):
        slug = self.kwargs.get("pillar_slug", "")
        if slug not in FOUR_PILLARS_ASSESSMENT_SLUGS:
            return ["template20/404.html"]
        return [f"template20/four_pillars_assessment_{slug.replace('-', '_')}.html"]

    def get_context_data(self, **kwargs):
        import os
        slug = kwargs.get("pillar_slug") or getattr(self, "kwargs", {}).get("pillar_slug")
        if slug not in FOUR_PILLARS_ASSESSMENT_SLUGS:
            return {}
        json_slug = slug.replace("-", "_")
        json_path = os.path.join(os.path.dirname(__file__), "four_pillars_assessments", f"{json_slug}.json")
        # Prefer admin-defined assessment from DB when active
        db_assessment = FourPillarsAssessment.objects.filter(slug=slug, is_active=True).prefetch_related(
            "questions__options", "profiles"
        ).first()
        if db_assessment:
            title = db_assessment.title
            subtitle = db_assessment.subtitle or ""
            questions = []
            for q in db_assessment.questions.order_by("order"):
                options = {o.option_key: o.text for o in q.options.all()}
                questions.append({"title": q.title, "text": q.text, "options": options})
            profiles = {}
            for p in db_assessment.profiles.all():
                profiles[p.option_key] = {
                    "name": p.name,
                    "summary": p.summary or "",
                    "scoring_heading": p.scoring_heading or "",
                    "scoring_bullets": list(p.scoring_bullets) if p.scoring_bullets else [],
                }
            data = {
                "questions": questions,
                "profiles": profiles,
                "scoring_intro": db_assessment.scoring_intro or "",
                "mixed_results": db_assessment.mixed_results or "",
            }
        else:
            title, subtitle = FOUR_PILLARS_ASSESSMENT_SLUGS[slug]
            data = {}
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            questions = data.get("questions", [])
            profiles = data.get("profiles", {})
        ctx = super().get_context_data(**kwargs)
        ctx["assessment_title"] = title
        ctx["assessment_subtitle"] = subtitle
        ctx["questions"] = questions
        ctx["profiles"] = profiles
        ctx["questions_json"] = json.dumps(questions)
        ctx["profiles_json"] = json.dumps(profiles)
        ctx["html_head"] = build_html_head(title=title, description=subtitle)
        ctx["assessment_submit_url"] = reverse("core:four_pillars_assessment_submit", kwargs={"pillar_slug": slug})
        ctx["pillar_slug"] = slug
        # Full "Understanding" accordion (Primary + Combination + Maximizing): use static include when generated
        understanding_include_path = os.path.join(settings.BASE_DIR, "templates", "template20", "includes", f"{json_slug}_understanding_guide.html")
        ctx["understanding_guide_include"] = f"template20/includes/{json_slug}_understanding_guide.html" if os.path.exists(understanding_include_path) else None
        # Fallback: understanding_data JSON (primary_profiles only) when no static include
        understanding_path = os.path.join(os.path.dirname(__file__), "four_pillars_assessments", f"{json_slug}_understanding_data.json")
        ctx["understanding_data"] = None
        if os.path.exists(understanding_path):
            try:
                with open(understanding_path, "r", encoding="utf-8") as f:
                    ctx["understanding_data"] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        copy = FOUR_PILLARS_ASSESSMENT_COPY.get(slug, {})
        ctx["lp_placeholder_text"] = copy.get("lp_placeholder_text", "summary here.")
        ctx["lp_profile_tab_label"] = copy.get("lp_profile_tab_label", "Your Learning Profile Guide")
        ctx["lp_scoring_intro"] = data.get("scoring_intro") or copy.get("lp_scoring_intro", "Count your responses for each letter:")
        ctx["lp_mixed_note"] = data.get("mixed_results") or copy.get("lp_mixed_note", "Mixed Results: Many learners have a combination of preferences. Look at your top two categories to understand your primary and secondary styles.")
        ctx["lp_style_card_tags"] = copy.get("lp_style_card_tags") or {"A": "Style A", "B": "Style B", "C": "Style C", "D": "Style D"}
        saved_result = None
        if getattr(self.request, "user", None) and self.request.user.is_authenticated:
            r = FourPillarsAssessmentResult.objects.filter(
                user=self.request.user, pillar_slug=slug
            ).order_by("-updated_at").first()
            if r:
                saved_result = {
                    "answers": r.answers,
                    "counts": r.counts,
                    "primary_style": r.primary_style,
                    "profile_name": r.profile_name,
                    "profile_summary": r.profile_summary or "",
                }
        ctx["saved_result"] = saved_result
        ctx["saved_result_json"] = json.dumps(saved_result) if saved_result else "null"
        # Debug: log to server console when each assessment page is served
        profile_keys = list(profiles.keys()) if profiles else []
        scoring_bullets = {k: len(profiles.get(k, {}).get("scoring_bullets", [])) for k in ("A", "B", "C", "D")} if profiles else {}
        source = "db" if db_assessment else "json"
        msg = (
            f"[Four Pillars] slug={slug!r} title={title!r} questions={len(questions)} "
            f"profiles={profile_keys} source={source} scoring_bullets={scoring_bullets}"
        )
        logger.info("%s", msg)
        return ctx

    def get(self, request, *args, **kwargs):
        if self.kwargs.get("pillar_slug") not in FOUR_PILLARS_ASSESSMENT_SLUGS:
            from django.http import Http404
            raise Http404("Assessment not found")
        return super().get(request, *args, **kwargs)


@require_http_methods(["POST"])
def four_pillars_assessment_submit(request, pillar_slug):
    """Save or update the latest assessment result for the current user. Requires login. Returns 200 or 401."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)
    if pillar_slug not in FOUR_PILLARS_ASSESSMENT_SLUGS:
        return JsonResponse({"error": "Invalid assessment"}, status=400)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    answers = body.get("answers")
    counts = body.get("counts")
    primary = body.get("primary")
    profile_name = body.get("profile_name", "")
    profile_summary = body.get("profile_summary", "")
    if not isinstance(answers, dict) or not isinstance(counts, dict) or primary not in ("A", "B", "C", "D"):
        return JsonResponse({"error": "Missing or invalid answers/counts/primary"}, status=400)
    # Normalize answers: keys as string indices
    answers = {str(k): str(v) for k, v in answers.items() if str(v) in ("A", "B", "C", "D")}
    counts = {k: int(v) for k, v in counts.items() if k in ("A", "B", "C", "D")}
    FourPillarsAssessmentResult.objects.update_or_create(
        user=request.user,
        pillar_slug=pillar_slug,
        defaults={
            "answers": answers,
            "primary_style": primary,
            "counts": counts,
            "profile_name": profile_name,
            "profile_summary": profile_summary,
        },
    )
    return JsonResponse({"status": "ok"})


class EbookListView(TemplateView):
    template_name = "template20/ebook.html"

    def html_head(self):
        name = "E-Books | Top Teen"
        return build_html_head(title=name, description="Explore our collection of career guidance e-books")

    def get_context(self, request, *args, **kwargs):
        from django.core.files.storage import default_storage
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = get_breadcrumb([{"text": "E-Books", "url": reverse("core:ebook_list")}])
        # Ebook hero banner: use storage so URL is correct on production (S3 proxy/direct) and demo (local media)
        ctx["ebook_hero_banner_url"] = default_storage.url("ebooks/ebook-hero-img.png")
        # Get published ebooks from database
        ebooks = Ebook.get_published_ebooks()
        ctx["ebooks"] = []
        for ebook in ebooks:
            # Ensure slug exists (should be auto-generated, but double-check)
            if not ebook.slug:
                ebook.save()  # This will generate the slug
            ebook_data = {
                "id": ebook.id,
                "title": ebook.title,
                "slug": ebook.slug,
                "cover": ebook.get_cover_url(),
                "pdf": ebook.get_pdf_url()
            }
            ctx["ebooks"].append(ebook_data)
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class EbookDetailView(FreetrailContentMixin, TemplateView):
    template_name = "template20/flip-book.html"
    freetrail_back_url = "core:ebook_list"

    def html_head(self):
        name = "E-Book Reader | Top Teen"
        return build_html_head(title=name, description="Read our interactive career guidance e-book")

    def get(self, request, *args, **kwargs):
        from django.http import Http404, HttpResponseRedirect
        
        # Check if slug is missing but query parameters are present (backward compatibility)
        slug = kwargs.get('slug')
        if not slug:
            # Try to redirect from old query parameter format to slug-based URL
            ebook_id = request.GET.get('id')
            pdf_path = request.GET.get('pdf')
            title = request.GET.get('title')
            
            if ebook_id:
                try:
                    ebook = Ebook.objects.get(id=ebook_id, publish_status=choices.PublishStatus.PUBLISHED)
                    # Ensure slug exists
                    if not ebook.slug:
                        ebook.save()
                    # Redirect to slug-based URL
                    return HttpResponseRedirect(reverse('core:ebook_detail', kwargs={'slug': ebook.slug}))
                except Ebook.DoesNotExist:
                    raise Http404("Ebook not found")
            elif pdf_path and title:
                # Try to find ebook by PDF URL or title
                try:
                    ebook = Ebook.objects.filter(
                        pdf_file_s3_url=pdf_path,
                        publish_status=choices.PublishStatus.PUBLISHED
                    ).first()
                    if not ebook:
                        # Try by title
                        ebook = Ebook.objects.filter(
                            title=title,
                            publish_status=choices.PublishStatus.PUBLISHED
                        ).first()
                    if ebook:
                        if not ebook.slug:
                            ebook.save()
                        return HttpResponseRedirect(reverse('core:ebook_detail', kwargs={'slug': ebook.slug}))
                    else:
                        raise Http404("Ebook not found")
                except:
                    raise Http404("Ebook not found")
            else:
                raise Http404("Ebook slug is required")
        
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

    def get_context(self, request, *args, **kwargs):
        from django.http import Http404
        
        ctx = {}
        ctx["html_head"] = self.html_head()
        
        # Get ebook by slug from URL
        slug = kwargs.get('slug')
        if not slug:
            raise Http404("Ebook slug is required")
        
        # Get ebook by slug
        try:
            ebook = Ebook.objects.get(slug=slug, publish_status=choices.PublishStatus.PUBLISHED)
            ctx["pdf_path"] = ebook.get_pdf_url()
            ctx["ebook_title"] = ebook.title
            ctx["breadcrumb"] = get_breadcrumb([{"text": "E-Books", "url": reverse("core:ebook_list")}, {"text": ebook.title, "url": ""}])
        except Ebook.DoesNotExist:
            raise Http404("Ebook not found")
        
        return self.inject_freetrail_context(request, ctx)


class SearchItems(TemplateView):
    template_name="topteenfrontend/searchandexplore.html"
    def html_head(self):
        name='EXPLORE CAREER'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        try:
            careeritems=CareerDocumentFilter()
            ctx['car']=careeritems.get_career_list_context(request)
        except Exception as e:
            logger.warning("Elasticsearch not available for careers, using Django ORM fallback: %s", e)
            ctx['car'] = {'careers': [], 'facets_filter': {'skill': [], 'profession': []}, 'shortlisted_career_ids': []}
        
        try:
            examitems=EntranceExamDocumentFilter()
            ctx['exm']=examitems.get_entrance_exam_list_context(request)
        except Exception as e:
            logger.warning("Elasticsearch not available for exams, using Django ORM fallback: %s", e)
            ctx['exm'] = {'exams': [], 'facets_filter': {}}
        
        ctx['videoscount']=Videos.objects.all().count()
        ctx['col']=College.get_all_colleges().count()
        ctx['coursecount']=Course.objects.all().count()
        ctx['most_searchcareers'] = Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).order_by('?')[:8]
        ctx['most_searchcolleges'] = College.objects.all().order_by('id')[:5]
        ctx['tranding_content']=Blog.objects.all()
        ctx["html_head"] = self.html_head()
        
        return ctx
    
    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))
    
class AjaxSearchResult(TemplateView):
    template_name="template20/search_results.html"
    def html_head(self,request):
        name=request.GET.get('search')
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        ctx={} 
        input=request.GET.get('search') or ''

        clf=AllSearch()
        search_results = clf.get_ajax_search_Item_list(request,input)
        ctx['allsearch'] = search_results if search_results else {}
        ctx["html_head"] = self.html_head(request)
        ctx['searchname']=input
        # Get trending blogs related to search term if search exists, otherwise get all trending
        from core import choices
        if input:
            related_blogs = Blog.objects.filter(
                Q(title__icontains=input) | Q(summary__icontains=input),
                publish_status=choices.PublishStatus.PUBLISHED
            )[:6]
            # If no related blogs found, show general trending
            related_count = related_blogs.count()
            if related_count > 0:
                ctx['tranding_content'] = related_blogs
            else:
                ctx['tranding_content'] = Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)[:6]
        else:
            ctx['tranding_content'] = Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)[:6]
        ctx['user'] = request.user
        
        # Build breadcrumb
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Search Results', 'url': ''}])

        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

class AjaxRecommandedSearchCollege(TemplateView):
    template_name ="topteenfrontend/includes/recommendedsearch.html"

    def get_context(self,request,*args, **kwargs):
        ctx={} 
        clf=AllSearch()
        ctx['colleges']=clf.get_ajax_search_Item_list(request)
        ctx['user'] = request.user
        return ctx

    def get(self, request,*args, **kwargs):
        html = render_to_string(self.template_name,self.get_context(request, *args, **kwargs))
        return HttpResponse(html)
    
class LeadData(APIView):
    def post(self,request,*args,**kwargs):
        name=request.POST.get("lead_name")
        mobile=request.POST.get("lead_mobile")
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        phone=re.match(mvalid,mobile)
        lead_exist=Lead.objects.filter(mobile=mobile).exists()
        if name and phone:
            if not lead_exist:
                lead_data=Lead(name=name,mobile=mobile)
                lead_data.save()
            # Return success even if phone number already exists
            response={"success":"true","message":"Thank you for connecting with us!"}
        else:
            response={"success":"false","message":"Please Enter the Correct Phone number!"}
        return JsonResponse(response)

def deletehistory(request):
    clr=UserSearchHistory.objects.filter(user=request.user)
    clr.delete() 
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


def page404(request,exception):
    ctx={}
    ctx["html_head"] = build_html_head(title="404 | Error")
    return render(request,"template20/404.html",ctx)


def career_battle_wrapper(request):
    """
    Career Battle page with main site header and footer. Uses same session as the rest of the site.
    The game itself is loaded in an iframe from /career-battle/app/ so it shares the same auth cookie.
    """
    ctx = {
        'html_head': build_html_head(title='Career Battle', description='Compare streams and courses with Career Battle'),
        'body_css_class': 'no-scrollbar overflow-x-hidden',
    }
    return render(request, 'template20/career_battle_wrapper.html', ctx)


def serve_game_spa(request, path=None):
    """
    Serve the React game SPA (Career Battle) at /career-battle/app/ on our domain.
    Assets are served by Django at /static/game/assets/... (from Vite build with base: '/static/game/').
    Same-origin iframe ensures the game receives the same session cookie as the main site.
    """
    from django.http import Http404, HttpResponse
    index_name = 'index.html'
    # Prefer collectstatic output (production), else dev static dir
    for base in [settings.STATIC_ROOT, os.path.join(settings.BASE_DIR, 'static')]:
        if not base:
            continue
        index_path = os.path.join(base, 'game', index_name)
        if os.path.isfile(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                return HttpResponse(f.read(), content_type='text/html; charset=utf-8')
    raise Http404('Game not built. Run: cd react-game/react-game && npm run build')


def _career_battle_stream_counts(request):
    """Return count of streams per source (for showing only options that have data)."""
    from careers.models import CareerShortlist
    from core.models import CareerBattleFight

    user = getattr(request, 'user', None)
    published = choices.PublishStatus.PUBLISHED
    out = {}

    # past_battles
    n = 0
    if user and user.is_authenticated:
        fights = CareerBattleFight.objects.filter(user=user).order_by('-created')[:100]
        seen = set()
        for f in fights:
            for s in (f.streams or []):
                if s and isinstance(s, str) and s.strip() and s.strip() not in seen:
                    seen.add(s.strip())
                    n += 1
    out['past_battles'] = n

    # shown_interest
    n = 0
    if user and user.is_authenticated:
        fights = CareerBattleFight.objects.filter(user=user).order_by('-created')[:100]
        seen = set()
        for f in fights:
            winner = (f.result or {}).get('winner') if isinstance(f.result, dict) else None
            if winner and isinstance(winner, str) and winner.strip() and winner.strip() not in seen:
                seen.add(winner.strip())
                n += 1
    out['shown_interest'] = n

    # psychometric
    n = 0
    if user and user.is_authenticated:
        try:
            from psychometric_tests.models import CentralTestCandidate, CandidateTest
            cand = getattr(user, 'central_test_candidate', None) or CentralTestCandidate.objects.filter(user=user).first()
            if cand:
                test = getattr(cand, 'candidate_test', None)
                if test is None:
                    test = CandidateTest.objects.filter(central_test_candidate=cand).order_by('-id').first()
                if test and getattr(test, 'psychometric_test_results', None):
                    res = test.psychometric_test_results
                    key = res.get_sort_form_riasec() if hasattr(res, 'get_sort_form_riasec') else None
                    if key:
                        n = Career.objects.filter(riasec_career__key=key).exclude(publish_status=choices.PublishStatus.DRAFT).count()
        except Exception:
            pass
    out['psychometric'] = n

    # shortlist
    n = 0
    if user and user.is_authenticated:
        try:
            n = CareerShortlist.objects.filter(user=user).filter(career__isnull=False).count()
        except Exception:
            pass
    out['shortlist'] = n

    # all_clusters (always include so game is always playable)
    n = 0
    clusters_qs = CareerCluster.objects.filter(
        object_status=choices.ObjectStatus.ACTIVE,
        career_clusters__publish_status=published,
    ).distinct()
    for cluster in clusters_qs:
        n += Career.objects.filter(career_cluster=cluster, publish_status=published).count()
    out['all_clusters'] = n

    return out


def career_battle_stream_sources_api(request):
    """
    GET: Return streams (career names) by source for Career Battle.
    Query params:
      available=1: return { available: { past_battles: n, ... } } (counts per source; show only options with n>0).
      sources=a,b,c: return { by_source: {...}, streams: [] } (streams = unique combined list).
    """
    from careers.models import CareerShortlist
    from core.models import CareerBattleFight

    if request.GET.get('available') == '1':
        counts = _career_battle_stream_counts(request)
        return JsonResponse({'available': counts})

    allowed = {'past_battles', 'shown_interest', 'psychometric', 'shortlist', 'all_clusters'}
    raw = (request.GET.get('sources') or '').strip()
    sources = [s.strip() for s in raw.split(',') if s.strip() and s.strip() in allowed]
    if not sources:
        return JsonResponse({'by_source': {}, 'streams': []})

    by_source = {}
    user = getattr(request, 'user', None)
    published = choices.PublishStatus.PUBLISHED

    if 'past_battles' in sources:
        names = []
        if user and user.is_authenticated:
            fights = CareerBattleFight.objects.filter(user=user).order_by('-created')[:100]
            for f in fights:
                for s in (f.streams or []):
                    if s and isinstance(s, str) and s.strip():
                        names.append(s.strip())
        by_source['past_battles'] = list(dict.fromkeys(names))

    if 'shown_interest' in sources:
        names = []
        if user and user.is_authenticated:
            fights = CareerBattleFight.objects.filter(user=user).order_by('-created')[:100]
            for f in fights:
                winner = (f.result or {}).get('winner') if isinstance(f.result, dict) else None
                if winner and isinstance(winner, str) and winner.strip():
                    names.append(winner.strip())
        by_source['shown_interest'] = list(dict.fromkeys(names))

    if 'psychometric' in sources:
        names = []
        if user and user.is_authenticated:
            try:
                from psychometric_tests.models import CentralTestCandidate, PsychometricTestResult
                cand = getattr(user, 'central_test_candidate', None)
                if cand is None:
                    try:
                        cand = CentralTestCandidate.objects.filter(user=user).first()
                    except Exception:
                        cand = None
                if cand:
                    test = getattr(cand, 'candidate_test', None)
                    if test is None:
                        try:
                            from psychometric_tests.models import CandidateTest
                            test = CandidateTest.objects.filter(central_test_candidate=cand).order_by('-id').first()
                        except Exception:
                            test = None
                    if test and getattr(test, 'psychometric_test_results', None):
                        res = test.psychometric_test_results
                        key = res.get_sort_form_riasec() if hasattr(res, 'get_sort_form_riasec') else None
                        if key:
                            careers_qs = Career.objects.filter(
                                riasec_career__key=key
                            ).exclude(publish_status=choices.PublishStatus.DRAFT).values_list('name', flat=True).distinct()
                            names = list(careers_qs)
            except Exception:
                pass
        by_source['psychometric'] = list(dict.fromkeys(names))

    if 'shortlist' in sources:
        names = []
        if user and user.is_authenticated:
            try:
                shortlists = CareerShortlist.objects.filter(user=user).select_related('career')
                for sl in shortlists:
                    if sl.career and getattr(sl.career, 'name', None):
                        names.append(sl.career.name.strip())
            except Exception:
                pass
        by_source['shortlist'] = list(dict.fromkeys(names))

    if 'all_clusters' in sources:
        names = []
        clusters_qs = CareerCluster.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE,
            career_clusters__publish_status=published,
        ).distinct().order_by('name')
        for cluster in clusters_qs:
            cluster_names = list(
                Career.objects.filter(
                    career_cluster=cluster,
                    publish_status=published,
                ).values_list('name', flat=True).order_by('name').distinct()
            )
            names.extend(n for n in cluster_names if n and isinstance(n, str))
        by_source['all_clusters'] = list(dict.fromkeys(names))

    combined = []
    for key in sources:
        combined.extend(by_source.get(key, []))
    streams = list(dict.fromkeys(combined))

    return JsonResponse({'by_source': by_source, 'streams': streams})


def career_battle_shortlist_career_api(request):
    """
    POST: Add the given career (by name) to the logged-in user's shortlist.
    Body: JSON { "career_name": "Architectural Engineer" }.
    Returns: { "ok": true, "message": "Added to shortlist" } or 400/401.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    career_name = (body.get('career_name') or '').strip()
    if not career_name:
        return JsonResponse({'ok': False, 'error': 'career_name required'}, status=400)
    from careers.models import CareerShortlist
    published = choices.PublishStatus.PUBLISHED
    career = Career.objects.filter(
        name__iexact=career_name,
        publish_status=published,
    ).first()
    if not career:
        career = Career.objects.filter(name=career_name, publish_status=published).first()
    if not career:
        return JsonResponse({'ok': False, 'error': 'Career not found'}, status=404)
    CareerShortlist.objects.get_or_create(user=request.user, career=career)
    return JsonResponse({'ok': True, 'message': 'Added to shortlist'})


def career_battle_clusters_api(request):
    """
    JSON API for Career Battle game: career clusters and their careers (streams) from DB.
    Same-origin iframe sends cookies, so request.user is the main site user.
    Optional: filter clusters/careers by user (e.g. class, preferences) in the future.
    """
    published = choices.PublishStatus.PUBLISHED
    # Clusters that have at least one published career (directly)
    clusters_qs = CareerCluster.objects.filter(
        object_status=choices.ObjectStatus.ACTIVE,
        career_clusters__publish_status=published,
    ).distinct().order_by('name')
    out = {}
    for cluster in clusters_qs:
        names = list(
            Career.objects.filter(
                career_cluster=cluster,
                publish_status=published,
            ).values_list('name', flat=True).order_by('name').distinct()
        )
        if names:
            # Use cluster name as key; if duplicate name, merge lists (last wins for simplicity)
            key = (cluster.name or '').strip() or f'Cluster_{cluster.id}'
            out[key] = names
    return JsonResponse({
        'clusters': out,
        'user': {
            'is_authenticated': request.user.is_authenticated,
            'id': getattr(request.user, 'id', None),
        } if hasattr(request, 'user') else {'is_authenticated': False, 'id': None},
    })


def career_battle_fights_api(request):
    """
    GET: List current user's fight history (newest first).
    POST: Save a new fight (requires auth). Body: title, cluster_name?, streams, parameters, result.
    """
    if request.method == 'GET':
        if not request.user.is_authenticated:
            return JsonResponse({'fights': []})
        fights = CareerBattleFight.objects.filter(user=request.user).order_by('-created')[:50]
        out = [
            {
                'id': f.id,
                'title': f.title,
                'cluster_name': f.cluster_name or '',
                'streams': f.streams,
                'winner': (f.result or {}).get('winner'),
                'created': f.created.isoformat() if f.created else None,
            }
            for f in fights
        ]
        return JsonResponse({'fights': out})

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login required to save fight history'}, status=401)
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        streams = body.get('streams')
        result = body.get('result') or {}
        if not streams or len(streams) != 2:
            return JsonResponse({'error': 'streams must be [stream1, stream2]'}, status=400)
        title = (body.get('title') or '').strip() or f"{streams[0]} vs {streams[1]}"
        cluster_name = (body.get('cluster_name') or '').strip()
        parameters = body.get('parameters')
        if parameters is None:
            parameters = []
        fight = CareerBattleFight.objects.create(
            user=request.user,
            title=title[:255],
            cluster_name=cluster_name[:255],
            streams=streams,
            parameters=parameters,
            result=result,
        )
        return JsonResponse({'id': fight.id, 'title': fight.title})


def career_battle_eligibility_profile_api(request):
    """
    GET: Return logged-in user's student/profile info for Course Eligibility form.
    Includes grade so frontend can show the form only for class 10 and above.
    POST: Update saved eligibility (education_background, stream, specific_area, study_location).
    """
    from core.models import _normalize_grade, CareerBattleEligibilityProfile

    out = {
        'grade': None,
        'education_background': None,
        'stream': None,
        'specific_area': None,
        'study_location': None,
    }
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return JsonResponse({'profile': out})

    user = request.user
    grade = None
    stream = None

    try:
        from users.models import UserProfile
        profile = getattr(user, 'user_profile', None)
        if profile is None:
            try:
                profile = UserProfile.objects.get(user=user)
            except Exception:
                profile = None
        if profile and getattr(profile, 'grade', None):
            grade = _normalize_grade(profile.grade)
    except Exception:
        pass

    try:
        from institute.models import StudentManagement
        sm = StudentManagement.objects.filter(student=user).select_related('class_and_section').first()
        if sm and sm.class_and_section:
            cas = sm.class_and_section
            if getattr(cas, 'stream', None):
                stream = (cas.stream or '').strip()
            if not grade and getattr(cas, 'class_and_section', None):
                cs = (cas.class_and_section or '').strip()
                grade = _normalize_grade(cs)
    except Exception:
        pass

    # Saved eligibility profile (from previous "Update profile" choice)
    try:
        eb_profile = CareerBattleEligibilityProfile.objects.filter(user=user).first()
        if eb_profile:
            if eb_profile.education_background:
                out['education_background'] = eb_profile.education_background
            if eb_profile.stream:
                out['stream'] = eb_profile.stream
            if eb_profile.specific_area:
                out['specific_area'] = eb_profile.specific_area
            if eb_profile.study_location:
                out['study_location'] = eb_profile.study_location
    except Exception:
        pass

    # From UserProfile/StudentManagement: set education_background and stream if not from saved
    if not out['education_background'] and grade and grade in ('12', '11'):
        out['education_background'] = '12th'
    if not out['stream'] and stream:
        for key in ('Medical', 'Non-Medical', 'Arts', 'Commerce'):
            if key.lower() in stream.lower() or stream.lower() in key.lower():
                out['stream'] = key
                break
        if not out['stream'] and stream:
            out['stream'] = stream

    out['grade'] = grade

    if request.method == 'POST':
        # Update saved eligibility profile (after user confirmed in popup)
        try:
            import json
            body = json.loads(request.body) if request.body else {}
            education_background = (body.get('education_background') or '').strip() or None
            stream = (body.get('stream') or '').strip() or None
            specific_area = (body.get('specific_area') or '').strip() or None
            study_location = (body.get('study_location') or '').strip() or None
            eb_profile, _ = CareerBattleEligibilityProfile.objects.get_or_create(
                user=user,
                defaults={
                    'education_background': education_background or '',
                    'stream': stream or '',
                    'specific_area': specific_area or '',
                    'study_location': study_location or '',
                }
            )
            if education_background is not None:
                eb_profile.education_background = education_background or ''
            if stream is not None:
                eb_profile.stream = stream or ''
            if specific_area is not None:
                eb_profile.specific_area = specific_area or ''
            if study_location is not None:
                eb_profile.study_location = study_location or ''
            eb_profile.save()
            return JsonResponse({'ok': True})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    return JsonResponse({'profile': out})


def s3_media_proxy(request, path):
    """
    Serve S3 media through Django so only your website can show the file.
    Used when S3_MEDIA_ACCESS_MODE is 'proxy'. Bucket stays private.
    """
    from urllib.parse import unquote
    from django.http import HttpResponse, HttpResponseNotFound
    import boto3
    from botocore.exceptions import ClientError

    if not path or '..' in path:
        return HttpResponseNotFound('Not found')

    path = unquote(path).lstrip('/')
    location = getattr(settings, 'S3_MEDIA_LOCATION', 'media')
    bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    if not bucket_name:
        return HttpResponseNotFound('Not configured')

    # Try keys: with location prefix (current storage), then without (legacy uploads)
    if location:
        s3_keys_to_try = [f'{location.rstrip("/")}/{path}', path]
    else:
        s3_keys_to_try = [path]

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''),
            region_name=getattr(settings, 'AWS_REGION', 'ap-northeast-1'),
        )
    except Exception as e:
        if settings.DEBUG:
            raise
        return HttpResponseNotFound('Not configured')

    response = None
    for s3_key in s3_keys_to_try:
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            break
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                continue
            if settings.DEBUG:
                raise
            return HttpResponseNotFound('Not found')
        except Exception:
            if settings.DEBUG:
                raise
            return HttpResponseNotFound('Not found')

    if response is None:
        return HttpResponseNotFound('Not found')

    body = response['Body']
    content_type = response.get('ContentType') or 'application/octet-stream'
    content_length = response.get('ContentLength')

    out = HttpResponse(body.read(), content_type=content_type)
    if content_length is not None:
        out['Content-Length'] = content_length
    out['Cache-Control'] = 'private, max-age=3600'
    return out


# ----- MI / EQ assessment save and PDF report -----

@require_POST
def save_mi_assessment(request):
    """Save MI assessment result for the current user. Requires login."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required to save."}, status=401)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
    answers = data.get("answers")
    counts = data.get("counts")
    primary_style = data.get("primary_style")
    style_name = data.get("style_name")
    style_summary = data.get("style_summary", "")
    if not isinstance(answers, dict) or not isinstance(counts, dict) or not primary_style or not style_name:
        return JsonResponse({"ok": False, "error": "Missing or invalid fields."}, status=400)
    # Normalize answers keys to string (0..59)
    answers = {str(k): v for k, v in answers.items() if str(v) in ("A", "B", "C", "D")}
    if len(answers) != 60:
        return JsonResponse({"ok": False, "error": "All 60 questions must be answered."}, status=400)
    MIAssessmentResult.objects.create(
        user=request.user,
        answers=answers,
        counts={"A": int(counts.get("A", 0)), "B": int(counts.get("B", 0)), "C": int(counts.get("C", 0)), "D": int(counts.get("D", 0))},
        primary_style=str(primary_style),
        style_name=str(style_name),
        style_summary=str(style_summary),
    )
    return JsonResponse({"ok": True})


@require_POST
def save_eq_assessment(request):
    """Save EQ assessment result for the current user. Requires login."""
    from core.eq_scoring import calculate_eq_result

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required to save."}, status=401)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
    responses = data.get("responses")
    if not isinstance(responses, dict):
        return JsonResponse({"ok": False, "error": "Missing or invalid fields."}, status=400)
    if len(responses) != 36:
        return JsonResponse({"ok": False, "error": "All 36 statements must be answered."}, status=400)
    result = calculate_eq_result(responses)
    subscale_scores = result["subscale_scores"]
    ei_total = result["ei_total"]
    band_label = result["band_label"]
    s = subscale_scores
    intrapersonal_eq = float(s.get("SA", 0) + s.get("SC", 0) + s.get("SM", 0))
    interpersonal_eq = float(s.get("EM", 0) + s.get("CR", 0) + s.get("AC", 0))
    vals = [s.get(c, 0) for c in ("SA", "SC", "EM", "CR", "SM", "AC")]
    pbi = float(max(vals) - min(vals)) if vals else 0.0
    EQAssessmentResult.objects.create(
        user=request.user,
        responses=responses,
        subscale_scores=subscale_scores,
        weighted=None,
        ei_total=float(ei_total),
        pbi=pbi,
        intrapersonal_eq=intrapersonal_eq,
        interpersonal_eq=interpersonal_eq,
        adaptive_eq=float(s.get("SC", 0) + s.get("SM", 0)),
        band_label=str(band_label) if band_label is not None else "",
    )
    return JsonResponse({"ok": True})


def _docx_path_to_html(docx_path):
    """Convert a .docx file path to HTML. Uses careers.docx_utils if available."""
    path = Path(docx_path)
    if not path.exists():
        return None
    try:
        from careers.docx_utils import convert_docx_to_html
        with open(path, "rb") as f:
            return convert_docx_to_html(f)
    except Exception:
        try:
            from docx import Document
            doc = Document(str(path))
            parts = []
            for p in doc.paragraphs:
                if p.text.strip():
                    parts.append("<p>%s</p>" % p.text.strip().replace("<", "&lt;").replace(">", "&gt;"))
            return "\n".join(parts) if parts else ""
        except Exception:
            return None


def _can_view_assessment_report(viewer, target_user):
    if not getattr(viewer, "is_authenticated", False):
        return False
    if getattr(viewer, "is_superuser", False):
        return True
    if getattr(viewer, "id", None) == getattr(target_user, "id", None):
        return True
    try:
        from counselor.models import Counselor
        from institute.models import StudentManagement

        student_rows = (
            StudentManagement.objects.filter(student=target_user)
            .select_related("institute", "institute__institute_group", "institute__marketing_group")
        )
        for sm in student_rows:
            institute = getattr(sm, "institute", None)
            if not institute:
                continue
            if getattr(institute, "created_by_id", None) == viewer.id:
                return True
            if getattr(institute, "institute_group_id", None):
                admin_id = getattr(getattr(institute, "institute_group", None), "institute_group_admin_id", None)
                if admin_id == viewer.id:
                    return True
            if getattr(institute, "marketing_group_id", None):
                admin_id = getattr(getattr(institute, "marketing_group", None), "marketing_group_admin_id", None)
                if admin_id == viewer.id:
                    return True
            if Counselor.qs_for_institute(institute).filter(coun_user=viewer).exists():
                return True
    except Exception:
        return False
    try:
        from users.parent_student_insights import parent_can_view_student_reports

        if parent_can_view_student_reports(viewer, target_user):
            return True
    except Exception:
        pass
    return False


def _resolve_assessment_report_user(request, user_id=None):
    target_user = request.user
    if user_id:
        target_user = get_object_or_404(User, id=user_id)
        if not _can_view_assessment_report(request.user, target_user):
            return None, HttpResponse("You are not allowed to view this assessment report.", status=403)
    return target_user, None


def _assessment_report_filename(target_user, suffix):
    raw_name = getattr(target_user, "name", None) or getattr(target_user, "email", "student")
    safe_name = re.sub(r"[^\w\s-]", "", str(raw_name)).strip()[:50] or "student"
    return f"{safe_name}-{suffix}.pdf"


@login_required(login_url=None)
def mi_report_pdf(request, user_id=None):
    """Generate and download MI report PDF from docx content + user's latest result."""
    target_user, denied = _resolve_assessment_report_user(request, user_id)
    if denied:
        return denied
    latest = MIAssessmentResult.objects.filter(user=target_user).order_by("-updated_at").first()
    if not latest:
        return HttpResponse("No MI assessment result found. Complete the assessment first.", status=404)
    base = getattr(settings, "ASSESSMENT_REFERENCE_BASE", None) or ""
    reports_path = Path(base) / "mi" / "reports.docx"
    scoring_path = Path(base) / "mi" / "scoring method.docx"
    html_parts = []
    if reports_path.exists():
        reports_html = _docx_path_to_html(reports_path)
        if reports_html:
            html_parts.append(reports_html)
    if scoring_path.exists():
        scoring_html = _docx_path_to_html(scoring_path)
        if scoring_html:
            html_parts.append("<h2>Scoring Method</h2>")
            html_parts.append(scoring_html)
    logo_url = request.build_absolute_uri("/static/images/logo.png")
    style_summary_html = (latest.style_summary or "").replace("\n", "<br>")
    dominant_count = latest.counts.get(latest.primary_style, 0) if isinstance(latest.counts, dict) else 0
    result_block = """
    <div class="result-card">
      <div class="topteen-watermark">
        <img src="%s" alt="TopTeen watermark" />
      </div>
      <h2>Your Multiple Intelligences Result</h2>
      <div class="score-highlight">
        <span class="label">Primary Learning Style</span>
        <div class="score-value">%s</div>
        <div class="score-band">Top score: %s points</div>
      </div>

      <div class="summary-box">%s</div>

      <h3>Response Distribution</h3>
      <table class="subscale-table">
        <thead>
          <tr>
            <th>A</th><th>B</th><th>C</th><th>D</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>%s</td><td>%s</td><td>%s</td><td>%s</td>
          </tr>
        </tbody>
      </table>
    </div>
    """ % (
        logo_url,
        latest.style_name,
        dominant_count,
        style_summary_html,
        latest.counts.get("A", 0), latest.counts.get("B", 0), latest.counts.get("C", 0), latest.counts.get("D", 0),
    )
    html_parts.append(result_block)
    full_html = """<!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Learning Style Report</title>
      <style>
        @page { size: A4; margin: 24mm 16mm 18mm 16mm; }
        body {
          font-family: "Segoe UI", Arial, sans-serif;
          color: #1f2937;
          line-height: 1.5;
          font-size: 13px;
        }
        .page-header {
          display: table;
          width: 100%%;
          margin-bottom: 16px;
          border-bottom: 2px solid #eef2ff;
          padding-bottom: 10px;
        }
        .brand-left, .brand-right { display: table-cell; vertical-align: middle; }
        .brand-right { text-align: right; color: #4f46e5; }
        .brand-left img { width: 118px; height: auto; }
        .brand-title { font-size: 20px; font-weight: 700; margin: 0; color: #111827; }
        .brand-subtitle { margin: 4px 0 0; color: #6b7280; font-size: 12px; }
        .doc-content h1, .doc-content h2, .doc-content h3 { color: #111827; }
        .doc-content h2 {
          font-size: 18px;
          border-left: 4px solid #4f46e5;
          padding-left: 8px;
          margin-top: 18px;
          margin-bottom: 8px;
        }
        .result-card {
          position: relative;
          margin-top: 18px;
          border: 1px solid #dbeafe;
          border-radius: 14px;
          background: linear-gradient(180deg, #ffffff 0%%, #f8faff 100%%);
          padding: 18px;
          overflow: hidden;
        }
        .topteen-watermark {
          position: absolute;
          top: 50%%;
          left: 50%%;
          transform: translate(-50%%, -50%%);
          opacity: 0.06;
          z-index: 0;
          pointer-events: none;
        }
        .topteen-watermark img {
          width: 360px;
          height: auto;
        }
        .result-card > * { position: relative; z-index: 1; }
        .score-highlight {
          border: 1px solid #c7d2fe;
          background: #eef2ff;
          border-radius: 12px;
          padding: 14px;
          margin: 8px 0 14px;
          text-align: center;
        }
        .score-highlight .label { display: block; color: #4338ca; font-weight: 600; }
        .score-value { font-size: 28px; line-height: 1.2; font-weight: 800; color: #312e81; margin-top: 2px; }
        .score-band { margin-top: 4px; font-size: 12px; color: #4b5563; }
        .summary-box {
          border: 1px solid #e5e7eb;
          background: #ffffff;
          border-radius: 10px;
          padding: 12px;
          margin-bottom: 12px;
        }
        .subscale-table {
          width: 100%%;
          border-collapse: collapse;
          margin-top: 6px;
        }
        .subscale-table th, .subscale-table td {
          border: 1px solid #d1d5db;
          text-align: center;
          padding: 8px 6px;
        }
        .subscale-table th {
          background: #eef2ff;
          color: #3730a3;
          font-weight: 700;
        }
        .doc-footer {
          margin-top: 16px;
          font-size: 11px;
          color: #6b7280;
          text-align: right;
        }
      </style>
    </head>
    <body>
      <div class="page-header">
        <div class="brand-left">
          <img src="%s" alt="TopTeen Logo" />
        </div>
        <div class="brand-right">
          <p class="brand-title">Multiple Intelligences Assessment</p>
          <p class="brand-subtitle">Personalized Result Report</p>
        </div>
      </div>
      <div class="doc-content">%s</div>
      <div class="doc-footer">Generated by TopTeen</div>
    </body>
    </html>""" % (logo_url, "\n".join(html_parts))
    try:
        import weasyprint
        import ssl
        _ssl = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        try:
            pdf_bytes = weasyprint.HTML(string=full_html, base_url=request.build_absolute_uri("/")).write_pdf()
        finally:
            ssl._create_default_https_context = _ssl
    except Exception as e:
        logger.exception("MI PDF generation failed")
        return HttpResponse("PDF generation failed: %s" % str(e), status=500)
    inline_preview = (request.GET.get("inline") or "").strip() == "1"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = _assessment_report_filename(target_user, "Learning-Style-Report")
    response["Content-Disposition"] = '%s; filename="%s"' % ("inline" if inline_preview else "attachment", filename)
    return response


@login_required(login_url=None)
def eq_report_pdf(request, user_id=None):
    """Generate and download EQ report PDF from docx content + user's latest result."""
    from core.eq_scoring import EQ_LEVELS, IMPROVEMENT_TIPS, LOW_SUBSCALE_THRESHOLD, calculate_eq_result

    target_user, denied = _resolve_assessment_report_user(request, user_id)
    if denied:
        return denied
    latest = EQAssessmentResult.objects.filter(user=target_user).order_by("-updated_at").first()
    if not latest:
        return HttpResponse("No EQ assessment result found. Complete the assessment first.", status=404)
    result = calculate_eq_result(latest.responses or {})
    subscale_scores = result["subscale_scores"]
    subscale_bands = result["subscale_bands"]
    base = getattr(settings, "ASSESSMENT_REFERENCE_BASE", None) or ""
    docx_path = Path(base) / "eq" / "EQ_Assessment_and_Scoring.docx"
    html_parts = []
    if docx_path.exists():
        docx_html = _docx_path_to_html(docx_path)
        if docx_html:
            html_parts.append(docx_html)
    logo_url = request.build_absolute_uri("/static/images/logo.png")
    subscale_rows = []
    for level in EQ_LEVELS:
        code = level["code"]
        score = subscale_scores.get(code, 0)
        band = subscale_bands.get(code, "")
        subscale_rows.append(
            "<tr><td>%s (%s)</td><td>%s</td><td>%s</td></tr>"
            % (code, level["name"], score, band)
        )
    tips_html = ""
    for level in EQ_LEVELS:
        code = level["code"]
        score = subscale_scores.get(code, 0)
        if score >= LOW_SUBSCALE_THRESHOLD:
            continue
        tips = IMPROVEMENT_TIPS.get(code, [])
        if not tips:
            continue
        tips_html += "<h4>%s – How to Improve</h4><ul>" % level["name"]
        for tip in tips:
            tips_html += "<li>%s</li>" % tip.replace("<", "&lt;").replace(">", "&gt;")
        tips_html += "</ul>"
    result_block = """
    <div class="result-card">
      <div class="topteen-watermark">
        <img src="%s" alt="TopTeen watermark" />
      </div>
      <h2>Your EQ Result</h2>
      <div class="score-highlight">
        <span class="label">Total EI Score</span>
        <div class="score-value">%d</div>
        <div class="score-band">%s</div>
        <div class="score-band-desc">%s</div>
      </div>

      <h3>Subscale Scores</h3>
      <table class="subscale-table">
        <thead>
          <tr>
            <th>Area</th><th>Score (6–30)</th><th>Band</th>
          </tr>
        </thead>
        <tbody>
          %s
        </tbody>
      </table>
      %s
    </div>
    """ % (
        logo_url,
        int(round(result["ei_total"])),
        result["band_label"],
        result["band_description"],
        "\n".join(subscale_rows),
        ("<div class=\"tips-section\">%s</div>" % tips_html) if tips_html else "",
    )
    html_parts.append(result_block)
    full_html = """<!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Emotional Intelligence Report</title>
      <style>
        @page { size: A4; margin: 24mm 16mm 18mm 16mm; }
        body {
          font-family: "Segoe UI", Arial, sans-serif;
          color: #1f2937;
          line-height: 1.5;
          font-size: 13px;
        }
        .page-header {
          display: table;
          width: 100%%;
          margin-bottom: 16px;
          border-bottom: 2px solid #eef2ff;
          padding-bottom: 10px;
        }
        .brand-left, .brand-right { display: table-cell; vertical-align: middle; }
        .brand-right { text-align: right; color: #4f46e5; }
        .brand-left img { width: 118px; height: auto; }
        .brand-title { font-size: 20px; font-weight: 700; margin: 0; color: #111827; }
        .brand-subtitle { margin: 4px 0 0; color: #6b7280; font-size: 12px; }
        .doc-content h1, .doc-content h2, .doc-content h3 { color: #111827; }
        .doc-content h2 {
          font-size: 18px;
          border-left: 4px solid #4f46e5;
          padding-left: 8px;
          margin-top: 18px;
          margin-bottom: 8px;
        }
        .result-card {
          position: relative;
          margin-top: 18px;
          border: 1px solid #dbeafe;
          border-radius: 14px;
          background: linear-gradient(180deg, #ffffff 0%%, #f8faff 100%%);
          padding: 18px;
          overflow: hidden;
        }
        .topteen-watermark {
          position: absolute;
          top: 50%%;
          left: 50%%;
          transform: translate(-50%%, -50%%);
          opacity: 0.06;
          z-index: 0;
          pointer-events: none;
        }
        .topteen-watermark img {
          width: 360px;
          height: auto;
        }
        .result-card > * { position: relative; z-index: 1; }
        .score-highlight {
          border: 1px solid #c7d2fe;
          background: #eef2ff;
          border-radius: 12px;
          padding: 14px;
          margin: 8px 0 14px;
          text-align: center;
        }
        .score-highlight .label { display: block; color: #4338ca; font-weight: 600; }
        .score-value { font-size: 30px; line-height: 1.1; font-weight: 800; color: #312e81; margin-top: 2px; }
        .score-band { margin-top: 4px; font-size: 12px; color: #4b5563; font-weight: 600; }
        .score-band-desc { margin-top: 6px; font-size: 12px; color: #4b5563; }
        .tips-section { margin-top: 14px; }
        .tips-section h4 { margin: 10px 0 6px; font-size: 14px; color: #111827; }
        .tips-section ul { margin: 0 0 8px 18px; padding: 0; }
        .tips-section li { margin-bottom: 4px; }
        .subscale-table {
          width: 100%%;
          border-collapse: collapse;
          margin-top: 6px;
        }
        .subscale-table th, .subscale-table td {
          border: 1px solid #d1d5db;
          text-align: center;
          padding: 8px 6px;
        }
        .subscale-table th {
          background: #eef2ff;
          color: #3730a3;
          font-weight: 700;
        }
        .doc-footer {
          margin-top: 16px;
          font-size: 11px;
          color: #6b7280;
          text-align: right;
        }
      </style>
    </head>
    <body>
      <div class="page-header">
        <div class="brand-left">
          <img src="%s" alt="TopTeen Logo" />
        </div>
        <div class="brand-right">
          <p class="brand-title">Emotional Intelligence Assessment</p>
          <p class="brand-subtitle">Personalized Result Report</p>
        </div>
      </div>
      <div class="doc-content">%s</div>
      <div class="doc-footer">Generated by TopTeen</div>
    </body>
    </html>""" % (logo_url, "\n".join(html_parts))
    try:
        import weasyprint
        import ssl
        _ssl = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        try:
            pdf_bytes = weasyprint.HTML(string=full_html, base_url=request.build_absolute_uri("/")).write_pdf()
        finally:
            ssl._create_default_https_context = _ssl
    except Exception as e:
        logger.exception("EQ PDF generation failed")
        return HttpResponse("PDF generation failed: %s" % str(e), status=500)
    inline_preview = (request.GET.get("inline") or "").strip() == "1"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = _assessment_report_filename(target_user, "Emotional-Intelligence-Report")
    response["Content-Disposition"] = '%s; filename="%s"' % ("inline" if inline_preview else "attachment", filename)
    return response


@require_POST
def translate_complexity_api(request):
    """
    Adjust already-translated page text to easy / medium / hard reading level.
    POST JSON: { texts: [...], target_lang: "hi", level: "easy" }
    """
    from core.translation_complexity import (
        DEFAULT_TRANSLATION_COMPLEXITY,
        TRANSLATION_MAX_SEGMENTS,
        is_valid_complexity,
    )
    from core.translation_service import adjust_text_complexity, translation_complexity_available

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    texts = body.get('texts')
    target_lang = (body.get('target_lang') or '').strip().lower()
    level = (body.get('level') or DEFAULT_TRANSLATION_COMPLEXITY).strip().lower()

    if not isinstance(texts, list) or not texts:
        return JsonResponse({'ok': False, 'error': 'texts must be a non-empty array'}, status=400)
    if len(texts) > TRANSLATION_MAX_SEGMENTS:
        return JsonResponse(
            {'ok': False, 'error': f'Maximum {TRANSLATION_MAX_SEGMENTS} text segments per request'},
            status=400,
        )
    if not target_lang or target_lang == 'en':
        return JsonResponse({'ok': False, 'error': 'target_lang required (not en)'}, status=400)
    if not is_valid_complexity(level):
        return JsonResponse({'ok': False, 'error': 'Invalid level (easy, medium, hard)'}, status=400)
    if not translation_complexity_available():
        return JsonResponse({'ok': False, 'error': 'Translation complexity is not configured'}, status=503)

    try:
        adjusted = adjust_text_complexity(texts, target_lang, level)
    except Exception as exc:
        logger.exception('translate_complexity_api failed')
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)

    return JsonResponse({'ok': True, 'texts': adjusted, 'level': level})
