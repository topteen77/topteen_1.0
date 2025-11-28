"""
API views for DOCX processing and autocomplete
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.files.uploadedfile import InMemoryUploadedFile
from .models import Profession, Skill, CareerCluster, Career
from .docx_utils import convert_docx_to_html, extract_career_data_from_html
import json


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
    """API endpoint for profession autocomplete - only shows professions with published careers"""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 30))  # Optimized default limit for better performance
    
    # Filter by cluster if provided (can be multiple)
    selected_clusters = request.GET.getlist('cluster')
    
    # Start with professions that have published careers
    careers_with_professions = Career.objects.filter(
        publish_status=1,
        profession__isnull=False
    ).distinct()
    
    # If clusters are selected, filter careers by those clusters
    if selected_clusters:
        careers_with_professions = careers_with_professions.filter(
            career_cluster__id__in=selected_clusters
        ).distinct()
    
    # Get professions from those careers (only active ones)
    professions = Profession.objects.filter(
        career__in=careers_with_professions,
        object_status=1  # Only active professions
    ).distinct()
    
    # Apply search query
    if query:
        professions = professions.filter(Q(name__icontains=query))
    
    # Filter out blank/empty names and limit results
    professions = professions.exclude(name__isnull=True).exclude(name='').order_by('name')[:limit]
    
    # Only return non-empty results that have associated careers (deduplicated by name)
    seen_names = set()  # Track unique names to prevent duplicates
    results = []
    for p in professions:
        if p.name and p.name.strip():
            name_lower = p.name.strip().lower()  # Case-insensitive comparison
            # Skip if we've already seen this name
            if name_lower in seen_names:
                continue
            # Count careers with this profession
            career_count = Career.objects.filter(
                profession=p,
                publish_status=1
            ).count()
            if career_count > 0:
                seen_names.add(name_lower)
                # Include count in the text
                results.append({
                    'id': p.id, 
                    'text': f"{p.name.strip()} ({career_count})", 
                    'value': p.name.strip()
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
    
    # Get clusters that have published careers
    careers_with_clusters = Career.objects.filter(
        publish_status=1,
        career_cluster__isnull=False
    ).distinct()
    
    # Get clusters from those careers (only active ones)
    # Note: CareerCluster uses ManyToMany relationship with related_name="career_clusters"
    clusters = CareerCluster.objects.filter(
        career_clusters__in=careers_with_clusters,
        object_status=1  # Only active clusters
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
            # Count careers with this cluster
            career_count = Career.objects.filter(
                career_cluster=c,
                publish_status=1
            ).count()
            if career_count > 0:
                seen_names.add(name_lower)
                # Include count in the text
                results.append({
                    'id': c.id, 
                    'text': f"{c.name.strip()} ({career_count})", 
                    'value': str(c.id)
                })
    
    return JsonResponse({'results': results})
