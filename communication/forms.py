from django import forms
from ckeditor.widgets import CKEditorWidget

from communication.email_template_registry import get_email_template_meta
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
        slug = (self.instance.slug if self.instance and self.instance.pk else '') or ''
        meta = get_email_template_meta(slug)
        placeholder_help = (meta.get('placeholder_help') or '').strip()
        if 'body_html_template' in self.fields:
            help_bits = [
                'Message body only (no header/footer). Shared TopTeen layout is added when sent.',
                'Use {placeholder} style — see Instructions above.',
            ]
            if placeholder_help:
                help_bits.append(placeholder_help.split('\n\n')[0])
            self.fields['body_html_template'].help_text = ' '.join(help_bits)
        if 'subject_template' in self.fields:
            self.fields['subject_template'].help_text = (
                'Prefilled from the built-in default. Use {placeholder} style — see Instructions above.'
            )
            self.fields['subject_template'].widget.attrs.update({
                'style': 'background:#ffffff;color:#111111;',
            })
