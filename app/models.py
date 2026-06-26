# quiz/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from . import choices
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from users.models import User

class Question(models.Model):
    question_text = models.CharField(max_length=300, blank=True, null=True)
    question_image = models.ImageField(upload_to='question_images/', blank=True, null=True)
    category = models.CharField(max_length=100)
    test_paper = models.CharField(max_length=100,default='')

    def __str__(self):
        return self.question_text or 'Question'

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.CharField(max_length=200, blank=True, null=True)
    answer_image = models.ImageField(upload_to='answer_images/', blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Answer {self.id} for Question {self.question.id}"
    
class TestCompletion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test1_complete = models.BooleanField(default=False)  # Default to False
    test2_complete = models.BooleanField(default=False)
    test3_complete = models.BooleanField(default=False)
    numerical_complete = models.BooleanField(default=False)
    verbal_complete = models.BooleanField(default=False)
    logical_complete = models.BooleanField(default=False)
    emotional_complete = models.BooleanField(default=False)
    machanical_complete = models.BooleanField(default=False)
    language_complete = models.BooleanField(default=False)
    spatial_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"Test Completion for {self.user}"

    def are_all_primary_tests_completed(self):
        return self.test1_complete and self.test2_complete and self.test3_complete
    
class Results(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test_paper = models.CharField(max_length=100, db_index=True)
    scores = models.JSONField(default=dict)
    results = models.JSONField(default=dict)
    selected_answers = models.JSONField(default=dict)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['user', '-modified'])]

    def __str__(self):
        return f"Scores for {self.test_paper} -| {self.user} -| {self.modified.astimezone().strftime('%Y-%m-%d - %H:%M %Z')}"

    # Property to check if the user has completed all the required tests
    @property
    def is_test_successful(self):   
        test_completion = TestCompletion.objects.filter(user=self.user).first()        
        if test_completion:            
            return test_completion.are_all_primary_tests_completed()
        return False
        
        
    # Custom method to get the test report link or a placeholder
    def get_test_report_or_test_link(self, user):
        """
        Generates a link to the final assessment report if all required tests
        are successfully completed; otherwise, redirects to the test buttons page.
        """

        # Check if is_success is a method or a property
        if hasattr(self, 'is_test_successful') and callable(self.is_test_successful):
            is_test_successful = self.is_test_successful()  # Call it if it's a method
        else:
            is_test_successful = self.is_test_successful  # Use it directly if it's a property

        # Determine the link based on test success status
        if is_test_successful:  # No parentheses since this is now a boolean
            # Generate the URL for the final assessment report view
            report_url = reverse('app:Assessment_pdf_inst_user', args=[user.id])
            return report_url  # Link to the final assessment report
        else:
            # Link to test buttons page if tests are not completed
            return '#'


# inserting the RIASEC.json

class Category(models.Model):
    CAREER_PATHWAYS_COMBINED = 'combined'
    CAREER_PATHWAYS_INDIVIDUAL = 'individual'
    CAREER_PATHWAYS_MODE_CHOICES = [
        (CAREER_PATHWAYS_COMBINED, 'Combined (Career Pathways)'),
        (CAREER_PATHWAYS_INDIVIDUAL, 'Individual (per stream)'),
    ]

    category = models.CharField(max_length=3, unique=True)  # e.g., 'RIA'
    fullname = models.CharField(max_length=255)  # e.g., 'RIA (Realistic, Investigative, Artistic)'
    summary = models.TextField()
    fields = models.TextField()
    best_colleges = models.TextField(blank=True, null=True)  # Colleges may be empty
    career_pathways_mode = models.CharField(
        max_length=16,
        choices=CAREER_PATHWAYS_MODE_CHOICES,
        default=CAREER_PATHWAYS_INDIVIDUAL,
        help_text='Combined shows one "Career Pathways" block; individual shows per-stream titles.',
    )

    def __str__(self):
        return self.fullname
    
class Course(models.Model):
    category = models.ForeignKey(Category, related_name='courses', on_delete=models.CASCADE)
    course_name = models.CharField(max_length=255)

    def __str__(self):
        return self.course_name


class Stream(models.Model):
    category = models.ForeignKey(Category, related_name='streams', on_delete=models.CASCADE)
    stream_name = models.CharField(max_length=50)  # e.g., 'PCM', 'Fine Arts / Design'
    subjects = models.TextField()  # e.g., 'Physics Chemistry Mathematics'
    career_options = models.JSONField(default=list, blank=True)  # e.g., ['Mechanical Engineer', ...]

    def __str__(self):
        return f"{self.stream_name}: {self.subjects}"


class Class10ReportGuidanceSettings(models.Model):
    """Section titles for Class 10 combined report appendix (singleton)."""

    stream_wise_title = models.CharField(
        max_length=255,
        default='Stream-Wise Premium Career Options',
    )
    future_relevant_title = models.CharField(
        max_length=255,
        default='Most Future-Relevant Careers Across All Streams',
    )

    class Meta:
        verbose_name = 'Class 10 report guidance settings'
        verbose_name_plural = 'Class 10 report guidance settings'

    def __str__(self):
        return 'Class 10 combined report career guidance'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Class10PremiumStream(models.Model):
    """Premium career catalogue per subject stream (combined report only)."""

    STREAM_CODE_CHOICES = [
        ('PCM', 'PCM'),
        ('PCB', 'PCB'),
        ('CWM', 'CWM (Commerce with Maths)'),
        ('CWOM', 'CWOM (Commerce without Maths)'),
        ('HUM', 'HUM (Humanities)'),
        ('FINEARTS', 'Fine Arts / Design'),
    ]

    stream_code = models.CharField(max_length=20, choices=STREAM_CODE_CHOICES, unique=True)
    display_label = models.CharField(
        max_length=255,
        help_text='Shown in the combined report, e.g. PCM (Physics, Chemistry, Mathematics)',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('sort_order', 'stream_code')
        verbose_name = 'Premium stream (Class 10 report)'
        verbose_name_plural = 'Premium streams (Class 10 report)'

    def __str__(self):
        return self.display_label or self.stream_code


class Class10PremiumStreamCareer(models.Model):
    stream = models.ForeignKey(
        Class10PremiumStream,
        on_delete=models.CASCADE,
        related_name='careers',
    )
    career = models.ForeignKey(
        'careers.Career',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='class10_premium_stream_slots',
        verbose_name='Career name',
        help_text='Search and select a published career from the site catalog.',
    )
    career_name = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        help_text='Auto-filled from the selected career (report cache).',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('sort_order', 'career__name')
        verbose_name = 'Premium stream career'
        verbose_name_plural = 'Premium stream careers'
        constraints = [
            models.UniqueConstraint(
                fields=['stream', 'career'],
                condition=models.Q(career__isnull=False),
                name='unique_class10_premium_stream_career',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.career_id:
            self.career_name = self.career.name or ''
        super().save(*args, **kwargs)

    def __str__(self):
        return self.career.name if self.career_id else self.career_name


class Class10FutureRelevantCareer(models.Model):
    """Cross-stream future careers section (combined report only)."""

    career = models.ForeignKey(
        'careers.Career',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='class10_future_relevant_slots',
        verbose_name='Career name',
        help_text='Search and select a published career from the site catalog.',
    )
    career_name = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        help_text='Auto-filled from the selected career (report cache).',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('sort_order', 'career__name')
        verbose_name = 'Future-relevant career (Class 10 report)'
        verbose_name_plural = 'Future-relevant careers (Class 10 report)'
        constraints = [
            models.UniqueConstraint(
                fields=['career'],
                condition=models.Q(career__isnull=False),
                name='unique_class10_future_relevant_career',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.career_id:
            self.career_name = self.career.name or ''
        super().save(*args, **kwargs)

    def __str__(self):
        return self.career.name if self.career_id else self.career_name


class AptitudeImprovementPlan(models.Model):
    """Admin-managed growth-area improvement plans for Class 10 / Class 12 aptitude reports."""

    CLASS_10 = 'class_10'
    CLASS_12 = 'class_12'
    EDUCATION_LEVEL_CHOICES = (
        (CLASS_10, 'Class 10'),
        (CLASS_12, 'Class 12'),
    )

    education_level = models.CharField(max_length=16, choices=EDUCATION_LEVEL_CHOICES)
    area_key = models.CharField(
        max_length=64,
        help_text='Stable key used to match student below-average areas (e.g. verbal, language_verbal_reasoning).',
    )
    growth_area_title = models.CharField(
        max_length=255,
        help_text='Display title shown in reports, e.g. Language & Verbal Reasoning.',
    )
    development_goal = models.TextField(blank=True)
    improvement_plan_items = models.JSONField(
        default=list,
        blank=True,
        help_text='List of suggested improvement plan bullet strings.',
    )
    practice_frequency = models.CharField(max_length=255, blank=True)
    expected_timeline = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('education_level', 'sort_order', 'growth_area_title')
        verbose_name = 'Aptitude improvement plan'
        verbose_name_plural = 'Aptitude improvement plans'
        constraints = [
            models.UniqueConstraint(
                fields=['education_level', 'area_key'],
                name='unique_aptitude_improvement_plan_level_area',
            ),
        ]

    def __str__(self):
        return f'{self.get_education_level_display()} — {self.growth_area_title}'


CLASS12_APTITUDE_REASONING_CODE_CHOICES = (
    ('AR', 'Abstract Reasoning'),
    ('NR', 'Numerical Reasoning'),
    ('LR', 'Logical Reasoning'),
    ('LVR', 'Language & Verbal Reasoning'),
    ('CR', 'Clerical Speed & Accuracy'),
    ('MR', 'Mechanical Reasoning'),
    ('SR', 'Spatial Reasoning'),
)


class Class12AptitudeConsolidatedReport(models.Model):
    """Consolidated Class 11–12 aptitude interpretation row (one per reasoning combination)."""

    reasoning_combination = models.CharField(
        max_length=64,
        unique=True,
        help_text='Normalized key, e.g. AR + CR + LR',
    )
    codes = models.JSONField(default=list, blank=True)
    aptitude_description = models.TextField(blank=True)
    interpretation_narrative = models.TextField(blank=True)
    career_clusters = models.JSONField(default=list, blank=True)
    career_pathways = models.JSONField(default=list, blank=True)
    degree_pathways = models.JSONField(default=list, blank=True)
    real_life_signs = models.JSONField(
        default=list,
        blank=True,
        help_text='Real-life sign bullets for this combination (one item per list entry).',
    )
    daily_life_impact = models.JSONField(
        default=list,
        blank=True,
        help_text='Daily life impact bullets for this combination (one item per list entry).',
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('reasoning_combination',)
        verbose_name = 'Class 12 aptitude consolidated report'
        verbose_name_plural = 'Class 12 aptitude consolidated reports'

    def __str__(self):
        return self.reasoning_combination

    def to_row_dict(self) -> dict:
        return {
            'reasoning_combination': self.reasoning_combination,
            'codes': list(self.codes or []),
            'aptitude_description': self.aptitude_description or '',
            'interpretation_narrative': self.interpretation_narrative or '',
            'career_clusters': list(self.career_clusters or []),
            'career_pathways': list(self.career_pathways or []),
            'degree_pathways': list(self.degree_pathways or []),
            'real_life_signs': list(self.real_life_signs or []),
            'daily_life_impact': list(self.daily_life_impact or []),
        }
