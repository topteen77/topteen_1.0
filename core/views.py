import json
import re
import os
from multiprocessing import get_context
from .utils import build_breadcrumb,build_html_head
from django.db.models import Q
from xml.etree.ElementInclude import include
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from blog.models import Blog
from careers.models import Career, CareerTags,Videos,CareerCluster
from core import choices
from django.views.generic import TemplateView
from core.models import CommonFAQ, Country, Review,Contact,Lead, Ebook
from courses.models import Course
from colleges.models import College
from django.conf import settings
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
from entrance_exams.models import EntranceExam
from users.models import UserSearchHistory
from django.shortcuts import HttpResponse,HttpResponseRedirect
from skilllab.models import SkillLabCourse
from django.contrib import messages
from rest_framework.views import APIView
from django.http import JsonResponse

class Home(TemplateView):
    template_name ="template20/home_new.html"
    
    def html_head(self):
        name='Every Student, Career Ready'
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        tags=CareerTags.objects.all().order_by('priority')[:5]
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['careers'] = Career.get_all_careers()
        try:
            print(f"[HOME] Published careers count: {ctx['careers'].count()}")
        except Exception:
            pass
        ctx['videos'] = Videos.objects.all().order_by('?')
        ctx['careers_video']=Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).exclude(Q(video_url=""))
        ctx['courses'] = Course.get_all_courses()
        ctx['reviewers'] = Review.get_published_objects()
        ctx['tags']=tags
        ctx['countries']=country
        ctx['body_css_class']='no-scrollbar overflow-x-hidden'
        ctx['comman_faq']=CommonFAQ.get_commonfaq_by_priority()
        ctx['parent_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.parent, is_featured=choices.FAQFeaturedType.HOME)[:10]
        ctx['student_faq']=CommonFAQ.get_commonfaq_by_priority().filter(user_type=choices.FAQType.student,is_featured=choices.FAQFeaturedType.HOME)[:10]
        ctx["html_head"] = self.html_head()
        ctx['skilllab_courses']=SkillLabCourse.all_objects()
        
        # Get specific courses for home page "Boost Your Skills" section (fully dynamic)
        # For After 10th: try category=1 first, then fallback to BOTH (category=3)
        ctx['after_10_course'] = SkillLabCourse.objects.filter(
            category=choices.SkillLabCourseTypeChoice.after_10_class
        ).first()
        if not ctx['after_10_course']:
            ctx['after_10_course'] = SkillLabCourse.objects.filter(
                category=choices.SkillLabCourseTypeChoice.BOTH
            ).first()
        
        # For After 12th: try category=2 first, then fallback to BOTH (category=3)
        ctx['after_12_course'] = SkillLabCourse.objects.filter(
            category=choices.SkillLabCourseTypeChoice.after_12_class
        ).first()
        if not ctx['after_12_course']:
            ctx['after_12_course'] = SkillLabCourse.objects.filter(
                category=choices.SkillLabCourseTypeChoice.BOTH
            ).first()
        
        # For After College: use category=4
        ctx['after_college_course'] = SkillLabCourse.objects.filter(
            category=choices.SkillLabCourseTypeChoice.after_college
        ).first()
        
        ctx['exams']=EntranceExam.objects.all().order_by('?')[:3]
        ctx['clusters']=CareerCluster.objects.filter(parent__isnull=True)
        return ctx
        
    def get(self, request,*args, **kwargs):
        print(f"[DEBUG] Rendering template: {self.template_name}")
        print(f"[DEBUG] Template file exists: {os.path.exists(os.path.join(settings.BASE_DIR, 'templates', self.template_name))}")
        return render(request, self.template_name,self.get_context(request,args, kwargs))


def privacy_policy(request):
    template_name='template20/privacy_policy.html'
    name="Privacy Policy"
    ctx={}
    ctx["html_head"]=build_html_head(title=name, description=name)
    from django.urls import reverse
    ctx['breadcrumb'] = {'text': 'Privacy Policy', 'url': reverse('core:privacypolicy')}
    return render(request,template_name,ctx)

def terms_and_condition(request):
    template_name='template20/terms_and_condition.html'
    name="Terms and Condition"
    ctx={}
    ctx["html_head"]=build_html_head(title=name, description=name)
    from django.urls import reverse
    ctx['breadcrumb'] = {'text': 'Terms and Condition', 'url': reverse('core:terms&condition')}
    return render(request,template_name,ctx)

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
    template_name='template20/contact_us.html'
    name="Contact Us"
    from django.urls import reverse
    from django.middleware.csrf import get_token
    ctx={}
    ctx['breadcrumb'] = {'text': 'Contact Us', 'url': reverse('core:contactus')}
    ctx['csrf_token'] = get_token(request)
    if request.method=="POST":
        first_name=request.POST.get("first_name")
        last_name=request.POST.get("last_name")
        full_name="{} {}".format(first_name,last_name)
        mobile=request.POST.get("mobile")
        email=request.POST.get("email")
        message=request.POST.get("message")
        if full_name and message and validation(request,mobile,email):
            form=Contact(name=full_name,mobile=mobile,email=email,message=message)
            form.save()
            messages.success(request,"Thank you, Your response has been submitted!")
        else:
            messages.error(request,"")
    ctx["html_head"]=build_html_head(title=name, description=name)
    return render(request,template_name,ctx)

def upload(request):
    if request.method == "POST":
        form = ImageUploadModelForm(request.POST, request.FILES)
        if form.is_valid():
            obj=form.save()
            print(obj)
            # return HttpResponse(obj.upload.url)
            return HttpResponse(json.dumps({'success':True,'url':obj.upload.url}), content_type='application/json')
        print(form.errors)
    return HttpResponse('')


class AboutUsView(TemplateView):
    template_name ="template20/about_us.html"

    def html_head(self):
        name='About Us'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'About Us', 'url': reverse('core:aboutus')}
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))

class AllFaqView(TemplateView):
    template_name ="template20/all_faq.html"
    
    def html_head(self):
        name='FAQ'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        from django.urls import reverse
        ctx['breadcrumb'] = {'text': 'FAQs', 'url': reverse('core:allfaq')}
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
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,args,kwargs))


class ExtracurricularActivitiesView(TemplateView):
    template_name = "template20/extracurricular_activities.html"

    def html_head(self):
        name = "Extracurricular Activities"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = {'text': 'Extracurricular Activities', 'url': reverse('core:extracurricular_activities')}
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

        # Get default tab from URL parameter or default to after-10
        default_tab = request.GET.get('tab', 'after-10')
        if default_tab not in ['after-10', 'after-12']:
            default_tab = 'after-10'

        # Load both levels
        levels_data = {}
        for level_slug in ['after-10', 'after-12']:
            try:
                level = VocationalCourseCategory.objects.filter(
                    slug=level_slug,
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
                ).first()
                
                if level:
                    levels_data[level_slug] = level
            except Exception:
                levels_data[level_slug] = None

        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = {'text': 'Vocational Courses', 'url': reverse('core:vocational_courses')}
        ctx["levels_data"] = levels_data
        ctx["default_tab"] = default_tab
        ctx["active_level"] = levels_data.get(default_tab)
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


class VocationalCourseDetailView(TemplateView):
    template_name = "template20/vocational_course_detail.html"

    def get_context(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from core.models import VocationalCourse
        from blog.models import Blog

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
        
        # Add latest blogs for the blog section
        try:
            ctx["blogs"] = Blog.get_published_objects().order_by('-created')[:3]
        except Exception:
            ctx["blogs"] = []
        
        if level:
            ctx["breadcrumb"] = [
                {"text": "Vocational Courses", "url": reverse("core:vocational_courses")},
                {"text": level.name, "url": f"/vocational-courses/{level.slug}/"},
                {"text": course.name, "url": reverse("core:vocational_course_detail", args=[course.pk])},
            ]
        else:
            ctx["breadcrumb"] = [
                {"text": "Vocational Courses", "url": reverse("core:vocational_courses")},
                {"text": course.name, "url": reverse("core:vocational_course_detail", args=[course.pk])},
            ]
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class ExtracurricularActivityDetailView(TemplateView):
    template_name = "template20/extracurricular_activity_detail.html"

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
        ctx["breadcrumb"] = [
            {"text": "Extracurricular Activities", "url": reverse("core:extracurricular_activities")},
            {"text": activity.name, "url": reverse("core:extracurricular_activity_detail", kwargs={"pk": activity.pk})},
        ]
        return ctx

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
        ctx["breadcrumb"] = {"text": "Career Planning Hub", "url": reverse("core:career_planning")}
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class EbookListView(TemplateView):
    template_name = "template20/ebook.html"

    def html_head(self):
        name = "E-Books | Top Teen"
        return build_html_head(title=name, description="Explore our collection of career guidance e-books")

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = {"text": "E-Books", "url": reverse("core:ebook_list")}
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


class EbookDetailView(TemplateView):
    template_name = "template20/flip-book.html"

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
            ctx["breadcrumb"] = {"text": ebook.title, "url": reverse("core:ebook_list")}
        except Ebook.DoesNotExist:
            raise Http404("Ebook not found")
        
        return ctx


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
            print(f"Elasticsearch not available for careers, using Django ORM fallback: {e}")
            ctx['car'] = {'careers': [], 'facets_filter': {'skill': [], 'profession': []}, 'shortlisted_career_ids': []}
        
        try:
            examitems=EntranceExamDocumentFilter()
            ctx['exm']=examitems.get_entrance_exam_list_context(request)
        except Exception as e:
            print(f"Elasticsearch not available for exams, using Django ORM fallback: {e}")
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
        breadcrumb_items = [
            {'title': 'Search', 'text': 'Search Results', 'url': ''}
        ]
        ctx['breadcrumb'] = build_breadcrumb(breadcrumb_items)

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
