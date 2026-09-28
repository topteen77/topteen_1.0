"""Add education_audience on institute students without rewriting existing tables."""

from django.db import migrations

from core.safe_schema_utils import safe_add_field_if_not_exists, table_exists


def add_education_audience(apps, schema_editor):
    from institute.models import StudentManagement

    table_name = StudentManagement._meta.db_table
    if not table_exists(schema_editor.connection, table_name):
        return
    field = StudentManagement._meta.get_field('education_audience')
    safe_add_field_if_not_exists(schema_editor, StudentManagement, field)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('core', '0058_ai_feature_quota'),
    ]

    operations = [
        migrations.RunPython(add_education_audience, noop_reverse),
    ]
