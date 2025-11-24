from django.shortcuts import render
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404,redirect
from django.http import JsonResponse
from django.db.models import Q
from careers.document_filters import CareerDocumentFilter
from .models import Career, CareerFAQ, CareerMedia, CareerPath, CareerTags, Profession,CareerCluster,Videos,VideoCategory,CareerShortlist,CareerRating
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from colleges.models import College
from core.models import Country
from core import choices
from colleges.views import is_ajax
from django.template.loader import render_to_string
from django.shortcuts import HttpResponse
from django.urls import reverse_lazy
from core.utils import build_breadcrumb,build_html_head
from entrance_exams.models import EntranceExam
from .document_filters import CareerDocumentFilter
from django.urls import reverse
from django.utils.html import strip_tags
from django.contrib import messages
# Create your views here.
class Careers(TemplateView):
    
    template_name = "template20/careers.html"
    
    def html_head(self):
        name='Career Tracks'
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        try:
            docmentservice=CareerDocumentFilter()
            ctx=docmentservice.get_career_list_context(request)
        except Exception as e:
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
            ctx = self.get_fallback_context(request)
        
        if request.GET.getlist('professions') or request.GET.getlist('skills') or request.GET.getlist('courses'):
            pro=request.GET.getlist('professions')
            skill=request.GET.getlist('skills')
            course=request.GET.getlist('courses')
            data=pro+skill+course
            ctx['data']=data
        ctx['html_head'] = self.html_head()
        ctx['breadcrumb'] = {'text': 'Career Tracks', 'url': reverse('careers:career')}
        
        return ctx
        
    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))
    
    def get_fallback_context(self, request):
        from django.core.paginator import Paginator
        from .models import Career, CareerCluster, CareerTags, Skill, ProspectiveEmploymentArea, ProspectiveRecruiter, Profession
        from courses.models import Course
        
        careers = Career.objects.filter(publish_status=1).select_related().prefetch_related(
            'skills', 'career_tags', 'prospective_employment_areas', 'prospective_recruiters', 'courses'
        ).order_by('name')

        # Handle selected filters
        # Handle selected filters
        selected_professions = request.GET.getlist("professions")
        selected_skills = request.GET.getlist("skills")
        selected_cluster = request.GET.get("cluster")
        
        # Apply cluster filtering
        if selected_cluster:
            careers = careers.filter(career_cluster__id=selected_cluster).distinct()
        
        # Apply profession filtering
        if selected_professions:
            careers = careers.filter(profession__name__in=selected_professions).distinct()
        
        # Apply skill filtering
        if selected_skills:
            careers = careers.filter(skills__name__in=selected_skills).distinct()

        # Basic search filtering
        search_query = request.GET.get('search', '')
        if search_query:
            careers = careers.filter(
                Q(name__icontains=search_query) | 
                Q(summary__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # Ensure deterministic ordering before pagination (distinct() may clear order_by)
        careers = careers.order_by('name', 'id')
        # Ensure deterministic ordering before pagination (distinct() may clear order_by)
        careers = careers.order_by('name', 'id')
        # Pagination
        paginator = Paginator(careers, 20)
        page = request.GET.get('page')
        try:
            careers_page = paginator.page(page)
        except PageNotAnInteger:
            careers_page = paginator.page(1)
        except EmptyPage:
            careers_page = paginator.page(paginator.num_pages)
        
        clusters = CareerCluster.objects.all()
        tags = CareerTags.objects.all()
        skills = Skill.objects.all()
        professions = Profession.objects.all()
        employment_areas = ProspectiveEmploymentArea.objects.all()
        recruiters = ProspectiveRecruiter.objects.all()
        courses = Course.objects.all()
        
        # Filter skills based on selected professions
        filtered_skills = skills
        if selected_professions:
            # Get careers that have the selected professions
            careers_with_professions = Career.objects.filter(
                profession__name__in=selected_professions,
                publish_status=1
            ).distinct()
            
            # Get skills from those careers
        # Filter professions based on selected cluster
        filtered_professions = professions
        if selected_cluster:
            # Get professions from careers in selected cluster
            careers_with_cluster = Career.objects.filter(
                career_cluster__id=selected_cluster,
                publish_status=1
            ).distinct()
            
            # Get professions from those careers
            filtered_professions = Profession.objects.filter(
                career__in=careers_with_cluster
            ).distinct().order_by("name")
        
        # Filter skills based on selected professions
        filtered_skills = skills
        if selected_professions:
            # Get careers that have the selected professions
            careers_with_professions = Career.objects.filter(
                profession__name__in=selected_professions,
                publish_status=1
            ).distinct()
            
            # Get skills from those careers
            filtered_skills = Skill.objects.filter(
                career__in=careers_with_professions
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
            'selected_skills': selected_skills,
        }
    
class CareerDetail(TemplateView):
    template_name = "template20/career_detail.html"
    
    def html_head(self,career):
        titleb=career.name
        descriptionb=career.summary
        return build_html_head(title=titleb, description=descriptionb)
    

    def get_context(self, request,career_id,slug, *args, **kwargs):
        ctx={}
        career=get_object_or_404(Career,id=career_id,slug=slug)
        ctx['career']=career
        bread_crumb =self._breadcrumb(career)
        ctx['breadcrumb']= bread_crumb[1]
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
        
        # Get related careers via courses and clusters
        related_careers = Career.objects.none()
        if career.courses.exists():
            # Get careers that share the same courses
            related_careers = Career.objects.filter(
                courses__in=career.courses.all(),
                publish_status=choices.PublishStatus.PUBLISHED
            ).exclude(id=career.id).distinct()
        
        if career.career_cluster.exists():
            # Get careers from the same clusters
            cluster_careers = Career.objects.filter(
                career_cluster__in=career.career_cluster.all(),
                publish_status=choices.PublishStatus.PUBLISHED
            ).exclude(id=career.id).distinct()
            # Combine and get unique careers, then slice
            if related_careers.exists():
                related_careers = (related_careers | cluster_careers).distinct()[:6]
            else:
                related_careers = cluster_careers[:6]
        else:
            # Slice if we only have course-based related careers
            if related_careers.exists():
                related_careers = related_careers[:6]
        
        ctx['related_careers'] = related_careers

        # Generate mindmap data (career clusters)
        ctx['mindmap_data'] = self._get_mindmap_data(career)
        
        # Generate career aspect mindmap data (like HIPPOLOGY example)
        ctx['career_aspect_mindmap'] = self._get_career_aspect_mindmap(career)

        return ctx
    
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
    
    def _get_career_aspect_mindmap(self, career):
        """Generate career aspect mindmap data from description field (H1, H2, H3 structure)"""
        import json
        import re
        from django.utils.html import strip_tags
        from bs4 import BeautifulSoup
        
        def summarize_content(html_content, max_length=200):
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
        
        # Parse description HTML to extract H1, H2, H3 structure
        mindmap_data = {
            "name": career.name,
            "summary": career.summary or "",
            "children": []
        }
        
        if not career.description:
            return json.dumps(mindmap_data)
        
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
                # Get all elements in order
                all_elements = soup.find_all(['p', 'ul', 'ol'])
                potential_h2s = []
                
                # Find all paragraphs with strong tags that could be H2
                # H2 sections are typically longer titles, not sub-items starting with a), b), c) or single words
                for elem in all_elements:
                    if elem.name == 'p':
                        strong = elem.find('strong')
                        if strong:
                            text = strong.get_text().strip()
                            # Skip if it's the title we already found
                            if text != mindmap_data["name"]:
                                # Skip sub-sections (starting with a), b), c), d) or single short words like "Level", "Eligibility")
                                if not (text.startswith(('a)', 'b)', 'c)', 'd)', 'e)', 'f)', 'g)', 'h)', 'i)', 'j)')) or 
                                        len(text.split()) <= 2):
                                    potential_h2s.append((elem, all_elements.index(elem)))
                
                # Use first few strong paragraphs as H2 sections
                for idx, (p, p_idx) in enumerate(potential_h2s[:10]):  # Limit to 10 sections
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
                        
                        # Get content after this paragraph until next main H2 section
                        content_parts = []
                        next_idx = p_idx + 1
                        while next_idx < len(all_elements):
                            next_elem = all_elements[next_idx]
                            # Stop if we hit another main H2 section (strong paragraph that's not a sub-section)
                            if next_elem.name == 'p':
                                next_strong = next_elem.find('strong')
                                if next_strong:
                                    next_text = next_strong.get_text().strip()
                                    # Check if it's a main section (not a sub-section)
                                    if not (next_text.startswith(('a)', 'b)', 'c)', 'd)', 'e)', 'f)', 'g)', 'h)', 'i)', 'j)')) or 
                                            len(next_text.split()) <= 2):
                                        # This is the next H2, stop here
                                        break
                                    else:
                                        # This is an H3 sub-section, add it as child
                                        h3_data = {
                                            "name": next_text,
                                            "summary": "",
                                            "content": ""
                                        }
                                        # Get content for this H3
                                        h3_content_parts = []
                                        h3_idx = next_idx + 1
                                        while h3_idx < len(all_elements):
                                            h3_elem = all_elements[h3_idx]
                                            if h3_elem.name == 'p' and h3_elem.find('strong'):
                                                break
                                            if h3_elem.name in ['p', 'ul', 'ol']:
                                                h3_content_parts.append(str(h3_elem))
                                            h3_idx += 1
                                        h3_data["content"] = "".join(h3_content_parts)
                                        h3_data["summary"] = summarize_content(h3_data["content"], max_length=100)
                                        current_h2_data["children"].append(h3_data)
                                        next_idx = h3_idx - 1  # Continue from after H3 content
                            # Collect regular paragraphs and lists
                            elif next_elem.name in ['ul', 'ol']:
                                content_parts.append(str(next_elem))
                            elif next_elem.name == 'p' and not next_elem.find('strong'):
                                content_parts.append(str(next_elem))
                            next_idx += 1
                        
                        full_content = "".join(content_parts)
                        current_h2_data["content"] = full_content
                        current_h2_data["summary"] = summarize_content(full_content, max_length=150)
                        
                        # Look for H3 sub-sections within this H2 content
                        if full_content:
                            content_soup = BeautifulSoup(full_content, 'html.parser')
                            sub_strongs = content_soup.find_all(['p', 'li'])
                            current_h3 = None
                            for elem in sub_strongs:
                                strong_tag = elem.find('strong')
                                if strong_tag:
                                    # This might be an H3 equivalent
                                    if current_h3:
                                        current_h2_data["children"].append(current_h3)
                                    current_h3 = {
                                        "name": strong_tag.get_text().strip(),
                                        "summary": "",
                                        "content": str(elem)
                                    }
                                    current_h3["summary"] = summarize_content(current_h3["content"], max_length=100)
                                elif current_h3:
                                    current_h3["content"] += str(elem)
                            
                            if current_h3:
                                current_h2_data["children"].append(current_h3)
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
                        
                        if content_parts:
                            full_content = "".join(content_parts)
                            h3_data["content"] = full_content
                            h3_data["summary"] = summarize_content(full_content, max_length=100)
                        
                        current_h2_data["children"].append(h3_data)
                        
                    elif element.name in ['p', 'ul', 'ol'] and current_h2_data:
                        # Add content to current H2 (if no H3 children yet or content before first H3)
                        if not current_h2_data["children"]:
                            current_h2_data["content"] += str(element)
            
            # Summarize H2 content and add last H2 if exists
            if current_h2_data:
                if current_h2_data["content"] and not current_h2_data["summary"]:
                    current_h2_data["summary"] = summarize_content(current_h2_data["content"], max_length=150)
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
                            "summary": summarize_content(content, max_length=150),
                            "content": content,
                            "children": []
                        })
        
        except Exception as e:
            # Fallback: create simple structure
            mindmap_data["children"] = [{
                "name": "Career Description",
                "summary": summarize_content(career.description, max_length=150),
                "content": career.description,
                "children": []
            }]
        
        return json.dumps(mindmap_data)

    @classmethod
    def _breadcrumb(self,career):
        url=reverse_lazy('careers:career')
        lst=[{'title':'{}'.format(career),'text':'{}'.format("Career"),'url':url}]
        return build_breadcrumb(lst)
        
    def get(self, request,career_id,slug, *args, **kwargs):
        data={}  
        if is_ajax(request=request):
            clgdf=CareerDocumentFilter()
            ctx=clgdf.get_career_detail(request,slug,is_ajax=True)
            html=render_to_string("topteenfrontend/includes/explore_college.html",ctx)
            return HttpResponse(html)    
        return render(request, self.template_name,self.get_context(request,career_id,slug, args, kwargs))

class Professions(TemplateView):
    template_name = "topteenfrontend/profession.html"
    
    def html_head(self):
        title="Profession"
        return build_html_head(title=title, description=title)

    def get_context(self, request,career_slug, *args, **kwargs):
        ctx={}
        career=Career.objects.get(slug=career_slug)
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
        ctx['html_head'] = self.html_head()
        return ctx
        
    def get(self, request,career_slug,*args, **kwargs):     
        return render(request, self.template_name, self.get_context(request,career_slug,args, kwargs))
 

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
            print(f"Elasticsearch not available, using Django ORM fallback: {e}")
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
        
        # Apply cluster filtering
        if selected_cluster:
            careers = careers.filter(career_cluster__id=selected_cluster).distinct()
        
        # Apply profession filtering
        if selected_professions:
            careers = careers.filter(profession__name__in=selected_professions).distinct()
        
        # Apply skill filtering
        if selected_skills:
            careers = careers.filter(skills__name__in=selected_skills).distinct()

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
        
        clusters = CareerCluster.objects.all()
        tags = CareerTags.objects.all()
        skills = Skill.objects.all()
        professions = Profession.objects.all()
        employment_areas = ProspectiveEmploymentArea.objects.all()
        recruiters = ProspectiveRecruiter.objects.all()
        courses = Course.objects.all()
        
        # Filter professions based on selected cluster
        filtered_professions = professions
        if selected_cluster:
            # Get professions from careers in selected cluster
            careers_with_cluster = Career.objects.filter(
                career_cluster__id=selected_cluster,
                publish_status=1
            ).distinct()
            
            # Get professions from those careers
            filtered_professions = Profession.objects.filter(
                career__in=careers_with_cluster
            ).distinct().order_by("name")
        
        # Filter skills based on selected professions
        filtered_skills = skills
        if selected_professions:
            # Get careers that have the selected professions
            careers_with_professions = Career.objects.filter(
                profession__name__in=selected_professions,
                publish_status=1
            ).distinct()
            
            # Get skills from those careers
            filtered_skills = Skill.objects.filter(
                career__in=careers_with_professions
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
    template_name='template20/careerlibrary.html'

    def __breadcrumb(self,name):
        l=[{'title':'Careers','text':'Careers','url':reverse_lazy('careers:career')},{'title':name,'text':name,'url':''}]
        return build_breadcrumb(l)

    def __html_head(self,name):
        return build_html_head(title=name, description=name)

    def get_context(self,request,cluster_slug,cluster_id,*args,**kwargs):
        ctx=CareerCluster.get_career_library_context(request,cluster_slug,cluster_id)
        ctx['html_head']=self.__html_head(ctx["cluster_name"])
        ctx['breadcrumb']=self.__breadcrumb(ctx["cluster_name"])
        ctx['body_css_class']="bg-white"
        return ctx

    def get(self, request,cluster_slug=None,cluster_id=None, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request,cluster_slug,cluster_id, *args, **kwargs))

class CareerVideosView(TemplateView):
    template_name ="template20/career_videos_list.html"

    def html_head(self,name):
        # name='Explore Career Videos'
        return build_html_head(title=name, description=name)

    def _breadcrumb(self):
        lst=[{'title':'','text':'Career Videos','url':''}]
        return build_breadcrumb(lst)

    def get_context(self,request,*args, **kwargs):
        ctx={}
        search_videos = request.GET.get('search')
        ctx['breadcrumb']=self._breadcrumb()[1]
        if search_videos:
            ctx['search_videos']=search_videos
            ctx['heading']=f"Results for '{search_videos}'"
            videos = Videos.objects.filter( Q(name__icontains=search_videos))
            ctx['videos'] = videos
            ctx['categories']=VideoCategory.objects.all()
            paginator = Paginator(videos, 5)
            page_numbers = request.GET.get('page')
            ctx['page_obj'] = paginator.get_page(page_numbers)
            ctx['html_head']=self.html_head('{} - Search Videos'.format(search_videos))
        else:
            ctx['search_videos']=""
            ctx['heading']="Explore Videos"
            videos = Videos.objects.all()
            ctx['videos'] = videos
            ctx['categories']=VideoCategory.objects.all()
            paginator = Paginator(videos, 5)
            page_numbers = request.GET.get('page')
            ctx['page_obj'] = paginator.get_page(page_numbers)
            ctx['html_head']=self.html_head('Explore Career Videos - Page - {}'.format(ctx['page_obj'].number))
        return ctx

    def get(self,request,*args, **kwargs):
        return render(request, self.template_name,self.get_context(request,args,kwargs))

class CategoryCareerVideosView(TemplateView):
    template_name ="template20/career_videos_list.html"

    def html_head(self,name):
        return build_html_head(title=name, description=name)

    def _breadcrumb(self, category_name):
        lst=[{'title':'Career Videos','text':'Career Videos','url':reverse_lazy('careers:careervideos')},{'title':category_name,'text':category_name,'url':''}]
        return build_breadcrumb(lst)

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
        ctx['breadcrumb']=self._breadcrumb(category.name)[1]
        ctx['heading'] = f"Videos in {category.name}"
        ctx['search_videos'] = ""
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
        bread_crumb =self._breadcrumb(video)
        ctx['breadcrumb']= bread_crumb[1]
        ctx['html_head']=self.html_head(video.name)
        
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
        
        ctx['related_videos'] = related_videos
        return ctx

    def _breadcrumb(self,video):
        url=reverse_lazy('careers:careervideos')
        lst=[{'title':'Career Videos','text':'Career Videos','url':url},{'title':video.name,'text':video.name,'url':''}]
        return build_breadcrumb(lst)
    
        
    def get(self, request,video_slug, *args, **kwargs):     
        return render(request, self.template_name, self.get_context(request,video_slug,args, kwargs))
    
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
    id=request.GET.get("id")
    video=get_object_or_404(Videos,id=id)
    data=Videos.objects.filter(id=id,shortlist=request.user).exists()
    if data:
        video.shortlist.remove(request.user)
        return JsonResponse({'success':'false'})
    else:
        video.shortlist.add(request.user)
        return JsonResponse({'success':'true'})