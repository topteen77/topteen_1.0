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
from django.conf import settings
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
    def get(cls, key, default=0, editable=True):
        defaults = {'value': str(default), 'editable': editable}
        c, created = Configuration.objects.get_or_create(key=key, defaults=defaults)
        return str(c.value) if c.value is not None else str(default)


class MasterClass(BaseModel):
    """
    Master table of school classes/grades. Admins can create rows (e.g. value=6..12)
    Templates should use get_active_master_classes() to render dropdowns.
    """
    # Numeric value used for storage and comparisons (e.g. 6,7,8,...12)
    value = models.PositiveSmallIntegerField(unique=True, db_index=True, help_text="Numeric grade value, e.g. 6..12")
    # Display label e.g. "Class 10"
    label = models.CharField(max_length=64, help_text="Display label, e.g. 'Class 10'")
    # If inactive, do not show in dropdowns
    active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ("-value",)
        verbose_name = "Master Class"
        verbose_name_plural = "Master Classes"

    def __str__(self):
        return "{}".format(self.label or str(self.value))

    @classmethod
    def get_active_master_classes(cls, min_value=6, max_value=12):
        """
        Return a list/queryset of active MasterClass rows filtered to the requested range,
        ordered descending by numeric value (so 12..6).
        """
        try:
            return cls.objects.filter(active=True, value__gte=min_value, value__lte=max_value).order_by("-value")
        except Exception:
            # In case migrations haven't been run or DB not available, fall back to sensible default
            # Return a list of simple dicts that templates can iterate over.
            return [
                {"value": v, "label": f"Class {v}"} for v in range(max_value, min_value - 1, -1)
            ]


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
    priority = models.PositiveSmallIntegerField(default=1, help_text="1 is higher than 2", db_index=True)
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

class Review(BaseModel, PublishableModel):
    """Student testimonial / success story shown on the home page."""
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to=review_image_directory, null=True, blank=True)
    image_s3_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 URL for testimonial photo (auto-set when uploading image in admin)."
    )
    quote = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        help_text="Short quote or headline shown above the full testimonial (avoids repeating the start of description)."
    )
    description = models.TextField(
        help_text="Full testimonial text shown below the quote."
    )
    profession = models.CharField(max_length=100)
    priority = models.PositiveSmallIntegerField(
        default=1,
        help_text="Display order on home page (1 = first). Lower number = higher position."
    )

    class Meta:
        verbose_name = "Student testimonial"
        verbose_name_plural = "Student testimonials"
        ordering = ["priority", "created"]
        indexes = [
            models.Index(fields=['publish_status', 'priority']),
        ]

    def get_image_url(self):
        """Get image URL: S3 URL if set, else local image, else default placeholder."""
        if self.image_s3_url:
            return self.image_s3_url
        if self.image and self.image.name:
            return self.image.url
        return "/static/images/review-default.png"

    @property
    def display_image_url(self):
        """For templates: single URL to use for the testimonial photo."""
        return self.get_image_url()

    @classmethod
    def get_all_reviews(cls):
        return Review.objects.all()

    def __str__(self):
        return self.name

    @classmethod
    def get_published_objects(cls):
        return Review.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by("priority", "created")

class CommonFAQ(BaseModel):
    question = models.CharField(max_length=300,null=True)
    answer = RichTextField(null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    user_type = models.PositiveSmallIntegerField(choices=choices.FAQType.CHOICES, default=0)
    is_featured = models.PositiveSmallIntegerField(choices=choices.FAQFeaturedType.CHOICES, default=choices.FAQFeaturedType.NONE)

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=['user_type', 'is_featured', 'priority']),
        ]

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
    content_json = models.JSONField(null=True, blank=True, help_text="Stored JSON structure parsed from content_html field with fixed accordion sections")
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
        # Always generate slug if it's missing or empty
        if not self.slug or not self.slug.strip():
            base_slug = slugify(self.title)
            if not base_slug:  # If title doesn't generate a valid slug, use a default
                base_slug = f"ebook-{self.id or 'new'}"
            slug = base_slug
            counter = 1
            
            # Check if slug already exists and make it unique
            while Ebook.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                # Prevent infinite loop if slug gets too long
                if len(slug) > 300:
                    slug = f"{base_slug[:290]}-{counter}"
                    break
            
            self.slug = slug
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


class S3FileUpload(BaseModel):
    """
    Model to track files uploaded to S3 bucket
    """
    file_name = models.CharField(max_length=500, help_text="Original file name")
    s3_key = models.CharField(max_length=1000, help_text="S3 object key/path")
    s3_url = models.URLField(max_length=1000, help_text="Full S3 URL")
    file_type = models.CharField(max_length=100, blank=True, null=True, help_text="File MIME type")
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="File size in bytes")
    folder_path = models.CharField(max_length=500, blank=True, null=True, help_text="Folder path in S3")
    description = models.TextField(blank=True, null=True, help_text="Optional description")
    uploaded_by = models.CharField(max_length=200, blank=True, null=True, help_text="User who uploaded the file")

    class Meta(BaseModel.Meta):
        ordering = ("-created",)
        verbose_name = "S3 File Upload"
        verbose_name_plural = "S3 File Uploads"

    def __str__(self):
        return f"{self.file_name} - {self.s3_key}"

    def get_file_size_display(self):
        """Return human-readable file size"""
        if not self.file_size:
            return "Unknown"
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


class FourPillarsAssessmentResult(models.Model):
    """Stores the latest assessment result per user per pillar (one row per user per pillar_slug)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="four_pillars_assessment_results",
    )
    pillar_slug = models.CharField(max_length=64, db_index=True)
    answers = models.JSONField(help_text="Question index -> choice, e.g. {\"0\": \"A\", \"1\": \"B\"}")
    primary_style = models.CharField(max_length=1)
    counts = models.JSONField(help_text="{\"A\": n, \"B\": n, \"C\": n, \"D\": n}")
    profile_name = models.CharField(max_length=255)
    profile_summary = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "pillar_slug"], name="unique_user_pillar_four_pillars"),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user_id} – {self.pillar_slug} ({self.primary_style})"


class MIAssessmentResult(models.Model):
    """Stores Multiple Intelligences (Learning Style) assessment result per user. One row per attempt."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mi_assessment_results",
    )
    answers = models.JSONField(help_text="Question index (0–59) -> choice: A/B/C/D")
    counts = models.JSONField(help_text="{\"A\": n, \"B\": n, \"C\": n, \"D\": n}")
    primary_style = models.CharField(max_length=1)
    style_name = models.CharField(max_length=255)
    style_summary = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "MI Assessment Result"
        verbose_name_plural = "MI Assessment Results"

    def __str__(self):
        return f"{self.user_id} – MI ({self.primary_style}) @ {self.updated_at}"


class EQAssessmentResult(models.Model):
    """Stores Emotional Intelligence assessment result per user. One row per attempt."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="eq_assessment_results",
    )
    responses = models.JSONField(help_text="Q1–Q36 -> 1–5")
    subscale_scores = models.JSONField(help_text="SA, SC, EM, CR, SM, AC")
    weighted = models.JSONField(blank=True, null=True)
    ei_total = models.FloatField()
    pbi = models.FloatField()
    intrapersonal_eq = models.FloatField()
    interpersonal_eq = models.FloatField()
    adaptive_eq = models.FloatField()
    band_label = models.CharField(max_length=128)
    created = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "EQ Assessment Result"
        verbose_name_plural = "EQ Assessment Results"

    def __str__(self):
        return f"{self.user_id} – EQ ({self.ei_total:.1f}) @ {self.updated_at}"


class FourPillarsAssessment(models.Model):
    """Definition of a Four Pillars assessment (questions, scoring, profiles). Editable from admin."""
    slug = models.SlugField(max_length=64, unique=True, help_text="URL slug, e.g. engagement-patterns")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=512, blank=True)
    scoring_intro = RichTextField(
        blank=True,
        help_text="Intro text for the Scoring Guide (e.g. How to Calculate Your Score). Use the editor for formatting.",
    )
    mixed_results = RichTextField(
        blank=True,
        help_text="Text for dual/balanced/multi-modal patterns (mixed results note). Use the editor for formatting.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="If True, assessment content is loaded from DB. If False, falls back to JSON file.",
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return f"{self.title} ({self.slug})"


class FourPillarsAssessmentScoringGuide(FourPillarsAssessment):
    """Proxy model: edit only the Scoring Guide section (intro + mixed results) separately in admin."""
    class Meta:
        proxy = True
        verbose_name = "Four Pillars Scoring Guide"
        verbose_name_plural = "Four Pillars Scoring Guides"


class FourPillarsAssessmentQuestion(models.Model):
    """A single question in a Four Pillars assessment."""
    assessment = models.ForeignKey(
        FourPillarsAssessment,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order (0-based).")
    title = models.CharField(max_length=255, help_text="e.g. Question 1: Energy Source")
    text = models.TextField(help_text="Question text shown to the user.")

    class Meta:
        ordering = ["assessment", "order"]
        unique_together = [["assessment", "order"]]

    def __str__(self):
        return f"{self.assessment.slug} – {self.title}"


class FourPillarsAssessmentQuestionOption(models.Model):
    """One option (A/B/C/D) for a question."""
    question = models.ForeignKey(
        FourPillarsAssessmentQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    option_key = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")])
    text = models.TextField()

    class Meta:
        ordering = ["question", "option_key"]
        unique_together = [["question", "option_key"]]

    def __str__(self):
        return f"{self.question.title} – {self.option_key}"


class FourPillarsAssessmentProfile(models.Model):
    """Scoring profile (A/B/C/D) for an assessment – name, summary, scoring heading and bullets."""
    assessment = models.ForeignKey(
        FourPillarsAssessment,
        on_delete=models.CASCADE,
        related_name="profiles",
    )
    option_key = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")])
    name = models.CharField(max_length=255, help_text="Short profile name, e.g. Goal-Oriented Achiever")
    summary = RichTextField(blank=True, help_text="Profile summary. Use the editor for formatting.")
    scoring_heading = RichTextField(blank=True, help_text="Heading for the Scoring Guide card. Use the editor for formatting.")
    scoring_bullets = models.JSONField(
        default=list,
        help_text="List of bullet strings for the Scoring Guide card.",
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assessment", "option_key"]
        unique_together = [["assessment", "option_key"]]

    def __str__(self):
        return f"{self.assessment.slug} – {self.option_key} ({self.name})"


class CareerBattleFight(models.Model):
    """Stored Career Battle comparison: streams, parameters, result. Per-user history."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='career_battle_fights',
    )
    title = models.CharField(max_length=255, help_text='e.g. "Stream A vs Stream B"')
    cluster_name = models.CharField(max_length=255, blank=True, default='')
    streams = models.JSONField(default=list)  # [stream1_name, stream2_name]
    parameters = models.JSONField(default=list)  # [param_id, ...]
    result = models.JSONField(default=dict)  # { winner, reasoning, details, ... }
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Career Battle Fight'
        verbose_name_plural = 'Career Battle Fights'

    def __str__(self):
        return self.title or f"Fight #{self.pk}"


class CounsellingSession(models.Model):
    """Metadata for AI counselling sessions (analytics / One Student One Mentor). No message content stored."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='counselling_sessions',
    )
    session_id = models.CharField(max_length=64, db_index=True)
    first_message_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    crisis_flagged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-last_message_at']
        verbose_name = 'Counselling Session'
        verbose_name_plural = 'Counselling Sessions'

    def __str__(self):
        return f"Session {self.session_id[:16]}... ({self.user_id})"


def _normalize_grade(value):
    """Return '8','9','10','11','12' or None from UserProfile.grade or class string."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # "10", "10th", "Class 10" -> 10
    import re
    m = re.search(r'\b(8|9|10|11|12)\b', s)
    if m:
        return m.group(1)
    return None


class CareerBattleEligibilityProfile(models.Model):
    """Stored course eligibility choices for Career Battle (education, stream, area, location)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='career_battle_eligibility_profile',
    )
    education_background = models.CharField(max_length=64, blank=True, default='')
    stream = models.CharField(max_length=64, blank=True, default='')
    specific_area = models.CharField(max_length=128, blank=True, default='')
    study_location = models.CharField(max_length=64, blank=True, default='')
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Career Battle Eligibility Profile'
        verbose_name_plural = 'Career Battle Eligibility Profiles'

    def __str__(self):
        return f"Eligibility for {self.user_id}"


# --- Static Page CMS & SEO (Content & SEO Dashboard) ---

STATIC_PAGE_URL_KEYS = [
    "terms",
    "privacy",
    "contact",
    "about",
    "career_planning",
    "career_planning_4_year",
    "career_planning_class_9",
    "career_planning_class_10",
    "career_planning_class_11",
    "career_planning_class_12",
    "emotional_intelligences",
    "multiple_intelligences",
    "four_pillars",
]


class StaticPage(models.Model):
    """
    CMS content for static pages (terms, privacy, about, career planning, etc.).
    Editable from admin and from Content & SEO dashboard (staff only).
    """
    url_key = models.CharField(
        max_length=80,
        unique=True,
        db_index=True,
        help_text="Stable id matching the route, e.g. terms, about, career_planning",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional in-page heading",
    )
    content_html = RichTextField(
        blank=True,
        help_text="Main body HTML. Rendered when present; otherwise template uses default.",
    )
    content_json = models.JSONField(
        blank=True,
        null=True,
        help_text="Structured content as JSON. When set, edit form shows dynamic fields (text, textarea, image) and frontend can render from this.",
    )
    content_css = models.TextField(
        blank=True,
        help_text="Optional CSS injected in the page when rendering (edit via Edit HTML/CSS/JS).",
    )
    content_js = models.TextField(
        blank=True,
        help_text="Optional JavaScript injected at end of page when rendering (edit via Edit HTML/CSS/JS).",
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["url_key"]
        verbose_name = "Static Page (CMS)"
        verbose_name_plural = "Static Pages (CMS)"

    def __str__(self):
        return f"{self.url_key}"

    @property
    def content_html_display(self):
        """Content for display: breadcrumb stripped for all; leading h1 stripped only on simple pages."""
        from core.utils import get_static_page_content_display
        return get_static_page_content_display(self.content_html or "", self.url_key)


class StaticPageSection(models.Model):
    """Optional sectioned content for a static page (e.g. About Us: Our Story, Team)."""
    static_page = models.ForeignKey(
        StaticPage,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_id = models.CharField(max_length=80, help_text="Standard section ID, e.g. our_story, team")
    title = models.CharField(max_length=255, help_text="Section title")
    content_html = RichTextField(help_text="HTML content for this section")
    order = models.PositiveSmallIntegerField(default=1, help_text="Display order")

    class Meta:
        ordering = ["static_page", "order"]
        unique_together = [["static_page", "section_id"]]
        verbose_name = "Static Page Section"
        verbose_name_plural = "Static Page Sections"

    def __str__(self):
        return f"{self.static_page.url_key} – {self.title}"


class PageSEO(models.Model):
    """SEO meta (title, description, keywords, OG) for static pages and any url_key."""
    url_key = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
        help_text="Stable id: url_name e.g. core:aboutus or url_key e.g. about",
    )
    title = models.CharField(
        max_length=70,
        blank=True,
        validators=[MaxLengthValidator(70)],
        help_text="SEO title (50–60 chars recommended)",
    )
    description = models.CharField(
        max_length=300,
        blank=True,
        validators=[MaxLengthValidator(300)],
        help_text="Meta description (150–160 chars recommended)",
    )
    keywords = models.CharField(max_length=500, blank=True, help_text="Optional comma-separated keywords")
    og_image = models.URLField(max_length=500, blank=True, help_text="Open Graph image URL")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["url_key"]
        verbose_name = "Page SEO"
        verbose_name_plural = "Page SEO"

    def __str__(self):
        return f"{self.url_key}"


class ScannedURL(models.Model):
    """URL path collected by the SEO dashboard 'Scan' action. No duplicates; next scan adds only new URLs."""
    url_path = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="URL path without domain (e.g. careers/software-engineer)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True, help_text="Last time this URL was seen in a scan")

    class Meta:
        ordering = ["url_path"]
        verbose_name = "Scanned URL"
        verbose_name_plural = "Scanned URLs"

    def __str__(self):
        return self.url_path


class GeneratedPage(models.Model):
    """CMS page generated from a static HTML URL. Admin enters a URL; we fetch the page, extract HTML body + CSS + JS."""
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        help_text="URL path segment, e.g. my-landing → /page/my-landing/",
    )
    title = models.CharField(max_length=255, help_text="Page title (heading and SEO)")
    content_html = models.TextField(blank=True, help_text="Main body HTML extracted from the source page")
    content_css = models.TextField(blank=True, help_text="CSS to inject in the page")
    content_js = models.TextField(blank=True, help_text="JavaScript to inject at end of page")
    source_url = models.URLField(max_length=2000, blank=True, help_text="URL this page was imported from")
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Generated Page (from URL)"
        verbose_name_plural = "Generated Pages (from URL)"

    def __str__(self):
        return self.slug


# --- Dashboard Statistics (Gamification) - Admin-configurable for student dashboard ---

class DashboardLevelBand(models.Model):
    """Level name and point threshold for student dashboard (e.g. Rookie 0, Explorer 500)."""
    name = models.CharField(max_length=64, help_text="Display name, e.g. Rookie, Explorer")
    min_points = models.PositiveIntegerField(default=0, help_text="Minimum total points for this level")
    order = models.PositiveSmallIntegerField(default=0, help_text="Sort order; higher = higher level")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'min_points']
        verbose_name = 'Dashboard Level Band'
        verbose_name_plural = 'Dashboard Level Bands'

    def __str__(self):
        return f"{self.name} (from {self.min_points} pts)"


class DashboardPointRule(models.Model):
    """Points awarded when a rule_key condition is met (e.g. profile_complete=100)."""
    rule_key = models.CharField(max_length=80, db_index=True, help_text="e.g. profile_complete, test1_complete, psychometric_test_completed")
    points = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rule_key']
        verbose_name = 'Dashboard Point Rule'
        verbose_name_plural = 'Dashboard Point Rules'

    def __str__(self):
        return f"{self.rule_key}: {self.points} pts"


class DashboardTrophyDefinition(models.Model):
    """Defines what counts as one trophy (achievement) for the dashboard count."""
    rule_key = models.CharField(max_length=80, db_index=True, help_text="Same keys as point rules; condition must be true to count")
    label = models.CharField(max_length=120, blank=True, help_text="Admin display label")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rule_key']
        verbose_name = 'Dashboard Trophy Definition'
        verbose_name_plural = 'Dashboard Trophy Definitions'

    def __str__(self):
        return self.label or self.rule_key


class DashboardStreakConfig(models.Model):
    """Optional: how streak is computed (single row)."""
    activity_source = models.CharField(
        max_length=32,
        choices=[
            ('UserActivity', 'UserActivity (page views)'),
            ('UserEvent', 'UserEvent (events)'),
        ],
        default='UserActivity',
        help_text="Which model to use for 'activity' in streak calculation",
    )
    event_types = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated event_type values if source=UserEvent (e.g. page_view,psychometric_test_completed). Empty = all events.",
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dashboard Streak Config'
        verbose_name_plural = 'Dashboard Streak Config'

    def __str__(self):
        return f"Streak: {self.activity_source}"