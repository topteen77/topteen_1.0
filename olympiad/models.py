"""
NSEO (National School English Olympiad) models.
Part of topteen_1.0; uses core.BaseModel and users.User.
"""
from django.db import models
from django.conf import settings
from core.models import BaseModel
from core import choices


class OlympiadExam(BaseModel):
    """An Olympiad exam (e.g. Level 1 National Qualifier, Class 8 Mock)."""
    name = models.CharField(max_length=255)
    level = models.PositiveSmallIntegerField(
        help_text="1=National Qualifier, 2=Zonal Finals, 3=National Summit",
        default=1,
    )
    class_level = models.PositiveSmallIntegerField(
        help_text="Target class (e.g. 8, 9, 10)",
        null=True,
        blank=True,
    )
    exam_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    total_marks = models.PositiveIntegerField(default=60)
    instructions = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    # Reuse project's object_status via BaseModel; optional explicit status
    status = models.CharField(
        max_length=20,
        choices=(
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ),
        default='draft',
    )

    class Meta:
        verbose_name = 'Olympiad Exam'
        verbose_name_plural = 'Olympiad Exams'
        ordering = ['-exam_date', '-created']

    def __str__(self):
        return f"{self.name} (Level {self.level})"


class OlympiadQuestion(BaseModel):
    """A single question (MCQ or descriptive) for Olympiad exams."""
    QUESTION_TYPE_CHOICES = (
        ('mcq', 'MCQ'),
        ('multiple_response', 'Multiple Response'),
        ('descriptive', 'Descriptive'),
        ('essay', 'Essay'),
        ('fill_blank', 'Fill in the Blanks'),
    )
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('very_hard', 'Very Hard'),
    )
    exam = models.ForeignKey(
        OlympiadExam,
        on_delete=models.CASCADE,
        related_name='questions',
        null=True,
        blank=True,
        help_text="Optional: link to a specific exam. Otherwise use exam_question_sets.",
    )
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='mcq')
    content = models.JSONField(
        default=dict,
        help_text='{"text": "...", "images": [], "audio": ""}',
    )
    options = models.JSONField(
        null=True,
        blank=True,
        help_text='For MCQ: [{"id": "a", "text": "...", "is_correct": true}]',
    )
    correct_answer = models.JSONField(
        null=True,
        blank=True,
        help_text="Correct answer (structure depends on question_type).",
    )
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    topic = models.CharField(max_length=255, blank=True)
    syllabus_section = models.CharField(max_length=100, blank=True)
    marks = models.PositiveIntegerField(default=1)
    estimated_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order in exam.")

    class Meta:
        verbose_name = 'Olympiad Question'
        verbose_name_plural = 'Olympiad Questions'
        ordering = ['order', 'id']

    def __str__(self):
        text = (self.content or {}).get('text', '')[:50] or f'Question #{self.id}'
        return f"{text}... ({self.question_type})"


class OlympiadExamQuestionSet(BaseModel):
    """Links questions to exams (many-to-many with order)."""
    exam = models.ForeignKey(OlympiadExam, on_delete=models.CASCADE, related_name='exam_question_sets')
    question = models.ForeignKey(OlympiadQuestion, on_delete=models.CASCADE, related_name='exam_question_sets')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['exam', 'order']
        unique_together = ('exam', 'question')

    def __str__(self):
        return f"{self.exam.name} — Q{self.order}"


class OlympiadRegistration(BaseModel):
    """Student registration for an Olympiad exam."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='olympiad_registrations',
    )
    exam = models.ForeignKey(OlympiadExam, on_delete=models.CASCADE, related_name='registrations')
    registration_type = models.CharField(
        max_length=20,
        choices=(('school', 'School'), ('individual', 'Individual')),
        default='individual',
    )
    payment_status = models.CharField(
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
        ),
        default='pending',
    )
    payment_id = models.CharField(max_length=255, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Olympiad Registration'
        verbose_name_plural = 'Olympiad Registrations'
        unique_together = ('user', 'exam')

    def __str__(self):
        return f"{self.user} — {self.exam.name}"


class OlympiadSession(BaseModel):
    """Active or completed exam attempt (one per user per exam)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='olympiad_sessions',
    )
    exam = models.ForeignKey(OlympiadExam, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=(
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('abandoned', 'Abandoned'),
        ),
        default='in_progress',
    )
    device_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    total_marks_awarded = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Olympiad Session'
        verbose_name_plural = 'Olympiad Sessions'

    def __str__(self):
        return f"{self.user} — {self.exam.name} — {self.status}"


class OlympiadResponse(BaseModel):
    """A single answer submission within a session."""
    session = models.ForeignKey(
        OlympiadSession,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    question = models.ForeignKey(
        OlympiadQuestion,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    response = models.JSONField(
        null=True,
        blank=True,
        help_text="Student's answer (e.g. option id for MCQ, text for descriptive).",
    )
    time_taken_seconds = models.PositiveIntegerField(default=0)
    flagged_for_review = models.BooleanField(default=False)
    marks_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    auto_scored = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Olympiad Response'
        verbose_name_plural = 'Olympiad Responses'
        unique_together = ('session', 'question')

    def __str__(self):
        return f"Session {self.session_id} — Q{self.question_id}"
