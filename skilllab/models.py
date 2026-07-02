from django.db import models
from django.templatetags.static import static
from django.utils.text import slugify
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


def international_course_image_directory(instance, filename):
    return 'upload/international_courses/{0}/image/{1}'.format(instance.pk, filename)


def international_course_logo_directory(instance, filename):
    return 'upload/international_courses/{0}/logo/{1}'.format(instance.pk, filename)


DEFAULT_INTL_COURSE_IMAGE = "images_new/thirdparty/course-img-1.png"
DEFAULT_INTL_COURSE_LOGO = "images_new/thirdparty/logo.png"

# Create your models here.

class SkillLabCourse(SlugModel,BaseModel,BaseMoneyModel):
    name=models.CharField(max_length=160)
    image=models.ImageField(upload_to=skill_lab_image_directory,null=True,max_length=250)
    category=models.PositiveSmallIntegerField(choices=choices.SkillLabCourseTypeChoice.CHOICE,default=choices.SkillLabCourseTypeChoice.after_12_class, db_index=True)
    description = RichTextField(null=True, blank=True)  # Kept for SEO/fallback; use course_intro_html for tab
    course_intro_html = RichTextField(null=True, blank=True, help_text="HTML for Course Introduction tab")
    course_index_html = RichTextField(null=True, blank=True, help_text="HTML for Course Index tab")
    video_url=models.URLField(max_length=250,blank=True)

    class Meta:
        indexes = [models.Index(fields=['category', '-modified'])]

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

    def user_has_started(self, user):
        """True when the learner has opened or progressed in this course."""
        if not user or not getattr(user, "is_authenticated", False) or not user.is_authenticated:
            return False
        if self.skilllabcourseresume.filter(user=user).exists():
            return True
        summary = self.skilllabcourseprogresssummary.filter(user=user).first()
        if summary and summary.progress_percentage > 0:
            return True
        return self.skilllabcourseprogress.filter(user=user).exists()

    def _name_lower(self):
        return (self.name or "").lower()

    def get_topic_category_key(self):
        name = self._name_lower()
        career_kw = (
            "career", "job", "interview", "resume", "professional",
            "networking", "entrepreneurship", "college", "internship",
        )
        life_kw = (
            "life skill", "emotional", "time-management", "time management",
            "productivity", "conflict", "self-advocacy", "communication",
            "public speaking", "study technique", "personal finance",
            "budget", "notepad", "wellness",
        )
        future_kw = (
            "future", "sustainability", "green", "ai ", "artificial intelligence",
            "stem", "digital detox", "adaptability", "resilience", "coding",
            "app development", "cyber",
        )
        if any(k in name for k in career_kw):
            return "career"
        if any(k in name for k in life_kw):
            return "life-skills"
        if any(k in name for k in future_kw):
            return "future-readiness"
        return "skills"

    def get_topic_category_display(self):
        labels = {
            "career": "Career",
            "skills": "Skills",
            "life-skills": "Life Skills",
            "future-readiness": "Future readiness",
        }
        return labels.get(self.get_topic_category_key(), "Skills")

    def get_grade_numbers(self):
        import re

        name = self._name_lower()
        for grade in range(6, 13):
            if re.search(rf"\b(class|grade)\s*{grade}\b", name):
                return {grade}
        if any(x in name for x in ("middle school", "6-8", "6–8", "classes 6")):
            return {6, 7, 8}
        if any(x in name for x in ("high school", "highschool", "teen", "highschoolers")):
            return {9, 10, 11, 12}
        if self.category == choices.SkillLabCourseTypeChoice.after_10_class:
            return {9, 10}
        if self.category == choices.SkillLabCourseTypeChoice.after_12_class:
            return {11, 12}
        if self.category == choices.SkillLabCourseTypeChoice.BOTH:
            return {9, 10, 11, 12}
        if self.category == choices.SkillLabCourseTypeChoice.after_college:
            return {12}
        return {9, 10, 11, 12}

    def get_grade_label(self):
        grades = sorted(self.get_grade_numbers())
        if len(grades) == 1:
            g = grades[0]
            if g % 100 // 10 == 1:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(g % 10, "th")
            return f"Class {g}{suffix}"
        if grades == [9, 10]:
            return "Class 9–10"
        if grades == [11, 12]:
            return "Class 11–12"
        if grades == [9, 10, 11, 12]:
            return "Class 9–12"
        return f"Class {grades[0]}–{grades[-1]}"

    def matches_skilllab_filters(self, grade=None, topic_key=None):
        if grade not in (None, ""):
            try:
                grade_num = int(grade)
            except (TypeError, ValueError):
                grade_num = None
            if grade_num is not None and grade_num not in self.get_grade_numbers():
                return False
        if topic_key and self.get_topic_category_key() != topic_key:
            return False
        return True

    def get_image_url(self):
        """Image URL with S3-proxy support and static fallback."""
        if self.image and self.image.name:
            from django.conf import settings

            backend = (settings.STORAGES.get("default") or {}).get("BACKEND", "")
            if "S3MediaStorage" in backend or getattr(settings, "S3_MEDIA_ACCESS_MODE", "") == "proxy":
                from core.storage_backends import S3MediaStorage

                return S3MediaStorage().url(self.image.name)
            return self.image.url
        return static("images/skilllab-default.png")

    def url(self):
        return reverse('skilllabcourse:skilllabcoursedetail',args=[self.slug])

    def delete(self, hard_delete=False):
        """Override delete: when hard_delete=True, remove course + all related data and files."""
        if hard_delete:
            self._delete_all_related_files_and_s3()
        super().delete(hard_delete=hard_delete)

    def _delete_all_related_files_and_s3(self):
        """Delete course image, activity PDFs, and S3 folder before DB cascade."""
        # 1. Delete course image from storage
        if self.image and self.image.name:
            try:
                self.image.delete(save=False)
            except Exception:
                pass

        # 2. Delete activity downloadable files (PDFs) from storage
        for chapter in self.skilllabcoursechapter.all():
            for activity in chapter.skilllabcourseactivity.all():
                if activity.downloadable_file and activity.downloadable_file.name:
                    try:
                        activity.downloadable_file.delete(save=False)
                    except Exception:
                        pass

        # 3. Delete S3 folder (PDFs uploaded by upload script: skilllab_courses/{slug}/)
        try:
            from core.s3_utils import get_s3_upload_service
            s3_service = get_s3_upload_service()
            if s3_service.is_enabled():
                s3_folder = f"skilllab_courses/{slugify(self.name)}"
                result = s3_service.delete_folder(s3_folder)
                # Ignore "empty or does not exist" - that's fine
        except Exception:
            pass

class SkillLabCourseChapter(SlugModel,BaseModel):
    skilllab=models.ForeignKey(SkillLabCourse,null=True,on_delete=models.CASCADE,related_name="skilllabcoursechapter")
    chapter_name=models.CharField(max_length=160)
    content = RichTextField(null=True, blank=True, help_text="Legacy: full chapter content. Used when no sections exist.")
    
    def get_slug_field(self):
        return 'chapter_name'


class SkillLabChapterSection(BaseModel):
    """Chapter content: Introduction, Section 1, Section 2, ..., Chapter Wrap-Up (optional), then Worksheet, MCQ."""
    SECTION_TYPE_CHOICES = [
        ('introduction', 'Introduction'),
        ('section', 'Section'),
        ('chapter_wrap_up', 'Chapter Wrap-Up'),
    ]
    chapter = models.ForeignKey(
        SkillLabCourseChapter, on_delete=models.CASCADE, related_name='sections'
    )
    section_type = models.CharField(
        max_length=20, choices=SECTION_TYPE_CHOICES, default='section',
        help_text="Introduction (first) or Section (1, 2, 3...)"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order: 0=Introduction, 1+=Section 1, 2, 3...")
    title = models.CharField(max_length=255, help_text="Section title (from heading or auto-generated)")
    content = RichTextField(blank=True, help_text="HTML content for this section")

    class Meta:
        verbose_name = 'Skill Lab Chapter Section'
        verbose_name_plural = 'Skill Lab Chapter Sections'
        ordering = ['chapter', 'order']
        unique_together = [('chapter', 'order')]

    def __str__(self):
        return f"{self.chapter.chapter_name} - {self.title}"

class SkillLabCourseActivity(SlugModel,BaseModel):
    skilllab_chapter=models.ForeignKey(SkillLabCourseChapter,null=True,on_delete=models.CASCADE,related_name="skilllabcourseactivity")
    name = models.CharField(max_length=160)
    type = models.SmallIntegerField(choices=choices.SkillLabAcivityChoice.CHOICE)
    content = RichTextField(null=True,blank=True) 
    downloadable_file=models.FileField(upload_to=skill_lab_image_directory,null=True,blank=True,max_length=250)
    
    
class SkillLabMCQ(BaseModel):
    """MCQ/Quiz for a Skill Lab chapter."""
    title = models.CharField(max_length=200, blank=True, null=True)
    description = RichTextField(blank=True, null=True)
    skilllab_chapter = models.ForeignKey(
        SkillLabCourseChapter, null=True, blank=True, on_delete=models.CASCADE, related_name='mcqs'
    )

    class Meta:
        verbose_name = 'Skill Lab MCQ'
        verbose_name_plural = 'Skill Lab MCQs'
        ordering = ['created']


class SkillLabMCQQuestion(BaseModel):
    """Question within an MCQ."""
    question_number = models.PositiveIntegerField(default=1)
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    mcq = models.ForeignKey(
        SkillLabMCQ, on_delete=models.CASCADE, related_name='questions'
    )

    class Meta:
        verbose_name = 'MCQ Question'
        verbose_name_plural = 'MCQ Questions'
        ordering = ['order', 'question_number']
        unique_together = [('mcq', 'question_number')]


class SkillLabMCQAnswer(BaseModel):
    """Answer option for an MCQ question."""
    answer_letter = models.CharField(max_length=1, help_text='Answer option letter (A, B, C, D, etc.)')
    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    question = models.ForeignKey(
        SkillLabMCQQuestion, on_delete=models.CASCADE, related_name='answers'
    )

    class Meta:
        verbose_name = 'MCQ Answer'
        verbose_name_plural = 'MCQ Answers'
        ordering = ['order', 'answer_letter']
        unique_together = [('question', 'answer_letter')]


class SkillLabWorksheetProgress(BaseModel):
    """Tracks worksheet/activity download by user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllabworksheetprogress')
    activity = models.ForeignKey(SkillLabCourseActivity, on_delete=models.CASCADE, related_name='skilllabworksheetprogress')
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Skill Lab Worksheet Progress'
        verbose_name_plural = 'Skill Lab Worksheet Progress'
        unique_together = [('user', 'activity')]

    def __str__(self):
        return f"{self.user} - {self.activity.name}"


class SkillLabMCQAttempt(BaseModel):
    """Tracks MCQ attempt - score and answers for re-attempt / result view."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllabmcqattempts')
    mcq = models.ForeignKey(SkillLabMCQ, on_delete=models.CASCADE, related_name='skilllabmcqattempts')
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    answers = models.JSONField(default=dict, blank=True)  # {question_id: answer_id}
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Skill Lab MCQ Attempt'
        verbose_name_plural = 'Skill Lab MCQ Attempts'
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.user} - {self.mcq.title or 'Quiz'} - {self.score}/{self.total}"


class SkillLabCourseProgress(BaseModel):
    """Tracks user progress through Skill Lab Courses (chapter completion)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllabcourseprogress')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='skilllabcourseprogress')
    chapter = models.ForeignKey(SkillLabCourseChapter, null=True, blank=True, on_delete=models.CASCADE, related_name='skilllabcourseprogress')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Skill Lab Course Progress'
        verbose_name_plural = 'Skill Lab Course Progress'
        unique_together = [('user', 'skilllab_course', 'chapter')]
        indexes = [
            models.Index(fields=['user', 'skilllab_course']),
        ]

    def __str__(self):
        ch = self.chapter.chapter_name if self.chapter else 'Course'
        return f"{self.user} - {self.skilllab_course.name} - {ch}: {'Completed' if self.completed else 'In Progress'}"


class SkillLabCourseProgressSummary(BaseModel):
    """Stores overall course progress per user per course. Updated when worksheet downloaded or MCQ submitted."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllabcourseprogresssummary')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='skilllabcourseprogresssummary')
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    completed_sections_count = models.PositiveIntegerField(default=0)
    total_sections_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Skill Lab Course Progress Summary'
        verbose_name_plural = 'Skill Lab Course Progress Summary'
        unique_together = [('user', 'skilllab_course')]
        indexes = [models.Index(fields=['user', 'skilllab_course'])]

    def __str__(self):
        return f"{self.user} - {self.skilllab_course.name} - {self.progress_percentage}%"


class SkillLabCourseResume(BaseModel):
    """Stores last viewed section per user/course for state restore across devices."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllabcourseresume')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='skilllabcourseresume')
    last_section_index = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Skill Lab Course Resume'
        verbose_name_plural = 'Skill Lab Course Resume'
        unique_together = [('user', 'skilllab_course')]
        indexes = [models.Index(fields=['user', 'skilllab_course'])]

    def __str__(self):
        return f"{self.user} - {self.skilllab_course.name} - section {self.last_section_index}"


class SkillLabUserHighlight(BaseModel):
    """User highlight on Skill Lab course content (section/section step)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllab_highlights')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='user_highlights')
    section_type = models.CharField(max_length=20)  # intro, worksheet, mcq
    section_id = models.PositiveIntegerField()    # section id or chapter id (intro step) or activity id or mcq id
    section_step = models.PositiveIntegerField(null=True, blank=True)  # for intro steps only
    highlighted_text = models.TextField()
    color = models.CharField(max_length=20, default='yellow')

    class Meta:
        verbose_name = 'Skill Lab User Highlight'
        verbose_name_plural = 'Skill Lab User Highlights'
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', 'skilllab_course', 'section_type', 'section_id']),
        ]


class SkillLabUserNote(BaseModel):
    """User note on Skill Lab course content."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllab_notes')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='user_notes')
    section_type = models.CharField(max_length=20)
    section_id = models.PositiveIntegerField()
    section_step = models.PositiveIntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, help_text="Note title or name")
    note_text = models.TextField()
    anchor_text = models.TextField(blank=True)  # optional selected text this note refers to

    class Meta:
        verbose_name = 'Skill Lab User Note'
        verbose_name_plural = 'Skill Lab User Notes'
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', 'skilllab_course', 'section_type', 'section_id']),
        ]


class SkillLabUserBookmark(BaseModel):
    """User bookmark of a section in a Skill Lab course."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skilllab_bookmarks')
    skilllab_course = models.ForeignKey(SkillLabCourse, on_delete=models.CASCADE, related_name='user_bookmarks')
    section_type = models.CharField(max_length=20)
    section_id = models.PositiveIntegerField()
    section_step = models.PositiveIntegerField(null=True, blank=True)
    section_title = models.CharField(max_length=255)
    section_key = models.CharField(max_length=80, blank=True)  # e.g. intro_5_0, worksheet_10, mcq_3

    class Meta:
        verbose_name = 'Skill Lab User Bookmark'
        verbose_name_plural = 'Skill Lab User Bookmarks'
        unique_together = [('user', 'skilllab_course', 'section_key')]
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', 'skilllab_course']),
        ]

    def save(self, *args, **kwargs):
        if not self.section_key:
            step = self.section_step if self.section_step is not None else ''
            self.section_key = '{}_{}_{}'.format(self.section_type, self.section_id, step)
        super().save(*args, **kwargs)


class InternationalOnlineCourse(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=500)
    image = models.ImageField(
        upload_to=international_course_image_directory,
        null=True,
        blank=True,
        max_length=250,
        help_text="Course card image. Leave empty to use the default placeholder.",
    )
    logo = models.ImageField(
        upload_to=international_course_logo_directory,
        null=True,
        blank=True,
        max_length=250,
        help_text="Institute logo shown on the course card. Leave empty to use the default placeholder.",
    )
    subject = models.CharField(max_length=120, db_index=True)
    institute = models.CharField(max_length=120, db_index=True)
    priority = models.PositiveIntegerField(default=0, help_text="Lower values appear first")

    class Meta:
        ordering = ["priority", "title"]
        verbose_name = "International Online Course"
        verbose_name_plural = "International Online Courses"
        indexes = [
            models.Index(fields=["subject", "institute"]),
        ]

    def __str__(self):
        return self.title

    def _media_url_with_cache_buster(self, url):
        if not url or not self.modified:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}v={int(self.modified.timestamp())}"

    def save(self, *args, **kwargs):
        old_image_name = ""
        old_logo_name = ""
        if self.pk:
            previous = (
                InternationalOnlineCourse.objects.filter(pk=self.pk)
                .values_list("image", "logo")
                .first()
            )
            if previous:
                old_image_name = previous[0] or ""
                old_logo_name = previous[1] or ""

        if not self.pk:
            pending_image = self.image
            pending_logo = self.logo
            image_is_new = bool(
                pending_image and hasattr(pending_image, "_committed") and not pending_image._committed
            )
            logo_is_new = bool(
                pending_logo and hasattr(pending_logo, "_committed") and not pending_logo._committed
            )
            if image_is_new:
                self.image = None
            if logo_is_new:
                self.logo = None
            super().save(*args, **kwargs)
            if image_is_new or logo_is_new:
                if image_is_new:
                    self.image = pending_image
                if logo_is_new:
                    self.logo = pending_logo
                super().save(update_fields=["image", "logo", "modified"])
            return

        super().save(*args, **kwargs)

        new_image_name = self.image.name if self.image else ""
        new_logo_name = self.logo.name if self.logo else ""
        if old_image_name and new_image_name != old_image_name:
            self._delete_stored_file(old_image_name)
        if old_logo_name and new_logo_name != old_logo_name:
            self._delete_stored_file(old_logo_name)

    def _delete_stored_file(self, name):
        if not name:
            return
        from django.core.files.storage import default_storage

        try:
            if default_storage.exists(name):
                default_storage.delete(name)
        except Exception:
            pass

    def get_image_url(self):
        if self.image and self.image.name:
            return self._media_url_with_cache_buster(self.image.url)
        return static(DEFAULT_INTL_COURSE_IMAGE)

    def get_logo_url(self):
        if self.logo and self.logo.name:
            return self._media_url_with_cache_buster(self.logo.url)
        return static(DEFAULT_INTL_COURSE_LOGO)

    def _delete_uploaded_files(self):
        for field in (self.image, self.logo):
            if field and field.name:
                try:
                    field.delete(save=False)
                except Exception:
                    pass

    def delete(self, hard_delete=False):
        if hard_delete:
            self._delete_uploaded_files()
        super().delete(hard_delete=hard_delete)


class SkilllabCoursePayment(BaseModel,BaseMoneyModel):
    skilllab_course = models.ForeignKey(SkillLabCourse,null=True,on_delete=models.SET_NULL,related_name="skilllabcourpayment")
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="userskillabcourse")
    gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
    is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)
    
    def get_payment_success_fail_url(self):
        d={}
        sign = Signer()
        enc_id=sign.sign_object(({"enc_id":self.id}))
        d["success_url"]=reverse('skilllabcourse:skillabcoursepaymentsuccess',kwargs={'enc_id':enc_id})
        d["fail_url"]=reverse('skilllabcourse:skilllabcoursepaymentfail',kwargs={'enc_id':enc_id})
        return d
    
    def send_payment_mail(self):
        cs=ComService()
        cs.send_skillabcourse_payment_success_mail(self.user.email,self)