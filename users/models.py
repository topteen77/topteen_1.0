import datetime
import random
from datetime import datetime, timedelta, timezone

import requests
from core.models import BaseModel
from core.utils import get_current_user
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import (AbstractBaseUser, AbstractUser,
                                        BaseUserManager, Group, Permission,
                                        UserManager)
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from core.models import BaseModel,Hobbies,Subject,UserFigureOut
from ckeditor.fields import RichTextField
from dateutil import relativedelta
from django.core.signing import Signer
from core.models import SoftDeletionQuerySet
from core import choices
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
class PermissionsMixin(models.Model):
    """
    A mixin class that adds the fields and methods necessary to support
    Django's Group and Permission model using the ModelBackend.
    """
    is_superuser = models.BooleanField(
        _('superuser status'),
        default=False,
        help_text=_(
            'Designates that this user has all permissions without'
            'explicitly assigning them.'
        ),
    )
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="user_groups_set",
        related_query_name="goognu_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="user_permissions_set",
        related_query_name="goognu_user",
    )

    class Meta:
        abstract = True

    def get_group_permissions(self, obj=None):
        """
        Returns a list of permission strings that this user has through their
        groups. This method queries all available auth backends. If an object
        is passed in, only permissions matching this object are returned.
        """
        permissions = set()
        for backend in auth.get_backends():
            if hasattr(backend, "get_group_permissions"):
                permissions.update(backend.get_group_permissions(self, obj))
        return permissions

    def get_all_permissions(self, obj=None):
        return _user_get_all_permissions(self, obj)

    def has_perm(self, perm, obj=None):
        """
        Returns True if the user has the specified permission. This method
        queries all available auth backends, but returns immediately if any
        backend returns True. Thus, a user who has permission from a single
        auth backend is assumed to have permission in general. If an object is
        provided, permissions for this specific object are checked.
        """

        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        # Otherwise we need to check the backends.
        return _user_has_perm(self, perm, obj)

    def has_perms(self, perm_list, obj=None):
        """
        Returns True if the user has each of the specified permissions. If
        object is passed, it checks if the user has all required perms for this
        object.
        """
        for perm in perm_list:
            if not self.has_perm(perm, obj):
                return False
        return True

    def has_module_perms(self, app_label):
        """
        Returns True if the user has any permissions in the given app label.
        Uses pretty much the same logic as has_perm, above.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        return _user_has_module_perms(self, app_label)


def _user_get_all_permissions(user, obj):
    permissions = set()
    for backend in auth.get_backends():
        if hasattr(backend, "get_all_permissions"):
            permissions.update(backend.get_all_permissions(user, obj))
    return permissions


def _user_has_perm(user, perm, obj):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, 'has_perm'):
            continue
        try:
            if backend.has_perm(user, perm, obj):
                return True
        except PermissionDenied:
            return False
    return False


def _user_has_module_perms(user, app_label):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, 'has_module_perms'):
            continue
        try:
            if backend.has_module_perms(user, app_label):
                return True
        except PermissionDenied:
            return False
    return False

def filter_user_queryset_by_hierarchy(user, queryset,filter_on='assign_to_user__in'):

    if user.is_superuser:
        return queryset
    else:
        all_childrens = user.get_all_child
        return queryset.filter(**{filter_on:all_childrens})


class UserManager(BaseUserManager):
    def create_user(self, email, name=None, password=None):
        
        user = self.model(name=name, email=self.normalize_email(email))

        user.set_password(password)
        user.save(using=self._db)

        # #assing defult grade value.
        # for i in range(1,6):
        #     from colleges.models import UserGrade
        #     x = UserGrade(user=user,grade=i)
        #     x.save()
        return user

    def create_superuser(self, email, name, password):
        user = self.create_user(
            email=email, password=password, name=name)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user
    
    def get_queryset(self):
        return SoftDeletionQuerySet(self.model).filter(
            object_status=choices.ObjectStatus.ACTIVE
        )
    def complete(self):
        return super().get_queryset()


def user_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/users/{0}/{1}'.format(instance.id, filename)

class User(BaseModel,AbstractBaseUser, PermissionsMixin):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    
    name = models.CharField('Full Name',max_length=255,null=True,blank=True)
    email = models.EmailField(max_length=255,unique=True,null=True)
    mobile = models.CharField(max_length=25,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    image=models.ImageField(upload_to=user_image_directory,null=True,blank=True,max_length=250)
    is_completed=models.BooleanField(default=False)
    referral=models.CharField(max_length=255,null=True,blank=True)
    user_type = models.SmallIntegerField(choices=choices.UserType.CHOICES, default=choices.UserType.STUDENT)
    user_status=models.SmallIntegerField(choices=choices.UserStatus.CHOICES,default=choices.UserStatus.UNBLOCK)
    is_demo_account = models.BooleanField(
        default=False,
        help_text=_('If checked, this account is shown on the login page as a demo account (name and role only; credentials are not displayed).'),
    )
    is_system_demo = models.BooleanField(
        default=False,
        editable=False,
        help_text=_('Set only by the system when creating demo dataset. Only such data can be reset. Do not edit.'),
    )
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    @property
    def username(self):
        return self.email.replace('@','')

    def __str__(self):
        return "{}".format(self.name)
        
    @classmethod
    def create_user(cls,**kwargs):
        # password = kwargs.pop('password')
        password = '12345'

        # static password by manish"
        
        user = User.objects.create(**kwargs)
        user.set_password(password)
        user.save()
        return user

    def has_module_perms(self, app_label):
        return True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        super().save(*args, **kwargs)
        # Password / last_login-only saves must not run name fix or _grab_avatar (HTTP to ui-avatars.com,
        # up to ~5s) — otherwise admin "set password" and every login feel slow for users without an image.
        if update_fields is not None:
            uf = set(update_fields)
            identity_or_image = {"name", "email", "mobile", "image"}
            if not (uf & identity_or_image):
                return
        name_val = (self.name or "").strip()
        if not name_val or name_val == "Student":
            # str() so mobile (int) from signup doesn't break .strip()
            self.name = str(self.email or self.mobile or "").strip()
            if self.name:
                self.save(update_fields=["name"])
        if not self.image:
            try:
                self._grab_avatar()
            except Exception:
                # Don't fail user save if avatar fetch fails (network/timeout)
                pass

    def _grab_avatar(self):
        colors_lst=['00AA55','1BA39C','03A678','00AA00','26A65B','00A566','4183D7','3477DB','007FAA',\
            '3455DB','0000E0','0000B5','E26A6A','B381B3','E26A6A','BF6EE0','FF00FF','BF55EC','D252B2',\
            '9370DB','D25299','D25852','D2527F','E73C70','F62459','E000E0','AA8F00','AA8F00','D47500',\
            'FF4500','E63022','E76E3C','EF4836','FF0000','DC143C']
        url="https://ui-avatars.com/api/?name={}&background={}&color=FFF&font-size=0.55&bold=True&size=256".format(self.name or "User", random.choice(colors_lst))
        # image_content = ContentFile(requests.get(url).content)
        r = requests.get(url,timeout=5)

        img_temp = NamedTemporaryFile(delete=True)
        img_temp.write(r.content)
        img_temp.flush()

        self.image.save("user_{}.jpg".format(self.id), File(img_temp), save=True)

    def get_referral_url(self):
        sign = Signer()
        enc_id=sign.sign_object(({"refer_enc_id":self.id}))
        path=reverse('users:referallogin',args=[enc_id])
        url="{}{}".format("https://topteen.in",path)
        return url
    
    def get_user_status(self):
        return self.user_status==choices.UserStatus.UNBLOCK
    
    def get_user_type(self):
        return self.user_type==choices.UserType.STUDENT
    
    def get_institute_status(self):
        return self.user_type==choices.InstituteStatus.APPROVED

    def get_student_display_id(self):
        """Unique display ID for students (e.g. STU000123). Prefix from Configuration STUDENT_ID_PREFIX."""
        if self.user_type != choices.UserType.STUDENT:
            return None
        from core.models import Configuration
        prefix = (Configuration.get('STUDENT_ID_PREFIX', 'STU', editable=True) or 'STU').strip() or 'STU'
        return "{}{}".format(prefix, str(self.id).zfill(6))

    def get_display_student_id(self):
        """For school students: school ID (e.g. SCH/TT001919). Otherwise: direct student ID from get_student_display_id()."""
        # #region agent log
        import json
        import time as _time
        _log_path = "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/.cursor/debug.log"
        # #endregion
        if self.user_type != choices.UserType.STUDENT:
            out = None
            is_school = False
        else:
            from institute.models import StudentManagement
            sm = StudentManagement.objects.filter(student=self).first()
            is_school = sm is not None
            if is_school:
                out = sm.get_school_student_id()
            else:
                out = self.get_student_display_id()
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(json.dumps({"hypothesisId": "H1", "location": "users/models.py:get_display_student_id", "message": "display_student_id", "data": {"user_id": self.id, "is_school_student": is_school, "display_id": out}, "timestamp": round(_time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
        return out

    def get_profile_completion_percentage(self):
        """
        Return 0–100 based on how much of the user profile is filled.
        Used for the "Complete your profile" progress bar in the sidebar.
        """
        score = 0
        # User fields (40% total)
        if (self.name or '').strip() and (self.name or '').strip() != 'Student':
            score += 10
        if (self.email or '').strip():
            score += 10
        if (self.mobile or '').strip():
            score += 10
        if self.image:
            score += 10
        # UserProfile fields (60% total)
        try:
            profile = getattr(self, 'user_profile', None)
            if profile is None:
                return min(score, 100)
            if (getattr(profile, 'schoolname', None) or '').strip():
                score += 15
            if (getattr(profile, 'grade', None) or '').strip():
                score += 15
            if getattr(profile, 'birthdate', None):
                score += 10
            if profile.hobbies.exists():
                score += 10
            if profile.subject.exists():
                score += 5
            if profile.figure_out.exists():
                score += 5
        except Exception:
            pass
        return min(score, 100)

class UserSearchHistory(BaseModel):
    user=models.ForeignKey(User,blank=True,null=True,on_delete=models.SET_NULL)
    search=models.CharField(max_length=255,null=True,blank=True)

class UserProfile(BaseModel):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name="user_profile")
    birthdate=models.DateField(null=True,blank=True)
    gender=models.PositiveSmallIntegerField(choices=choices.GenderChoices.CHOICES,default=choices.GenderChoices.MALE)
    schoolname=models.CharField(max_length=250,null=True,blank=True)
    grade=models.CharField(max_length=100,null=True,blank=True)
    hobbies=models.ManyToManyField(Hobbies,related_name='hobbies',blank=True)
    subject=models.ManyToManyField(Subject,related_name='subject',blank=True)
    figure_out=models.ManyToManyField(UserFigureOut,related_name='figureout',blank=True)


class ParentStudentLink(BaseModel):
    """
    Link a parent user account to one or more student accounts.
    A parent can have multiple linked students; a student can have multiple parents.
    """
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_links",
        limit_choices_to={'user_type': choices.UserType.PARENT},
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_parent_links",
        limit_choices_to={'user_type': choices.UserType.STUDENT},
    )

    class Meta:
        unique_together = ('parent', 'student')
        verbose_name = "Parent Student Link"
        verbose_name_plural = "Parent Student Links"

    def __str__(self):
        return f"{self.parent_id} -> {self.student_id}"


class ParentStudentBookmark(BaseModel):
    """
    Parent-suggested bookmark scoped to a specific linked student.
    Example: parent bookmarks a Career *for* Student A; that should not automatically
    appear for Student B.
    """
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_student_bookmarks",
        limit_choices_to={'user_type': choices.UserType.PARENT},
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_parent_bookmarks",
        limit_choices_to={'user_type': choices.UserType.STUDENT},
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta(BaseModel.Meta):
        unique_together = ("parent", "student", "content_type", "object_id")
        verbose_name = "Parent Student Bookmark"
        verbose_name_plural = "Parent Student Bookmarks"

def user_note_icon_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/usernotes/{0}/{1}'.format(instance.id, filename)

class UserNote(BaseModel):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="user_notes")
    title=models.CharField(max_length=250,null=True,blank=True)
    content=RichTextField(null=True,blank=True)


class ResumeStudioHtmlTemplate(BaseModel):
    """
    Admin-managed gallery rows for the student HTML resume studio (static/js prototype).
    Each template_key must match a renderer in static/resume-builder-prototype/app.js.
    """

    name = models.CharField(max_length=120)
    template_key = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Layout id implemented in the studio prototype, e.g. classic-sidebar, minimalist.",
    )
    category = models.CharField(
        max_length=32,
        default="professional",
        db_index=True,
        help_text="Gallery filter: professional, modern, creative, simple",
    )
    mock_class = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text="Thumbnail mock CSS class, e.g. mock-classic-sidebar. Auto-filled as mock-<key> when empty.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        ordering = ("sort_order", "id")
        verbose_name = "Resume studio HTML template"
        verbose_name_plural = "Resume studio HTML templates"

    def __str__(self):
        return self.name or self.template_key or "Studio template"

    def clean(self):
        from django.core.exceptions import ValidationError

        from users.resume_studio_html import ALLOWED_STUDIO_HTML_TEMPLATE_KEYS

        k = (self.template_key or "").strip()
        if k and k not in ALLOWED_STUDIO_HTML_TEMPLATE_KEYS:
            raise ValidationError(
                {
                    "template_key": (
                        "This layout is not implemented in the studio prototype. "
                        "Choose a key from the documented list (same as app.js RENDERERS)."
                    )
                }
            )

    def save(self, *args, **kwargs):
        tid = (self.template_key or "").strip()
        if tid and not (self.mock_class or "").strip():
            self.mock_class = f"mock-{tid}"
        super().save(*args, **kwargs)


class UserResume(BaseModel):
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_resumes",
    )
    title = models.CharField(max_length=120, default="My resume", blank=True)
    about = models.TextField(null=True, blank=True)
    # AI-guided studio: full HTML from OpenAI + last wizard payload for restore / audit
    generated_html = models.TextField(null=True, blank=True)
    wizard_draft_json = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ("-modified",)

    def __str__(self):
        return self.title or "Resume"

    def delete(self, hard_delete=False):
        """Hard-delete related sections first so CASCADE does not soft-delete child rows only."""
        if hard_delete and self.pk is not None:
            rid = self.pk
            # `.complete()` returns a plain QuerySet (no `hard_delete`); use SoftDeletionQuerySet directly.
            for model in (
                UserResumeSkill,
                UserResumeCertificate,
                UserResumeInternship,
                UserResumeActivity,
                UserResumeVolunteerInvolvement,
            ):
                SoftDeletionQuerySet(model).filter(resume_id=rid).hard_delete()
        super().delete(hard_delete=hard_delete)


class UserResumeChild(BaseModel):
    resume = models.ForeignKey(UserResume,null=True,blank=True,on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.resume.save()


class UserResumeSkill(UserResumeChild):
    title = models.CharField(max_length=250,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    profficiency = models.PositiveSmallIntegerField(choices=choices.UserResumeProficiency.CHOICES,default=choices.UserResumeProficiency.BEGINNER)

class UserResumeCertificate(UserResumeChild):
    title = models.CharField(max_length=250,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    issue_date=models.DateField(null=True,blank=True)

class UserResumeInternship(UserResumeChild):
    provider= models.CharField(max_length=250,null=True,blank=True)
    role = models.CharField(max_length=250,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    start_date=models.DateField(null=True,blank=True)    
    end_date=models.DateField(null=True,blank=True)    

class UserResumeActivity(UserResumeChild):
    title = models.CharField(max_length=250,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    issue_date=models.DateField(null=True,blank=True)    
  
class UserResumeVolunteerInvolvement(UserResumeChild):
    title = models.CharField(max_length=250,null=True,blank=True)
    role= models.CharField(max_length=250,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    start_date=models.DateField(null=True,blank=True)    
    end_date=models.DateField(null=True,blank=True)  

    def get_time_priode(self):
        delta = relativedelta.relativedelta(self.end_date, self.start_date)
        return delta
    
class UserFolder(BaseModel):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="user_folders")
    title=models.CharField(max_length=250)

def user_folder_upload_file_directory(instance, filename):
    return 'upload/userfolder/{0}/{1}'.format(instance.id, filename)    

class FolderFile(BaseModel):
    folder=models.ForeignKey(UserFolder,on_delete=models.CASCADE,related_name="folder_files")
    title=models.CharField(max_length=250)
    file = models.FileField(upload_to=user_folder_upload_file_directory)

class UserCalender(BaseModel):
    user=models.ForeignKey(User,blank=True,null=True,on_delete=models.CASCADE,related_name="user_calender")
    event_name=models.CharField(max_length=50)
    start_date=models.DateField()
    end_date=models.DateField()