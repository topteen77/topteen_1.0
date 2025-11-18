
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Base model with created and updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TestCategory(TimeStampedModel):
    """Represents the four main assessment types (Personality, Motivation, Career Interest, Aptitude)"""
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Test Categories"


class Test(TimeStampedModel):
    """Individual tests within each category"""
    category = models.ForeignKey(TestCategory, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=200)
    description = models.TextField()
    time_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Time limit in minutes")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class Sections(TimeStampedModel):
    """A section or sub-test within a test"""
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    time_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Time limit in minutes for this section")  # ✅ NEW

    def __str__(self):
        return f"{self.test.title} - Section {self.order}: {self.title}"

    class Meta:
        ordering = ['order']

class Question(TimeStampedModel):
    """Test questions with various formats"""
    QUESTION_TYPES = (
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('scale', 'Scale'),
        ('open_ended', 'Open Ended'),
    )
    QUESTION_LEVELS = (
        ('HARD', 'Hard'),
        ('MEDIUM', 'Medium'),
        ('EASY', 'Easy'),
    )
    
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    text = models.TextField()
    image = models.ImageField(upload_to='question_images/', null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    question_dimension = models.CharField(  # Corrected the typo here
        max_length=50,
        choices=[
            ('H', 'Honesty-Humility'),
            ('E', 'Emotionality'),
            ('X', 'eXtraversion'),
            ('A', 'Agreeableness'),
            ('C', 'Conscientiousness'),
            ('O', 'Openness'),
            # RIASEC Traits
            ('R', 'Realistic'),
            ('I', 'Investigative'),
            ('A2', 'Artistic'),
            ('S', 'Social'),
            ('E2', 'Enterprising'),
            ('C2', 'Conventional')

        ],
        default='H',
        help_text="Dimension of the question (HEXACO: H, E, X, A, C, O)"
    )
    parttern = models.CharField(
        max_length=20, 
        choices=[
            ('Straight', 'Straight Scoring'),
            ('Reverse', 'Reverse Scoring'),
        ],
        default='Straight',
        help_text="Type of scoring or selection allowed for this answer"
    )
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    question_level = models.CharField(max_length=20, choices=QUESTION_LEVELS, default='MEDIUM', help_text="Difficulty level of the question")

    def __str__(self):
        return f"{self.test.title} - Question {self.order}"

    class Meta:
        ordering = ['order']

class Answer(TimeStampedModel):
    """Possible answers for questions"""
    CATEGORY_CHOICES = [
        ('Business', 'Business'),
        ('Medical', 'Medical'),
        ('Social', 'Social'),
        ('Engineer', 'Engineer'),
    ]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.TextField()
    image = models.ImageField(upload_to='answer_images/', null=True, blank=True)
    is_correct = models.BooleanField(default=False, help_text="Whether answer is correct (for aptitude tests)")
    score = models.IntegerField(default=0, help_text="Point value (for personality/motivation tests)")
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='Business',
        help_text="Category this answer belongs to (e.g., Business, Medical)"
    )

    def __str__(self):
        return f"{self.question} - {self.text[:30]}"

class TestSession(TimeStampedModel):
    """Tracks a user's attempt at a test"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_sessions')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    attempt_count = models.PositiveIntegerField(default=1)

    class Meta:
        # Update unique_together to include attempt_count
        unique_together = ['user', 'test', 'attempt_count']

    @classmethod
    def get_or_update_session(cls, user, test):
        """Get existing session or create/update it"""
        try:
            # Try to get an incomplete session first
            session = cls.objects.filter(
                user=user,
                test=test,
                is_completed=False
            ).first()
            
            if session:
                # If found an incomplete session, return it
                return session
                
            # If no incomplete session exists, get the latest session
            latest_session = cls.objects.filter(
                user=user,
                test=test
            ).order_by('-attempt_count').first()
            
            # Calculate next attempt number
            next_attempt = (latest_session.attempt_count + 1) if latest_session else 1
            
            # Create new session
            session = cls.objects.create(
                user=user,
                test=test,
                start_time=timezone.now(),
                is_completed=False,
                attempt_count=next_attempt
            )
            
            # Create section sessions for all sections in the test
            for section in test.sections.all():
                SectionSession.objects.create(
                    session=session,
                    section=section,
                    start_time=timezone.now(),
                    is_completed=False
                )
                    
        except Exception as e:
            print(f"Error in get_or_update_session: {str(e)}")
            # If error occurs, create new session with attempt 1
            session = cls.objects.create(
                user=user,
                test=test,
                start_time=timezone.now(),
                is_completed=False,
                attempt_count=1
            )
            
            # Create section sessions for all sections
            for section in test.sections.all():
                SectionSession.objects.create(
                    session=session,
                    section=section,
                    start_time=timezone.now(),
                    is_completed=False
                )
        
        return session


    def __str__(self):
        return f"{self.user.username} - {self.test.title} ({self.start_time.strftime('%Y-%m-%d')}) Attempt: {self.attempt_count}"


class SectionSession(TimeStampedModel):
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='section_sessions')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ['session', 'section']

    @classmethod
    def get_or_update_section_session(cls, test_session, section):
        """Get existing section session or create/update it"""
        try:
            # First, try to get an existing incomplete session
            section_session = cls.objects.get(
                session=test_session,
                section=section,
                is_completed=False
            )
            # Update start time
            section_session.start_time = timezone.now()
            section_session.save()
            
        except cls.DoesNotExist:
            # If no incomplete session exists, create new one
            section_session = cls.objects.create(
                session=test_session,
                section=section,
                start_time=timezone.now(),
                is_completed=False
            )
        
        return section_session

    def __str__(self):
        return f"{self.session} - {self.section.title}"

class UserResponse(TimeStampedModel):
    """Individual answers provided by users"""
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='responses')
    session_section = models.ForeignKey(
        SectionSession,
        on_delete=models.CASCADE,

        related_name='section_responses',
        null=True,
        blank=True
    )
    test = models.ForeignKey(Test, on_delete=models.CASCADE,null=True, blank=True, related_name='user_responses')  # Add this field
    selected_answer = models.JSONField(
        default=dict,
        null=True, 
        blank=True,
        help_text="Selected answer (nullable for open-ended questions)"
    )
    attempt_number = models.PositiveIntegerField(default=1)  # Add this field
    
    class Meta:
        # Add unique constraint for question per session and attempt
        unique_together = ['session', 'session_section' , 'test', 'attempt_number']

    @classmethod
    def update_or_create_response(cls, session, session_section, test, answer_data):
        """Update existing response or create new one"""
        try:
            # Ensure we have valid data
            if not session or not test:
                raise ValueError("Session and test are required")

            # Normalize the answer data
            if isinstance(answer_data, dict):
                if 'submitted_answers' in answer_data:
                    # If it's already in the correct format, use as is
                    normalized_data = answer_data
                else:
                    # If it's raw answers, wrap them in the expected structure
                    normalized_data = {
                        'submitted_answers': answer_data,
                        'category_counts': {},
                        'score': 0
                    }
            else:
                raise ValueError("Invalid answer data format")

            # Create or update the response
            response, created = cls.objects.update_or_create(
                session=session,
                session_section=session_section,
                test=test,
                attempt_number=session.attempt_count,
                defaults={
                    'selected_answer': normalized_data
                }
            )
            
            return response

        except Exception as e:
            print(f"Error in update_or_create_response: {str(e)}")
            raise



class TestResult(TimeStampedModel):
    """Calculated results and feedback"""
    session = models.OneToOneField(TestSession, on_delete=models.CASCADE, related_name='result')
    score = models.FloatField(null=True, blank=True, help_text="Numerical score (for aptitude tests)")
    result_data = models.JSONField(default=dict, help_text="Complex results data (for personality/career tests)")
    grade = models.CharField(max_length=10, blank=True, help_text="Letter grade (optional)")
    feedback = models.TextField(blank=True, help_text="Detailed feedback")
    category_counts = models.JSONField(
        default=dict,
        help_text="Counts of answers for each category (e.g., {'Business': 3, 'Medical': 2})"
    )

    def __str__(self):
        return f"Result for {self.session}"