from django.db import models
from institute.models import Institute, StudentManagement
from psychometric_tests.models import PsychometricTestPayment
from psychometric_tests.task import create_central_test_candidate

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.timezone import localtime

from users.models import User
from core import choices
from core.models import BaseModel, BaseMoneyModel, Configuration,SlugModel

class CounselorCourse(models.Model):
    title = models.CharField(max_length=200, blank=True, null=True)
    currency = models.PositiveSmallIntegerField(
        choices=choices.Currency.CHOICES,
        default=choices.Currency.IND,
        verbose_name='Currency',
        help_text='Default is INR (same as other payments in this app).',
    )
    actual_price = models.PositiveIntegerField(
        default=19999,
        verbose_name='MRP',
        help_text='Maximum retail price (list price) in the selected currency.',
    )
    discount_percent = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Discount (%)',
        help_text='Price is calculated from MRP. Use 0 for no discount (price equals MRP).',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    amount = models.PositiveIntegerField(
        default=19999,
        verbose_name='Price',
        help_text='Always calculated from MRP and discount %. Charged at checkout unless dynamic price is set.',
    )
    dynamic_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Dynamic price',
        help_text='Optional. If set, this amount is charged at checkout instead of the calculated price.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.title or ''

    def get_charge_amount_rupees(self):
        """Major currency units (INR, USD, …) stored on Payment and sent to the gateway."""
        if self.dynamic_price is not None:
            return int(self.dynamic_price)
        return int(self.amount)

    def apply_discount_from_percent(self):
        """Set ``amount`` from MRP and ``discount_percent`` (0 = pay full MRP)."""
        if self.actual_price is None:
            return
        p = int(self.discount_percent)
        mrp = int(self.actual_price)
        self.amount = max(0, int(round(mrp * (100 - p) / 100.0)))

    def has_active_discount(self):
        """True when a promotional discount % is applied (shows discount UI on site)."""
        return int(self.discount_percent) > 0

    def get_currency_code(self):
        """ISO code for payment gateways (matches project default mapping)."""
        return 'USD' if int(self.currency) == choices.Currency.USD else 'INR'

    def get_currency_symbol(self):
        return '$' if int(self.currency) == choices.Currency.USD else '₹'

    def clean(self):
        self.apply_discount_from_percent()
        super().clean()
        mrp = self.actual_price
        if mrp is None:
            return
        mrp = int(mrp)
        if self.amount is not None:
            amt = int(self.amount)
            if amt > mrp:
                raise ValidationError({'amount': 'Price cannot be greater than MRP.'})
            if amt >= mrp and int(self.discount_percent) != 0:
                raise ValidationError(
                    {'amount': 'Price must be less than MRP unless discount is 0% (full MRP).'}
                )
        if self.dynamic_price is not None:
            d = int(self.dynamic_price)
            if d > mrp:
                raise ValidationError({'dynamic_price': 'Dynamic price cannot be greater than MRP.'})
            if d >= mrp and int(self.discount_percent) != 0:
                raise ValidationError(
                    {'dynamic_price': 'Dynamic price must be less than MRP unless discount is 0%.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Chapter(models.Model):
    course = models.ForeignKey(CounselorCourse, on_delete=models.CASCADE, related_name="chapters",blank=True, null=True)
    title = models.CharField(max_length=100)    

    class Meta:
        verbose_name_plural = "Course Chapters"

    def __str__(self):
        return self.title

class Part(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="parts",blank=True, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)  # URL for the video
    video_vtt = models.URLField(blank=True, null=True)  # URL for the video
    pdf_url = models.URLField(blank=True, null=True)  # URL for the PDF

    class Meta:
        verbose_name_plural = "Course Parts"

    def __str__(self):
        return self.title

class Notes(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    video_timestamp = models.CharField(max_length=8, null=True, blank=True)  # New field to store HH:MM:SS format
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note by {self.user.username if self.user else 'Anonymous'} on {self.part.title}"

class Quiz(models.Model):
    title = models.CharField(max_length=200, blank=True, null=True)
    quiz_part = models.ForeignKey(Part, related_name='quizzes', on_delete=models.CASCADE,blank=True, null=True)

    class Meta:
        verbose_name_plural = "Course Quizzes"

    def __str__(self):
        return f"Quiz: {self.title} (Part: {self.quiz_part.title})"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE,blank=True, null=True)
    question_text = models.TextField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Quiz Questions"

    def __str__(self):
        return f"Question: {self.question_text[:50]} (Quiz: {self.quiz.title})"

class QuizAnswers(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE,blank=True, null=True)
    answer_text = models.CharField(max_length=200, blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Quiz Answers"

    def __str__(self):
        return f"Answer {self.id} for Question {self.question.id}"

class QuizResults(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True
    )
    scores = models.JSONField(default=dict)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        user_info = self.user.username if self.user else "Anonymous User"
        modified_time = localtime(self.modified).strftime("%Y-%m-%d %H:%M:%S")
        return f"Scores for {user_info} | Last Modified: {modified_time}"

class VideoProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    video_id = models.CharField(max_length=255, db_index=True)
    progress = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    duration = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'video_id'])]
        verbose_name_plural = "Video progress"

    def __str__(self):
        return f"{self.video_id}: {self.progress}%"


class CounselorCertification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    certificate_code = models.CharField(max_length=8, null=True, blank=True)
    grade = models.CharField(max_length=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set the field to now when the object is created

    def __str__(self):
        return f"{self.user} - {self.certificate_code}"

# class Notes(models.Model):
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
#     )
#     part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='notes')
#     content = models.TextField()
#     video_timestamp = models.CharField(max_length=8, null=True, blank=True)  # New field to store HH:MM:SS format
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"Note by {self.user.username if self.user else 'Anonymous'} on {self.part.title}"

# class UserQuizAttempt(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE,blank=True, null=True)
#     quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE,blank=True, null=True)
    

#     class Meta:
#         verbose_name_plural = "User Quiz Attempt"

#     def __str__(self):
#         return f"{self.user.username} - {self.quiz.title}"


# Create your models here.
class Counselor(BaseModel):
    counselor_name=models.CharField(max_length=250)    
    coun_user =models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="counselor",limit_choices_to={'user_type':choices.UserType.COUNSELOR})
    counselor_email = models.EmailField(max_length=255,unique=True,null=True)
    counselor_address=models.CharField(max_length=350,null=True,blank=True)
    counselor_contact_info=models.CharField(max_length=250,null=True,blank=True)
    counselor_education=models.CharField(max_length=250,null=True,blank=True)
    counselor_gender=models.PositiveSmallIntegerField(choices=choices.GenderChoices.CHOICES,default=choices.GenderChoices.MALE)
    counselor_admin = models.ForeignKey(Institute,on_delete=models.SET_NULL,null=True,blank=True,related_name="coun_institute")

    # Many-to-Many relationship with StudentManagement
    students = models.ManyToManyField('institute.StudentManagement', related_name='counselors', blank=True)
    
    def __str__(self):
        return self.counselor_name

    def get_students(self, institute):
        """Return students assigned to this counselor within the specified institute."""
        return self.students.filter(institute=institute)

class FollowUpStatus(BaseModel):

    MODE_CHOICES = [
        ('email', 'Email'),
        ('call', 'Call'),
        ('meeting', 'Meeting'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('follow-up', 'Follow-up'),
    ]

    counselor = models.ForeignKey('Counselor', on_delete=models.CASCADE, related_name='follow_ups')
    student = models.ForeignKey('institute.StudentManagement', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_up_statuses')
    mode_of_follow_up = models.CharField(max_length=20, choices=MODE_CHOICES,default='Call')
    follow_up_status = models.CharField(max_length=20, choices=STATUS_CHOICES,default='pending')
    next_follow_up_date = models.DateField(null=True, blank=True)
    last_follow_up_date = models.DateField(null=True, blank=True)
    is_followed_up = models.BooleanField(default=False)
    message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Follow Up for {self.student} - Mode: {self.mode_of_follow_up}"
    

# class PsychometricTestPayment(BaseModel,BaseMoneyModel):
#     user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="counselorcourses")
#     gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
#     test_type = models.SmallIntegerField(choices=choices.PsychometricTestType.CHOICES)
#     is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)

# class CounselorCourses(BaseModel,BaseMoneyModel):
#     course = models.ForeignKey(User,on_delete=models.CASCADE,related_name="counselorcourses")
#     gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
#     test_type = models.SmallIntegerField(choices=choices.PsychometricTestType.CHOICES)
#     is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)