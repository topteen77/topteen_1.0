from django.shortcuts import render
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404,redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Q
from careers.document_filters import CareerDocumentFilter
from .models import Career, CareerFAQ, CareerMedia, CareerPath, CareerTags, Profession,CareerCluster,Videos,VideoCategory,CareerShortlist,CareerRating
from .utils import extract_intro_html_from_description
from .career_description_html import (
    convert_bold_candidates_to_h2,
    conclusion_text_normalized,
    split_trailing_conclusion_from_description,
    strip_conclusion_from_accordion_sections,
)
from core.accordion_utils import (
    build_description_accordion_sections,
    count_h2_in_html,
    filter_blank_sections,
    split_trailing_untitled_section_for_frontend,
    toc_from_sections,
    is_intro_heading,
)
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from colleges.models import College
from core.models import Country
from core import choices
from colleges.views import is_ajax
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from core.utils import build_html_head
from core.breadcrumbs import get_breadcrumb
from entrance_exams.models import EntranceExam
from .document_filters import CareerDocumentFilter
from django.urls import reverse
from django.utils.html import strip_tags
from django.contrib import messages
from pathlib import Path
from django.conf import settings
import xmindparser
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
# Create your views here.
class Careers(TemplateView):
    
    template_name = "template20/careers.html"
    
    def html_head(self):
        name='Career Tracks'
        return build_html_head(title=name, description=name)
    

    def get_context(self, request, *args, **kwargs):
        # Support both GET and POST requests
        request_data = request.POST if request.method == 'POST' else request.GET
        # SEO-friendly URL: /careers/cluster/<slug>-<id>/ passes cluster_id (and cluster_slug) in URL kwargs
        url_kwargs = args[1] if len(args) > 1 else {}
        url_cluster_id = url_kwargs.get('cluster_id')

        # When cluster is specified in URL, use fallback context so careers are filtered by that cluster
        if url_cluster_id is not None:
            ctx = self.get_fallback_context(request, url_cluster_id=url_cluster_id)
        else:
            try:
                docmentservice=CareerDocumentFilter()
                ctx=docmentservice.get_career_list_context(request)
                # Ensure all required variables are set (Elasticsearch context may be missing some)
                if 'selected_professions' not in ctx:
                    ctx['selected_professions'] = request_data.getlist("professions")
                if 'selected_clusters' not in ctx:
                    ctx['selected_clusters'] = request_data.getlist("cluster")
                if 'clusters' not in ctx:
                    from .models import CareerCluster
                    ctx['clusters'] = CareerCluster.objects.filter(object_status=1, parent__isnull=True)
                if 'professions' not in ctx:
                    from .models import Profession
                    ctx['professions'] = Profession.objects.filter(object_status=1)
                # Ensure counts are set (may be missing from Elasticsearch context)
                if 'clusters_with_counts' not in ctx:
                    ctx['clusters_with_counts'] = []
                if 'professions_with_counts' not in ctx:
                    ctx['professions_with_counts'] = []
            except Exception as e:
                logger.warning("Elasticsearch not available, using Django ORM fallback: %s", e)
                ctx = self.get_fallback_context(request)

        # Parent -> Student context (parent bookmarking careers for a specific linked student)
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request_data.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                from careers.models import Career
                # only allow if linked
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Career)
                    ctx['shortlisted_career_ids'] = list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user,
                            student_id=int(student_id),
                            content_type=ct,
                        ).values_list("object_id", flat=True)
                    )
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
        except Exception:
            pass
        
        if request_data.getlist('professions') or request_data.getlist('skills') or request_data.getlist('courses'):
            pro=request_data.getlist('professions')
            skill=request_data.getlist('skills')
            course=request_data.getlist('courses')
            data=pro+skill+course
            ctx['data']=data
        ctx['html_head'] = self.html_head()
        # Breadcrumb: Home / Career Tracks; on cluster page add cluster name (first letter capital, e.g. Architecture Construction Planning)
        if ctx.get('current_cluster_name'):
            ctx['breadcrumb'] = get_breadcrumb([
                {'text': 'Career Tracks', 'url': reverse('careers:career')},
                {'text': (ctx.get('current_cluster_name') or '').title(), 'url': ''},
            ])
        else:
            ctx['breadcrumb'] = get_breadcrumb([{'text': 'Career Tracks', 'url': reverse('careers:career')}])
        
        # Add mode context for template toggle (default to view mode; AI/View toggle hidden for now)
        ctx['view_mode'] = request_data.get('mode', 'view-mode')
        ctx['is_ai_mode'] = ctx['view_mode'] != 'view-mode'
        
        # Add request parameters as context variables for Jinja2 compatibility
        ctx['search_param'] = request_data.get('search', '')
        ctx['cluster_param'] = request_data.get('cluster', '')
        
        from users.parent_suggestions import apply_student_parent_suggestions_context, maybe_mark_parent_suggestions_seen
        apply_student_parent_suggestions_context(ctx, request, "careers")
        maybe_mark_parent_suggestions_seen(
            request, "careers", is_parent_student_context=ctx.get("is_parent_student_context", False)
        )
        return ctx
        
    def get(self, request, *args, **kwargs):
        # Cluster page: store GET params in session for clean URL; clear session when no params (Reset)
        url_cluster_id = kwargs.get('cluster_id')
        if url_cluster_id is not None and request.method == 'GET':
            session_key = 'career_cluster_%s' % url_cluster_id
            if request.GET.getlist('career') or request.GET.get('page'):
                request.session[session_key] = {
                    'career_ids': request.GET.getlist('career'),
                    'page': request.GET.get('page') or '1',
                }
                request.session.modified = True
            else:
                # Clean URL with no params (e.g. Reset): clear session so results are unfiltered
                if session_key in request.session:
                    del request.session[session_key]
                    request.session.modified = True
        return render(request, self.template_name, self.get_context(request, args, kwargs))
    
    def post(self, request, *args, **kwargs):
        # SEO redirect: single cluster from form -> /careers/cluster/<slug>-<id>/
        clusters_post = request.POST.getlist("cluster")
        if len(clusters_post) == 1:
            try:
                cid = int(clusters_post[0])
                cluster = CareerCluster.objects.filter(id=cid).first()
                if cluster:
                    return redirect(reverse("careers:career_cluster", args=[cluster.slug, cluster.id]))
            except (ValueError, TypeError):
                pass
        return render(request, self.template_name, self.get_context(request, args, kwargs))
    
    def get_fallback_context(self, request, url_cluster_id=None):
        from django.core.paginator import Paginator
        from .models import Career, CareerCluster, CareerTags, Skill, ProspectiveEmploymentArea, ProspectiveRecruiter, Profession
        from courses.models import Course
        from django.db.models import Count, Prefetch

        # Support both GET and POST requests
        request_data = request.POST if request.method == 'POST' else request.GET
        reasoning_filter_active = False
        reasoning_filter_area = None
        reasoning_filter_label = None
        mapped_filter_active = False
        # SEO-friendly URL can pass single cluster via url_cluster_id
        selected_clusters = request_data.getlist("cluster") or ([str(url_cluster_id)] if url_cluster_id is not None else [])
        # Cluster page: prefer session-stored params (clean URL); fall back to GET
        session_page = None
        if url_cluster_id is not None:
            session_data = request.session.get('career_cluster_%s' % url_cluster_id, {})
            selected_career_ids = session_data.get('career_ids') or request_data.getlist("career")
            session_page = session_data.get('page')
        else:
            selected_career_ids = request_data.getlist("career")
        
        # Optimize prefetch_related to avoid N+1 queries in template
        # Prefetch career_cluster with only active clusters to reduce data transfer
        careers = Career.objects.filter(publish_status=1).select_related().prefetch_related(
            'skills', 'career_tags', 'prospective_employment_areas', 'prospective_recruiters', 'courses',
            Prefetch('career_cluster', queryset=CareerCluster.objects.filter(object_status=1))
        ).order_by('name')

        # Handle selected filters
        selected_professions = request_data.getlist("professions")
        selected_skills = request_data.getlist("skills")
        
        # Apply career filter (inner page: filter by selected career IDs)
        if selected_career_ids:
            try:
                career_ids = [int(x) for x in selected_career_ids if str(x).strip().isdigit()]
                if career_ids:
                    careers = careers.filter(id__in=career_ids).distinct()
            except (ValueError, TypeError):
                pass
        
        # Apply cluster filtering (multi-select) - OR logic within clusters
        if selected_clusters:
            # Convert to integers if they're strings, filter out invalid values
            cluster_ids = []
            for c in selected_clusters:
                try:
                    cluster_ids.append(int(c))
                except (ValueError, TypeError):
                    continue
            if cluster_ids:
                careers = careers.filter(career_cluster__id__in=cluster_ids).distinct()
        
        # Apply profession filtering - OR logic within professions
        # Match by exact name (handles trailing colons/spaces in database)
        if selected_professions:
            # Clean the profession names and filter
            cleaned_professions = [p.strip() for p in selected_professions if p and p.strip()]
            if cleaned_professions:
                careers = careers.filter(profession__name__in=cleaned_professions).distinct()
        

        # Basic search filtering
        search_query = request_data.get('search', '')
        if search_query:
            careers = careers.filter(
                Q(name__icontains=search_query) | 
                Q(summary__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        mapped_param = request_data.get('mapped', '').strip().lower()
        if mapped_param in ('1', 'true', 'yes') and url_cluster_id is not None:
            from careers.vocational_cluster import vocational_career_cluster_id

            if int(url_cluster_id) == vocational_career_cluster_id():
                mapped_filter_active = True
                careers = careers.filter(
                    vocational_reasoning_mappings__object_status=choices.ObjectStatus.ACTIVE,
                ).distinct()

        reasoning_area_param = request_data.get('reasoning_area', '').strip()
        if reasoning_area_param and url_cluster_id is not None:
            from app.vocational_recommendations import normalize_reasoning_area_code
            from careers.vocational_cluster import vocational_career_cluster_id
            from core.choices import ReasoningArea

            if int(url_cluster_id) == vocational_career_cluster_id():
                area_code = normalize_reasoning_area_code(reasoning_area_param)
                if area_code:
                    reasoning_filter_active = True
                    reasoning_filter_area = area_code
                    reasoning_filter_label = ReasoningArea.label(area_code)
                    careers = careers.filter(
                        vocational_reasoning_mappings__reasoning_area=area_code,
                        vocational_reasoning_mappings__object_status=choices.ObjectStatus.ACTIVE,
                    ).distinct()

        # Ensure deterministic ordering before pagination (distinct() may clear order_by)
        careers = careers.order_by('name', 'id')
        # Pagination: 15 results per page (use session page on cluster page for clean URL)
        paginator = Paginator(careers, 15)
        page = session_page if session_page is not None else request_data.get('page')
        try:
            careers_page = paginator.page(page)
        except PageNotAnInteger:
            careers_page = paginator.page(1)
        except EmptyPage:
            careers_page = paginator.page(paginator.num_pages)
        
        # Clusters with counts in one query (avoid N+1)
        clusters_list = list(CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1
        ).annotate(
            career_count=Count('career_clusters', distinct=True)
        ).filter(career_count__gt=0).distinct().order_by('name'))
        clusters = clusters_list
        clusters_with_counts = [{'cluster': c, 'count': c.career_count} for c in clusters_list]

        # Profession counts by name in one query (Profession has FK to Career; count distinct careers per name)
        profession_name_to_count = dict(
            Profession.objects.filter(
                career__publish_status=1,
                object_status=1
            ).values('name').annotate(c=Count('career', distinct=True)).filter(c__gt=0).order_by('name').values_list('name', 'c')
        )
        profession_names_ordered = list(profession_name_to_count.keys())[:100]
        # One Profession instance per name for template (any row per name)
        profession_by_name = {p.name: p for p in Profession.objects.filter(
            name__in=profession_names_ordered,
            object_status=1
        )}
        professions_list = [profession_by_name[n] for n in profession_names_ordered if n in profession_by_name]
        professions = professions_list
        professions_with_counts = [{'profession': p, 'count': profession_name_to_count.get(p.name, 0)} for p in professions_list]

        # Facets: same counts, first 30; filter by cluster when selected
        if selected_clusters:
            facet_names = list(
                Profession.objects.filter(
                    career__publish_status=1,
                    career__career_cluster__id__in=selected_clusters,
                    object_status=1
                ).values_list('name', flat=True).distinct().order_by('name')[:30]
            )
        else:
            facet_names = profession_names_ordered[:30]
        profession_facets = [
            (name, profession_name_to_count.get(name, 0), name in selected_professions)
            for name in facet_names
        ]
        facets_filter = {
            "profession": profession_facets,
        }

        # Only load skills that have active careers AND are active themselves
        skills = Skill.objects.filter(
            career__publish_status=1,
            object_status=1  # Only active skills
        ).distinct().order_by('priority', 'name')[:200]  # Limit to 200 for performance

        # Other models - only load if needed, limit results
        tags = CareerTags.objects.all()[:50]  # Limit tags
        employment_areas = ProspectiveEmploymentArea.objects.all()[:50]
        recruiters = ProspectiveRecruiter.objects.all()[:50]
        courses = Course.objects.all()[:50]

        # Get shortlisted career IDs for authenticated users
        shortlisted_career_ids = []
        if request.user.is_authenticated:
            from .models import CareerShortlist
            shortlisted_career_ids = list(CareerShortlist.objects.filter(
                user=request.user
            ).values_list('career_id', flat=True))
        
        # Pre-process careers to convert ManyRelatedManager to list for template compatibility
        # This prevents the "object of type 'ManyRelatedManager' has no len()" error
        for career in careers_page:
            # Convert career_cluster ManyRelatedManager to list
            if hasattr(career, 'career_cluster'):
                try:
                    # Prefetch and convert to list to avoid ManyRelatedManager issues in template
                    career._career_cluster_list = list(career.career_cluster.all())
                except:
                    career._career_cluster_list = []
        
        # Current cluster for inner page (when viewing a single cluster)
        current_cluster_id = None
        current_cluster_slug = None
        current_cluster_name = None
        cluster_page_url = None
        if url_cluster_id is not None:
            try:
                current_cluster = CareerCluster.objects.filter(id=url_cluster_id).first()
                if current_cluster:
                    current_cluster_id = current_cluster.id
                    current_cluster_slug = current_cluster.slug or ''
                    current_cluster_name = current_cluster.name or ''
                    cluster_page_url = reverse('careers:career_cluster', args=[current_cluster_slug, current_cluster_id])
            except (ValueError, TypeError):
                pass
        elif len(selected_clusters) == 1:
            try:
                cid = int(selected_clusters[0])
                current_cluster = CareerCluster.objects.filter(id=cid).first()
                if current_cluster:
                    current_cluster_id = current_cluster.id
                    current_cluster_slug = current_cluster.slug or ''
                    current_cluster_name = current_cluster.name or ''
                    cluster_page_url = reverse('careers:career_cluster', args=[current_cluster_slug, current_cluster_id])
            except (ValueError, TypeError):
                pass

        # Pre-fill display text for selected careers (for inner-page filter multiselect)
        selected_careers_display = []
        if selected_career_ids:
            try:
                cids = [int(x) for x in selected_career_ids if str(x).strip().isdigit()]
                if cids:
                    from django.db.models import Prefetch
                    prefetch = Prefetch('career_cluster', queryset=CareerCluster.objects.filter(object_status=1))
                    for c in Career.objects.filter(id__in=cids).prefetch_related(prefetch).order_by('name'):
                        cluster_names = [cl.name for cl in c.career_cluster.all() if cl and cl.name]
                        cluster_part = ' | '.join(cluster_names) if cluster_names else ''
                        text = f"{c.name}  [{cluster_part}]" if cluster_part else c.name
                        selected_careers_display.append({'id': c.id, 'text': text, 'name': c.name, 'cluster': cluster_part})
            except (ValueError, TypeError):
                pass

        # All careers in this cluster for dropdown (load from memory, no AJAX delay)
        cluster_careers_options = []
        if current_cluster_id and current_cluster_name:
            cluster_careers_qs = Career.objects.filter(
                publish_status=1
            ).filter(
                Q(career_cluster__id=current_cluster_id) | Q(career_cluster__parent_id=current_cluster_id)
            ).distinct().order_by('name', 'id')
            for c in cluster_careers_qs.only('id', 'name'):
                name = (c.name or '').strip() or 'Career'
                text = f"{name}  [{current_cluster_name}]"
                cluster_careers_options.append({
                    'id': str(c.id),
                    'text': text,
                    'name': name,
                    'cluster': current_cluster_name,
                })
        ctx_out = {
            'careers': careers_page,
            'clusters': clusters,
            'clusters_with_counts': clusters_with_counts,  # For template display with counts
            'tags': tags,
            'skills': skills,
            'professions': professions,
            'professions_with_counts': professions_with_counts,  # For template display with counts
            'employment_areas': employment_areas,
            'recruiters': recruiters,
            'courses': courses,
            'total_careers': paginator.count,  # Use paginator count (already calculated)
            'facets_filter': facets_filter,
            'selected_professions': selected_professions,
            'selected_skills': selected_skills,
            'selected_clusters': selected_clusters,
            'selected_career_ids': selected_career_ids if selected_career_ids else [],
            'current_cluster_id': current_cluster_id,
            'current_cluster_slug': current_cluster_slug,
            'current_cluster_name': current_cluster_name,
            'cluster_page_url': cluster_page_url,
            'selected_careers_display': selected_careers_display,
            'cluster_careers_options': cluster_careers_options,
            'shortlisted_career_ids': shortlisted_career_ids,
            'reasoning_filter_active': reasoning_filter_active,
            'reasoning_filter_area': reasoning_filter_area,
            'reasoning_filter_label': reasoning_filter_label,
            'reasoning_filter_count': paginator.count if reasoning_filter_active else 0,
            'mapped_filter_active': mapped_filter_active,
            'mapped_filter_count': paginator.count if mapped_filter_active and not reasoning_filter_active else 0,
        }

        # Parent -> Student context override for shortlist state
        ctx_out['is_parent_student_context'] = False
        ctx_out['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Career)
                    ctx_out['shortlisted_career_ids'] = list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user,
                            student_id=int(student_id),
                            content_type=ct,
                        ).values_list("object_id", flat=True)
                    )
                    ctx_out['is_parent_student_context'] = True
                    ctx_out['parent_student_id'] = int(student_id)
        except Exception:
            pass
        return ctx_out
    
class CareerDetail(TemplateView):
    template_name = "template20/career_detail_accordion.html"
    # template_name = "template20/career_detail.html"  # Original template
    # template_name = "template20/career_detail_mindmap.html"  # Mindmap version
    def html_head(self, career):
        # Use admin-configured SEO when set (SeoModel), else name/summary for title/description and OG alignment
        titleb = (career.seo_title or career.name or "").strip() or career.name
        summary = career.get_display_summary() or ""
        descriptionb = (career.seo_description or summary).strip() or summary
        return build_html_head(title=titleb, description=descriptionb)
    

    def get_context(self, request,career_id,slug, *args, **kwargs):
        ctx={}
        career=get_object_or_404(
            Career.objects.prefetch_related('profession', 'career_cluster', 'videos'),
            id=career_id, slug=slug,
        )
        ctx['career']=career
        description_body, conclusion_paragraph_html = split_trailing_conclusion_from_description(
            career.description or ''
        )
        intro_html = extract_intro_html_from_description(description_body)
        # Do not show intro box when it is the same paragraph as the conclusion footer.
        if intro_html and conclusion_paragraph_html:
            intro_norm = conclusion_text_normalized(intro_html)
            concl_norm = conclusion_text_normalized(conclusion_paragraph_html)
            if intro_norm and intro_norm == concl_norm:
                intro_html = ""
        ctx['description_intro_html'] = intro_html
        ctx['breadcrumb'] = self._breadcrumb(career)
        country=Country.objects.all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['countries']=country
        ctx['html_head'] = self.html_head(career)
        ctx['career_rating']=career.career_rating.all()
        ctx['career_rating_url']=reverse("careers:careerrating")
        try:
            ctx['shortlisted_career'] = CareerShortlist.objects.get(user=request.user,career=career)
        except:
             ctx['shortlisted_career'] = None
        
        from careers.related_careers import get_related_careers
        ctx['related_careers'] = get_related_careers(career, limit=6, published_only=True).prefetch_related(
            'career_cluster', 'profession'
        )

        # Generate mindmap data (career clusters)
        ctx['mindmap_data'] = self._get_mindmap_data(career)
        
        # Generate career aspect mindmap data (like HIPPOLOGY example)
        ctx['career_aspect_mindmap'] = self._get_career_aspect_mindmap(career)

        # Build accordion from live description HTML only (not description_json).
        # Stale JSON often embeds the full document in multiple sections and duplicates the conclusion.
        accordion_source_html = description_body
        if count_h2_in_html(description_body) == 0:
            accordion_source_html, _ = convert_bold_candidates_to_h2(description_body)

        accordion_sections = build_description_accordion_sections(
            accordion_source_html,
            json_sections=None,
        )
        if conclusion_paragraph_html:
            accordion_sections = strip_conclusion_from_accordion_sections(
                accordion_sections,
                conclusion_paragraph_html,
            )
            accordion_sections = filter_blank_sections(accordion_sections)

        accordion_sections, footer_html = split_trailing_untitled_section_for_frontend(
            accordion_sections
        )
        # Career detail page already shows an intro/summary at the top (description_intro_html).
        # Hide redundant intro-like sections (Overview/About/Intro) inside the accordion for careers only.
        accordion_sections = [
            s for s in accordion_sections
            if (s.get("section_id") or "").strip().lower() != "overview"
            and not is_intro_heading(s.get("title"))
        ]

        ctx['accordion_sections'] = accordion_sections
        ctx['career_footer_paragraph_html'] = conclusion_paragraph_html or footer_html
        ctx['accordion_toc'] = toc_from_sections(accordion_sections)

        # Mindmap: API-backed radial/classic vs static SVG accordion navigator
        try:
            from core.models import Configuration

            ctx['career_mindmap_api_available'] = career.has_career_mindmap_api_data()
            dmt = choices.coerce_default_mindmap_type(
                Configuration.get('DEFAULT_MINDMAP_TYPE', '6', editable=True) or '6'
            )
            ctx['career_detail_use_classic_mindmap'] = dmt in ('16', '17', '18', '19')
            ctx['career_detail_classic_layout'] = 'vertical' if dmt in ('17', '19') else 'horizontal'
            ctx['career_detail_classic_visual_ribbon'] = dmt in ('18', '19')
            # Backward-compatible name used by some templates / logic
            ctx['has_xmind_file'] = ctx['career_mindmap_api_available']
            ctx['xmind_file_path'] = str(career.get_xmind_file_path()) if career.has_xmind_file() else None
            # Pre-fetch clusters as list for Jinja2 template
            ctx['career_clusters'] = list(career.career_cluster.all())
        except Exception:
            # Gracefully handle any errors
            ctx['career_mindmap_api_available'] = False
            ctx['career_detail_use_classic_mindmap'] = False
            ctx['career_detail_classic_layout'] = 'horizontal'
            ctx['career_detail_classic_visual_ribbon'] = False
            ctx['has_xmind_file'] = False
            ctx['xmind_file_path'] = None
            ctx['career_clusters'] = []

        # Parse career description into 11 JSON sections
        json_parser = self._parse_career_json_sections(career)
        ctx['career_json'] = json_parser.sections if json_parser else {}
        
        # Parse infographics - use JSON sections for all sections
        try:
            from .infographic_parser import parse_infographic
            
            # Get HTML from JSON sections
            # Initialize all section HTMLs to empty strings
            overview_html = ''
            roles_html = ''
            study_route_html = ''
            observations_html = ''
            internships_html = ''
            courses_html = ''
            employers_html = ''
            skills_trends_html = ''
            advice_html = ''
            
            if json_parser:
                # For overview: try overview section first, then fallback to career_description
                overview_html = json_parser.get_section_html('overview')
                if not overview_html:
                    overview_html = json_parser.get_section_html('career_description')
                roles_html = json_parser.get_section_html('roles_and_responsibilities') or ''
                study_route_html = json_parser.get_section_html('study_route_and_eligibility_criteria') or ''
                observations_html = json_parser.get_section_html('significant_observations') or ''
                internships_html = json_parser.get_section_html('internships_and_practical_exposure') or ''
                courses_html = json_parser.get_section_html('courses_and_specializations') or ''
                employers_html = json_parser.get_section_html('prominent_employers') or ''
                skills_trends_html = json_parser.get_section_html('skills_required_industry_trends') or ''
                advice_html = json_parser.get_section_html('advice_for_aspiring') or ''
            
            # Add overview HTML to context
            ctx['overview_html'] = overview_html
            
            # Add JSON section HTMLs to context for templates
            ctx['roles_html'] = roles_html
            ctx['study_route_html'] = study_route_html
            ctx['observations_html'] = observations_html
            ctx['internships_html'] = internships_html
            ctx['courses_html'] = courses_html
            ctx['employers_html'] = employers_html
            ctx['skills_trends_html'] = skills_trends_html
            ctx['advice_html'] = advice_html
            
            # Parse infographics from JSON sections
            # For skills_industry_trends, try section first, then fallback to full description
            skills_industry_trends_data = None
            if skills_trends_html:
                skills_industry_trends_data = parse_infographic(skills_trends_html, 'skills_industry_trends')
            elif career.description:
                # Fallback: try parsing from full description
                skills_industry_trends_data = parse_infographic(career.description, 'skills_industry_trends')
            
            ctx['infographics'] = {
                'study_route': parse_infographic(study_route_html, 'study_route') if study_route_html else None,
                'roles_responsibilities': parse_infographic(roles_html, 'roles_responsibilities') if roles_html else None,
                'observations': parse_infographic(observations_html, 'observations') if observations_html else None,
                'internships': parse_infographic(internships_html, 'internships') if internships_html else None,
                'courses': parse_infographic(courses_html, 'courses') if courses_html else None,
                'prominent_employers': parse_infographic(employers_html, 'prominent_employers') if employers_html else None,
                'skills_industry_trends': skills_industry_trends_data,
                'advice_for_aspiring': parse_infographic(advice_html, 'advice_for_aspiring') if advice_html else None,
            }
            
            # For institutes, use description content
            combined_content = career.description or ''
            ctx['infographics']['institutes'] = parse_infographic(combined_content, 'institutes')
            
            # Keep backward compatibility
            ctx['study_routes'] = ctx['infographics'].get('study_route')
        except Exception as e:
            logger.warning(f'Error parsing infographics: {str(e)}', exc_info=True)
            ctx['infographics'] = {}
            ctx['study_routes'] = None

        return ctx
    
    def _parse_career_json_sections(self, career):
        """Parse career description into 11 JSON sections"""
        try:
            from .career_json_parser import CareerDescriptionJSONParser
            
            parser = CareerDescriptionJSONParser(career)
            parser.parse_all_sections()
            return parser
        except Exception as e:
            logger.error(f'Error parsing career JSON sections: {str(e)}', exc_info=True)
            return None
    
    def _get_mindmap_data(self, current_career):
        """Generate mindmap data structure from database"""
        import json
        from .models import CareerCluster
        
        # Get all top-level clusters (no parent)
        top_clusters = CareerCluster.objects.filter(parent__isnull=True)
        
        mindmap_data = {
            "name": "Career Paths",
            "children": []
        }
        
        # Limit to 10 clusters for performance
        for cluster in top_clusters[:10]:
            # Get careers in this cluster (published only)
            careers = Career.objects.filter(
                career_cluster=cluster,
                publish_status=choices.PublishStatus.PUBLISHED
            ).distinct()[:8]  # Limit to 8 careers per cluster
            
            if careers.exists():
                cluster_data = {
                    "name": cluster.name,
                    "children": []
                }
                
                for career in careers:
                    # Generate full URL for the career
                    career_url = reverse('careers:careerdetail', args=[career.slug, career.id])
                    career_data = {
                        "name": career.name,
                        "slug": career.slug,
                        "id": career.id,
                        "url": career_url,
                        "is_current": (career.id == current_career.id)
                    }
                    cluster_data["children"].append(career_data)
                
                mindmap_data["children"].append(cluster_data)
        
        return json.dumps(mindmap_data)
    
    def _parse_study_routes(self, career):
        """
        Parse study routes from career.description HTML content.
        Handles both table format (Route/Steps columns) and heading-based format.
        Extracts routes and steps to create infographic structure.
        Returns list of route dictionaries or None if parsing fails.
        """
        if not career.description:
            return None
        
        try:
            soup = BeautifulSoup(career.description, 'html.parser')
            
            # Route colors
            route_colors = [
                {'name': 'route-1', 'color': '#0064c8', 'display': 'Route 1'},  # Blue
                {'name': 'route-2', 'color': '#228b22', 'display': 'Route 2'},  # Green
                {'name': 'route-3', 'color': '#8a2be2', 'display': 'Route 3'},  # Purple
                {'name': 'route-4', 'color': '#ff8c00', 'display': 'Route 4'}   # Orange
            ]
            
            routes = []
            
            # METHOD 1: Try parsing table structure first (Route/Steps columns)
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        route_cell = cells[0].get_text(strip=True)
                        steps_cell = cells[1].get_text(strip=True)
                        
                        # Skip header row (usually first row with "Route" and "Steps")
                        if row_idx == 0 and route_cell.lower() == 'route' and steps_cell.lower() == 'steps':
                            continue
                        
                        # Check if first cell contains "Route" keyword
                        if 'route' in route_cell.lower() and route_cell.lower() != 'route':
                            # Extract route number and name
                            route_match = re.search(r'route\s*(\d+)[:\s]*(.*)', route_cell, re.IGNORECASE)
                            if route_match:
                                route_num = int(route_match.group(1))
                                route_name = route_match.group(2).strip() if route_match.group(2) else f'Route {route_num}'
                            else:
                                route_num = len(routes) + 1
                                route_name = route_cell
                            
                            # Parse steps from second cell (numbered list)
                            steps = []
                            # Split by "number. " or "number) " pattern to handle numbers in text
                            step_parts = re.split(r'(\d+)[\.\)]\s+', steps_cell)
                            
                            # step_parts[0] is text before first number (usually empty)
                            # Then pairs of (number, text) follow
                            if len(step_parts) > 1:
                                for i in range(1, len(step_parts), 2):
                                    if i + 1 < len(step_parts):
                                        step_num = int(step_parts[i])
                                        step_text = step_parts[i + 1].strip()
                                        
                                        # Clean up: remove any trailing text that looks like start of next step
                                        # But keep numbers that are part of the step (like "10+2", "4 years")
                                        step_text = re.sub(r'\s+(?=\d+[\.\)]\s)', '', step_text)
                                        
                                        # Clean up extra whitespace
                                        step_text = re.sub(r'\s+', ' ', step_text)
                                        
                                        # Extract duration
                                        duration = ''
                                        duration_patterns = [
                                            r'\((\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                                            r'\((\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                                        ]
                                        for dur_pattern in duration_patterns:
                                            duration_match = re.search(dur_pattern, step_text, re.IGNORECASE)
                                            if duration_match:
                                                duration = duration_match.group(1)
                                                break
                                        
                                        # Remove duration from title
                                        title = re.sub(r'\([^)]*\)', '', step_text).strip()
                                        
                                        if title:
                                            steps.append({
                                                'number': step_num,
                                                'title': title,
                                                'description': '',
                                                'duration': duration
                                            })
                            else:
                                # Fallback: Try splitting by newlines or semicolons
                                step_lines = re.split(r'[\n;]', steps_cell)
                                for idx, line in enumerate(step_lines, 1):
                                    line = line.strip()
                                    if line and not line.lower().startswith('route'):
                                        # Extract duration
                                        duration = ''
                                        duration_match = re.search(r'\((\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)', line, re.IGNORECASE)
                                        if duration_match:
                                            duration = duration_match.group(1)
                                        
                                        # Remove duration from title
                                        title = re.sub(r'\([^)]*\)', '', line).strip()
                                        
                                        if title:
                                            steps.append({
                                                'number': idx,
                                                'title': title,
                                                'description': '',
                                                'duration': duration
                                            })
                            
                            if steps:
                                route_index = route_num - 1
                                if route_index < len(route_colors):
                                    route_data = {
                                        'name': route_name,
                                        'class': route_colors[route_index]['name'],
                                        'color': route_colors[route_index]['color'],
                                        'display': route_colors[route_index]['display'],
                                        'steps': steps
                                    }
                                else:
                                    route_data = {
                                        'name': route_name,
                                        'class': 'route-default',
                                        'color': '#666666',
                                        'display': f'Route {route_num}',
                                        'steps': steps
                                    }
                                routes.append(route_data)
            
            # METHOD 2: If no table found, try heading-based parsing
            if not routes:
                current_route = None
                route_index = 0
                
                # Find all headings and content
                all_elements = soup.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li'])
                
                for element in all_elements:
                    tag_name = element.name.lower()
                    text = element.get_text(strip=True)
                    
                    if not text:
                        continue
                    
                    # Check if it's a route heading (h2 or h3 with "route" keyword)
                    is_route_heading = (
                        (tag_name == 'h2') or 
                        (tag_name == 'h3' and ('route' in text.lower() or text.lower().startswith('pathway')))
                    )
                    
                    if is_route_heading:
                        # Save previous route
                        if current_route and current_route['steps']:
                            routes.append(current_route)
                        
                        # Start new route
                        route_index = len(routes)
                        if route_index < len(route_colors):
                            current_route = {
                                'name': text,
                                'class': route_colors[route_index]['name'],
                                'color': route_colors[route_index]['color'],
                                'display': route_colors[route_index]['display'],
                                'steps': []
                            }
                        else:
                            # Use default if more than 4 routes
                            current_route = {
                                'name': text,
                                'class': 'route-default',
                                'color': '#666666',
                                'display': f'Route {route_index + 1}',
                                'steps': []
                            }
                    
                    elif current_route and (tag_name == 'h3' or tag_name == 'h4'):
                        # Step heading
                        step_text = text
                        
                        # Look for description in next paragraph
                        description = ''
                        duration = ''
                        next_elem = element.find_next_sibling(['p', 'ul', 'ol'])
                        
                        if next_elem:
                            if next_elem.name == 'p':
                                description = next_elem.get_text(strip=True)
                            elif next_elem.name in ['ul', 'ol']:
                                # Get first list item as description
                                first_li = next_elem.find('li')
                                if first_li:
                                    description = first_li.get_text(strip=True)
                        
                        # Extract duration pattern (e.g., "3-4 Years", "2 Years", "(1-2 Yrs)")
                        duration_patterns = [
                            r'\(?(\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)?',
                            r'\(?(\d+\s*(?:Years?|Months?|Yrs?|Months?))\)?',
                            r'(\d+[-–]\d+\s*(?:Years?|Months?|Yrs?))',
                        ]
                        
                        for pattern in duration_patterns:
                            match = re.search(pattern, description, re.IGNORECASE)
                            if match:
                                duration = match.group(1)
                                break
                        
                        current_route['steps'].append({
                            'number': len(current_route['steps']) + 1,
                            'title': step_text,
                            'description': description[:200] if description else '',  # Limit length
                            'duration': duration
                        })
                
                # Add last route
                if current_route and current_route['steps']:
                    routes.append(current_route)
            
            return routes if routes else None
        
        except Exception as e:
            logger.warning(f'Error parsing study routes for career {career.name}: {str(e)}')
            return None
    
    def _parse_study_routes_from_description(self, career):
        """
        Parse study routes from career.description HTML content.
        Looks for "Study Route" section and extracts table or heading-based routes.
        """
        if not career.description:
            return None
        
        try:
            soup = BeautifulSoup(career.description, 'html.parser')
            
            # Find "Study Route" or "Eligibility" section
            study_route_section = None
            for heading in soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                text = heading.get_text(strip=True).lower()
                if 'study route' in text or ('eligibility' in text and 'route' in text):
                    # Get the section starting from this heading
                    study_route_section = heading
                    break
            
            if not study_route_section:
                return None
            
            # Get content from this heading until next major section
            section_content = []
            current = study_route_section
            section_content.append(str(current))
            
            # Collect following elements until next major heading
            while current:
                current = current.find_next_sibling()
                if not current:
                    break
                if current.name in ['h2', 'h3', 'h4']:
                    # Check if it's a new major section
                    text = (current.get_text() or '').strip().lower()
                    if any(keyword in text for keyword in ['significant', 'observation', 'pros', 'cons', 'skills', 'employment']):
                        break
                section_content.append(str(current))
            
            # Parse the section content
            section_soup = BeautifulSoup(''.join(section_content), 'html.parser')
            
            # Route colors
            route_colors = [
                {'name': 'route-1', 'color': '#0064c8', 'display': 'Route 1'},  # Blue
                {'name': 'route-2', 'color': '#228b22', 'display': 'Route 2'},  # Green
                {'name': 'route-3', 'color': '#8a2be2', 'display': 'Route 3'},  # Purple
                {'name': 'route-4', 'color': '#ff8c00', 'display': 'Route 4'}   # Orange
            ]
            
            routes = []
            
            # Try parsing table structure first
            tables = section_soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        route_cell = cells[0].get_text(strip=True)
                        steps_cell = cells[1].get_text(strip=True)
                        
                        # Skip header row (usually first row with "Route" and "Steps")
                        if row_idx == 0 and route_cell.lower() == 'route' and steps_cell.lower() == 'steps':
                            continue
                        
                        # Check if first cell contains "Route" keyword
                        if 'route' in route_cell.lower() and route_cell.lower() != 'route':
                            # Extract route number and name
                            route_match = re.search(r'route\s*(\d+)[:\s]*(.*)', route_cell, re.IGNORECASE)
                            if route_match:
                                route_num = int(route_match.group(1))
                                route_name = route_match.group(2).strip() if route_match.group(2) else f'Route {route_num}'
                            else:
                                route_num = len(routes) + 1
                                route_name = route_cell
                            
                            # Parse steps from second cell (numbered list)
                            steps = []
                            # Split by "number. " or "number) " pattern to handle numbers in text
                            step_parts = re.split(r'(\d+)[\.\)]\s+', steps_cell)
                            
                            # step_parts[0] is text before first number (usually empty)
                            # Then pairs of (number, text) follow
                            if len(step_parts) > 1:
                                for i in range(1, len(step_parts), 2):
                                    if i + 1 < len(step_parts):
                                        step_num = int(step_parts[i])
                                        step_text = step_parts[i + 1].strip()
                                        
                                        # Clean up: remove any trailing text that looks like start of next step
                                        # But keep numbers that are part of the step (like "10+2", "4 years")
                                        step_text = re.sub(r'\s+(?=\d+[\.\)]\s)', '', step_text)
                                        
                                        # Clean up extra whitespace
                                        step_text = re.sub(r'\s+', ' ', step_text)
                                        
                                        # Extract duration
                                        duration = ''
                                        duration_patterns = [
                                            r'\((\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                                            r'\((\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                                        ]
                                        for dur_pattern in duration_patterns:
                                            duration_match = re.search(dur_pattern, step_text, re.IGNORECASE)
                                            if duration_match:
                                                duration = duration_match.group(1)
                                                break
                                        
                                        # Remove duration from title
                                        title = re.sub(r'\([^)]*\)', '', step_text).strip()
                                        
                                        if title:
                                            steps.append({
                                                'number': step_num,
                                                'title': title,
                                                'description': '',
                                                'duration': duration
                                            })
                            else:
                                # Fallback: Try splitting by newlines or semicolons
                                step_lines = re.split(r'[\n;]', steps_cell)
                                for idx, line in enumerate(step_lines, 1):
                                    line = line.strip()
                                    if line and not line.lower().startswith('route'):
                                        # Extract duration
                                        duration = ''
                                        duration_match = re.search(r'\((\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)', line, re.IGNORECASE)
                                        if duration_match:
                                            duration = duration_match.group(1)
                                        
                                        # Remove duration from title
                                        title = re.sub(r'\([^)]*\)', '', line).strip()
                                        
                                        if title:
                                            steps.append({
                                                'number': idx,
                                                'title': title,
                                                'description': '',
                                                'duration': duration
                                            })
                            
                            if steps:
                                route_index = route_num - 1
                                if route_index < len(route_colors):
                                    route_data = {
                                        'name': route_name,
                                        'class': route_colors[route_index]['name'],
                                        'color': route_colors[route_index]['color'],
                                        'display': route_colors[route_index]['display'],
                                        'steps': steps
                                    }
                                else:
                                    route_data = {
                                        'name': route_name,
                                        'class': 'route-default',
                                        'color': '#666666',
                                        'display': f'Route {route_num}',
                                        'steps': steps
                                    }
                                routes.append(route_data)
            
            return routes if routes else None
        
        except Exception as e:
            logger.warning(f'Error parsing study routes from description for career {career.name}: {str(e)}')
            return None
    
    def _get_career_aspect_mindmap(self, career):
        """Generate career aspect mindmap data from description field (H1, H2, H3 structure)"""
        import json
        import re
        from django.utils.html import strip_tags
        from bs4 import BeautifulSoup
        
        # Parse description HTML to extract H1, H2, H3 structure
        mindmap_data = {
            "name": career.name,
            "summary": career.get_display_summary() or "",
            "children": []
        }
        
        if not career.description:
            return json.dumps(mindmap_data)
        
        def summarize_content(html_content, max_length=150):
            """Summarize HTML content to make it concise for mindmap"""
            if not html_content:
                return ""
            
            # Strip HTML tags and get plain text
            text = strip_tags(html_content)
            
            # Remove extra whitespace
            text = ' '.join(text.split())
            
            # If content is short, return as is
            if len(text) <= max_length:
                return text
            
            # Find first sentence or paragraph break
            sentences = text.split('. ')
            summary = ""
            for sentence in sentences:
                if len(summary + sentence) <= max_length:
                    summary += sentence + ". "
                else:
                    break
            
            # If no sentences found, truncate
            if not summary:
                summary = text[:max_length] + "..."
            else:
                summary = summary.strip()
                if len(summary) < len(text):
                    summary += "..."
            
            return summary
        
        try:
            soup = BeautifulSoup(career.description, 'html.parser')
            
            # Extract body content if it's a full HTML document
            body = soup.find('body')
            if body:
                soup = body
            
            # Find H1 as root title (or first strong paragraph)
            h1_tag = soup.find('h1')
            if h1_tag:
                mindmap_data["name"] = h1_tag.get_text().strip()
            else:
                # Try to find first <p><strong> as title
                first_strong_p = soup.find('p')
                if first_strong_p and first_strong_p.find('strong'):
                    mindmap_data["name"] = first_strong_p.find('strong').get_text().strip()
            
            # Find all H2 tags (main children) or <p><strong> patterns
            h2_tags = soup.find_all('h2')
            current_h2 = None
            current_h2_data = None
            
            # If no H2 tags, look for <p><strong> patterns as potential H2
            if not h2_tags:
                # Find all paragraphs with strong tags
                strong_paragraphs = soup.find_all('p')
                potential_h2s = []
                for p in strong_paragraphs:
                    strong = p.find('strong')
                    if strong:
                        text = strong.get_text().strip()
                        # Skip if it's the title we already found
                        if text != mindmap_data["name"]:
                            potential_h2s.append(p)
                
                # Use first few strong paragraphs as H2 sections
                for p in potential_h2s[:12]:  # Limit to 12 sections
                    strong = p.find('strong')
                    if strong:
                        # Save previous H2 if exists
                        if current_h2_data:
                            mindmap_data["children"].append(current_h2_data)
                        
                        # Start new H2
                        h2_name = strong.get_text().strip()
                        current_h2_data = {
                            "name": h2_name,
                            "summary": "",
                            "content": "",
                            "children": []
                        }
                        
                        # Get content after this paragraph until next strong paragraph
                        content_parts = []
                        # Find all paragraphs after this one
                        all_paragraphs = soup.find_all('p')
                        current_index = all_paragraphs.index(p) if p in all_paragraphs else -1
                        
                        if current_index >= 0:
                            # Get paragraphs after current one until we hit another strong paragraph
                            for next_p in all_paragraphs[current_index + 1:]:
                                if next_p.find('strong'):
                                    break
                                content_parts.append(str(next_p))
                        
                        full_content = "".join(content_parts)
                        current_h2_data["content"] = full_content
                        current_h2_data["summary"] = summarize_content(full_content, max_length=120)
            else:
                # Original H2/H3 parsing logic
                for element in soup.find_all(['h2', 'h3', 'p', 'ul', 'ol']):
                    if element.name == 'h2':
                        # Save previous H2 if exists
                        if current_h2_data:
                            mindmap_data["children"].append(current_h2_data)
                        
                        # Start new H2
                        current_h2 = element
                        current_h2_data = {
                            "name": element.get_text().strip(),
                            "summary": "",
                            "content": "",
                            "children": []
                        }
                        
                    elif element.name == 'h3' and current_h2_data:
                        # H3 is a subchild of current H2
                        h3_data = {
                            "name": element.get_text().strip(),
                            "summary": "",
                            "content": ""
                        }
                        
                        # Get content after H3 until next heading
                        content_parts = []
                        next_sibling = element.next_sibling
                        while next_sibling:
                            if next_sibling.name in ['h2', 'h3']:
                                break
                            if next_sibling.name in ['p', 'ul', 'ol']:
                                content_parts.append(str(next_sibling))
                            next_sibling = next_sibling.next_sibling
                        
                        full_content = "".join(content_parts)
                        h3_data["content"] = full_content
                        h3_data["summary"] = summarize_content(full_content, max_length=100)
                        
                        current_h2_data["children"].append(h3_data)
                        
                    elif element.name in ['p', 'ul', 'ol'] and current_h2_data:
                        # Add content to current H2 (if no H3 children yet or content before first H3)
                        if not current_h2_data["children"]:
                            current_h2_data["content"] += str(element)
            
            # Summarize H2 content
            if current_h2_data and current_h2_data["content"]:
                current_h2_data["summary"] = summarize_content(current_h2_data["content"], max_length=120)
            
            # Add last H2 if exists
            if current_h2_data:
                mindmap_data["children"].append(current_h2_data)
            
            # If still no children, create a simple overview
            if not mindmap_data["children"]:
                # Get first few paragraphs as overview
                paragraphs = soup.find_all('p')[:5]
                if paragraphs:
                    content = "".join([str(p) for p in paragraphs if not (p.find('strong') and p.find('strong').get_text().strip() == mindmap_data["name"])])
                    if content:
                        mindmap_data["children"].append({
                            "name": "Overview",
                            "summary": summarize_content(content, max_length=120),
                            "content": content,
                            "children": []
                        })
            
        except Exception as e:
            # Fallback: create simple structure
            if career.description:
                mindmap_data["children"] = [{
                    "name": "Career Description",
                    "summary": summarize_content(career.description, max_length=120),
                    "content": career.description,
                    "children": []
                }]
        
        return json.dumps(mindmap_data)
        
        # Roles & Responsibilities - now extracted from description_json
        # Study Route & Eligibility - now extracted from description_json
        
        # Courses
        if career.courses.exists():
            courses_list = "\n".join([f"<li>{course.name}</li>" for course in career.courses.all()[:10]])
            aspects.append({
                "id": "courses",
                "name": "Courses",
                "icon": "book-open",
                "color": "#81fbb8,#28c76f",
                "hasContent": True,
                "modalContent": {
                    "title": "Related Courses",
                    "body": f"<ul class='list-styled'>{courses_list}</ul>"
                }
            })
        
        # Career Path
        if career.career_paths.exists():
            paths_html = ""
            for path in career.career_paths.all():
                steps = path.get_sorted_priority()
                if steps:
                    steps_list = "\n".join([f"<li>{step.name}</li>" for step in steps])
                    paths_html += f"<h5>{path.name}</h5><ul class='list-styled'>{steps_list}</ul>"
            if paths_html:
                aspects.append({
                    "id": "career-path",
                    "name": "Career Path",
                    "icon": "route",
                    "color": "#6a11cb,#2575fc",
                    "hasContent": True,
                    "modalContent": {
                        "title": "Career Path",
                        "body": paths_html
                    }
                })
        
        # Pros & Cons - now extracted from description_json
        
        # Skills
        if career.skills.exists():
            skills_list = "\n".join([f"<span class='badge-custom'>{skill.name}</span>" for skill in career.skills.all()[:20]])
            aspects.append({
                "id": "skills",
                "name": "Skills",
                "icon": "star",
                "color": "#a8edea,#fed6e3",
                "hasContent": True,
                "modalContent": {
                    "title": "Required Skills",
                    "body": f"<div class='d-flex flex-wrap mt-3'>{skills_list}</div>"
                }
            })
        
        # Employment Areas
        if career.prospective_employment_areas.exists():
            areas_list = "\n".join([f"<li>{area.name}</li>" for area in career.prospective_employment_areas.all()[:15]])
            aspects.append({
                "id": "employment-areas",
                "name": "Employment Areas",
                "icon": "building",
                "color": "#ff9a56,#ff6a88",
                "hasContent": True,
                "modalContent": {
                    "title": "Employment Areas",
                    "body": f"<ul class='list-styled'>{areas_list}</ul>"
                }
            })
        
        # Top Recruiters
        if career.prospective_recruiters.exists():
            recruiters_list = "\n".join([f"<li>{recruiter.name}</li>" for recruiter in career.prospective_recruiters.all()[:15]])
            aspects.append({
                "id": "recruiters",
                "name": "Top Recruiters",
                "icon": "users",
                "color": "#f857a6,#ff5858",
                "hasContent": True,
                "modalContent": {
                    "title": "Top Recruiters",
                    "body": f"<ul class='list-styled'>{recruiters_list}</ul>"
                }
            })
        
        # Salary
        salary = career.get_max_salary()
        if salary and salary != "N/A":
            # Get profession salary details if available
            from .models import Profession
            professions = Profession.objects.filter(career=career).order_by('-salary')[:5]
            salary_html = f"<p><strong>Maximum Salary Range:</strong> {salary}</p>"
            if professions.exists():
                salary_html += "<h5>Salary by Profession:</h5><ul class='list-styled'>"
                for prof in professions:
                    salary_html += f"<li><strong>{prof.name}:</strong> {prof.get_salary_display()}</li>"
                salary_html += "</ul>"
            aspects.append({
                "id": "salary",
                "name": "Salary Range",
                "icon": "rupee-sign",
                "color": "#ff6e7f,#bfe9ff",
                "hasContent": True,
                "modalContent": {
                    "title": "Salary Expectations",
                    "body": salary_html
                }
            })
        
        # Videos
        if career.videos.exists():
            videos_list = ""
            for video in career.videos.all()[:5]:
                videos_list += f"<li><strong>{video.name}</strong>"
                if video.description:
                    desc = strip_tags(video.description)[:100]
                    videos_list += f"<br><small>{desc}...</small>"
                videos_list += "</li>"
            aspects.append({
                "id": "videos",
                "name": "Career Videos",
                "icon": "video",
                "color": "#e0c3fc,#8ec5fc",
                "hasContent": True,
                "modalContent": {
                    "title": "Career Videos",
                    "body": f"<ul class='list-styled'>{videos_list}</ul>"
                }
            })
        
        # FAQs
        if career.careerFAQ.exists():
            faqs_html = ""
            for faq in career.careerFAQ.all()[:10]:
                faqs_html += f"<h5>{faq.question}</h5><p>{faq.answer}</p>"
            aspects.append({
                "id": "faqs",
                "name": "FAQs",
                "icon": "question-circle",
                "color": "#ffecd2,#fcb69f",
                "hasContent": True,
                "modalContent": {
                    "title": "Frequently Asked Questions",
                    "body": faqs_html
                }
            })
        
        mindmap_data = {
            "name": career.name,
            "summary": career.get_display_summary() or "",
            "aspects": aspects
        }
        
        return json.dumps(mindmap_data)

    @classmethod
    def _breadcrumb(self, career):
        url = reverse_lazy('careers:career')
        lst = [{'text': 'Career', 'url': url}, {'text': str(career), 'url': ''}]
        return get_breadcrumb(lst)
        
    def get(self, request,career_id,slug, *args, **kwargs):
        data={}  
        if is_ajax(request=request):
            clgdf=CareerDocumentFilter()
            ctx=clgdf.get_career_detail(request,slug,is_ajax=True)
            html=render_to_string("topteenfrontend/includes/explore_college.html",ctx)
            return HttpResponse(html)    
        return render(request, self.template_name,self.get_context(request,career_id,slug, args, kwargs))


def convert_xmind_to_jsmind_json(xmind_data, career_name=None):
    """
    Convert xmindparser output to jsMind format.
    If career_name is provided, use it as the root topic title instead of XMind file's title.
    """
    if not xmind_data or not isinstance(xmind_data, list) or len(xmind_data) == 0:
        return None
    
    sheet = xmind_data[0]
    root_topic = sheet.get('topic', {})
    
    def build_jsmind_node(topic, node_id='root', parent_id=None, is_root=False):
        """Recursively build jsMind node structure"""
        # Use career_name for root node if provided, otherwise use XMind title
        if is_root and career_name:
            title = career_name
        else:
            title = topic.get('title') or topic.get('label') or 'Untitled'
        
        node = {
            'id': node_id,
            'topic': str(title),
            'expanded': True
        }
        
        if parent_id:
            node['parentid'] = parent_id
        
        children = []
        topics = topic.get('topics', [])
        
        if isinstance(topics, list):
            for idx, child in enumerate(topics):
                child_id = f'{node_id}-{idx}'
                children.append(build_jsmind_node(child, child_id, node_id, is_root=False))
        elif isinstance(topics, dict):
            for topic_list in topics.values():
                if isinstance(topic_list, list):
                    for idx, child in enumerate(topic_list):
                        child_id = f'{node_id}-{idx}'
                        children.append(build_jsmind_node(child, child_id, node_id, is_root=False))
        
        if children:
            node['children'] = children
        
        return node
    
    root_node = build_jsmind_node(root_topic, is_root=True)
    
    # Use career_name in meta if provided
    meta_name = career_name if career_name else sheet.get('title', 'Mind Map')
    
    return {
        'meta': {
            'name': meta_name,
            'author': 'XMind Converter',
            'version': '1.0'
        },
        'format': 'node_tree',
        'data': root_node
    }


def career_mindmap_json_api(request, career_id, slug):
    """
    API endpoint: Convert career's XMind file to JSON (jsMind format)
    Falls back to parsing HTML from career.description if XMind file not found.
    Uses career.get_xmind_file_path() which points to /career_mindmap directory.
    Returns graceful 404 if neither XMind file nor description available.
    """
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        career = get_object_or_404(Career, id=career_id, slug=slug)
        
        # Try XMind file first
        xmind_file_path = career.get_xmind_file_path()
        
        if xmind_file_path and xmind_file_path.exists():
            # Process XMind file
            try:
                xmind_data = xmindparser.xmind_to_dict(str(xmind_file_path))
                
                if xmind_data:
                    jsmind_json = convert_xmind_to_jsmind_json(xmind_data, career_name=career.name)
                    
                    if jsmind_json:
                        response = JsonResponse(jsmind_json, json_dumps_params={'ensure_ascii': False})
                        response['Access-Control-Allow-Origin'] = '*'
                        response['Content-Type'] = 'application/json; charset=utf-8'
                        return response
            except Exception as e:
                logger.warning(f'Error processing XMind file for career {career.name}: {str(e)}')
                # Fall through to HTML parsing fallback
        
        # Fallback: Parse HTML from career.description using model method
        if career.description:
            try:
                jsmind_json = career.convert_description_to_jsmind_json()
                
                if jsmind_json:
                    response = JsonResponse(jsmind_json, json_dumps_params={'ensure_ascii': False})
                    response['Access-Control-Allow-Origin'] = '*'
                    response['Content-Type'] = 'application/json; charset=utf-8'
                    return response
            except Exception as e:
                logger.warning(f'Error parsing HTML description for career {career.name}: {str(e)}')
        
        # No mindmap available from either source
        response = JsonResponse({
            'error': 'Mind map not available for this career',
            'available': False
        }, status=404)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    except Exception as e:
        # Catch-all for any unexpected errors
        logger.error(f'Unexpected error in career_mindmap_json_api: {str(e)}')
        
        response = JsonResponse({
            'error': 'Service temporarily unavailable',
            'available': False
        }, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response


class Professions(TemplateView):
    template_name = "template20/profession.html"
    
    def html_head(self):
        title="Profession"
        return build_html_head(title=title, description=title)

    def get_context(self, request, *args, **kwargs):
        ctx={}
        career_slug = kwargs.get('career_slug')
        career=get_object_or_404(Career, slug=career_slug)
        profession=Profession.objects.filter(career=career)
        paginated_profession =Paginator(profession,12)
        page_number = request.GET.get('page')
        try:
            profession_page_obj = paginated_profession.get_page(page_number)
        except PageNotAnInteger:
            profession_page_obj = paginated_profession.get_page(1)
        except EmptyPage:
            profession_page_obj = paginated_profession.get_page(paginated_profession.num_pages)

        ctx['professions']= profession_page_obj
        ctx['career'] = career
        ctx['html_head'] = self.html_head()
        return ctx
        
    def get(self, request, *args, **kwargs):     
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
 

class CareerTagFilter(TemplateView):
    template_name = "topteenfrontend/careers.html"

    def __html_head(self):
        name="Career"
        return build_html_head(title=name, description=name)

    def get_context(self, request,tagslug, *args, **kwargs):
        try:
            docmentservice=CareerDocumentFilter()
            ctx=docmentservice.get_career_list_context(request,tagslug)
        except Exception as e:
            logger.warning("Elasticsearch not available, using Django ORM fallback: %s", e)
            ctx = self.get_fallback_context(request, tagslug)
        
        if request.GET.getlist('professions') or request.GET.getlist('skills') or request.GET.getlist('courses'):
            pro=request.GET.getlist('professions')
            skill=request.GET.getlist('skills')
            course=request.GET.getlist('courses')
            data=pro+skill+course
            ctx['data']=data
        ctx['html_head']=self.__html_head()
        return ctx
        
    def get(self, request,tagslug=None,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,tagslug,args, kwargs))
    
    def get_fallback_context(self, request, tagslug):
        from django.core.paginator import Paginator
        from .models import Career, CareerCluster, CareerTags, Skill, ProspectiveEmploymentArea, ProspectiveRecruiter, Profession
        from courses.models import Course
        
        # Get careers filtered by tag
        try:
            tag = CareerTags.objects.get(slug=tagslug)
            careers = Career.objects.filter(
                publish_status=1, 
                career_tags=tag
            ).select_related().prefetch_related(
                'skills', 'career_tags', 'prospective_employment_areas', 'prospective_recruiters', 'courses'
            ).order_by('name')
        except CareerTags.DoesNotExist:
            careers = Career.objects.none()

        # Handle selected filters
        selected_professions = request.GET.getlist('professions')
        selected_skills = request.GET.getlist('skills')
        selected_cluster = request.GET.get('cluster')
        
        # Apply cluster filtering (handle both single and multi-select)
        if selected_cluster:
            try:
                cluster_id = int(selected_cluster) if isinstance(selected_cluster, str) and selected_cluster.isdigit() else selected_cluster
                careers = careers.filter(career_cluster__id=cluster_id).distinct()
            except (ValueError, TypeError):
                pass  # Skip invalid cluster ID
        
        # Apply profession filtering - OR logic within professions
        if selected_professions:
            cleaned_professions = [p.strip() for p in selected_professions if p and p.strip()]
            if cleaned_professions:
                careers = careers.filter(profession__name__in=cleaned_professions).distinct()
        
        # Apply skill filtering - OR logic within skills
        if selected_skills:
            cleaned_skills = [s.strip() for s in selected_skills if s and s.strip()]
            if cleaned_skills:
                careers = careers.filter(skills__name__in=cleaned_skills).distinct()

        # Basic search filtering
        search_query = request.GET.get('search', '')
        if search_query:
            careers = careers.filter(
                Q(name__icontains=search_query) | 
                Q(summary__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # Pagination
        paginator = Paginator(careers, 20)
        page = request.GET.get('page')
        try:
            careers_page = paginator.page(page)
        except PageNotAnInteger:
            careers_page = paginator.page(1)
        except EmptyPage:
            careers_page = paginator.page(paginator.num_pages)
        
        # Only load clusters that have active careers AND are active themselves
        clusters = CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1  # Only active clusters
        ).distinct().order_by('name')
        
        tags = CareerTags.objects.all()[:50]
        employment_areas = ProspectiveEmploymentArea.objects.all()[:50]
        recruiters = ProspectiveRecruiter.objects.all()[:50]
        courses = Course.objects.all()[:50]
        
        # Only load professions that have active careers AND are active themselves
        professions = Profession.objects.filter(
            career__publish_status=1,
            object_status=1  # Only active professions
        ).distinct().order_by('name')[:100]
        
        # Only load skills that have active careers AND are active themselves
        skills = Skill.objects.filter(
            career__publish_status=1,
            object_status=1  # Only active skills
        ).distinct().order_by('priority', 'name')[:200]
        
        # Filter professions based on selected cluster
        filtered_professions = professions
        if selected_cluster:
            # Get professions from careers in selected cluster
            careers_with_cluster = Career.objects.filter(
                career_cluster__id=selected_cluster,
                publish_status=1
            ).distinct()
            
            # Get professions from those careers (only active ones)
            filtered_professions = Profession.objects.filter(
                career__in=careers_with_cluster,
                object_status=1  # Only active professions
            ).distinct().order_by("name")
        
        # Filter skills based on selected professions
        filtered_skills = skills
        if selected_professions:
            # Get careers that have the selected professions
            careers_with_professions = Career.objects.filter(
                profession__name__in=selected_professions,
                publish_status=1
            ).distinct()
            
            # Get skills from those careers (only active ones)
            filtered_skills = Skill.objects.filter(
                career__in=careers_with_professions,
                object_status=1  # Only active skills
            ).distinct().order_by("priority", "name")
        
        # Create facets_filter with proper counts and selection status
        facets_filter = {
            "skill": [(skill.name, 0, skill.name in selected_skills) for skill in filtered_skills[:50]],
            "profession": [(prof.name, 0, prof.name in selected_professions) for prof in filtered_professions[:50]],
        }
        
        return {
            'careers': careers_page,
            'clusters': clusters,
            'tags': tags,
            'skills': skills,
            'professions': professions,
            'employment_areas': employment_areas,
            'recruiters': recruiters,
            'courses': courses,
            'total_careers': careers.count(),
            'facets_filter': facets_filter,
            'selected_professions': selected_professions,
            "selected_cluster": selected_cluster,
            'selected_skills': selected_skills,
            "selected_cluster": selected_cluster,
            'current_tag': tag if 'tag' in locals() else None,
        }

class CareerLibrary(TemplateView):
    tracks_template_name = 'template20/careerlibrary.html'
    category_template_name = 'template20/career_category.html'

    def __breadcrumb(self, name, is_category=False):
        if is_category:
            l = [
                {'text': 'Career Tracks', 'url': reverse_lazy('careers:defaultcareerlibrary')},
                {'text': name, 'url': ''},
            ]
        else:
            l = [{'text': 'Career Tracks', 'url': ''}]
        return get_breadcrumb(l)

    def __html_head(self,name):
        return build_html_head(title=name, description=name)

    def get_context(self,request,cluster_slug,cluster_id,*args,**kwargs):
        ctx=CareerCluster.get_career_library_context(request,cluster_slug,cluster_id)
        ctx['html_head']=self.__html_head(ctx["cluster_name"])
        ctx['breadcrumb']=self.__breadcrumb(ctx["cluster_name"], is_category=bool(cluster_slug and cluster_id))
        ctx['body_css_class']="bg-white"
        return ctx

    def get(self, request,cluster_slug=None,cluster_id=None, *args, **kwargs):
        template_name = self.category_template_name if (cluster_slug and cluster_id) else self.tracks_template_name
        return render(request, template_name, self.get_context(request,cluster_slug,cluster_id, *args, **kwargs))

class CareerVideosView(TemplateView):
    template_name ="template20/career_videos_list.html"

    def html_head(self,name):
        # name='Explore Career Videos'
        return build_html_head(title=name, description=name)

    def _breadcrumb(self):
        return get_breadcrumb([{'text': 'Career Videos', 'url': ''}])

    def get_context(self,request,*args, **kwargs):
        ctx={}
        search_videos = request.GET.get('search')
        ctx['breadcrumb'] = self._breadcrumb()
        if search_videos:
            ctx['search_videos']=search_videos
            ctx['heading']=f"Results for '{search_videos}'"
            videos = Videos.objects.filter( Q(name__icontains=search_videos)).prefetch_related('category')
            ctx['videos'] = videos
            ctx['categories']=VideoCategory.objects.all()
            paginator = Paginator(videos, 5)
            page_numbers = request.GET.get('page')
            ctx['page_obj'] = paginator.get_page(page_numbers)
            ctx['html_head']=self.html_head('{} - Search Videos'.format(search_videos))
        else:
            ctx['search_videos']=""
            ctx['heading']="Explore Videos"
            videos = Videos.objects.all().prefetch_related('category')
            ctx['videos'] = videos
            ctx['categories']=VideoCategory.objects.all()
            paginator = Paginator(videos, 5)
            page_numbers = request.GET.get('page')
            ctx['page_obj'] = paginator.get_page(page_numbers)
            ctx['html_head']=self.html_head('Explore Career Videos - Page - {}'.format(ctx['page_obj'].number))
        
        # Parent->Student context for suggesting videos
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Videos)
                    ctx['bookmarked_video_ids'] = list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user,
                            student_id=int(student_id),
                            content_type=ct,
                        ).values_list("object_id", flat=True)
                    )
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
                else:
                    ctx['bookmarked_video_ids'] = []
            else:
                # Regular user bookmarks
                if request.user.is_authenticated:
                    ctx['bookmarked_video_ids'] = list(Videos.objects.filter(shortlist=request.user).values_list('id', flat=True))
                else:
                    ctx['bookmarked_video_ids'] = []
        except Exception:
            if request.user.is_authenticated:
                ctx['bookmarked_video_ids'] = list(Videos.objects.filter(shortlist=request.user).values_list('id', flat=True))
            else:
                ctx['bookmarked_video_ids'] = []
        
        # Pre-evaluate thumbnail URLs for videos in page_obj
        video_thumbnails = {}
        if 'page_obj' in ctx and ctx['page_obj']:
            for video in ctx['page_obj'].object_list:
                video_thumbnails[video.id] = video.get_thumbnail_url()
        
        ctx['video_thumbnails'] = video_thumbnails
        
        from users.parent_suggestions import apply_student_parent_suggestions_context, maybe_mark_parent_suggestions_seen
        apply_student_parent_suggestions_context(ctx, request, "videos")
        maybe_mark_parent_suggestions_seen(
            request, "videos", is_parent_student_context=ctx.get("is_parent_student_context", False)
        )
        return ctx

    def get(self,request,*args, **kwargs):
        return render(request, self.template_name,self.get_context(request,args,kwargs))

class CategoryCareerVideosView(TemplateView):
    template_name ="template20/career_videos_list.html"

    def html_head(self,name):
        return build_html_head(title=name, description=name)

    def _breadcrumb(self, category_name):
        return get_breadcrumb([
            {'text': 'Career Videos', 'url': reverse_lazy('careers:careervideos')},
            {'text': category_name, 'url': ''},
        ])

    def get_context(self,request,category_slug,*args, **kwargs):
        ctx={}
        category=get_object_or_404(VideoCategory,slug=category_slug)
        ctx['videos'] = Videos.objects.filter(category=category)
        ctx['categories']=VideoCategory.objects.all()
        ctx['category'] = category
        paginator = Paginator(ctx['videos'], 5)
        page_numbers = request.GET.get('page')
        ctx['page_obj'] = paginator.get_page(page_numbers)
        ctx['html_head']=self.html_head('Explore Career Videos - {} - Page {}'.format(category.name,ctx['page_obj'].number))
        ctx['breadcrumb'] = self._breadcrumb(category.name)
        ctx['heading'] = f"Videos in {category.name}"
        ctx['search_videos'] = ""
        
        # Parent->Student context for suggesting videos
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Videos)
                    ctx['bookmarked_video_ids'] = list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user,
                            student_id=int(student_id),
                            content_type=ct,
                        ).values_list("object_id", flat=True)
                    )
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
                else:
                    ctx['bookmarked_video_ids'] = []
            else:
                if request.user.is_authenticated:
                    ctx['bookmarked_video_ids'] = list(Videos.objects.filter(shortlist=request.user).values_list('id', flat=True))
                else:
                    ctx['bookmarked_video_ids'] = []
        except Exception:
            if request.user.is_authenticated:
                ctx['bookmarked_video_ids'] = list(Videos.objects.filter(shortlist=request.user).values_list('id', flat=True))
            else:
                ctx['bookmarked_video_ids'] = []
        
        # Pre-evaluate thumbnail URLs for videos in page_obj
        video_thumbnails = {}
        if 'page_obj' in ctx and ctx['page_obj']:
            for video in ctx['page_obj'].object_list:
                video_thumbnails[video.id] = video.get_thumbnail_url()
        
        ctx['video_thumbnails'] = video_thumbnails
        
        from users.parent_suggestions import apply_student_parent_suggestions_context, maybe_mark_parent_suggestions_seen
        apply_student_parent_suggestions_context(ctx, request, "videos")
        maybe_mark_parent_suggestions_seen(
            request, "videos", is_parent_student_context=ctx.get("is_parent_student_context", False)
        )
        return ctx

    def get(self,request,category_slug,*args, **kwargs):
        return render(request, self.template_name,self.get_context(request,category_slug,args,kwargs))

class VideoDetail(TemplateView):
    template_name = "template20/video_detail.html"

    def html_head(self,name):
        return build_html_head(title=name, description=name)

    def get_context(self,request,video_slug, *args, **kwargs):  
        ctx={}
        video=get_object_or_404(Videos,slug=video_slug)
        ctx['video']=video 
        ctx['categories']=VideoCategory.objects.all()
        ctx['breadcrumb'] = self._breadcrumb(video)
        ctx['html_head']=self.html_head(video.name)
        
        # Parent->Student context for suggesting videos
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            student_id = request.GET.get("student_id")
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                from django.contrib.contenttypes.models import ContentType
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Videos)
                    ctx['is_video_bookmarked'] = ParentStudentBookmark.objects.filter(
                        parent=request.user, student_id=int(student_id), content_type=ct, object_id=video.id
                    ).exists()
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
                else:
                    ctx['is_video_bookmarked'] = False
            else:
                if request.user.is_authenticated:
                    ctx['is_video_bookmarked'] = video.shortlist.filter(id=request.user.id).exists()
                else:
                    ctx['is_video_bookmarked'] = False
        except Exception:
            if request.user.is_authenticated:
                ctx['is_video_bookmarked'] = video.shortlist.filter(id=request.user.id).exists()
            else:
                ctx['is_video_bookmarked'] = False
        
        # Get related videos from same categories
        related_videos = Videos.objects.none()
        if video.category.exists():
            related_videos = Videos.objects.filter(
                category__in=video.category.all()
            ).exclude(id=video.id).distinct()[:6]
        
        # If not enough related videos, get recent videos
        if related_videos.count() < 6:
            recent_videos = Videos.objects.exclude(id=video.id).order_by('-created')[:6]
            related_videos = (related_videos | recent_videos).distinct()[:6]
        
        # Pre-compute thumbnail URLs for related videos (same as career-videos listing)
        related_video_thumbnails = {}
        for rv in related_videos:
            try:
                related_video_thumbnails[rv.id] = rv.get_thumbnail_url()
            except Exception:
                related_video_thumbnails[rv.id] = None
        
        ctx['related_videos'] = related_videos
        ctx['related_video_thumbnails'] = related_video_thumbnails
        # Same-origin WebVTT proxy URL when a .vtt exists beside the video (see Videos.get_caption_vtt_url)
        ctx["caption_track_proxy_url"] = None
        if video.get_caption_vtt_url():
            ctx["caption_track_proxy_url"] = reverse("careers:video_caption_vtt", args=[video.id])
        return ctx

    def _breadcrumb(self, video):
        return get_breadcrumb([
            {'text': 'Career Videos', 'url': reverse_lazy('careers:careervideos')},
            {'text': video.name, 'url': ''},
        ])
    
        
    def get(self, request,video_slug, *args, **kwargs):     
        return render(request, self.template_name, self.get_context(request,video_slug,args, kwargs))


def career_video_caption_vtt(request, video_id):
    """
    Public proxy for career video WebVTT files (same path as MP4 with .vtt on CDN/S3).
    Avoids crossorigin on <video>, which often breaks MP4 playback when CORS is not set on the bucket.
    """
    import urllib.error
    import urllib.request

    video = get_object_or_404(Videos, pk=video_id, object_status=choices.ObjectStatus.ACTIVE)
    vtt_url = video.get_caption_vtt_url()
    if not vtt_url:
        raise Http404("No captions for this video.")
    try:
        req = urllib.request.Request(
            vtt_url,
            headers={"User-Agent": "TopTeen-career-video-caption/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            # Support HEAD requests so the client can check availability without downloading.
            if request.method == "HEAD":
                data = b""
            else:
                data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        raise Http404("Captions unavailable.")
    r = HttpResponse(data, content_type="text/vtt; charset=utf-8")
    r["Cache-Control"] = "public, max-age=3600"
    return r


class CareerMindmapView(TemplateView):
    """
    Dedicated career mindmap page. Supported ?variation= values: 6 (radial), 16–19 (classic / career-tree API).
    Legacy variation numbers are coerced to the site default or radial (6).
    """
    template_name = "template20/career_mindmap.html"
    
    def html_head(self, career):
        titleb = f"{career.name} - Mind Map"
        descriptionb = f"Interactive mind map for {career.name}"
        return build_html_head(title=titleb, description=descriptionb)
    
    def get_context(self, request, *args, **kwargs):
        ctx = {}
        career_id = kwargs.get('career_id')
        slug = kwargs.get('slug')
        career = get_object_or_404(Career, id=career_id, slug=slug)
        ctx['career'] = career
        
        # Get variation from query parameter; default from Core website settings (DEFAULT_MINDMAP_TYPE)
        from core.models import Configuration

        allowed = {c[0] for c in choices.MINDMAP_TYPE_CHOICES}
        default_type = choices.coerce_default_mindmap_type(
            Configuration.get('DEFAULT_MINDMAP_TYPE', '6', editable=True) or '6'
        )
        variation_param = request.GET.get('variation')
        variation = str(variation_param).strip() if variation_param else default_type
        variation = variation or default_type
        if variation not in allowed:
            variation = default_type
        ctx['variation'] = variation
        ctx['default_mindmap_type'] = default_type
        ctx['mindmap_type_choices'] = choices.MINDMAP_TYPE_CHOICES
        ctx['variations'] = dict(choices.MINDMAP_TYPE_CHOICES)
        
        # Breadcrumb
        ctx['breadcrumb'] = self._breadcrumb(career)
        ctx['html_head'] = self.html_head(career)
        
        # Check if XMind file exists
        try:
            ctx['has_xmind_file'] = career.has_xmind_file()
            ctx['xmind_file_path'] = str(career.get_xmind_file_path()) if career.has_xmind_file() else None
            ctx['career_clusters'] = list(career.career_cluster.all())
        except Exception:
            ctx['has_xmind_file'] = False
            ctx['xmind_file_path'] = None
            ctx['career_clusters'] = []
        
        return ctx
    
    def _breadcrumb(self, career):
        return get_breadcrumb([
            {'text': 'Careers', 'url': reverse_lazy('careers:career')},
            {'text': career.name, 'url': reverse('careers:careerdetail', args=[career.slug, career.id])},
            {'text': 'Mind Map', 'url': ''},
        ])
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
class CareerRatingView(TemplateView):
    def get(self,request):
        rate= request.GET.get("rate")
        career_slug= request.GET.get("slug")
        career=get_object_or_404(Career,slug=career_slug)
        if rate and career:
            obj,created=CareerRating.objects.get_or_create(user=request.user,career=career)
            if rate == '0':
                obj.rating=obj.rating
            else:
                obj.rating=rate
            obj.save()
            return JsonResponse({'success':'true'},safe=False)
        return JsonResponse({'success':'false'})
    
    def post(self,request):
        url=request.META.get('HTTP_REFERER')
        career_slug= request.POST.get("slug")
        title=request.POST.get("title")
        description=request.POST.get("description")
        career=get_object_or_404(Career,slug=career_slug)
        if career and title and description:
            obj,created=CareerRating.objects.get_or_create(user=request.user,career=career)
            obj.title=title
            obj.description=description
            obj.save()
            messages.success(request,"Thank you for your honest review")
            return redirect(url)
        messages.error(request,"Something went wrong !!")
        return redirect(url)
    
def career_rate_delete_view(request,id):
    url=request.META.get('HTTP_REFERER')
    rating=get_object_or_404(CareerRating,id=id)
    rating.delete()
    return redirect(url)

def shortlist_video_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Authentication required"}, status=401)
    id=request.GET.get("id")
    video=get_object_or_404(Videos,id=id)

    if getattr(request.user, "user_type", None) == choices.UserType.PARENT:
        from users.parent_saved_items import toggle_parent_video_bookmark

        student_id = request.GET.get("student_id")
        try:
            sid = int(student_id) if student_id not in (None, "", b"") else None
        except (TypeError, ValueError):
            sid = None
        return JsonResponse(toggle_parent_video_bookmark(request.user, video, student_id=sid))

    data=Videos.objects.filter(id=id,shortlist=request.user).exists()
    if data:
        video.shortlist.remove(request.user)
        return JsonResponse({'success':'false'})
    else:
        video.shortlist.add(request.user)
        return JsonResponse({'success':'true'})