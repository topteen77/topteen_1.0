# Generated manually for DashboardPointRule.label

from django.db import migrations, models


RULE_LABELS = {
    'registration': 'Account registration',
    'profile_complete': 'Profile completion',
    'payment_success': 'Test payment',
    'personality_test_complete': 'Personality test completion',
    'motivation_test_complete': 'Motivation test completion',
    'interest_test_complete': 'Interest test completion',
    'aptitude_test_complete': 'Aptitude test completion',
    'report_reading': 'Report reading',
    'test1_complete': 'Personality test (Part 1)',
    'test2_complete': 'Interest test (Part 2)',
    'test3_complete': 'Aptitude test (Part 3)',
    'numerical_complete': 'Numerical reasoning',
    'verbal_complete': 'Verbal reasoning',
    'logical_complete': 'Logical reasoning',
    'emotional_complete': 'Emotional intelligence',
    'machanical_complete': 'Mechanical reasoning',
    'language_complete': 'Language & spelling',
    'spatial_complete': 'Spatial reasoning',
    'career_direction_complete': 'Career direction test',
    'psychometric_test_completed': 'Psychometric test completed',
}


def populate_labels(apps, schema_editor):
    DashboardPointRule = apps.get_model('core', 'DashboardPointRule')
    for rule in DashboardPointRule.objects.all().only('id', 'rule_key', 'label'):
        if (rule.label or '').strip():
            continue
        label = RULE_LABELS.get(rule.rule_key) or rule.rule_key.replace('_', ' ').title()
        DashboardPointRule.objects.filter(pk=rule.pk).update(label=label)


def clear_labels(apps, schema_editor):
    DashboardPointRule = apps.get_model('core', 'DashboardPointRule')
    DashboardPointRule.objects.all().update(label='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_translatelanguage'),
    ]

    operations = [
        migrations.AddField(
            model_name='dashboardpointrule',
            name='label',
            field=models.CharField(
                blank=True,
                help_text='Display label shown in admin and student Points Breakdown.',
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name='dashboardpointrule',
            name='order',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Display order in admin and dashboard (lower = first). Drag rows on the list to reorder.',
            ),
        ),
        migrations.RunPython(populate_labels, clear_labels),
    ]
