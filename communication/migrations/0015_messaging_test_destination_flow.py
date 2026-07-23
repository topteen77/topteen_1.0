# Generated manually for stepped messaging flow (test destination)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0014_messaging_wa_template_fetch'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagingsettings',
            name='test_destination',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'E.164 phone for admin Test / Sandbox sends (e.g. +9198…). '
                    'Plivo sandbox often requires a verified destination number.'
                ),
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name='messagingsettings',
            name='sender_mode',
            field=models.CharField(
                choices=[
                    ('production', 'Production (live From numbers + optional Test button)'),
                    ('testing', 'Sandbox / testing only (test button only; blocked on production app)'),
                ],
                default='production',
                help_text=(
                    'Step 3a: Production = save + Test button (needs From number). '
                    'Sandbox = testing button only. Auto-switches to Sandbox when Step 4 finds no From number. '
                    'Sandbox is blocked when ENVIRONMENT=production and DEBUG=False.'
                ),
                max_length=20,
            ),
        ),
    ]
