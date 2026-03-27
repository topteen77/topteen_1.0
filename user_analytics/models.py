from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models import BaseModel
from users.models import User
from core import choices
import json
import secrets


class EnquirySource(BaseModel):
    """
    Tracks enquiry/source links used in social media or other channels.
    The public URL uses only a non-readable token (?ref=TOKEN) so users cannot
    identify the source; admins identify by name in the dashboard.
    """
    name = models.CharField(
        max_length=255,
        help_text="Admin-only label (e.g. Facebook March 2025). Not shown in the URL."
    )
    agency_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Agency or partner name for easy tracking (e.g. ABC Agency)."
    )
    user_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Contact or user name for this source (e.g. John from Marketing)."
    )
    event = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Event or campaign (e.g. Career Fair 2025, Instagram Campaign)."
    )
    token = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Random token used in URL as ?ref=TOKEN. Not human-readable."
    )
    base_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Full page URL for the link (e.g. https://www.topteen.in or https://www.topteen.in/skilllab/course/xyz/). Leave blank to use site root from settings."
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Enquiry Source (UTM Link)"
        verbose_name_plural = "Enquiry Sources (UTM Links)"
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.token:
            # URL-safe random token, 12 chars – not readable, no utm params in URL
            self.token = secrets.token_urlsafe(9)[:16]
        super().save(*args, **kwargs)

    def get_full_url(self, fallback_base_url=None):
        """Build the non-readable link: base is always from settings (www.topteen.in or demo.topteen.in)."""
        from django.conf import settings
        base = (
            self.base_url
            or getattr(settings, 'ENQUIRY_SOURCE_BASE_URL', None)
            or fallback_base_url
            or ''
        ).rstrip('/')
        if not base:
            return ""
        return f"{base}/?ref={self.token}"

    def __str__(self):
        return self.name


class ChatbotPageRule(BaseModel):
    """
    Per-page chatbot visibility rules managed from User Analytics dashboard.
    """
    BOT_CHOICES = (
        ('chat_this_page', 'Chat this page'),
        ('career_counsellor', 'Career Counsellor'),
    )
    POSITION_CHOICES = (
        ('left', 'Left'),
        ('right', 'Right'),
    )

    page_url = models.CharField(
        max_length=500,
        db_index=True,
        help_text="URL path, e.g. /, /four-pillars-of-learning/, /career-planning/",
    )
    bot_name = models.CharField(max_length=40, choices=BOT_CHOICES, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True, help_text="Show or hide this bot on matched pages")
    include_subpages = models.BooleanField(
        default=False,
        help_text="If enabled, apply to direct child paths of page_url",
    )
    position = models.CharField(
        max_length=10,
        choices=POSITION_CHOICES,
        default='right',
        db_index=True,
        help_text="Widget position for matched page(s)",
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        db_index=True,
        help_text="Lower number = higher priority",
    )

    class Meta:
        ordering = ['priority', '-modified', '-id']
        verbose_name = "Chatbot Page Rule"
        verbose_name_plural = "Chatbot Page Rules"
        indexes = [
            models.Index(fields=['bot_name', 'is_visible', 'priority']),
            models.Index(fields=['page_url', 'bot_name']),
        ]

    def __str__(self):
        state = 'Show' if self.is_visible else 'Hide'
        return f"{state} {self.bot_name} @ {self.page_url}"


class UserActivity(BaseModel):
    """
    Tracks user page views, sessions, and user journey on the website.
    Optimized for performance with async processing.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_activities'
    )
    session_id = models.CharField(max_length=255, db_index=True, help_text="Unique session identifier")
    page_path = models.CharField(max_length=500, db_index=True, help_text="URL path visited")
    page_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        db_index=True,
        help_text="Full URL visited (for filtering local vs production in admin)."
    )
    page_title = models.CharField(max_length=500, blank=True, null=True)
    referrer = models.CharField(max_length=500, blank=True, null=True, help_text="HTTP referrer")
    utm_source = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    utm_medium = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    utm_campaign = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    utm_term = models.CharField(max_length=255, blank=True, null=True)
    utm_content = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    browser = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    traffic_source_category = models.CharField(
        max_length=20, blank=True, null=True, db_index=True,
        help_text="Category: search, social, referral, direct, internal"
    )
    time_on_page = models.IntegerField(default=0, help_text="Time spent on page in seconds")
    is_bounce = models.BooleanField(default=False, help_text="Single page visit")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    enquiry_source = models.ForeignKey(
        EnquirySource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
        db_index=True,
        help_text="Set when user arrived via ?ref= token (non-readable link)."
    )

    class Meta:
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created', 'user']),
            models.Index(fields=['session_id', '-created']),
            models.Index(fields=['enquiry_source', '-created']),
            models.Index(fields=['enquiry_source', 'session_id']),
            models.Index(fields=['object_status', 'enquiry_source', '-created']),
            models.Index(fields=['utm_source', 'utm_medium']),
            models.Index(fields=['device_type', '-created']),
            models.Index(fields=['traffic_source_category', '-created']),
        ]
    
    @property
    def is_registered_user(self):
        """Check if this activity is from a registered user"""
        return self.user is not None
    
    @property
    def user_type(self):
        """Get user type: 'Registered' or 'Organic'"""
        return 'Registered' if self.user else 'Organic'
    
    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{user_str} - {self.page_path} - {self.created}"


class Lead(BaseModel):
    """
    Tracks prospects and leads with source attribution.
    Links to users when they register.
    """
    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_leads',
        help_text="Linked user when they register"
    )
    source = models.CharField(max_length=255, db_index=True, help_text="Traffic source")
    medium = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    campaign = models.CharField(max_length=255, blank=True, null=True)
    referrer = models.CharField(max_length=500, blank=True, null=True)
    landing_page = models.CharField(max_length=500, blank=True, null=True)
    first_visit = models.DateTimeField(auto_now_add=True, db_index=True)
    last_visit = models.DateTimeField(auto_now=True)
    visit_count = models.IntegerField(default=1)
    is_converted = models.BooleanField(default=False, db_index=True, help_text="Converted to customer")
    converted_at = models.DateTimeField(null=True, blank=True)
    conversion_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Revenue from conversion")
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ['-first_visit']
        indexes = [
            models.Index(fields=['-first_visit', 'is_converted']),
            models.Index(fields=['source', 'medium']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.source}"


class UserEvent(BaseModel):
    """
    Tracks business-specific events: enrollments, payments, test completions, etc.
    """
    EVENT_TYPES = (
        ('registration', 'User Registration'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('payment_pending', 'Payment Pending'),
        ('psychometric_test_started', 'Psychometric Test Started'),
        ('psychometric_test_completed', 'Psychometric Test Completed'),
        ('result_generated', 'Result Generated'),
        ('course_enrolled', 'Course Enrolled'),
        ('skilllab_enrolled', 'SkillLab Course Enrolled'),
        ('institute_student_registered', 'Institute Student Registered'),
        ('counselor_course_enrolled', 'Counselor Course Enrolled'),
        ('page_view', 'Page View'),
        ('download', 'Download'),
        ('form_submission', 'Form Submission'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_events'
    )
    event_type = models.CharField(max_length=100, choices=EVENT_TYPES, db_index=True)
    event_name = models.CharField(max_length=255, db_index=True)
    event_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Monetary value if applicable")
    
    # Generic foreign key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional event data")
    session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = "User Event"
        verbose_name_plural = "User Events"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created', 'event_type']),
            models.Index(fields=['user', '-created']),
            models.Index(fields=['event_type', 'event_name']),
            models.Index(fields=['session_id', '-created']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{user_str} - {self.event_name} - {self.created}"


class AnalyticsCache(BaseModel):
    """
    Caches aggregated analytics data for performance optimization.
    Reduces database load for frequently accessed reports.
    """
    CACHE_TYPES = (
        ('daily_summary', 'Daily Summary'),
        ('weekly_summary', 'Weekly Summary'),
        ('monthly_summary', 'Monthly Summary'),
        ('revenue_report', 'Revenue Report'),
        ('conversion_funnel', 'Conversion Funnel'),
        ('traffic_sources', 'Traffic Sources'),
        ('top_pages', 'Top Pages'),
    )
    
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    cache_type = models.CharField(max_length=50, choices=CACHE_TYPES, db_index=True)
    date_range_start = models.DateField(db_index=True)
    date_range_end = models.DateField(db_index=True)
    cached_data = models.JSONField(help_text="Cached aggregated data")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True, help_text="Cache expiration time")
    
    class Meta:
        verbose_name = "Analytics Cache"
        verbose_name_plural = "Analytics Caches"
        ordering = ['-updated']
        indexes = [
            models.Index(fields=['cache_type', 'date_range_start', 'date_range_end']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.cache_type} - {self.date_range_start} to {self.date_range_end}"


class UserJourney(BaseModel):
    """
    Tracks complete user journey through the website.
    Aggregated from UserActivity records.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_journeys'
    )
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_pages = models.IntegerField(default=0)
    total_time = models.IntegerField(default=0, help_text="Total session time in seconds")
    entry_page = models.CharField(max_length=500)
    exit_page = models.CharField(max_length=500, blank=True, null=True)
    referrer = models.CharField(max_length=500, blank=True, null=True)
    utm_source = models.CharField(max_length=255, blank=True, null=True)
    utm_medium = models.CharField(max_length=255, blank=True, null=True)
    utm_campaign = models.CharField(max_length=255, blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    traffic_source_category = models.CharField(
        max_length=20, blank=True, null=True, db_index=True,
        help_text="Category: search, social, referral, direct, internal"
    )
    enquiry_source = models.ForeignKey(
        EnquirySource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journeys',
        db_index=True,
        help_text="Set when user arrived via ?ref= token (non-readable link)."
    )
    converted = models.BooleanField(default=False, db_index=True, help_text="Did this session convert?")
    conversion_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journeys'
    )
    journey_path = models.JSONField(default=list, help_text="Sequence of pages visited")
    ga4_client_id = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="GA4 client ID for session linking")
    
    # Journey completion tracking
    is_registered = models.BooleanField(default=False, db_index=True, help_text="User registered during this journey")
    has_payment = models.BooleanField(default=False, db_index=True, help_text="User made a payment during this journey")
    has_psychometric_test = models.BooleanField(default=False, db_index=True, help_text="User started psychometric test during this journey")
    test_completed = models.BooleanField(default=False, db_index=True, help_text="User completed psychometric test during this journey")
    result_generated = models.BooleanField(default=False, db_index=True, help_text="Psychometric test result was generated during this journey")
    
    # Event references for detailed tracking
    registration_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registration_journeys',
        help_text="User registration event"
    )
    payment_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_journeys',
        help_text="Payment event"
    )
    psychometric_test_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='psychometric_test_journeys',
        help_text="Psychometric test started event"
    )
    test_completion_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_completion_journeys',
        help_text="Test completion event"
    )
    result_generation_event = models.ForeignKey(
        UserEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='result_generation_journeys',
        help_text="Result generation event"
    )
    
    class Meta:
        verbose_name = "User Journey"
        verbose_name_plural = "User Journeys"
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['-start_time', 'user']),
            models.Index(fields=['session_id']),
            models.Index(fields=['enquiry_source', '-start_time']),
            models.Index(fields=['enquiry_source', 'session_id']),
            models.Index(fields=['object_status', 'enquiry_source', '-start_time']),
            models.Index(fields=['converted', '-start_time']),
        ]
    
    @property
    def is_registered_user(self):
        """Check if this journey is from a registered user"""
        return self.user is not None
    
    @property
    def user_type(self):
        """Get user type: 'Registered' or 'Organic'"""
        return 'Registered' if self.user else 'Organic'
    
    @property
    def is_new_user(self):
        """Check if user is new (registered within 24 hours of journey start)"""
        if not self.user:
            return False
        from datetime import timedelta
        return self.user.created > (self.start_time - timedelta(hours=24))
    
    @property
    def is_ga4_tracked(self):
        """Check if journey is tracked by GA4"""
        return bool(self.ga4_client_id)
    
    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{user_str} - {self.session_id} - {self.start_time}"


class GA4Session(BaseModel):
    """
    Stores synced GA4 session data for faster querying and offline access.
    Links GA4 sessions with Django user sessions via client ID.
    """
    ga4_client_id = models.CharField(max_length=255, db_index=True, help_text="GA4 client ID")
    ga4_session_id = models.CharField(max_length=255, blank=True, null=True, help_text="GA4 session ID")
    django_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="Django session ID")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ga4_sessions',
        help_text="Linked Django user if identified"
    )
    date = models.DateField(db_index=True, help_text="Session date")
    source = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="Traffic source")
    medium = models.CharField(max_length=255, blank=True, null=True)
    campaign = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    device = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    entry_page = models.CharField(max_length=500, blank=True, null=True, db_index=True)
    exit_page = models.CharField(max_length=500, blank=True, null=True)
    sessions_count = models.IntegerField(default=1, help_text="Number of sessions (for aggregated data)")
    pageviews = models.IntegerField(default=0, help_text="Total page views")
    users = models.IntegerField(default=1, help_text="Number of unique users")
    synced_at = models.DateTimeField(auto_now_add=True, db_index=True, help_text="When this data was synced from GA4")
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "GA4 Session"
        verbose_name_plural = "GA4 Sessions"
        ordering = ['-date', '-synced_at']
        indexes = [
            models.Index(fields=['ga4_client_id', 'date']),
            models.Index(fields=['django_session_id', 'date']),
            models.Index(fields=['user', '-date']),
            models.Index(fields=['date', 'source', 'country', 'device']),
            models.Index(fields=['-synced_at']),
        ]
        # Unique constraint to prevent duplicates (entry_page excluded - exceeds MySQL 3072 byte index limit with utf8mb4)
        unique_together = [['ga4_client_id', 'date', 'source', 'country', 'device']]
    
    @property
    def is_registered_user(self):
        """Check if this session is from a registered user"""
        return self.user is not None
    
    @property
    def user_type(self):
        """Get user type: 'Registered' or 'New'"""
        if self.user:
            # Check if user was new at the time of this session
            if self.user.created.date() <= self.date:
                return 'Registered'
        return 'New'
    
    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{user_str} - {self.ga4_client_id[:10]}... - {self.date}"
