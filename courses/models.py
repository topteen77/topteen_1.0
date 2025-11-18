from django.db import models
from colleges.models import College,CollegeChildModel
from core.models import BaseModel,BaseMoneyModel, SeoModel,SlugModel
from core import choices
from users.models import User
# Create your models here.


class Stream(BaseModel,SlugModel):
    name=models.CharField(max_length=200)
    def __str__(self):
        return self.name

def course_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/course/logo/{0}/{1}'.format(instance.id, filename)

class Degree(BaseModel,SlugModel):
    name=models.CharField(max_length=250)


class Course(SeoModel,SlugModel,BaseModel):
    college=models.ForeignKey(College,on_delete=models.SET_NULL,null=True,related_name="courses")
    name=models.CharField(max_length=250)
    slug=models.CharField(max_length=150,null=True)
    overview=models.TextField(blank=True)
    logo=models.ImageField(upload_to=course_image_directory,null=True,max_length=250)
    duration_months=models.PositiveSmallIntegerField(default=0,help_text="Duration in Months")
    program_level=models.PositiveSmallIntegerField(choices=choices.ProgramLevel.CHOICES,default=choices.ProgramLevel.UG)
    course_type = models.PositiveSmallIntegerField(choices=choices.CourseType.CHOICES,default=choices.CourseType.FULL_TIME_ON_CAMPUS)
    stream = models.ForeignKey(Stream,on_delete=models.SET_NULL,null=True,related_name="streams")
    class Meta:
        verbose_name_plural="Courses"
    
    @classmethod
    def get_all_courses(cls):
        return Course.objects.all()

class CourseChildModel(BaseModel):
    class Meta:
        abstract = True

class CourseFacts(CourseChildModel):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="facts")
    type=models.PositiveSmallIntegerField(choices=choices.CourseFactType.CHOICES,default=0)
    value=models.IntegerField(default=0)

    class Meta:
        verbose_name_plural="College Facts"

class CourseText(CourseChildModel):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="texts")
    type=models.PositiveSmallIntegerField(choices=choices.CourseTextType.CHOICES,default=1)
    value=models.TextField(blank=True)


class CourseMoneyValue(CourseChildModel,BaseMoneyModel):
    '''
    Currency and Value are inherited from base money model
    '''
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="money_values")  
    type = models.IntegerField(choices=choices.CourseMoneyType.CHOICES,default=0)
    class Meta:
        verbose_name_plural="Course Money"

class CourseIntake(CourseChildModel):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="intakes")  
    intake_date=models.DateField()
    intake_start_date=models.DateField()
    intake_end_date=models.DateField()
    

    class Meta:
        verbose_name_plural="Course Intakes"

class CourseEnglighRequirements(CourseChildModel):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name="english_requirements")  
    test=models.PositiveSmallIntegerField(choices=choices.EnglishRequirementTest.CHOICES,default=0)
    test_score_type=models.PositiveSmallIntegerField(choices=choices.EnglishRequirementTestScoreType.CHOICES,default=0)
    test_score=models.FloatField(default=0)

    class Meta:
        verbose_name_plural="Course English Requirements"

class CourseShortlist(BaseModel):
    user=models.ForeignKey(User,null=True,on_delete=models.CASCADE,related_name="course_shortlists")
    course=models.ForeignKey(Course,null=True,on_delete=models.CASCADE,related_name="course_shortslists")