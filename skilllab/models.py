from django.db import models
from core.models import BaseModel,BaseMoneyModel, SeoModel,SlugModel
from ckeditor.fields import RichTextField
from core.utils import choices
from users.models import User
from django.core.signing import Signer
from django.urls import reverse,reverse_lazy
from communication.com_service import ComService

def skill_lab_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/skill_lab/{0}/{1}'.format(instance.id, filename)

# Create your models here.

class SkillLabCourse(SlugModel,BaseModel,BaseMoneyModel):
    name=models.CharField(max_length=160)
    image=models.ImageField(upload_to=skill_lab_image_directory,null=True,max_length=250)
    category=models.PositiveSmallIntegerField(choices=choices.SkillLabCourseTypeChoice.CHOICE,default=choices.SkillLabCourseTypeChoice.after_12_class)
    description = RichTextField(null=True)
    video_url=models.URLField(max_length=250,blank=True)
    

    @classmethod
    def all_objects(cls):
        return SkillLabCourse.objects.all().order_by('-modified')
    
    @property
    def is_paid(self):
        if self.amount > 0:
            return True
        return False
    
    def is_user_vissible(self,request):
        if self.is_paid:
            if request.user.is_authenticated:
                if SkilllabCoursePayment.objects.filter(user=request.user,skilllab_course=self,is_success=choices.YesNoChoices.YES).exists():
                    return True
            return False
        else:
            return True

    def get_image_url(self):
        """Get image URL with default fallback"""
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/skilllab-default.png'  # Default skilllab image

    def url(self):
        return reverse('skilllab:skilllabcoursedetail',args=[self.slug])

class SkillLabCourseChapter(SlugModel,BaseModel):
    skilllab=models.ForeignKey(SkillLabCourse,null=True,on_delete=models.SET_NULL,related_name="skilllabcoursechapter")
    chapter_name=models.CharField(max_length=160)
    content = RichTextField(null=True)
    
    def get_slug_field(self):
        return 'chapter_name'

class SkillLabCourseActivity(SlugModel,BaseModel):
    skilllab_chapter=models.ForeignKey(SkillLabCourseChapter,null=True,on_delete=models.SET_NULL,related_name="skilllabcourseactivity")
    name = models.CharField(max_length=160)
    type = models.SmallIntegerField(choices=choices.SkillLabAcivityChoice.CHOICE)
    content = RichTextField(null=True,blank=True) 
    downloadable_file=models.FileField(upload_to=skill_lab_image_directory,null=True,blank=True,max_length=250)
    
    
class SkilllabCoursePayment(BaseModel,BaseMoneyModel):
    skilllab_course = models.ForeignKey(SkillLabCourse,null=True,on_delete=models.SET_NULL,related_name="skilllabcourpayment")
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="userskillabcourse")
    gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
    is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)
    
    def get_payment_success_fail_url(self):
        d={}
        sign = Signer()
        enc_id=sign.sign_object(({"enc_id":self.id}))
        d["success_url"]=reverse('skilllab:skillabcoursepaymentsuccess',kwargs={'enc_id':enc_id})
        d["fail_url"]=reverse('skilllab:skilllabcoursepaymentfail',kwargs={'enc_id':enc_id})
        return d
    
    def send_payment_mail(self):
        cs=ComService()
        cs.send_skillabcourse_payment_success_mail(self.user.email,self)