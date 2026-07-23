from django.db import migrations


def reload_content_only_templates(apps, schema_editor):
    from communication.builtin_email_content import populate_template_defaults
    from communication.email_template_registry import EMAIL_TEMPLATE_REGISTRY

    EmailMessageTemplate = apps.get_model('communication', 'EmailMessageTemplate')
    for slug in EMAIL_TEMPLATE_REGISTRY:
        obj = EmailMessageTemplate.objects.filter(slug=slug).first()
        if obj:
            populate_template_defaults(obj, force=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0008_repopulate_empty_email_templates'),
    ]

    operations = [
        migrations.RunPython(reload_content_only_templates, noop_reverse),
    ]
