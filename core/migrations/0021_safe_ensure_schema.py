# Safe, idempotent schema sync: create tables/columns only if they do not exist.
# Applicable for all models across all installed apps.

from django.db import migrations

from core.safe_schema_utils import safe_ensure_all_apps_schema


def safe_forward(apps, schema_editor):
    """Ensure all app tables and columns exist. No-op where already present."""
    # Optionally exclude system apps that are managed elsewhere
    safe_ensure_all_apps_schema(apps, schema_editor, exclude_apps=None)


def safe_reverse(apps, schema_editor):
    """Reverse is a no-op: we do not drop tables/columns for safety."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_remove_fourpillarsassessment_guide_content"),
    ]

    operations = [
        migrations.RunPython(safe_forward, safe_reverse),
    ]
