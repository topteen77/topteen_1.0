from django.db import migrations


def repopulate_still_empty_templates(apps, schema_editor):
    from communication.builtin_email_content import populate_template_defaults
    from communication.email_template_registry import EMAIL_TEMPLATE_REGISTRY

    EmailMessageTemplate = apps.get_model('communication', 'EmailMessageTemplate')
    for slug in EMAIL_TEMPLATE_REGISTRY:
        obj = EmailMessageTemplate.objects.filter(slug=slug).first()
        if not obj:
            continue
        if not (obj.subject_template or '').strip() or not (obj.body_html_template or '').strip():
            populate_template_defaults(obj, force=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0007_prefill_email_template_content'),
    ]

    operations = [
        migrations.RunPython(repopulate_still_empty_templates, noop_reverse),
    ]
