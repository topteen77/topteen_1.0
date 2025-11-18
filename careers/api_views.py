"""
API views for DOCX processing
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.uploadedfile import InMemoryUploadedFile
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
