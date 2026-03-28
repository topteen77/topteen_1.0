from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class NotificationCategory:
    PAYMENT = 'payment'
    COURSE = 'course'
    INSTITUTE = 'institute'
    MARKETING = 'marketing'
    SYSTEM = 'system'

    CHOICES = (
        (PAYMENT, 'Payment'),
        (COURSE, 'Course'),
        (INSTITUTE, 'Institute'),
        (MARKETING, 'Marketing'),
        (SYSTEM, 'System'),
    )


class NotificationRoleHint:
    ADMIN = 'admin'
    STUDENT = 'student'
    PARENT = 'parent'
    INSTITUTE = 'institute'
    MARKETING = 'marketing'
    ACCOUNTS = 'accounts'
    UNKNOWN = 'unknown'

    CHOICES = (
        (ADMIN, 'Admin'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent'),
        (INSTITUTE, 'Institute'),
        (MARKETING, 'Marketing'),
        (ACCOUNTS, 'Accounts'),
        (UNKNOWN, 'Unknown'),
    )


class NotificationTypeConfig(models.Model):
    event_type = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=30, choices=NotificationCategory.CHOICES, default=NotificationCategory.SYSTEM)
    description = models.CharField(max_length=255, blank=True, default='')
    enabled = models.BooleanField(default=True)
    requires_celery = models.BooleanField(default=False)
    requires_email = models.BooleanField(default=False)
    requires_redis = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('event_type',)

    def __str__(self):
        return '{} [{}]'.format(self.event_type, 'on' if self.enabled else 'off')


class NotificationMessageTemplate(models.Model):
    """
    Admin-editable title/body templates for in-app notifications.

    Use Python ``str.format`` placeholders, e.g. ``{amount_display}``, ``{item}``, ``{currency_code}``,
    ``{payment_id}``, ``{gateway_order_id}``, ``{retry_payment_label}``, ``{reason}``.
    Leave empty to use the built-in default strings from code.
    """

    event_type = models.CharField(max_length=120, unique=True, db_index=True)
    title_template = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Optional. Empty = use built-in default title. Placeholders: see model docstring.',
    )
    body_template = models.TextField(
        blank=True,
        default='',
        help_text='Optional. Empty = use built-in default body. Placeholders: see model docstring.',
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('event_type',)
        verbose_name = 'Notification message template'
        verbose_name_plural = 'Notification message templates'

    def __str__(self):
        return self.event_type


class Notification(models.Model):
    """
    In-app notification row. Deletion is always a hard delete (SQL ``DELETE``) — there is no
    soft-delete or archive flag. Marking as read (``mark_read()``) removes the row from the database.
    """

    class Environment:
        PRODUCTION = 'production'
        DEVELOPMENT = 'development'
        CHOICES = (
            (PRODUCTION, 'Production'),
            (DEVELOPMENT, 'Development'),
        )

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    role_hint = models.CharField(max_length=30, choices=NotificationRoleHint.CHOICES, default=NotificationRoleHint.UNKNOWN)
    category = models.CharField(max_length=30, choices=NotificationCategory.CHOICES, default=NotificationCategory.SYSTEM)
    environment = models.CharField(max_length=20, choices=Environment.CHOICES, default=Environment.PRODUCTION, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    dedupe_key = models.CharField(max_length=255, blank=True, default='', db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['recipient', '-created']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'event_type']),
            models.Index(fields=['recipient', 'environment', '-created']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'dedupe_key'],
                condition=~models.Q(dedupe_key=''),
                name='notifications_unique_recipient_dedupe_key',
            )
        ]

    def mark_read(self):
        """Dismiss this notification: hard-delete the row (no separate read/archive state)."""
        self.delete()

    def delete(self, using=None, keep_parents=False):
        """Remove this row from the database (hard delete)."""
        return super().delete(using=using, keep_parents=keep_parents)

