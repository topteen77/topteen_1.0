from django import forms
from ckeditor.widgets import CKEditorWidget

from communication.email_template_registry import get_email_template_meta
from communication.models import EmailMessageTemplate, SmsSettings, WhatsAppSettings
from communication.providers import sms_provider_choices, whatsapp_provider_choices


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


class SmsSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = SmsSettings
        fields = '__all__'
        widgets = {
            'smartping_password': forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
            'plivo_auth_token': forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
            'message_template': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'test_destination': forms.TextInput(attrs={'placeholder': '+9198XXXXXXXX', 'style': 'max-width:280px;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        help_text = self.fields['provider'].help_text
        self.fields['provider'] = forms.ChoiceField(
            choices=sms_provider_choices() or [('smartping', 'SmartPing'), ('plivo', 'Plivo')],
            initial=getattr(self.instance, 'provider', None) or 'smartping',
            help_text=help_text,
        )


class WhatsAppSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = WhatsAppSettings
        fields = '__all__'
        widgets = {
            'plivo_auth_token': forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
            'test_destination': forms.TextInput(attrs={'placeholder': '+9198XXXXXXXX', 'style': 'max-width:280px;'}),
            'otp_template_preview': forms.Textarea(attrs={'rows': 4, 'cols': 80, 'readonly': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        help_text = self.fields['provider'].help_text
        self.fields['provider'] = forms.ChoiceField(
            choices=whatsapp_provider_choices() or [('plivo', 'Plivo')],
            initial=getattr(self.instance, 'provider', None) or 'plivo',
            help_text=help_text,
        )
