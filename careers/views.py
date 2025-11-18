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

        return ctx

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