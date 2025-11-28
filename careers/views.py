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
        selected_clusters = request.GET.getlist("cluster")
        
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
        
        # Apply skill filtering - OR logic within skills
        # Match by exact name
        if selected_skills:
            # Clean the skill names and filter
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
        
        # Only load clusters that have active careers AND are active themselves
        clusters = CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1  # Only active clusters
        ).distinct().order_by('name')
        
        # Only load professions that have active careers AND are active themselves
        professions = Profession.objects.filter(
            career__publish_status=1,
            object_status=1  # Only active professions
        ).distinct().order_by('name')[:100]  # Limit to 100 for performance
        
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
        
        # Filter professions based on selected clusters (only if clusters selected)
        filtered_professions = professions
        if selected_clusters:
            # Get professions from careers in selected clusters - optimized query
            profession_ids = Career.objects.filter(
                career_cluster__id__in=selected_clusters,
                publish_status=1,
                profession__isnull=False
            ).values_list('profession__id', flat=True).distinct()
            
            filtered_professions = Profession.objects.filter(
                id__in=profession_ids,
                object_status=1  # Only active professions
            ).distinct().order_by("name")[:100]
        
        # Filter skills based on selected professions and clusters (only if filters selected)
        filtered_skills = skills
        if selected_professions or selected_clusters:
            # Build optimized query for careers with filters
            careers_query = Career.objects.filter(publish_status=1)
            
            if selected_professions:
                careers_query = careers_query.filter(profession__name__in=selected_professions)
            
            if selected_clusters:
                careers_query = careers_query.filter(career_cluster__id__in=selected_clusters)
            
            # Get skill IDs from those careers - optimized
            skill_ids = careers_query.values_list('skills__id', flat=True).distinct()
            
            filtered_skills = Skill.objects.filter(
                id__in=skill_ids,
                object_status=1  # Only active skills
            ).distinct().order_by("priority", "name")[:200]
        
        # Create facets_filter with proper counts and selection status (limit for performance)
        # Calculate actual career counts for each option
        skill_facets = []
        for skill in filtered_skills[:30]:
            count = Career.objects.filter(
                publish_status=1,
                skills__name=skill.name
            ).distinct().count()
            skill_facets.append((skill.name, count, skill.name in selected_skills))
        
        profession_facets = []
        for prof in filtered_professions[:30]:
            count = Career.objects.filter(
                publish_status=1,
                profession__name=prof.name
            ).distinct().count()
            profession_facets.append((prof.name, count, prof.name in selected_professions))
        
        facets_filter = {
            "skill": skill_facets,
            "profession": profession_facets,
        }
        
        # Get shortlisted career IDs for authenticated users
        shortlisted_career_ids = []
        if request.user.is_authenticated:
            from .models import CareerShortlist
            shortlisted_career_ids = list(CareerShortlist.objects.filter(
                user=request.user
            ).values_list('career_id', flat=True))
        
        # Add counts to clusters for display
        clusters_with_counts = []
        for cluster in clusters:
            count = Career.objects.filter(
                publish_status=1,
                career_cluster__id=cluster.id
            ).distinct().count()
            clusters_with_counts.append({
                'cluster': cluster,
                'count': count
            })
        
        # Add counts to professions for display
        professions_with_counts = []
        for prof in professions:
            count = Career.objects.filter(
                publish_status=1,
                profession__name=prof.name
            ).distinct().count()
            professions_with_counts.append({
                'profession': prof,
                'count': count
            })
        
        return {
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
            'shortlisted_career_ids': shortlisted_career_ids,
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
        
        # Parse description HTML to extract H1, H2, H3 structure
        mindmap_data = {
            "name": career.name,
            "summary": career.summary or "",
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
        
        # Roles & Responsibilities
        if career.role_description:
            aspects.append({
                "id": "roles",
                "name": "Roles & Responsibilities",
                "icon": "tasks",
                "color": "#fa709a,#fee140",
                "hasContent": True,
                "modalContent": {
                    "title": "Roles and Responsibilities",
                    "body": career.role_description
                }
            })
        
        # Study Route & Eligibility
        if career.eligibility:
            aspects.append({
                "id": "study-route",
                "name": "Study Route",
                "icon": "graduation-cap",
                "color": "#30cfd0,#330867",
                "hasContent": True,
                "modalContent": {
                    "title": "Study Route & Eligibility",
                    "body": career.eligibility
                }
            })
        
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
        
        # Pros & Cons
        if career.pros_cons:
            aspects.append({
                "id": "pros-cons",
                "name": "Pros & Cons",
                "icon": "balance-scale",
                "color": "#ffecd2,#fcb69f",
                "hasContent": True,
                "modalContent": {
                    "title": "Pros and Cons",
                    "body": career.pros_cons
                }
            })
        
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
            "summary": career.summary or "",
            "aspects": aspects
        }
        
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
    template_name='topteenfrontend/careerlibrary.html'

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