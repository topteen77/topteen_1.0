from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Question categories"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, default='fas fa-folder')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
        indexes = [models.Index(fields=['order', 'name'])]

    def __str__(self):
        return self.name


class Country(models.Model):
    """Countries for study abroad"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=2, unique=True)  # ISO code
    flag_emoji = models.CharField(max_length=10, default='🌍')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

    def __str__(self):
        return self.name


class KnowledgeBaseEntry(models.Model):
    """Knowledge base entries for AI responses"""
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.JSONField(default=dict)  # Structured knowledge data
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Knowledge Base Entries"
        ordering = ['-last_updated']
        indexes = [models.Index(fields=['category', '-last_updated'])]

    def __str__(self):
        return f"{self.title} ({self.category.name})"


class Query(models.Model):
    """User queries"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    question_text = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    country_context = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)  # Response time in milliseconds
    source = models.CharField(max_length=20, default='ai', choices=[('ai', 'AI Generated'), ('database', 'From Database')])
    # Moderation: staff can hide posts from public display without deleting.
    is_hidden = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden posts are not shown in Exploration / Trending.',
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='forum_hidden_queries',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Queries"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_hidden', 'status', '-created_at']),
        ]

    def __str__(self):
        return self.question_text[:50]

    def mark_completed(self):
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save()

    def hide(self, user=None):
        self.is_hidden = True
        self.hidden_at = timezone.now()
        if user is not None and getattr(user, 'is_authenticated', False):
            self.hidden_by = user
        self.save(update_fields=['is_hidden', 'hidden_at', 'hidden_by', 'updated_at'])

    def unhide(self):
        self.is_hidden = False
        self.hidden_at = None
        self.hidden_by = None
        self.save(update_fields=['is_hidden', 'hidden_at', 'hidden_by', 'updated_at'])


class Response(models.Model):
    """AI responses to queries"""
    query = models.OneToOneField(Query, on_delete=models.CASCADE, related_name='response')
    response_text = models.TextField()
    confidence_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    sources = models.JSONField(default=list, blank=True)  # List of source URLs/references
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Response to: {self.query.question_text[:30]}"


class PerformanceMetrics(models.Model):
    """Track system performance metrics"""
    date = models.DateField(auto_now_add=True)
    total_queries = models.IntegerField(default=0)
    ai_generated = models.IntegerField(default=0)
    database_cached = models.IntegerField(default=0)
    average_response_time_ms = models.FloatField(default=0.0)
    total_cost_usd = models.FloatField(default=0.0)
    accuracy_rate = models.FloatField(default=0.0)  # Based on user feedback if implemented
    
    class Meta:
        ordering = ['-date']
        unique_together = ['date']
    
    def __str__(self):
        return f"Metrics for {self.date}"


class AIFeature(models.Model):
    """AI Features that can be displayed"""
    name = models.CharField(max_length=200)
    icon = models.CharField(max_length=50, default='fas fa-check-circle')
    description = models.TextField(blank=True, null=True)
    link_url = models.CharField(max_length=500, blank=True, null=True, help_text='URL to link this feature to (e.g., /careers/, /psychometrictest/)')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class AICapability(models.Model):
    """AI Capabilities that can be displayed"""
    name = models.CharField(max_length=200)
    icon = models.CharField(max_length=50, default='fas fa-brain')
    description = models.TextField(blank=True, null=True)
    link_url = models.CharField(max_length=500, blank=True, null=True, help_text='URL to link this capability to (e.g., /careers/, /testprep/)')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "AI Capabilities"
    
    def __str__(self):
        return self.name
