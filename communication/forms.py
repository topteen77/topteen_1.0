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
                'HTML email body. Use the editor toolbar or click Source to paste HTML and '
                'placeholders like {inviter_name}, {referral_url}, {invitee_email}.'
            )
