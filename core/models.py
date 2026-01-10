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


class ExtracurricularActivityCategory(BaseModel, SlugModel):
    """
    A section/card on the Extracurricular Activities page (e.g. Sports, Arts, Technology).
    """
    name = models.CharField(max_length=250)
    icon_class = models.CharField(
        max_length=120,
        default="bx bx-star",
        help_text="Boxicons class, e.g. 'bx bx-brain', 'bx bx-football'",
    )
    css_class = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Optional extra CSS class for the card wrapper, e.g. 'academic', 'sports', 'arts'.",
    )
    priority = models.PositiveSmallIntegerField(default=1, help_text="Lower comes first")
    image = models.ImageField(upload_to="upload/core/extracurricular/category/", blank=True, null=True)

    class Meta(BaseModel.Meta):
        ordering = ("priority", "name")
        verbose_name = "Extracurricular Category"
        verbose_name_plural = "Extracurricular Categories"


class ExtracurricularActivity(BaseModel, SlugModel):
    """
    A single activity row under a category (e.g. 'Debating & Public Speaking Events').
    """
    category = models.ForeignKey(
        ExtracurricularActivityCategory,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    name = models.CharField(max_length=300)
    image = models.ImageField(upload_to="upload/core/extracurricular/activity/", blank=True, null=True)
    url = models.URLField(blank=True, null=True, help_text="Optional external link")
    content_html = RichTextField(blank=True, null=True, help_text="Optional detailed content (HTML) for the activity detail page")
    priority = models.PositiveSmallIntegerField(default=1, help_text="Lower comes first")

    class Meta(BaseModel.Meta):
        ordering = ("priority", "name")
        verbose_name = "Extracurricular Activity"
        verbose_name_plural = "Extracurricular Activities"


class ExtracurricularActivitySection(BaseModel):
    """
    A section within an ExtracurricularActivity (e.g., "Objectives & Goals", "Participation Details").
    Each numbered heading from the DOCX becomes a separate section record.
    """
    activity = models.ForeignKey(
        ExtracurricularActivity,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_id = models.CharField(
        max_length=50,
        help_text="Standard section ID: objectives, participation, keyskills, etc."
    )
    title = models.CharField(max_length=300, help_text="Section title (e.g., 'Objectives & Goals')")
    content_html = RichTextField(help_text="HTML content for this section")
    order = models.PositiveSmallIntegerField(default=1, help_text="Display order")
    icon = models.CharField(
        max_length=50,
        default="bx-target-lock",
        help_text="Boxicons class for navigation icon"
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short description for navigation (e.g., 'Academic excellence, critical thinking')"
    )

    class Meta(BaseModel.Meta):
        ordering = ("order",)
        unique_together = [("activity", "section_id")]
        verbose_name = "Extracurricular Activity Section"
        verbose_name_plural = "Extracurricular Activity Sections"


class VocationalCourseCategory(BaseModel, SlugModel):
    """
    Category hierarchy for vocational courses, derived from folder structure like:
    - after 10 / after 12
      - ITI certificate courses / diploma courses / ...
    """
    name = models.CharField(max_length=250)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    priority = models.PositiveSmallIntegerField(default=1, help_text="Lower comes first")
    image = models.ImageField(upload_to="upload/core/vocational/category/", blank=True, null=True)

    class Meta(BaseModel.Meta):
        ordering = ("priority", "name")
        verbose_name = "Vocational Course Category"
        verbose_name_plural = "Vocational Course Categories"


class VocationalCourse(BaseModel, SlugModel):
    category = models.ForeignKey(
        VocationalCourseCategory,
        on_delete=models.CASCADE,
        related_name="courses",
    )
    name = models.CharField(max_length=300)
    image = models.ImageField(upload_to="upload/core/vocational/course/", blank=True, null=True)
    content_html = RichTextField(blank=True, null=True)
    priority = models.PositiveSmallIntegerField(default=1, help_text="Lower comes first")

    class Meta(BaseModel.Meta):
        ordering = ("priority", "name")
        verbose_name = "Vocational Course"
        verbose_name_plural = "Vocational Courses"


def ebook_cover_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/ebook/cover/<filename>
    return 'upload/core/ebook/cover/{0}'.format(filename)


def ebook_pdf_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/ebook/pdf/<filename>
    return 'upload/core/ebook/pdf/{0}'.format(filename)


class Ebook(BaseModel, PublishableModel):
    title = models.CharField(max_length=300, help_text="Title of the ebook")
    description = models.TextField(blank=True, null=True, help_text="Description of the ebook")
    cover_image = models.ImageField(
        upload_to=ebook_cover_directory,
        blank=True,
        null=True,
        help_text="Cover image for the ebook (recommended size: 400x600px). Leave empty if using S3 URL."
    )
    cover_image_s3_url = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        help_text="S3 URL for cover image (e.g., https://topteenc.s3.ap-northeast-1.amazonaws.com/ebook/cover/image.jpg). Leave empty if uploading file."
    )
    pdf_file = models.FileField(
        upload_to=ebook_pdf_directory,
        blank=True,
        null=True,
        help_text="PDF file of the ebook. Leave empty if using S3 URL."
    )
    pdf_file_s3_url = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        help_text="S3 URL for PDF file (e.g., https://topteenc.s3.ap-northeast-1.amazonaws.com/ebook/pdf/book.pdf). Leave empty if uploading file."
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        help_text="Lower number appears first in listing"
    )
    slug = models.SlugField(max_length=300, unique=True, blank=True, null=True)

    class Meta(BaseModel.Meta):
        ordering = ("priority", "title")
        verbose_name = "Ebook"
        verbose_name_plural = "Ebooks"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_cover_url(self):
        """Get cover image URL - prioritizes S3 URL over uploaded file"""
        if self.cover_image_s3_url:
            return self.cover_image_s3_url
        if self.cover_image and self.cover_image.name:
            return self.cover_image.url
        return None

    def get_pdf_url(self):
        """Get PDF file URL - prioritizes S3 URL over uploaded file"""
        if self.pdf_file_s3_url:
            return self.pdf_file_s3_url
        if self.pdf_file and self.pdf_file.name:
            return self.pdf_file.url
        return None

    @classmethod
    def get_published_ebooks(cls):
        """Get all published ebooks"""
        return cls.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)