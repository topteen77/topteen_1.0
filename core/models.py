from datetime import timedelta
from doctest import Example
from django.utils import timezone
from django.db import models
from django.db.models.query import QuerySet
from core import choices
from django.db.models.signals import post_delete
from simple_history.models import HistoricalRecords
from ckeditor.fields import RichTextField
from django.utils.text import slugify
from django.core.validators import MaxLengthValidator
from django.urls import reverse
import datetime
# Create your models here.

def core_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/flag/{0}/{1}'.format(instance.id, filename)


class SoftDeletionQuerySet(QuerySet):
    def delete(self):
        return super(SoftDeletionQuerySet, self).update(object_status = choices.ObjectStatus.DELETED)

    def hard_delete(self):
        return super(SoftDeletionQuerySet, self).delete()

class SoftDeletionManager(models.Manager):        
    def get_queryset(self):
        return SoftDeletionQuerySet(self.model).filter(object_status=choices.ObjectStatus.ACTIVE)

    def complete(self):
        return super().get_queryset()


class BaseModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    object_status = models.SmallIntegerField(choices=choices.ObjectStatus.CHOICES, default=choices.ObjectStatus.ACTIVE)

    objects = SoftDeletionManager()

    class Meta:
        abstract = True

    def delete(self, hard_delete=False):
        if not hard_delete:
            self.object_status = choices.ObjectStatus.DELETED
            self.save()
        else:
            super().delete()
        # Trigger the post_delete signal to update the ES index
        # TODO: Check how it impacts fields in other indexes
        post_delete.send(sender=self.__class__, instance=self)

    def __str__(self):
        value = self.name if hasattr(self,'name') else getattr(self,"id")
        return "{}".format(value)

    def _get_class_name(self):
        return self.__class__.__name__

    @property
    def edit_url(self):
        cls_name=self._get_class_name().lower()
        return reverse('topteenadminmanaged:{}edit'.format(cls_name), kwargs={'pk': self.pk})
    
    @property
    def detail_url(self):
        cls_name=self._get_class_name().lower()
        return reverse('topteenadminmanaged:{}detail'.format(cls_name), kwargs={'pk': self.pk})

    @property
    def delete_url(self):
        cls_name=self._get_class_name().lower()
        return reverse('topteenadminmanaged:{}delete'.format(cls_name), kwargs={'pk': self.pk})
    
    @property
    def list_url(self):
        cls_name=self._get_class_name().lower()
        return reverse('topteenadminmanaged:{}list'.format(cls_name))
    
    

class Configuration(BaseModel):
    key = models.CharField(max_length=120,unique=True)
    value = models.CharField(max_length=120)
    editable = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return "{}".format(self.key)


    @classmethod
    def get(cls,key,default=0,editable=True):
        c,created=Configuration.objects.get_or_create(key=key,defaults={'value':default,'editable':editable})
        return c.value


class BaseCSC(BaseModel):
    name=models.CharField(max_length=120)
    class Meta:
        abstract = True

    @classmethod
    def search(cls,q,q_type,selected_countries=None):
        if q_type == 'country':
            countris = Country.objects.filter(name__icontains=q)
            return list(countris)
        states=State.objects.filter(name__icontains=q)
        cities=City.objects.filter(name__icontains=q)
        if selected_countries:
            country_ids=[]
            for country in selected_countries:
                country,id=country.split('-')
                country_ids.append(id)
            states=states.filter(country_id__in=country_ids)
            cities=cities.filter(state__country_id__in=country_ids)
        
        return list(states) + list(cities)

class SlugModel(models.Model):
    slug=models.SlugField(max_length=255,unique=True,null=True)
    
    def get_slug_field(self):
        return 'name'

    def save(self, *args, **kwargs):
        if self.slug is None:
            self.slug = slugify(getattr(self,self.get_slug_field()))
            existing_slug_count = self.__class__.objects.filter(slug__icontains=self.slug).count()
            if existing_slug_count > 0 and self.id is None:
                self.slug += "-{}".format(existing_slug_count+1)
        super(SlugModel, self).save(*args, **kwargs)
    class Meta:
        abstract = True

    def __str__(self):
        return "{}".format(getattr(self,self.get_slug_field()))
  
class PublishableModel(models.Model):
    publish_status = models.SmallIntegerField(db_index=True,choices=choices.PublishStatus.CHOICES,default=choices.PublishStatus.PUBLISHED)

    class Meta:
        abstract = True

  
class SeoModel(models.Model):
    seo_title = models.CharField(
        max_length=70, blank=True, null=True, validators=[MaxLengthValidator(70)]
    )
    seo_description = models.CharField(
        max_length=300, blank=True, null=True, validators=[MaxLengthValidator(300)]
    )

    class Meta:
        abstract = True
          
class Country(BaseCSC):
    short_name=models.CharField(max_length=5)
    phone_code=models.CharField(max_length=5)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    flag = models.ImageField(upload_to=core_image_directory,null=True,max_length=250)
    class Meta:
        verbose_name_plural = "Countries"
    
class State(BaseCSC):
    country=models.ForeignKey(Country,null=True,on_delete=models.SET_NULL,related_name="states")

class City(BaseCSC):
    state=models.ForeignKey(State,null=True,on_delete=models.SET_NULL,related_name="cities")

    class Meta:
        verbose_name_plural = "Cities"

class BaseMoneyModel(models.Model):
    currency = models.PositiveSmallIntegerField(choices=choices.Currency.CHOICES,default=choices.Currency.IND)
    amount =models.PositiveIntegerField(default=0)
    class Meta:
        abstract = True

    
    def get_display_price(self):
        return '₹ {}'.format(self.amount)


class ImageUploadModel(BaseModel):
   file = models.FileField(upload_to='upload/documents/', null=True,blank=True)
   upload = models.ImageField(upload_to='upload/images/', null=True,blank=True)



def review_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/review/image/{0}'.format(filename)

class Review(BaseModel,PublishableModel):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to=review_image_directory)
    description = models.TextField()
    profession= models.CharField(max_length=100)

    def get_image_url(self):
        """Get image URL with default fallback"""
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/review-default.png'  # Default review image

    @classmethod
    def get_all_reviews(cls):
        return Review.objects.all()

    def __str__(self):
        return self.name

    @classmethod
    def get_published_objects(cls):
        return Review.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)

class CommonFAQ(BaseModel):
    question = models.CharField(max_length=300,null=True)
    answer = RichTextField(null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    user_type = models.PositiveSmallIntegerField(choices=choices.FAQType.CHOICES, default=0)
    is_featured = models.PositiveSmallIntegerField(choices=choices.FAQFeaturedType.CHOICES, default=choices.FAQFeaturedType.NONE)

    @classmethod
    def get_commonfaq_by_priority(cls):
        return cls.objects.order_by('priority')     

def hobbies_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/hobbies/image/{0}'.format(filename)

def subject_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/subject/image/{0}'.format(filename)

def figure_out_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/figureout/image/{0}'.format(filename)

class Hobbies(BaseModel):
    name=models.CharField(max_length=250)
    image = models.ImageField(upload_to=hobbies_image_directory)
    

class Subject(BaseModel,SlugModel):
    name=models.CharField(max_length=250)
    image = models.ImageField(upload_to=subject_image_directory)
    

    @property
    def is_story(self):
        now=timezone.now()
        return Stories.objects.filter(obj_id=self.id,obj_type=choices.StoryObjectType.SUBJECT,start_date__lte=now,end_date__gte=now).exists()

    @property
    def get_first_story(self):
        now=timezone.now()
        return Stories.objects.filter(obj_id=self.id,obj_type=choices.StoryObjectType.SUBJECT,start_date__lte=now,end_date__gte=now).first()

    def get_story(self):
        now=timezone.now()
        return Stories.objects.filter(obj_id=self.id,obj_type=choices.StoryObjectType.SUBJECT,start_date__lte=now,end_date__gte=now)

class UserFigureOut(BaseModel,SlugModel):
    name=models.CharField(max_length=250,null=True,blank=True)
    description=models.CharField(max_length=250,null=True,blank=True)
    image = models.ImageField(upload_to=figure_out_image_directory,null=True,blank=True)
      
class APILog(BaseModel):
    api_name=models.CharField(max_length=120,null=True,blank=True)
    url = models.TextField()
    request = models.TextField()
    response = models.TextField()
    status_code = models.SmallIntegerField()

def story_file_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/core/story/file/{0}'.format(filename)

class Stories(BaseModel):
    obj_id=models.IntegerField()
    obj_type=models.SmallIntegerField(choices=choices.StoryObjectType.CHOICES)
    file_type=models.SmallIntegerField(choices=choices.FileType.CHOICES,default=choices.FileType.IMAGE)
    file = models.FileField(upload_to=story_file_directory)
    title=models.CharField(max_length=250,null=True,blank=True)
    summary=models.TextField(null=True,blank=True)
    start_date=models.DateTimeField()
    end_date=models.DateTimeField()

class Contact(BaseModel):
    name=models.CharField(max_length=100)
    mobile=models.CharField(max_length=20,null=True)
    email=models.EmailField()
    message=models.TextField(max_length=500)

class Lead(BaseModel):
    name=models.CharField(max_length=100)
    mobile=models.CharField(max_length=20,null=True)