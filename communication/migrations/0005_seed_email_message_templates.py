from django.db import migrations


def seed_email_message_templates(apps, schema_editor):
    from communication.email_template_registry import EMAIL_TEMPLATE_REGISTRY

    EmailMessageTemplate = apps.get_model('communication', 'EmailMessageTemplate')
    for slug, meta in EMAIL_TEMPLATE_REGISTRY.items():
        EmailMessageTemplate.objects.get_or_create(
            slug=slug,
            defaults={
                'name': meta['name'],
                'subject_template': '',
                'body_html_template': '',
                'is_active': True,
            },
        )


def unseed_email_message_templates(apps, schema_editor):
    from communication.email_template_registry import EMAIL_TEMPLATE_REGISTRY

    EmailMessageTemplate = apps.get_model('communication', 'EmailMessageTemplate')
    EmailMessageTemplate.objects.filter(slug__in=EMAIL_TEMPLATE_REGISTRY.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0004_utf8mb4_text_columns'),
    ]

    operations = [
        migrations.RunPython(seed_email_message_templates, unseed_email_message_templates),
    ]
