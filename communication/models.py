from django.db import models
from django.conf import settings
from core import choices
# Create your models here.

class CommunicationLog(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    to  = models.CharField(max_length=500)
    body = models.TextField()
    response = models.TextField()
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['type', '-created'])]

    def __str__(self):
        return "{} ({})".format(self.to,self.get_type_display())

class EmailMessageTemplate(models.Model):
    """
    Admin-editable subject/body for transactional emails.

    Use Python ``str.format`` placeholders, e.g. ``{inviter_name}``, ``{referral_url}``.
    Leave subject/body empty to use the built-in default from code.
    """

    slug = models.CharField(max_length=120, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    subject_template = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=(
            'Email subject line. Leave empty to use the built-in default. '
            'Use placeholders like {inviter_name}, {referral_url}, {invitee_email}.'
        ),
    )
    body_html_template = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Full HTML email body. Leave empty to use the built-in default file. '
            'Use the same placeholders as the subject. See admin instructions above the fields.'
        ),
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('slug',)
        verbose_name = 'Email message template'
        verbose_name_plural = 'Email message templates'

    def __str__(self):
        return self.name or self.slug


class OTP(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    user  = models.CharField(max_length=500, db_index=True)
    otp = models.CharField(max_length=10)
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'type', '-created'])]

    def __str__(self):
        return "{} ({}) : ".format(self.user, self.get_type_display(), self.otp)
