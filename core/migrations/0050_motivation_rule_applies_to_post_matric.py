from django.db import migrations


def set_motivation_applies_to_post_matric(apps, schema_editor):
    DashboardPointRule = apps.get_model('core', 'DashboardPointRule')
    DashboardPointRule.objects.filter(rule_key='motivation_test_complete').update(applies_to='post_matric')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_dashboard_rule_applies_to'),
    ]

    operations = [
        migrations.RunPython(set_motivation_applies_to_post_matric, migrations.RunPython.noop),
    ]
