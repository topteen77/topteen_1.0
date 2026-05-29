from dataclasses import field, fields
import django_filters
from django.db.models import Count, Q
from blog.models import Blog,BlogCategory,BlogTag
from colleges.models import College,CollegeImages,CollegeFlatText,CollegeFacts,CollegeFacility, CollegeText,Facility,CollegeMoneyValue, RecruitingCompanies,CollegeRecruitingCompanies
from core.models import CommonFAQ, Country, Review,State,City,Hobbies,Subject,UserFigureOut,Stories,APILog,VocationalCourseCategory,VocationalCourse,ExtracurricularActivityCategory,ExtracurricularActivity,EntranceTestPrepCategory,EntranceTestPrepExam
from core import choices
from careers.models import Career, CareerFAQ, CareerMedia, CareerPath, Profession,Skill,ProspectiveRecruiter,ProspectiveEmploymentArea,CareerCluster,CareerTags,CareerPathStep,VideoCategory,Videos
from .base_filters import NamedBaseFilter,BaseFilter       
from courses.models import Stream,Course,CourseFacts,CourseIntake,CourseMoneyValue,CourseText,CourseEnglighRequirements
from entrance_exams.models import EntranceExam,ExamTags
from skilllab.models import SkillLabCourse, SkillLabCourseActivity,SkillLabCourseChapter
from crm.models import Lead
from psychometric_tests.models import PsychometricFAQ
from users.models import User
from app_post_matric.models import Test

class CareerFilter(NamedBaseFilter):
    career_cluster = django_filters.ModelChoiceFilter(
        queryset=CareerCluster.objects.filter(object_status=choices.ObjectStatus.ACTIVE).order_by('name'),
        label='Career Cluster',
        empty_label='-- Any --'
    )
    career_cluster_empty = django_filters.ChoiceFilter(
        choices=[('empty', 'Blank or null (not linked)'), ('has', 'Has cluster(s)')],
        label='Career Cluster Status',
        method='filter_career_cluster_empty',
        empty_label='-- Any --'
    )
    image_empty = django_filters.ChoiceFilter(
        choices=[('empty', 'Blank or null (no image)'), ('has', 'Has image')],
        label='Image',
        method='filter_image_empty',
        empty_label='-- Any --'
    )
    image_duplicate = django_filters.ChoiceFilter(
        choices=[('duplicate', 'Same image name (duplicate)'), ('unique', 'Unique image name')],
        label='Image Duplicate',
        method='filter_image_duplicate',
        empty_label='-- Any --'
    )

    class Meta:
        model = Career
        fields = ['name', 'skills', 'publish_status']

    def filter_career_cluster_empty(self, queryset, name, value):
        active_cluster_filter = Q(career_cluster__object_status=choices.ObjectStatus.ACTIVE)
        if value == 'empty':
            return queryset.annotate(
                cc_count=Count('career_cluster', filter=active_cluster_filter)
            ).filter(cc_count=0)
        elif value == 'has':
            return queryset.annotate(
                cc_count=Count('career_cluster', filter=active_cluster_filter)
            ).filter(cc_count__gt=0)
        return queryset

    def filter_image_empty(self, queryset, name, value):
        if value == 'empty':
            return queryset.filter(Q(image='') | Q(image__isnull=True))
        elif value == 'has':
            return queryset.exclude(Q(image='') | Q(image__isnull=True))
        return queryset

    def filter_image_duplicate(self, queryset, name, value):
        dupes = Career.objects.exclude(
            Q(image='') | Q(image__isnull=True)
        ).values('image').annotate(c=Count('id')).filter(c__gt=1).values_list('image', flat=True)
        if value == 'duplicate':
            return queryset.filter(image__in=dupes)
        elif value == 'unique':
            return queryset.exclude(Q(image='') | Q(image__isnull=True)).exclude(image__in=dupes)
        return queryset


class CareerRelatedCareersFilter(NamedBaseFilter):
    career_cluster = django_filters.ModelChoiceFilter(
        queryset=CareerCluster.objects.filter(object_status=choices.ObjectStatus.ACTIVE).order_by('name'),
        label='Career Cluster',
        empty_label='-- Any --',
    )
    has_related = django_filters.ChoiceFilter(
        choices=[('yes', 'Has related careers'), ('no', 'No related careers')],
        label='Related Careers',
        method='filter_has_related',
        empty_label='-- Any --',
    )

    class Meta:
        model = Career
        fields = ['name', 'publish_status']

    def filter_has_related(self, queryset, name, value):
        qs = queryset.annotate(_related_count=Count('related_careers', distinct=True))
        if value == 'yes':
            return qs.filter(_related_count__gt=0)
        if value == 'no':
            return qs.filter(_related_count=0)
        return queryset


class CareerTagsFilter(NamedBaseFilter):
    class Meta:
        model = CareerTags
        fields = ['name','priority']


class SkillFilter(NamedBaseFilter):
    class Meta:
        model = Skill
        fields = ['name','priority']

class SkillLabCourseFilter(NamedBaseFilter):
    class Meta:
        model = SkillLabCourse
        fields = ['name']

class SkillLabCourseChapterFilter(NamedBaseFilter):
    class Meta:
        model = SkillLabCourseChapter
        fields = ['name']


class VideoCategoryFilter(NamedBaseFilter):
    class Meta:
        model = VideoCategory
        fields = ['name']

class VideosFilter(NamedBaseFilter):
    class Meta:
        model = Videos
        fields = ['name']

class SkillLabCourseActivityFilter(NamedBaseFilter):
    class Meta:
        model = SkillLabCourseActivity
        fields = ['name']

        
class ProspectiveEmploymentAreaFilter(NamedBaseFilter):
    class Meta:
        model = ProspectiveEmploymentArea
        fields = ['name']
        
class ProspectiveRecruiterFilter(NamedBaseFilter):
    class Meta:
        model = ProspectiveRecruiter
        fields = ['name']
        
class CareerMediaFilter(BaseFilter):
    class Meta:
        model = CareerMedia
        fields = ['career','type','priority']
        
class CareerPathFilter(NamedBaseFilter):
    class Meta:
        model = CareerPath
        fields = ['name',]

class CareerPathStepFilter(NamedBaseFilter):
    class Meta:
        model = CareerPathStep
        fields = ['name',]

class CareerFAQFilter(BaseFilter):
    question = django_filters.CharFilter(lookup_expr='icontains')
    class Meta:
        model = CareerFAQ
        fields = ['question',]

class CollegeFilter(NamedBaseFilter):
    class Meta:
        model = College
        fields = ['name','country','created_by','publish_status']
        
class CollegeImagesFilter(BaseFilter):
    class Meta:
        model = CollegeImages
        fields = ['college']    
        
class CollegeFlatTextFilter(BaseFilter):
    class Meta:
        model = CollegeFlatText
        fields = ['college','type']
        
class CollegeTextFilter(BaseFilter):
    class Meta:
        model = CollegeText
        fields = ['college','type']
        
class CollegeFactsFilter(BaseFilter):
    class Meta:
        model = CollegeFacts
        fields = ['college','type']   
        
class RecruitingCompaniesFilter(NamedBaseFilter):
    class Meta:
        model = RecruitingCompanies
        fields = ['name']      
        
class CollegeRecruitingCompaniesFilter(BaseFilter):
    class Meta:
        model = CollegeRecruitingCompanies
        fields = ['college','company']   

class FacilityFilter(NamedBaseFilter):
    class Meta:
        model = Facility
        fields = ['name']  
        
class CollegeFacilityFilter(BaseFilter):
    class Meta:
        model = CollegeFacility
        fields = ['college','facility']  
        
class CollegeMoneyValueFilter(BaseFilter):
    class Meta:
        model = CollegeMoneyValue
        fields = ['college','type'] 
        
class CountryFilter(NamedBaseFilter):
    class Meta:
        model = Country
        fields = ['name']   
        
class StateFilter(NamedBaseFilter):
    class Meta:
        model = State
        fields = ['name'] 
        
class CareerClusterFilter(NamedBaseFilter):
    class Meta:
        model = CareerCluster
        fields = ['name']


class VocationalCourseCategoryFilter(NamedBaseFilter):
    class Meta:
        model = VocationalCourseCategory
        fields = ['name']


class VocationalCourseFilter(NamedBaseFilter):
    class Meta:
        model = VocationalCourse
        fields = ['name', 'category']


class ExtracurricularActivityCategoryFilter(NamedBaseFilter):
    class Meta:
        model = ExtracurricularActivityCategory
        fields = ['name']


class ExtracurricularActivityFilter(NamedBaseFilter):
    class Meta:
        model = ExtracurricularActivity
        fields = ['name', 'category']


class EntranceTestPrepCategoryFilter(NamedBaseFilter):
    class Meta:
        model = EntranceTestPrepCategory
        fields = ['name', 'parent']


class EntranceTestPrepExamFilter(NamedBaseFilter):
    class Meta:
        model = EntranceTestPrepExam
        fields = ['name', 'category']


class CityFilter(NamedBaseFilter):
    class Meta:
        model = City
        fields = ['name'] 
        
class ProfessionFilter(NamedBaseFilter):
    class Meta:
        model = Profession
        fields = ['name','career']
        
class StreamFilter(NamedBaseFilter):
    class Meta:
        model = Stream
        fields = ['name']
        
class CourseFilter(NamedBaseFilter):
    class Meta:
        model = Course
        fields = ['name','course_type']

class CourseFactsFilter(BaseFilter):
    class Meta:
        model = CourseFacts
        fields = ['course','type'] 
        
class CourseTextFilter(BaseFilter):
    class Meta:
        model = CourseText
        fields = ['course','type'] 
        
class CourseMoneyValueFilter(BaseFilter):
    class Meta:
        model = CourseMoneyValue
        fields = ['course','type','currency']
        
class CourseIntakeFilter(BaseFilter):
    class Meta:
        model = CourseIntake
        fields = ['course'] 
        
class CourseEnglighRequirementsFilter(BaseFilter):
    class Meta:
        model = CourseEnglighRequirements
        fields = ['course','test'] 
        
class EntranceExamFilter(NamedBaseFilter):
    class Meta:
        model = EntranceExam
        fields = ['name','category']

class ExamTagsFilter(NamedBaseFilter):
    class Meta:
        model = ExamTags
        fields = ['name']


class BlogFilter(BaseFilter):
    title = django_filters.CharFilter(lookup_expr='icontains')
    class Meta:        
        model = Blog
        fields = ['title','author','publish_status']

class BlogCategoryFilter(NamedBaseFilter):
    class Meta:
        model = BlogCategory
        fields = ['name'] 

class BlogTagFilter(NamedBaseFilter):
    class Meta:
        model = BlogTag
        fields = ['name']


class ReviewFilter(NamedBaseFilter):
    class Meta:
        model = Review
        fields = ['name']  

class CommonFAQFilter(BaseFilter):
    question = django_filters.CharFilter(lookup_expr='icontains')
    class Meta:
        model = CommonFAQ
        fields = ['question']        

class HobbiesFilter(NamedBaseFilter):
    class Meta:
        model = Hobbies
        fields = ['name']  

class SubjectFilter(NamedBaseFilter):
    class Meta:
        model = Subject
        fields = ['name']  

class UserFigureOutFilter(NamedBaseFilter):
    class Meta:
        model = UserFigureOut
        fields = ['name']  

class StoriesFilter(BaseFilter):
    title = django_filters.CharFilter(lookup_expr='icontains')
    class Meta:        
        model = Stories
        fields = ['title','file_type','obj_type']
        
class ApilogFilter(BaseFilter):
    api_name = django_filters.CharFilter(lookup_expr='icontains')
    class Meta:
        model = APILog
        fields = ['api_name']  
        
        
class LeadFilter(BaseFilter):
    class Meta:
        model = Lead
        fields = ['action','status']  
        
class PsychometricFaqFilter(BaseFilter):
    class Meta:
        model=PsychometricFAQ
        fields = ['question']

class StudentFilter(BaseFilter):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    email = django_filters.CharFilter(field_name='email', lookup_expr='icontains')
    mobile = django_filters.CharFilter(field_name='mobile', lookup_expr='icontains')
    test = django_filters.ModelChoiceFilter(
        field_name='test_sessions__test',
        queryset=Test.objects.filter(is_active=True),
        label='Test'
    )
    status = django_filters.ChoiceFilter(
        method='filter_by_status',
        choices=[
            ('all', 'All'),
            ('completed', 'Completed'),
            ('pending', 'Pending'),
            ('not_started', 'Not Started'),
        ],
        label='Status'
    )
    
    class Meta:
        model = User
        fields = ['name', 'email', 'mobile', 'test', 'status']
    
    def filter_by_status(self, queryset, name, value):
        if value == 'completed':
            return queryset.filter(test_sessions__is_completed=True).distinct()
        elif value == 'pending':
            return queryset.filter(test_sessions__is_completed=False).distinct()
        elif value == 'not_started':
            return queryset.filter(test_sessions__isnull=True)
        return queryset