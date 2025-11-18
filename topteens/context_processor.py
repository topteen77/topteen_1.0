from careers.models import Career, CareerTags,Videos
from core.models import Configuration
from blog.models import Blog, BlogCategory
from django.db.models import Count
from core.utils import build_html_head
from colleges.models import College
from courses.models import Course
from users.models import UserSearchHistory
from entrance_exams.models import EntranceExam
from users.models import User
from core import choices
from django.db.models import Q
from functools import reduce
from operator import or_

def globals(request): 
    career_list=[]
    college_list=[]
    exam_list=[] 
    input=request.GET.get('search')
    login_user=request.user
    if login_user.is_authenticated:
        usersearch,_=UserSearchHistory.objects.get_or_create(user=login_user,search=input)

        user_search_hisotry=UserSearchHistory.objects.filter(user=login_user.id,search__isnull=False).order_by('-modified').values_list('search',flat=True)
        if user_search_hisotry.exists():
            q_object = reduce(or_,(Q(name__icontains=sh) for sh in user_search_hisotry))
            career_list=Career.objects.filter(q_object)[:5]
            college_list=College.objects.filter(q_object)[:5]
            exam_list=EntranceExam.objects.filter(q_object)[:5]

        
    popular_categories = Blog.objects.values("category").annotate(count=Count('category')).order_by("-count").values_list('category')
    popular_tags = Career.objects.values("career_tags").annotate(count=Count('career_tags')).order_by("-count").values_list('career_tags')
    # for p in popular_tags:
        # popular_tag_count=Career.objects.filter(career_tags=p).count()
    kwargs = {
        "popular_categories":BlogCategory.objects.filter(id__in=popular_categories),
        "popular_tags":CareerTags.objects.filter(id__in=popular_tags),
        "blogs":Blog.get_published_objects().all(),
        "seo_year":"2025",
        "recentcareer":career_list,
        "recentcollege":college_list,
        "recentexam":exam_list,
        "most_searchcareers":Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).order_by('?')[:8],
        'most_searchcolleges':College.objects.all().order_by('id')[:5],
        'tranding_content':Blog.objects.all(),
        "careervideos_count":Videos.objects.count(),
        # "popular_tag_count":popular_tag_count
    }
    return kwargs