# Migration to fix duplicate index issue
# This migration safely handles the case where index might already exist

from django.db import migrations


def check_and_fix_indexes(apps, schema_editor):
    """Safely check and fix indexes - skip if already exists"""
    with schema_editor.connection.cursor() as cursor:
        # Check if the new index already exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = 'user_analytics_ga4session' 
            AND index_name = 'user_analyt_ga4_cli_d86f7b_idx'
        """)
        new_index_exists = cursor.fetchone()[0] > 0
        
        # Check if old index still exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = 'user_analytics_ga4session' 
            AND index_name = 'user_analy_ga4_cli_idx'
        """)
        old_index_exists = cursor.fetchone()[0] > 0
        
        # If new index exists, we're good - do nothing
        if new_index_exists:
            return
        
        # If old index exists but new doesn't, rename it
        if old_index_exists:
            try:
                cursor.execute(
                    "ALTER TABLE user_analytics_ga4session RENAME INDEX `user_analy_ga4_cli_idx` TO `user_analyt_ga4_cli_d86f7b_idx`"
                )
            except Exception as e:
                # If rename fails (e.g., index already exists with different name), skip
                pass


def reverse_fix_indexes(apps, schema_editor):
    """Reverse operation - not needed but included for completeness"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('user_analytics', '0006_add_journey_tracking_fields'),
    ]

    operations = [
        migrations.RunPython(
            check_and_fix_indexes,
            reverse_fix_indexes,
        ),
    ]
