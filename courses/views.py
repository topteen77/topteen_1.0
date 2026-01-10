from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from .models import Course
from core.utils import build_html_head

class CourseDetailView(TemplateView):
    """Public view for Course details accessible to all users including students"""
    template_name = "template20/course_detail.html"
    
    def html_head(self, course):
        title = course.name
        description = course.overview[:200] if course.overview else course.name
        return build_html_head(title=title, description=description)
    
    def get_context(self, request, course_id, slug=None, *args, **kwargs):
        ctx = {}
        
        # Get course by ID (slug is optional for backward compatibility)
        if slug:
            course = get_object_or_404(Course, id=course_id, slug=slug)
        else:
            course = get_object_or_404(Course, id=course_id)
        
        ctx['course'] = course
        ctx['html_head'] = self.html_head(course)
        
        # Get related courses from same college
        related_courses = Course.objects.none()
        if course.college:
            related_courses = Course.objects.filter(
                college=course.college
            ).exclude(id=course.id)[:6]
        
        ctx['related_courses'] = related_courses
        
        return ctx
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
