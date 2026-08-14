from django.db import migrations


def prefill_email_template_content(apps, schema_editor):
    from communication.builtin_email_content import populate_template_defaults
    from communication.email_template_registry import EMAIL_TEMPLATE_REGISTRY

    EmailMessageTemplate = apps.get_model('communication', 'EmailMessageTemplate')
    for slug in EMAIL_TEMPLATE_REGISTRY:
        obj = EmailMessageTemplate.objects.filter(slug=slug).first()
        if obj:
            populate_template_defaults(obj, force=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0006_alter_emailmessagetemplate_body_html_template_and_more'),
    ]

    operations = [
        migrations.RunPython(prefill_email_template_content, noop_reverse),
    ]
