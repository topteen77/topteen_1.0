# Generated data migration: seed default Dashboard Level Bands and Point Rules

from django.db import migrations


def seed_dashboard_defaults(apps, schema_editor):
    DashboardLevelBand = apps.get_model('core', 'DashboardLevelBand')
    DashboardPointRule = apps.get_model('core', 'DashboardPointRule')
    DashboardTrophyDefinition = apps.get_model('core', 'DashboardTrophyDefinition')

    if not DashboardLevelBand.objects.exists():
        for order, (name, min_points) in enumerate([
            ('Rookie', 0), ('Explorer', 500), ('Champion', 1000), ('Legend', 2000)
        ]):
            DashboardLevelBand.objects.create(name=name, min_points=min_points, order=order)

    if not DashboardPointRule.objects.exists():
        rules = [
            ('profile_complete', 100), ('test1_complete', 150), ('test2_complete', 150),
            ('test3_complete', 200), ('numerical_complete', 50), ('verbal_complete', 50),
            ('logical_complete', 50), ('emotional_complete', 50), ('machanical_complete', 50),
            ('language_complete', 50), ('spatial_complete', 50), ('career_direction_complete', 200),
            ('payment_success', 50), ('psychometric_test_completed', 200), ('registration', 25),
        ]
        for rule_key, points in rules:
            DashboardPointRule.objects.create(rule_key=rule_key, points=points, active=True)

    if not DashboardTrophyDefinition.objects.exists():
        keys = [
            'profile_complete', 'test1_complete', 'test2_complete', 'test3_complete',
            'numerical_complete', 'verbal_complete', 'logical_complete', 'emotional_complete',
            'machanical_complete', 'language_complete', 'spatial_complete',
            'career_direction_complete', 'payment_success',
        ]
        for key in keys:
            DashboardTrophyDefinition.objects.create(rule_key=key, label=key.replace('_', ' ').title(), active=True)


def reverse_seed(apps, schema_editor):
    # Optional: leave data in place on reverse
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_dashboard_stats_models'),
    ]

    operations = [
        migrations.RunPython(seed_dashboard_defaults, reverse_seed),
    ]
