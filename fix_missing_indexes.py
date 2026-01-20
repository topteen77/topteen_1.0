#!/usr/bin/env python
"""
Script to add missing indexes to user_analytics_ga4session table.
Run this if you get "Key 'user_analy_ga4_cli_idx' doesn't exist" error.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error: Could not setup Django: {e}")
    sys.exit(1)

from django.db import connection

def add_missing_indexes():
    """Add missing indexes to GA4Session table"""
    print("=" * 80)
    print("Adding Missing Indexes to GA4Session Table")
    print("=" * 80)
    
    indexes = [
        {
            'name': 'user_analy_ga4_cli_idx',
            'sql': 'CREATE INDEX `user_analy_ga4_cli_idx` ON `user_analytics_ga4session` (`ga4_client_id`, `date`)'
        },
        {
            'name': 'user_analy_django__idx',
            'sql': 'CREATE INDEX `user_analy_django__idx` ON `user_analytics_ga4session` (`django_session_id`, `date`)'
        },
        {
            'name': 'user_analy_user_id_idx',
            'sql': 'CREATE INDEX `user_analy_user_id_idx` ON `user_analytics_ga4session` (`user_id`, `date`)'
        },
        {
            'name': 'user_analy_date_so_idx',
            'sql': 'CREATE INDEX `user_analy_date_so_idx` ON `user_analytics_ga4session` (`date`, `source`, `country`, `device`)'
        },
        {
            'name': 'user_analy_synced__idx',
            'sql': 'CREATE INDEX `user_analy_synced__idx` ON `user_analytics_ga4session` (`synced_at`)'
        },
        {
            'name': 'user_analytics_ga4session_user_id_fk',
            'sql': 'CREATE INDEX `user_analytics_ga4session_user_id_fk` ON `user_analytics_ga4session` (`user_id`)'
        },
        {
            'name': 'user_analytics_ga4session_source_idx',
            'sql': 'CREATE INDEX `user_analytics_ga4session_source_idx` ON `user_analytics_ga4session` (`source`)'
        },
        {
            'name': 'user_analytics_ga4session_country_idx',
            'sql': 'CREATE INDEX `user_analytics_ga4session_country_idx` ON `user_analytics_ga4session` (`country`)'
        },
        {
            'name': 'user_analytics_ga4session_device_idx',
            'sql': 'CREATE INDEX `user_analytics_ga4session_device_idx` ON `user_analytics_ga4session` (`device`)'
        },
        {
            'name': 'user_analytics_ga4session_entry_page_idx',
            'sql': 'CREATE INDEX `user_analytics_ga4session_entry_page_idx` ON `user_analytics_ga4session` (`entry_page`(255))'
        },
        {
            'name': 'user_analytics_ga4session_unique_idx',
            'sql': """CREATE UNIQUE INDEX `user_analytics_ga4session_unique_idx` 
ON `user_analytics_ga4session` (
    `ga4_client_id`(100),
    `date`,
    `source`(100),
    `country`,
    `device`,
    `entry_page`(100)
)"""
        },
    ]
    
    try:
        with connection.cursor() as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            if cursor.fetchone()[0] == 0:
                print("\n✗ Error: Table 'user_analytics_ga4session' does not exist!")
                print("Please run the CREATE TABLE script first.")
                return False
            
            print(f"\nFound {len(indexes)} indexes to create\n")
            
            created = 0
            skipped = 0
            errors = 0
            
            for idx in indexes:
                try:
                    print(f"Creating index: {idx['name']}...")
                    cursor.execute(idx['sql'])
                    print(f"  ✓ Success")
                    created += 1
                except Exception as e:
                    error_msg = str(e)
                    # Check if it's a "Duplicate key" error (index already exists)
                    if 'Duplicate key' in error_msg or 'already exists' in error_msg.lower():
                        print(f"  ⚠ Skipped (already exists)")
                        skipped += 1
                    else:
                        print(f"  ✗ Error: {error_msg[:200]}")
                        errors += 1
            
            # Commit transaction
            connection.commit()
            
            print("\n" + "=" * 80)
            print(f"Index creation completed!")
            print(f"  Created: {created}")
            print(f"  Skipped (already exists): {skipped}")
            print(f"  Errors: {errors}")
            print("=" * 80)
            
            # Verify indexes
            print("\nVerifying indexes...")
            cursor.execute("SHOW INDEXES FROM `user_analytics_ga4session`")
            existing_indexes = [row[2] for row in cursor.fetchall()]  # Index name is in column 2
            
            print(f"\nFound {len(existing_indexes)} indexes in table:")
            for idx_name in sorted(set(existing_indexes)):
                print(f"  - {idx_name}")
            
            return errors == 0
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

if __name__ == '__main__':
    success = add_missing_indexes()
    sys.exit(0 if success else 1)
