from django import forms
from ckeditor.widgets import CKEditorWidget

from .models import EmailMessageTemplate


class EmailMessageTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = EmailMessageTemplate
        fields = '__all__'
        widgets = {
            'body_html_template': CKEditorWidget(config_name='email_template'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'body_html_template' in self.fields:
            self.fields['body_html_template'].help_text = (
                'HTML email body. Placeholders: {invitee_name}, {inviter_name}, '
                '{inviter_email}, {invitee_email}, {referral_url} (no http), {referral_url_full}. '
                'CKEditor link: use http://{referral_url}'
            )
        if 'subject_template' in self.fields:
            self.fields['subject_template'].widget.attrs.update({
                'style': 'background:#ffffff;color:#111111;',
            })
