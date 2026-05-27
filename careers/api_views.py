"""
API views for DOCX processing and autocomplete
"""
import queue
import threading
import time
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.urls import reverse
from .models import Profession, Skill, CareerCluster, Career, Videos
from .docx_utils import convert_docx_to_html, extract_career_data_from_html
from .ai_query_processor import QueryProcessor
import json
import logging

logger = logging.getLogger(__name__)


def extract_accordion_sections(career):
    """Accordion section metadata from centralized H2 parser (core.accordion_utils)."""
    from core.accordion_utils import accordion_sections_for_api

    try:
        return accordion_sections_for_api(career)
    except Exception as e:
        logger.error('Error extracting accordion sections: %s', e)
        return []


def detect_section_query(query):
    """Detect if query is asking for a specific section/feature of a career"""
    query_lower = query.lower().strip()
    
    # Section keywords mapping
    section_keywords = {
        'mindmap': ['mindmap', 'mind map', 'mind-map', 'mindmap of', 'mind map of', 'show mindmap', 'show mind map', 'career mindmap', 'career mind map'],
        'roles': ['roles', 'responsibilities', 'role description', 'duties'],
        'eligibility': ['eligibility', 'study route', 'education', 'qualification', 'requirements'],
        'skills': ['skills', 'skill', 'knowledge', 'abilities'],
        'pros and cons': ['pros and cons', 'pros', 'cons', 'advantages', 'disadvantages'],
        'employment': ['employment', 'job areas', 'work areas', 'where to work'],
        'courses': ['courses', 'course', 'programs', 'program', 'specializations'],
        'overview': ['overview', 'introduction', 'summary', 'about'],
        'internships': ['internships', 'internship', 'practical exposure', 'training'],
        'employers': ['employers', 'prominent employers', 'companies', 'recruiters', 'organizations', 'employer'],
        'trends': ['trends', 'future outlook', 'industry trends', 'future'],
        'advice': ['advice', 'tips', 'guidance', 'recommendations']
    }
    
    # Check if query contains a career name and a section keyword
    detected_section = None
    for section_id, keywords in section_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            detected_section = section_id
            break
    
    return detected_section


def format_career_list_item(career):
    """Light career payload for list/search results. Use career-detail API for full data."""
    cluster_name = None
    cluster_url = None
    if hasattr(career, 'career_cluster') and career.career_cluster.exists():
        cluster = career.career_cluster.first()
        cluster_name = cluster.name
        try:
            cluster_url = reverse('careers:careerlibrary', args=[cluster.slug, cluster.id])
        except Exception:
            pass
    has_mindmap = False
    try:
        if hasattr(career, 'has_xmind_file') and career.has_xmind_file():
            from core.models import Configuration
            enabled = Configuration.get('ENABLE_CAREER_MINDMAP', 'true', editable=True)
            if str(enabled).lower() in ('true', '1', 'yes', 'on'):
                has_mindmap = True
    except Exception:
        pass
    summary = (career.get_display_summary() or '')[:200] if hasattr(career, 'get_display_summary') else ''
    return {
        'id': career.id,
        'name': career.name,
        'slug': career.slug,
        'summary': summary,
        'url': reverse('careers:careerdetail', args=[career.slug, career.id]),
        'cluster_name': cluster_name,
        'cluster_url': cluster_url,
        'has_mindmap': has_mindmap,
        'detail_url': reverse('careers:career_detail_api') + '?id=' + str(career.id),
    }


def format_career_for_response(career, include_sections=False):
    """Format a single career object for API response"""
    from django.utils.html import strip_tags
    
    # Get salary info
    salary = None
    salary_display = None
    try:
        if hasattr(career, 'get_max_salary'):
            salary_raw = career.get_max_salary()
            if salary_raw and salary_raw != 'N/A':
                salary_value = str(salary_raw).replace('LPA', '').replace('lpa', '').strip()
                if salary_value and salary_value != '0' and salary_value != '0.0' and salary_value != '':
                    salary = salary_raw
                    salary_display = salary_value
    except:
        pass
    
    # Get cluster info
    cluster_name = None
    cluster_url = None
    if hasattr(career, 'career_cluster') and career.career_cluster.exists():
        cluster = career.career_cluster.first()
        cluster_name = cluster.name
        try:
            cluster_url = reverse('careers:careerlibrary', args=[cluster.slug, cluster.id])
        except:
            pass
    
    # Get skills
    skills_list = []
    all_skills_list = []
    if hasattr(career, 'skills'):
        all_skills_list = [skill.name for skill in career.skills.filter(object_status=1) if skill.name]
        skills_list = all_skills_list[:5]
    
    # Get employment areas
    employment_areas = []
    all_employment_areas = []
    if hasattr(career, 'prospective_employment_areas'):
        all_employment_areas = [area.name for area in career.prospective_employment_areas.all() if area.name]
        employment_areas = all_employment_areas[:3]
    
    # Get related courses
    related_courses = []
    all_related_courses = []
    if hasattr(career, 'courses'):
        for course in career.courses.all()[:10]:
            if course.name:
                all_related_courses.append({
                    'name': course.name,
                    'slug': course.slug if hasattr(course, 'slug') else None
                })
        related_courses = [c['name'] for c in all_related_courses[:3]]
    
    # Get career videos
    videos_list = []
    if hasattr(career, 'videos'):
        for video in career.videos.filter(object_status=1)[:3]:
            if video.name:
                try:
                    video_url = reverse('careers:videodetail', args=[video.slug]) if hasattr(video, 'slug') and video.slug else None
                except:
                    video_url = None
                video_data = {
                    'name': video.name,
                    'slug': video.slug if hasattr(video, 'slug') else None,
                    'url': video_url,
                }
                # Add video image if available
                if hasattr(video, 'video_image') and video.video_image:
                    video_data['image_url'] = video.video_image.url
                elif hasattr(video, 'upload_video') and video.upload_video:
                    video_data['video_url'] = video.upload_video.url
                videos_list.append(video_data)
    
    related_careers_list = []
    try:
        from careers.related_careers import get_related_careers
        for rel_career in get_related_careers(career, limit=6, published_only=True):
            related_careers_list.append({
                'id': rel_career.id,
                'name': rel_career.name,
                'slug': rel_career.slug,
                'url': reverse('careers:careerdetail', args=[rel_career.slug, rel_career.id]),
                'summary': (rel_career.get_display_summary() or '')[:100],
            })
    except Exception:
        pass
    
    # Get eligibility from description_json if available
    eligibility_text = None
    eligibility_full = None
    if career.description_json:
        sections = career.description_json.get('sections', {})
        eligibility_section = sections.get('study_route_and_eligibility_criteria', {})
        if eligibility_section and eligibility_section.get('html'):
            eligibility_clean = strip_tags(eligibility_section.get('html', '')).strip()
            if eligibility_clean:
                eligibility_text = eligibility_clean[:100] + ('...' if len(eligibility_clean) > 100 else '')
                eligibility_full = eligibility_section.get('html', '')
    
    # Get role description from description_json if available
    role_description_full = None
    if career.description_json:
        sections = career.description_json.get('sections', {})
        roles_section = sections.get('roles_and_responsibilities', {})
        if roles_section and roles_section.get('html'):
            role_description_full = roles_section.get('html', '')
    
    # Get pros and cons from description_json if available
    pros_cons_full = None
    if career.description_json:
        sections = career.description_json.get('sections', {})
        # Pros/cons might be in a specific section or embedded in description
        # For now, leave as None as it's not a standard section
    
    # Check if mindmap exists and is enabled site-wide
    has_mindmap = False
    try:
        if hasattr(career, 'has_xmind_file') and career.has_xmind_file():
            from core.models import Configuration
            enabled = Configuration.get('ENABLE_CAREER_MINDMAP', 'true', editable=True)
            if str(enabled).lower() in ('true', '1', 'yes', 'on'):
                has_mindmap = True
    except Exception:
        pass
    
    # Get rating
    rating = None
    try:
        if hasattr(career, 'get_average_rating'):
            rating = career.get_average_rating()
            try:
                rating = float(rating)
            except:
                pass
    except:
        pass
    
    # Get available sections from description_json
    available_sections = []
    if career.description_json:
        sections = career.description_json.get('sections', {})
        # Map section keys to display info
        section_mapping = {
            'roles_and_responsibilities': {'id': 'roles', 'label': 'Roles & Responsibilities', 'icon': 'bx-briefcase', 'color': '#28a745'},
            'study_route_and_eligibility_criteria': {'id': 'eligibility', 'label': 'Study Route & Eligibility', 'icon': 'bx-book-reader', 'color': '#ffc107'},
            'significant_observations': {'id': 'observations', 'label': 'Significant Observations', 'icon': 'bx-info-circle', 'color': '#17a2b8'},
            'internships_and_practical_exposure': {'id': 'internships', 'label': 'Internships & Practical Exposure', 'icon': 'bx-briefcase-alt', 'color': '#6f42c1'},
            'courses_and_specializations': {'id': 'courses_spec', 'label': 'Courses & Specializations', 'icon': 'bx-book', 'color': '#fd7e14'},
            'prominent_employers': {'id': 'employers', 'label': 'Prominent Employers', 'icon': 'bx-building', 'color': '#20c997'},
            'salary_expectations': {'id': 'salary', 'label': 'Salary Expectations', 'icon': 'bx-money', 'color': '#e83e8c'},
            'skills_required_industry_trends': {'id': 'skills_trends', 'label': 'Skills & Industry Trends', 'icon': 'bx-trending-up', 'color': '#6610f2'},
            'advice_for_aspiring': {'id': 'advice', 'label': 'Advice for Aspiring', 'icon': 'bx-bulb', 'color': '#ffc107'},
        }
        
        for section_key, section_data in sections.items():
            if section_data and section_data.get('html'):
                if section_key in section_mapping:
                    available_sections.append(section_mapping[section_key])
    
    formatted = {
        'id': career.id,
        'name': career.name,
        'slug': career.slug,
        'summary': (career.get_display_summary() or '')[:200],
        'salary': salary,
        'salary_display': salary_display,
        'has_salary': salary is not None,
        'cluster_name': cluster_name,
        'cluster_url': cluster_url,
        'skills': skills_list,
        'all_skills': all_skills_list,
        'employment_areas': employment_areas,
        'all_employment_areas': all_employment_areas,
        'related_courses': related_courses,
        'all_related_courses': all_related_courses,
        'eligibility': eligibility_text,
        'eligibility_full': eligibility_full,
        'role_description': role_description_full,
        'pros_cons': pros_cons_full,
        'has_mindmap': has_mindmap,
        'rating': rating,
        'url': reverse('careers:careerdetail', args=[career.slug, career.id]),
        'description_json_sections': available_sections,  # Add available sections from description_json
        'description_json': career.description_json,  # Include full description_json for icon clicks
        'videos': videos_list,  # Add career videos
        'related_careers': related_careers_list,  # Add related careers
    }
    
    if include_sections:
        formatted['accordion_sections'] = extract_accordion_sections(career)
    
    return formatted


@csrf_exempt
@require_http_methods(["POST"])
def process_docx_api(request):
    """API endpoint to process DOCX files and return extracted content"""
    try:
        # Get the uploaded file
        docx_file = request.FILES.get('docx_file')
        if not docx_file:
            return JsonResponse({'error': 'No DOCX file provided'}, status=400)
        
        # Validate file type
        if not docx_file.name.lower().endswith('.docx'):
            return JsonResponse({'error': 'Only DOCX files are allowed'}, status=400)
        
        # Validate file size (10MB limit)
        if docx_file.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File size must be under 10MB'}, status=400)
        
        # Convert DOCX to HTML
        html_content = convert_docx_to_html(docx_file)
        
        # Extract title, summary, and description
        title, summary, description = extract_career_data_from_html(html_content)
        
        # Return the extracted content
        return JsonResponse({
            'success': True,
            'title': title,
            'summary': summary,
            'description': description
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing DOCX file: {str(e)}'}, status=500)

@require_http_methods(["GET"])
def autocomplete_professions(request):
    """
    API endpoint for profession autocomplete with unique results.
    - Filters by selected clusters (if provided)
    - Returns unique profession names (case-insensitive)
    - Supports search query
    - Only shows professions with published careers
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 100))  # Increased limit for better selection
    
    # Filter by cluster if provided (can be multiple)
    selected_clusters = request.GET.getlist('cluster')
    
    # Step 1: Get careers that have professions and are published
    careers_qs = Career.objects.filter(
        publish_status=1,
        profession__isnull=False
    )
    
    # Step 2: Filter by clusters if provided
    if selected_clusters:
        try:
            cluster_ids = [int(c) for c in selected_clusters if str(c).isdigit()]
            if cluster_ids:
                careers_qs = careers_qs.filter(
                    career_cluster__id__in=cluster_ids
                )
        except (ValueError, TypeError):
            pass
    
    # Step 3: Get unique profession names from these careers
    profession_qs = Profession.objects.filter(
        career__in=careers_qs,
        object_status=1
    ).exclude(
        name__isnull=True
    ).exclude(
        name=''
    )
    
    # Step 4: Apply search filter if provided
    if query:
        profession_qs = profession_qs.filter(
            Q(name__icontains=query)
        )
    
    # Step 5: Get distinct profession names (case-insensitive)
    # Use values_list with distinct to get unique names from database
    unique_names = profession_qs.values_list('name', flat=True).distinct()
    
    # Step 6: Build results with proper deduplication and career counts
    results = []
    seen_lower = set()  # Track seen names (case-insensitive)
    
    for name in unique_names.order_by('name')[:limit]:
        if not name or not name.strip():
            continue
        
        name_clean = name.strip()
        name_lower = name_clean.lower()
        
        # Skip duplicates (case-insensitive)
        if name_lower in seen_lower:
            continue
        
        seen_lower.add(name_lower)
        
        # Get first profession object with this name for ID
        profession = profession_qs.filter(name__iexact=name_clean).first()
        if not profession:
            continue
        
        # Count careers with this profession (respecting cluster filter)
        career_count_qs = Career.objects.filter(
            profession__name__iexact=name_clean,
            publish_status=1
        )
        
        if selected_clusters:
            try:
                cluster_ids = [int(c) for c in selected_clusters if str(c).isdigit()]
                if cluster_ids:
                    career_count_qs = career_count_qs.filter(
                        career_cluster__id__in=cluster_ids
                    )
            except (ValueError, TypeError):
                pass
        
        career_count = career_count_qs.distinct().count()
        
        # Only include if there are careers
        if career_count > 0:
            results.append({
                'id': profession.id,
                'text': f"{name_clean} ({career_count})",
                'value': name_clean
            })
    
    return JsonResponse({'results': results})

@require_http_methods(["GET"])
def autocomplete_skills(request):
    """API endpoint for skill autocomplete - only shows skills with published careers"""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 30))  # Optimized default limit for better performance
    
    # Filter by selected professions
    selected_professions = request.GET.getlist('professions')
    # Filter by selected clusters (can be multiple)
    selected_clusters = request.GET.getlist('cluster')
    
    # Start with careers that have skills and are published
    careers_with_skills = Career.objects.filter(
        publish_status=1,
        skills__isnull=False
    ).distinct()
    
    # If professions are selected, filter careers by those professions
    if selected_professions:
        careers_with_skills = careers_with_skills.filter(
            profession__name__in=selected_professions
        ).distinct()
    
    # If clusters are selected, filter careers by those clusters
    if selected_clusters:
        careers_with_skills = careers_with_skills.filter(
            career_cluster__id__in=selected_clusters
        ).distinct()
    
    # Get skills from those careers (only active ones)
    skills = Skill.objects.filter(
        career__in=careers_with_skills,
        object_status=1  # Only active skills
    ).distinct()
    
    # Apply search query
    if query:
        skills = skills.filter(Q(name__icontains=query))
    
    # Filter out blank/empty names, order, and limit
    skills = skills.exclude(name__isnull=True).exclude(name='').order_by('priority', 'name')[:limit]
    
    # Only return non-empty results that have associated careers (deduplicated by name)
    seen_names = set()  # Track unique names to prevent duplicates
    results = []
    for s in skills:
        if s.name and s.name.strip():
            name_lower = s.name.strip().lower()  # Case-insensitive comparison
            # Skip if we've already seen this name
            if name_lower in seen_names:
                continue
            # Count careers with this skill
            career_count = Career.objects.filter(
                skills=s,
                publish_status=1
            ).count()
            if career_count > 0:
                seen_names.add(name_lower)
                # Include count in the text
                results.append({
                    'id': s.id, 
                    'text': f"{s.name.strip()} ({career_count})", 
                    'value': s.name.strip()
                })
    
    return JsonResponse({'results': results})

@require_http_methods(["GET"])
def autocomplete_clusters(request):
    """API endpoint for cluster autocomplete - only shows clusters with published careers"""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 30))  # Optimized default limit for better performance
    
    # Get clusters directly used by published careers
    direct_cluster_ids = CareerCluster.objects.filter(
        career_clusters__publish_status=1
    ).values_list('id', flat=True).distinct()

    # Also include their parents so top-level tracks with only child careers can still be suggested
    parent_cluster_ids = CareerCluster.objects.filter(
        id__in=direct_cluster_ids
    ).exclude(parent__isnull=True).values_list('parent_id', flat=True).distinct()

    # Only include clusters that have published careers either directly OR via children
    clusters = CareerCluster.objects.filter(
        Q(id__in=direct_cluster_ids) | Q(id__in=parent_cluster_ids),
        object_status=1
    ).distinct()
    
    # Apply search query
    if query:
        clusters = clusters.filter(Q(name__icontains=query))
    
    # Filter out blank/empty names, order, and limit
    clusters = clusters.exclude(name__isnull=True).exclude(name='').order_by('name')[:limit]
    
    # Only return non-empty results that have associated careers (deduplicated by name)
    seen_names = set()  # Track unique names to prevent duplicates
    results = []
    for c in clusters:
        if c.name and c.name.strip():
            name_lower = c.name.strip().lower()  # Case-insensitive comparison
            # Skip if we've already seen this name
            if name_lower in seen_names:
                continue
            # Count published careers in this cluster or its children (active careers)
            career_count = Career.objects.filter(
                publish_status=1
            ).filter(
                Q(career_cluster=c) | Q(career_cluster__parent=c)
            ).distinct().count()
            if career_count > 0:
                seen_names.add(name_lower)
                # Include count in the text
                results.append({
                    'id': c.id, 
                    'text': f"{c.name.strip()} ({career_count})", 
                    'value': str(c.id)
                })
    
    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def cluster_cards_search_api(request):
    """Return JSON with count + HTML fragment of cluster cards (q). Used by careers page AJAX search."""
    from django.db.models import Count
    q = (request.GET.get('q') or '').strip()
    clusters_qs = CareerCluster.objects.filter(
        career_clusters__publish_status=1,
        object_status=1
    ).annotate(
        career_count=Count('career_clusters', distinct=True)
    ).filter(career_count__gt=0).distinct().order_by('name')
    if q:
        clusters_qs = clusters_qs.filter(name__icontains=q)
    clusters_list = list(clusters_qs)
    clusters_with_counts = [{'cluster': c, 'count': c.career_count} for c in clusters_list]
    html = render_to_string(
        'template20/includes/career_cluster_cards_fragment.html',
        {'clusters_with_counts': clusters_with_counts, 'request': request},
        request=request,
    )
    return JsonResponse({'count': len(clusters_list), 'html': html})


@require_http_methods(["GET"])
def autocomplete_careers(request):
    """API endpoint for career autocomplete - can be filtered by a cluster (track)."""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 20))

    # Optional: restrict suggestions to a given cluster (and its children)
    cluster_id = request.GET.get('cluster_id', '').strip()

    careers = Career.objects.filter(publish_status=1)

    if cluster_id:
        try:
            cluster_id_int = int(cluster_id)
            careers = careers.filter(
                Q(career_cluster__id=cluster_id_int) | Q(career_cluster__parent_id=cluster_id_int)
            ).distinct()
        except ValueError:
            pass

    if query:
        careers = careers.filter(name__icontains=query)

    careers = careers.exclude(name__isnull=True).exclude(name='').order_by('name')[:limit]

    seen_names = set()
    results = []
    for c in careers:
        nm = (c.name or '').strip()
        if not nm:
            continue
        key = nm.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        results.append({
            'id': c.id,
            'text': nm,
            'value': nm,
        })

    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def admin_autocomplete_careers(request):
    """
    Staff autocomplete for related-careers admin (all active careers, any publish status).
    Select2 format: { results: [ { id, text } ] }.
    """
    if not request.user.is_staff:
        return JsonResponse({'results': []}, status=403)

    query = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 30)), 50)
    exclude_id = request.GET.get('exclude_id', '').strip()

    careers = Career.objects.all().order_by('name')
    if exclude_id:
        try:
            careers = careers.exclude(id=int(exclude_id))
        except (TypeError, ValueError):
            pass
    if query:
        careers = careers.filter(name__icontains=query)

    careers = careers.exclude(name__isnull=True).exclude(name='')[:limit]

    results = [
        {'id': c.id, 'text': (c.name or '').strip()}
        for c in careers
        if (c.name or '').strip()
    ]
    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def autocomplete_careers_from_clusters(request):
    """
    API for inner (cluster) page filter: career search with suggestions as [careername] [cluster name].
    Select2-compatible: returns { results: [ { id, text } ] }.
    Optional cluster_id: limit to careers in that cluster (and its children).
    """
    query = (request.GET.get('q') or '').strip()
    limit = min(int(request.GET.get('limit', 30)), 50)
    cluster_id_param = (request.GET.get('cluster_id') or '').strip()

    careers = Career.objects.filter(publish_status=1).prefetch_related(
        'career_cluster'
    ).exclude(name__isnull=True).exclude(name='')

    if cluster_id_param:
        try:
            cid = int(cluster_id_param)
            careers = careers.filter(
                Q(career_cluster__id=cid) | Q(career_cluster__parent_id=cid)
            ).distinct()
        except ValueError:
            pass

    if query:
        careers = careers.filter(
            Q(name__icontains=query) | Q(career_cluster__name__icontains=query)
        ).distinct()

    careers = careers.order_by('name', 'id')[:limit]

    seen_ids = set()
    results = []
    for c in careers:
        if c.id in seen_ids:
            continue
        seen_ids.add(c.id)
        career_name = (c.name or '').strip() or 'Career'
        cluster_names = []
        if hasattr(c, 'career_cluster') and c.career_cluster.exists():
            cluster_names = [cl.name for cl in c.career_cluster.all() if cl and cl.name]
        cluster_part = ' | '.join(cluster_names) if cluster_names else ''
        text = f"{career_name}  [{cluster_part}]" if cluster_part else career_name
        results.append({
            'id': str(c.id),  # string so Select2 multiselect matches form values
            'text': text,
        })

    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def autocomplete_videos(request):
    """API endpoint for career video autocomplete - returns video titles for suggest dropdown."""
    query = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 15)), 30)

    videos = Videos.objects.all().exclude(name__isnull=True).exclude(name='')
    if query:
        videos = videos.filter(name__icontains=query)
    videos = videos.order_by('name')[:limit]

    seen = set()
    results = []
    for v in videos:
        name = (v.name or '').strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'id': v.id,
            'text': name,
            'value': name,
            'slug': v.slug or '',
        })

    return JsonResponse({'results': results})


@csrf_exempt
@require_http_methods(["POST"])
def ai_query_api(request):
    """Process natural language career queries - works without AI, optional AI enhancement"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        # full=1 (default): full payload per career. full=0: light list; frontend fetches detail via GET api/career-detail/?id=
        use_light_list = data.get('full', 1) == 0
        
        # Get pagination parameters
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 6))  # Default 6 careers per page
        
        # Get context from request (for "another career", "similar career" requests)
        context_career_id = data.get('context_career_id')  # Current career being viewed
        context_career_ids = data.get('context_career_ids', [])  # Previously shown careers to exclude
        
        # Get filters from request (can be in POST body or GET params)
        selected_clusters = data.get('clusters', []) or request.GET.getlist('cluster')
        selected_professions = data.get('professions', []) or request.GET.getlist('professions')
        
        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)
        
        query_lower = query.lower().strip()
        
        # Check for career track queries: "list of career tracks", "show list of career tracks"
        is_career_tracks_query = any(phrase in query_lower for phrase in [
            'list of career tracks', 'show list of career tracks', 'career tracks',
            'all career tracks', 'show career tracks', 'career track list'
        ])
        
        # Check for "explore [cluster name]" queries: "explore health science", "explore engineering"
        explore_cluster_match = None
        if query_lower.startswith('explore '):
            cluster_name = query_lower.replace('explore ', '').strip()
            if cluster_name:
                explore_cluster_match = cluster_name
        
        # Check if query is asking for a specific section/feature
        detected_section = detect_section_query(query)
        
        # Check for special requests: "another career", "similar career", "different career"
        is_another_request = any(phrase in query_lower for phrase in [
            'another career', 'other career', 'different career', 'show me another',
            'show me other', 'show me different', 'more careers', 'similar career',
            'similar careers', 'like this', 'related career', 'related careers'
        ])
        
        # Handle "list of career tracks" query
        if is_career_tracks_query:
            # Get all clusters that have published careers (similar to autocomplete_clusters logic)
            # Get clusters directly used by published careers
            direct_cluster_ids = CareerCluster.objects.filter(
                career_clusters__publish_status=1
            ).values_list('id', flat=True).distinct()
            
            # Also include their parents so top-level tracks with only child careers can still be shown
            parent_cluster_ids = CareerCluster.objects.filter(
                id__in=direct_cluster_ids
            ).exclude(parent__isnull=True).values_list('parent_id', flat=True).distinct()
            
            # Get all clusters that have published careers either directly OR via children
            clusters = CareerCluster.objects.filter(
                Q(id__in=direct_cluster_ids) | Q(id__in=parent_cluster_ids),
                object_status=1
            ).distinct()
            
            # Filter out blank/empty names and get unique clusters
            clusters = clusters.exclude(name__isnull=True).exclude(name='').order_by('name')
            
            # Build list with career counts (deduplicated by name)
            seen_names = set()
            clusters_with_careers = []
            for cluster in clusters:
                if not cluster.name or not cluster.name.strip():
                    continue
                name_lower = cluster.name.strip().lower()
                # Skip if we've already seen this name
                if name_lower in seen_names:
                    continue
                
                # Count published careers in this cluster or its children
                career_count = Career.objects.filter(
                    publish_status=1
                ).filter(
                    Q(career_cluster=cluster) | Q(career_cluster__parent=cluster)
                ).distinct().count()
                
                if career_count > 0:
                    seen_names.add(name_lower)
                    try:
                        cluster_url = reverse('careers:careerlibrary', args=[cluster.slug, cluster.id]) if cluster.slug else None
                    except:
                        cluster_url = None
                    
                    clusters_with_careers.append({
                        'id': cluster.id,
                        'name': cluster.name.strip(),
                        'slug': cluster.slug,
                        'career_count': career_count,
                        'url': cluster_url
                    })
            
            # Sort by name
            clusters_with_careers.sort(key=lambda x: x['name'])
            
            return JsonResponse({
                'success': True,
                'query': query,
                'is_career_tracks_query': True,
                'career_tracks': clusters_with_careers,
                'count': len(clusters_with_careers),
                'summary': f"I found {len(clusters_with_careers)} career tracks available."
            })
        
        # Handle "explore [cluster name]" query
        if explore_cluster_match:
            # Find cluster by name
            cluster = CareerCluster.objects.filter(
                name__icontains=explore_cluster_match,
                object_status=1
            ).first()
            
            if cluster:
                # Get 5 careers from this cluster (prefetch only what list/detail needs)
                careers = Career.objects.filter(
                    Q(career_cluster=cluster) | Q(career_cluster__parent=cluster),
                    publish_status=1
                ).prefetch_related('career_cluster').distinct()[:5]
                format_fn = format_career_list_item if use_light_list else (lambda c: format_career_for_response(c, include_sections=True))
                formatted_careers = [format_fn(c) for c in careers]
                return JsonResponse({
                    'success': True,
                    'query': query,
                    'is_cluster_explore_query': True,
                    'cluster_name': cluster.name,
                    'careers': formatted_careers,
                    'light': use_light_list,
                    'count': len(formatted_careers),
                    'summary': f"I found {len(formatted_careers)} careers in {cluster.name}."
                })
        
        # Handle section-specific queries (e.g., "show me agricultural economist mindmap")
        # Also handle queries like "show me prominent employers of Hippologist"
        if detected_section and not is_another_request:
            # Extract career name from query (remove section keywords and common words)
            career_name_query = query_lower
            
            # For "prominent employers", also remove "prominent" keyword
            if detected_section == 'employers':
                career_name_query = career_name_query.replace('prominent', '').strip()
            
            # Remove section keywords based on detected section
            section_keywords_map = {
                'mindmap': ['mindmap', 'mind map', 'mind-map'],
                'roles': ['roles', 'responsibilities', 'role description', 'duties'],
                'eligibility': ['eligibility', 'study route', 'education', 'qualification', 'requirements'],
                'skills': ['skills', 'skill', 'knowledge', 'abilities'],
                'pros and cons': ['pros and cons', 'pros', 'cons', 'advantages', 'disadvantages'],
                'employment': ['employment', 'job areas', 'work areas', 'where to work'],
                'courses': ['courses', 'course', 'programs', 'program', 'specializations'],
                'overview': ['overview', 'introduction', 'summary', 'about'],
                'internships': ['internships', 'internship', 'practical exposure', 'training'],
                'employers': ['employers', 'prominent employers', 'companies', 'recruiters', 'organizations', 'employer'],
                'trends': ['trends', 'future outlook', 'industry trends', 'future'],
                'advice': ['advice', 'tips', 'guidance', 'recommendations']
            }
            
            keywords_to_remove = section_keywords_map.get(detected_section, [])
            import re
            # Remove section keywords (case insensitive, whole words)
            for keyword in keywords_to_remove:
                # Remove keyword as whole word (case insensitive)
                career_name_query = re.sub(r'\b' + re.escape(keyword) + r'\b', '', career_name_query, flags=re.IGNORECASE).strip()
            
            # Remove common words
            for word in ['show', 'me', 'the', 'a', 'an', 'for', 'of']:
                # Only remove if it's a standalone word (not part of another word)
                career_name_query = re.sub(r'\b' + re.escape(word) + r'\b', '', career_name_query, flags=re.IGNORECASE).strip()
            
            # Clean up multiple spaces
            career_name_query = ' '.join(career_name_query.split()).strip()
            
            # Search for career by name
            try:
                career = Career.objects.filter(
                    Q(name__icontains=career_name_query) | Q(slug__icontains=career_name_query),
                    publish_status=1
                ).first()
                
                if career:
                    # Get accordion sections
                    accordion_sections = extract_accordion_sections(career)
                    
                    # Format career data (we'll create this function)
                    formatted_career = format_career_for_response(career, include_sections=True)
                    
                    # Map section type to section ID used in frontend (matching description_json keys)
                    section_id_map = {
                        'mindmap': 'mindmap',
                        'roles': 'roles',
                        'eligibility': 'eligibility',
                        'skills': 'skills_trends',  # Map to skills_trends to match description_json
                        'pros and cons': 'proscons',
                        'employment': 'employment',
                        'courses': 'courses_spec',  # Map to courses_spec to match description_json
                        'overview': 'overview',
                        'internships': 'internships',
                        'employers': 'employers',
                        'trends': 'skills_trends',  # Map to skills_trends (same as skills)
                        'advice': 'advice'
                    }
                    section_id = section_id_map.get(detected_section, detected_section)
                    
                    return JsonResponse({
                        'success': True,
                        'query': query,
                        'is_section_query': True,
                        'section_type': detected_section,
                        'section_id': section_id,
                        'career': formatted_career,
                        'available_sections': accordion_sections,
                        'summary': f"Here's the {detected_section.replace('_', ' ')} for {career.name}:"
                    })
            except Exception as e:
                logger.error(f'Error handling section query: {str(e)}')
                # Fall through to normal processing
        
        # Initialize processor (handles AI/rule-based automatically)
        processor = QueryProcessor()

        # Handle "another/similar career" requests (no streaming)
        if is_another_request and context_career_id:
            careers = processor.get_similar_or_alternative_careers(
                context_career_id,
                exclude_ids=context_career_ids,
                limit=per_page
            )
            summary = f"I found {len(careers)} related careers for you."
            result = {
                'careers': careers,
                'method': 'context_based',
                'criteria': {},
                'query': query,
                'summary': summary
            }
        else:
            # Stream progress + result (actual messages from backend, no repeat)
            progress_queue = queue.Queue()

            def run_process():
                try:
                    res = processor.process_query(
                        query,
                        progress_callback=lambda msg: progress_queue.put(('progress', msg))
                    )
                    progress_queue.put(('result', res))
                except Exception as e:
                    progress_queue.put(('error', str(e)))

            thread = threading.Thread(target=run_process)
            thread.start()

            def stream_ndjson():
                t0 = time.perf_counter()
                while True:
                    try:
                        item = progress_queue.get(timeout=60)
                    except queue.Empty:
                        break
                    if item[0] == 'progress':
                        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                        yield json.dumps({'progress': item[1], 'elapsed_ms': elapsed_ms}) + '\n'
                    elif item[0] == 'error':
                        yield json.dumps({'success': False, 'error': item[1]}) + '\n'
                        return
                    else:
                        result = item[1]
                        break
                # Apply context similar careers merge
                careers = result['careers']
                if context_career_id and careers:
                    similar_careers = processor.get_similar_careers(context_career_id, limit=3)
                    existing_ids = {c.id for c in careers}
                    for similar in similar_careers:
                        if similar.id not in existing_ids and len(careers) < per_page * 2:
                            careers.append(similar)
                # Filters
                if selected_clusters or selected_professions:
                    filter_q = Q(publish_status=1)
                    if selected_clusters:
                        cluster_ids = [int(c) for c in selected_clusters if str(c).isdigit()]
                        if cluster_ids:
                            filter_q &= Q(career_cluster__id__in=cluster_ids)
                    if selected_professions:
                        cleaned = [p.strip() for p in selected_professions if p and p.strip()]
                        if cleaned:
                            filter_q &= Q(profession__name__in=cleaned)
                    filtered_ids = set(Career.objects.filter(filter_q).values_list('id', flat=True))
                    careers = [c for c in careers if getattr(c, 'id', getattr(c, 'pk', c.get('id') if isinstance(c, dict) else None)) in filtered_ids]
                # Pagination
                if result.get('method') == 'context_based':
                    paginated_careers = careers
                    total_careers = len(careers)
                    has_more = False
                    next_page = None
                else:
                    total_careers = len(careers)
                    start_index = (page - 1) * per_page
                    end_index = start_index + per_page
                    paginated_careers = careers[start_index:end_index]
                    has_more = end_index < total_careers
                    next_page = page + 1 if has_more else None
                format_fn = format_career_list_item if use_light_list else (lambda c: format_career_for_response(c, include_sections=True))
                formatted_careers = [format_fn(c) for c in paginated_careers]
                summary = result.get('summary') or processor.generate_summary(paginated_careers, query)
                suggested_questions = [] if result.get('method') == 'context_based' else processor.get_suggested_questions(query, paginated_careers)
                yield json.dumps({
                    'success': True,
                    'query': query,
                    'summary': summary,
                    'careers': formatted_careers,
                    'light': use_light_list,
                    'count': len(formatted_careers),
                    'total_count': total_careers,
                    'has_more': has_more,
                    'next_page': next_page,
                    'current_page': page,
                    'suggested_questions': suggested_questions,
                    'method': result.get('method', 'rule_based')
                }) + '\n'

            response = StreamingHttpResponse(stream_ndjson(), content_type='application/x-ndjson')
            response['Cache-Control'] = 'no-cache'
            return response

        # Non-streaming path (another_request with context_career_id): continue with filters/pagination/format
        careers = result['careers']

        # Apply filters if provided - filter by career IDs using Django ORM
        if selected_clusters or selected_professions:
            # Career and CareerCluster are already imported at the top
            # Q is already imported at the top
            
            # Build filter query
            filter_q = Q(publish_status=1)
            
            # Apply cluster filter
            if selected_clusters:
                cluster_ids = [int(c) for c in selected_clusters if str(c).isdigit()]
                if cluster_ids:
                    filter_q &= Q(career_cluster__id__in=cluster_ids)
            
            # Apply profession filter
            if selected_professions:
                cleaned_professions = [p.strip() for p in selected_professions if p and p.strip()]
                if cleaned_professions:
                    filter_q &= Q(profession__name__in=cleaned_professions)
            
            # Get filtered career IDs
            filtered_career_ids = set(Career.objects.filter(filter_q).values_list('id', flat=True))
            
            # Filter careers list to only include those matching the filters
            filtered_careers = []
            for career in careers:
                career_id = None
                try:
                    if hasattr(career, 'id'):
                        career_id = career.id
                    elif hasattr(career, 'pk'):
                        career_id = career.pk
                    elif isinstance(career, dict) and 'id' in career:
                        career_id = career['id']
                    
                    if career_id and career_id in filtered_career_ids:
                        filtered_careers.append(career)
                except:
                    # If we can't get the ID, skip this career
                    continue
            
            careers = filtered_careers
        
        # Apply pagination (skip for context-based results as they're already limited)
        if result.get('method') == 'context_based':
            # Context-based results are already paginated
            paginated_careers = careers
            total_careers = len(careers)
            has_more = False
            next_page = None
        else:
            total_careers = len(careers)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            paginated_careers = careers[start_index:end_index]
            has_more = end_index < total_careers
            next_page = page + 1 if has_more else None
        
        # Format results: light list or full payload
        format_fn = format_career_list_item if use_light_list else (lambda c: format_career_for_response(c, include_sections=True))
        formatted_careers = [format_fn(c) for c in paginated_careers]
        
        # Generate summary (template-based or AI) - use result summary if available
        if result.get('summary'):
            summary = result['summary']
        else:
            summary = processor.generate_summary(paginated_careers, query)
        
        # Get suggestions (rule-based) - skip for context-based
        if result.get('method') == 'context_based':
            suggested_questions = []
        else:
            suggested_questions = processor.get_suggested_questions(query, paginated_careers)
        
        return JsonResponse({
            'success': True,
            'query': query,
            'summary': summary,
            'careers': formatted_careers,
            'light': use_light_list,
            'count': len(formatted_careers),
            'total_count': total_careers,
            'has_more': has_more,
            'next_page': next_page,
            'current_page': page,
            'suggested_questions': suggested_questions,
            'method': result.get('method', 'rule_based')
        })
        
    except Exception as e:
        import traceback
        logger.error(f"AI query API error: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_career_detail_api(request):
    """Return full career payload for one career. Use after list/search for detail-on-demand."""
    career_id = request.GET.get('id')
    career_slug = request.GET.get('slug')
    if not career_id and not career_slug:
        return JsonResponse({'error': 'id or slug required'}, status=400)
    qs = Career.objects.filter(publish_status=1)
    if career_id:
        try:
            qs = qs.filter(id=int(career_id))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'invalid id'}, status=400)
    else:
        qs = qs.filter(slug=career_slug)
    career = qs.prefetch_related(
        'skills', 'career_cluster', 'profession', 'prospective_employment_areas',
        'courses', 'videos'
    ).first()
    if not career:
        return JsonResponse({'error': 'Career not found'}, status=404)
    return JsonResponse(format_career_for_response(career, include_sections=True))


@require_http_methods(["GET"])
def get_sample_career_questions(request):
    """Get sample career questions for AI mode initial load"""
    try:
        limit = int(request.GET.get('limit', 6))
        
        # Get diverse careers from different clusters for variety
        careers = Career.objects.filter(
            publish_status=1
        ).select_related().prefetch_related('career_cluster')[:limit * 3]  # Get more to ensure diversity
        
        # Group by cluster to ensure variety
        seen_clusters = set()
        selected_careers = []
        
        for career in careers:
            if len(selected_careers) >= limit:
                break
            # Get first cluster for this career
            clusters = career.career_cluster.all()[:1]
            if clusters:
                cluster_id = clusters[0].id
                if cluster_id not in seen_clusters or len(selected_careers) < limit // 2:
                    selected_careers.append(career)
                    seen_clusters.add(cluster_id)
            else:
                # If no cluster, add it anyway if we need more
                if len(selected_careers) < limit:
                    selected_careers.append(career)
        
        # If we still need more, fill with any remaining
        for career in careers:
            if len(selected_careers) >= limit:
                break
            if career not in selected_careers:
                selected_careers.append(career)
        
        questions = []
        for career in selected_careers[:limit]:
            # Create question like "I want to become a pilot"
            career_name = career.name.lower()
            # Remove common suffixes for cleaner questions
            if career_name.endswith(' career'):
                career_name = career_name[:-7]
            if career_name.endswith(' profession'):
                career_name = career_name[:-11]
            
            questions.append({
                'text': f"I want to become a {career_name}",
                'career_id': career.id,
                'career_name': career.name,
                'career_slug': career.slug
            })
        
        return JsonResponse({'questions': questions})
        
    except Exception as e:
        import traceback
        logger.error(f"Sample career questions API error: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
