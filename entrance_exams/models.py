from lib2to3.pgen2.token import SLASH
from django.db import models
from core.models import BaseModel,SlugModel,SeoModel
from colleges.models import College,CollegeChildModel
from core.utils import date_format
from ckeditor.fields import RichTextField
from core.utils import choices
from courses.models import Stream
from django.urls import reverse
from users.models import User
# Create your models here.
from django.templatetags.static import static

def exam_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/exam/logo/{0}'.format(filename)

class ExamTags(BaseModel,SlugModel,SeoModel):
    name=models.CharField(max_length=250)

class EntranceExam(BaseModel,SlugModel,SeoModel):
    name=models.CharField(max_length=160)
    about=RichTextField(null=True)
    exam_pattern = RichTextField(null=True) 
    eligibility = RichTextField(null=True)
    more_info = RichTextField(null=True)
    category=models.PositiveSmallIntegerField(choices=choices.EntranceExamTypechoice.CHOICE,default=choices.EntranceExamTypechoice.after_12_class)
    stream=models.ManyToManyField(Stream)
    logo=models.ImageField(upload_to=exam_image_directory,null=True,max_length=250,blank=True)
    examtags=models.ManyToManyField(ExamTags,related_name="exams")
    shortlist = models.ManyToManyField(User,related_name='exam_shortlist')
    exam_date=models.DateField(null=True,blank=True)

    def url(self):
        return reverse('entrance_exams:testprepdetail',args=[self.slug])

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        return static('topteenfrontend/assets/images/BITS_LARGE.png')

    #def formated_date(self):
    #    return date_format(self.next_exam_date)

