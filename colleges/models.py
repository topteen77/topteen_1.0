import re
import uuid
from datetime import date, datetime, timedelta
from statistics import mode

from core import choices, utils
from core.models import (BaseModel, BaseMoneyModel, City, Configuration,
                         Country, SeoModel, SlugModel, State,PublishableModel)
from core.utils import (build_breadcrumb, get_current_user,
                        ratio)
from django.contrib.contenttypes.fields import (GenericForeignKey,
                                                GenericRelation)
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Avg, Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from topteens.jinja_env import currency_format
from users.models import User

# Create your models here.

def college_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/college/logo/{0}/{1}'.format(instance.id, filename)


class CollegeCategory(BaseModel,SlugModel):
    name = models.CharField(max_length=200)

class Stream(BaseModel,SlugModel):
    name = models.CharField(max_length=200)

class College(BaseModel,SeoModel,SlugModel,PublishableModel):
    '''
    DO NOT CREATE ANY TEXT FIELD HERE OR STAT FIELD, 
    USE THE TEXT AND STAT MODELS INSTEAD
    WHICH ARE FOLLOWING THIS CLASS
    '''
    name=models.CharField(max_length=200,blank=True)
    created_by = models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name="colleges_created")
    updated_by = models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name="colleges_updated")
    country = models.ForeignKey(Country,null=True,on_delete=models.SET_NULL)
    banner=models.ImageField(upload_to=college_image_directory,null=True,max_length=250)
    logo=models.ImageField(upload_to=college_image_directory,null=True,max_length=250)
    state =models.ForeignKey(State,blank=True,null=True,on_delete=models.SET_NULL)
    city =models.ForeignKey(City,blank=True,null=True,on_delete=models.SET_NULL)
    category =models.ForeignKey(CollegeCategory,blank=True,null=True,on_delete=models.SET_NULL)
    stream =models.ForeignKey(Stream,blank=True,null=True,on_delete=models.SET_NULL)
    college_type=models.PositiveSmallIntegerField(choices=choices.CollegeType.CHOICES,default=choices.CollegeType.PRIVATE)
    university_type=models.PositiveSmallIntegerField(choices=choices.UniversityType.CHOICES,default=choices.UniversityType.COLLEGE)
    shortlist = models.ManyToManyField(User,blank=True,related_name='college_shortlist')
    
    @classmethod
    def get_all_colleges(cls):
        return College.objects.all()

    def save(self, *args, **kwargs):
        current_user=get_current_user()
        if self.created_by is None:
            self.created_by = current_user
        self.updated_by=current_user
        super().save(*args, **kwargs)

   
    def get_location(self):
        try:
            state_name=self.state.name if self.state and self.state.name else self.country.name
            return "{}, {}, {}".format(self.city.name, state_name,self.country.short_name)
        except:
            return None
    
    def _get_fact(self,fact_type,value_only=True):
        fact=self.facts.filter(type=fact_type).last()
        if value_only:
            return fact.value if fact else ''
        return fact
    
    def _get_text(self,text_type,value_only=True):
        text=self.texts.filter(type=text_type).last()
        if value_only:
            return text.value if text else ''
        return text

    
    def _get_flat_text(self,text_type,value_only=True):
        text=self.flat_texts.filter(type=text_type).last()
        if value_only:
            return text.value if text else ''
        return text

    def get_email(self):
        return self._get_flat_text(choices.FlatTextType.EMAIL)
    
    def get_banner(self):
        if self.banner:
            return self.banner.url
        return self.logo.url

    def get_mobile(self):
        return self._get_flat_text(choices.FlatTextType.MOBILE)

    def get_website(self):
        return self._get_flat_text(choices.FlatTextType.WEBSITE)

    def get_about_us(self):
        return self._get_text(choices.CollegeTextType.ABOUT)
    
    def prepare_texts_about(self):
        return self.texts.filter(type=choices.CollegeTextType.ABOUT)
    
    
    def url(self):
        return reverse('colleges:collegedetail',args=[self.slug])

   

def college_images_dir(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/college/college-images/{0}/{1}'.format(instance.college, filename)
    


class CollegeImages(BaseModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="college_images")
    college_image = models.FileField(upload_to=college_images_dir)
    image_alt_text = models.CharField(max_length=255, null=False, blank=False)
    
class CollegeChildModel(BaseModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.college.save()

class CollegeFlatText(CollegeChildModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="flat_texts")
    type=models.PositiveSmallIntegerField(choices=choices.FlatTextType.CHOICES,default=0)
    value=models.CharField(max_length=255)

class CollegeText(CollegeChildModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="texts")
    type=models.PositiveSmallIntegerField(choices=choices.CollegeTextType.CHOICES,default=0)
    value=models.TextField(blank=True)

class CollegeFacts(CollegeChildModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="facts")
    type=models.PositiveSmallIntegerField(choices=choices.CollegeFactType.CHOICES,default=0)
    value=models.IntegerField(blank=True)

    class Meta:
        verbose_name_plural="College Facts"
        
def college_child_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/college/common/{0}'.format(filename)

class RecruitingCompanies(BaseModel):
    name=models.CharField(max_length=120)
    logo=models.ImageField(upload_to=college_child_image_directory,null=True,blank=True,max_length=250)
    class Meta:
        verbose_name_plural="Recruiting Companies"

class CollegeRecruitingCompanies(CollegeChildModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="recruiting_companies")  
    company=models.ForeignKey(RecruitingCompanies,on_delete=models.CASCADE,related_name="college_companies")
    class Meta:
        verbose_name_plural="College Recruiting Companies"

class Facility(BaseModel):
    name=models.CharField(max_length=120)
    logo=models.ImageField(upload_to=college_child_image_directory,null=True,max_length=250)
    class Meta:
        verbose_name_plural="Facilities"

class CollegeFacility(CollegeChildModel):
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="facilities")  
    facility=models.ForeignKey(Facility,on_delete=models.CASCADE,related_name="colleges")
    class Meta:
        verbose_name_plural="College Facilities"


class CollegeMoneyValue(CollegeChildModel,BaseMoneyModel):
    '''
    Currency and Value are inherited from base money model
    '''
    college=models.ForeignKey(College,on_delete=models.CASCADE,related_name="money_values")  
    type = models.PositiveSmallIntegerField(choices=choices.CollegeMoneyType.CHOICES,default=0)
    class Meta:
        verbose_name_plural="College MoneyValues"

class CollegeShortlist(BaseModel):
    user=models.ForeignKey(User,null=True,on_delete=models.CASCADE,related_name="college_shortlists")
    college=models.ForeignKey(College,null=True,on_delete=models.CASCADE,related_name="college_shortslists")