
from django.db import models
from users.models import User
from django.forms import ValidationError
from django.utils import timezone
from django.conf import settings

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
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='sections', default='')
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
    
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions',null=True, blank=True)
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
        # db_table = 'question'

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
        """
        Get the existing session for this user and test.
        If a completed session exists, return it and do NOT create a new one.
        If an incomplete session exists, return it.

        """
        # Check for any session (completed or not)
        # breakpoint()
        session = cls.objects.filter(user=user, test=test).order_by('-attempt_count').first()
        if session:
            # If already completed, do not allow retake
            if session.is_completed:
                return session  # Return the completed session (frontend should block retake)
            
            # If not completed, just update the session itself, not all section sessions
            # This fixes the issue with all sections being updated when the test is started
            session.save()
            return session
        
        # If no session exists, create a new one
        session = cls.objects.create(
            user=user,
            test=test,
            start_time=timezone.now(),
            is_completed=False,
            attempt_count=1
        )
        
        # Create section sessions with NULL start times
        # They will be initialized when each section is actually started
        for section in test.sections.all():
            SectionSession.objects.create(
                session=session,
                section=section,
                start_time=None,  # Don't set start time until section is actually started
                is_completed=False
            )
        return session

    def __str__(self):
        return f"{self.user.username} - {self.test.title} ({self.start_time.strftime('%Y-%m-%d')}) Attempt: {self.attempt_count}"


class SectionSession(TimeStampedModel):
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='section_sessions')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ['session', 'section']

    @classmethod
    def get_or_update_section_session(cls, test_session, section):
        """
        Get existing section session if not completed.
        If completed, do NOT allow retake — return None or raise exception.
        """
        # Check if the section is already completed
        completed_exists = cls.objects.filter(
            session=test_session,
            section=section,
            is_completed=True
        ).exists()

        if completed_exists:
            # Section is already completed — do not allow retake
            raise ValidationError("This section has already been completed and cannot be retaken.")

        try:
            # Try to get an existing incomplete session
            section_session = cls.objects.get(
                session=test_session,
                section=section,
                is_completed=False
            )
            # Update the start time
            section_session.start_time = timezone.now()
            section_session.save()
        except cls.DoesNotExist:
            # No session exists at all, create a new one
            section_session = cls.objects.create(
                session=test_session,
                section=section,
                start_time=timezone.now(),
                is_completed=False
            )

        return section_session



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

    # @classmethod
    # def update_or_create_response(cls, session, session_section, test, answer_data):
    #     """Update existing response or create new one"""
    #     try:
    #         # Ensure we have valid data
    #         if not session or not test:
    #             raise ValueError("Session and test are required")

    #         # Normalize the answer data
    #         if isinstance(answer_data, dict):
    #             if 'submitted_answers' in answer_data:
    #                 # If it's already in the correct format, use as is
    #                 normalized_data = answer_data
    #             else:
    #                 # If it's raw answers, wrap them in the expected structure
    #                 normalized_data = {
    #                     'submitted_answers': answer_data,
    #                     'category_counts': {},
    #                     'score': 0
    #                 }
    #         else:
    #             raise ValueError("Invalid answer data format")

    #         # Create or update the response
    #         response, created = cls.objects.update_or_create(
    #             session=session,
    #             session_section=session_section,
    #             test=test,
    #             attempt_number=session.attempt_count,
    #             defaults={
    #                 'selected_answer': normalized_data
    #             }
    #         )
            
    #         return response

    #     except Exception as e:
    #         print(f"Error in update_or_create_response: {str(e)}")
    #         raise

    @classmethod
    def update_or_create_response(cls, session, session_section, test, answer_data):
        try:
            if not session or not test:
                raise ValueError("Session and test are required")

            # Extract or normalize submitted_answers
            if 'submitted_answers' in answer_data:
                new_answers = answer_data['submitted_answers']
            else:
                new_answers = answer_data

            # Get or create the response object
            response, created = cls.objects.get_or_create(
                session=session,
                session_section=session_section,
                test=test,
                attempt_number=session.attempt_count,
                defaults={'selected_answer': {}}
            )

            # Get existing data or initialize
            existing_data = response.selected_answer or {}
            existing_submitted = existing_data.get('submitted_answers', {})
            existing_category_counts = existing_data.get('category_counts', {})
            existing_score = existing_data.get('score', 0)

            # Merge new answers and compute score/category_counts
            # Answer is defined in the same file, so we can reference it directly
            
            for q_key, q_data in new_answers.items():
                # Overwrite or add new question
                existing_submitted[q_key] = q_data

                # Handle different data formats
                # If q_data is a list of answer IDs, fetch answer objects
                if isinstance(q_data, list):
                    # q_data is a list of answer IDs
                    answer_ids = q_data
                    for answer_id in answer_ids:
                        try:
                            answer = Answer.objects.get(id=answer_id)
                            # Add category count
                            if answer.category:
                                existing_category_counts[answer.category] = existing_category_counts.get(answer.category, 0) + 1
                            # Add score
                            existing_score += answer.score or 0
                        except Answer.DoesNotExist:
                            pass
                elif isinstance(q_data, dict):
                    # q_data is already a dictionary with category/score
                    category = q_data.get('category')
                    if category:
                        existing_category_counts[category] = existing_category_counts.get(category, 0) + 1
                    existing_score += q_data.get('score', 0)
                else:
                    # Single answer ID (integer)
                    try:
                        answer = Answer.objects.get(id=q_data)
                        if answer.category:
                            existing_category_counts[answer.category] = existing_category_counts.get(answer.category, 0) + 1
                        existing_score += answer.score or 0
                    except (Answer.DoesNotExist, ValueError):
                        pass

            # Final update
            response.selected_answer = {
                'submitted_answers': existing_submitted,
                'category_counts': existing_category_counts,
                'score': existing_score
            }

            response.save()
            return response

        except Exception as e:
            print(f"[ERROR] update_or_create_response: {e}")
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

class TestTopCategories(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='TestTopCategories')
    test_paper = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='top_categories')
    high_category = models.TextField(null=True, blank=True)  # Changed from CharField to TextField
    low_category = models.CharField(max_length=100, null=True, blank=True)


class TestCompletionPopup(TimeStampedModel):
    """Stores answers from popup questions shown after test completion"""
    TEST_TYPE_CHOICES = [
        ('personality', 'Personality Assessment'),
        ('motivation', 'Motivation Assessment'),
        ('career_interest', 'Career Interest Inventory'),
        ('aptitude', 'Aptitude Assessment'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_completion_popups')
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES)
    answer = models.CharField(max_length=200, help_text="Selected answer option")
    country = models.CharField(max_length=100, null=True, blank=True, help_text="Country selection for career interest 'Outside India' option")
    
    class Meta:
        unique_together = ['user', 'test_type']
        verbose_name = "Test Completion Popup Answer"
        verbose_name_plural = "Test Completion Popup Answers"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_test_type_display()}: {self.answer}"


class CareerMatch(TimeStampedModel):
    """Store user's career swipe actions (like/pass) and match scores"""
    ACTION_CHOICES = [
        ('like', 'Like'),
        ('pass', 'Pass'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='career_matches')
    career = models.ForeignKey('careers.Career', on_delete=models.CASCADE, related_name='matches')
    match_score = models.FloatField(null=True, blank=True, help_text="Compatibility score (0-100)")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='like')
    notes = models.TextField(blank=True, help_text="Optional notes from user")
    
    class Meta:
        unique_together = ['user', 'career']
        verbose_name = "Career Match"
        verbose_name_plural = "Career Matches"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.career.name} ({self.action})"


# ============================================================================
# Combined Report Mapping Models
# ============================================================================

class ClusterMapping(TimeStampedModel):
    """Maps Excel cluster names to database CareerCluster entities"""
    excel_name = models.CharField(max_length=500, unique=True, help_text="Cluster name from Excel")
    db_cluster = models.ForeignKey(
        'careers.CareerCluster',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='excel_mappings',
        help_text="Mapped database cluster"
    )
    is_mapped = models.BooleanField(default=False, help_text="Whether this Excel name is mapped to DB")
    notes = models.TextField(blank=True, help_text="Admin notes about this mapping")
    
    class Meta:
        verbose_name = "Cluster Mapping"
        verbose_name_plural = "Cluster Mappings"
        ordering = ['excel_name']
    
    def __str__(self):
        status = "[MAPPED]" if self.is_mapped else "[UNMAPPED]"
        db_name = self.db_cluster.name if self.db_cluster else "Unmapped"
        return f"{status} {self.excel_name} -> {db_name}"


class RoleMapping(TimeStampedModel):
    """Maps Excel role names to database Career entities"""
    excel_name = models.CharField(max_length=500, unique=True, help_text="Role name from Excel")
    db_role = models.ForeignKey(
        'careers.Career',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='excel_role_mappings',
        help_text="Mapped database career/role"
    )
    is_mapped = models.BooleanField(default=False, help_text="Whether this Excel name is mapped to DB")
    notes = models.TextField(blank=True, help_text="Admin notes about this mapping")
    
    class Meta:
        verbose_name = "Role Mapping"
        verbose_name_plural = "Role Mappings"
        ordering = ['excel_name']
    
    def __str__(self):
        status = "[MAPPED]" if self.is_mapped else "[UNMAPPED]"
        db_name = self.db_role.name if self.db_role else "Unmapped"
        return f"{status} {self.excel_name} -> {db_name}"


class PathwayMapping(TimeStampedModel):
    """Maps Excel pathway names to database Course entities"""
    excel_name = models.CharField(max_length=500, unique=True, help_text="Pathway name from Excel")
    db_pathway = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='excel_pathway_mappings',
        help_text="Mapped database course/pathway"
    )
    is_mapped = models.BooleanField(default=False, help_text="Whether this Excel name is mapped to DB")
    notes = models.TextField(blank=True, help_text="Admin notes about this mapping")
    
    class Meta:
        verbose_name = "Pathway Mapping"
        verbose_name_plural = "Pathway Mappings"
        ordering = ['excel_name']
    
    def __str__(self):
        status = "[MAPPED]" if self.is_mapped else "[UNMAPPED]"
        db_name = self.db_pathway.name if self.db_pathway else "Unmapped"
        return f"{status} {self.excel_name} -> {db_name}"


class AptitudeCombinationMapping(TimeStampedModel):
    """Stores the complete mapping for each aptitude code combination"""
    aptitude_code = models.CharField(max_length=100, unique=True, help_text="Aptitude code (e.g., AR, AR+NR)")
    aptitude_areas = models.CharField(max_length=500, help_text="Full aptitude area names")
    
    # Many-to-many relationships for clusters, roles, and pathways
    clusters = models.ManyToManyField(
        'careers.CareerCluster',
        related_name='aptitude_combinations',
        blank=True,
        help_text="Career clusters for this aptitude combination"
    )
    roles = models.ManyToManyField(
        'careers.Career',
        related_name='aptitude_combinations',
        blank=True,
        help_text="Career roles for this aptitude combination"
    )
    pathways = models.ManyToManyField(
        'courses.Course',
        related_name='aptitude_combinations',
        blank=True,
        help_text="Educational pathways for this aptitude combination"
    )
    
    is_complete = models.BooleanField(default=False, help_text="Whether all mappings are complete")
    notes = models.TextField(blank=True, help_text="Admin notes")
    
    class Meta:
        verbose_name = "Aptitude Combination Mapping"
        verbose_name_plural = "Aptitude Combination Mappings"
        ordering = ['aptitude_code']
    
    def __str__(self):
        status = "[COMPLETE]" if self.is_complete else "[INCOMPLETE]"
        return f"{status} {self.aptitude_code}: {self.aptitude_areas}"