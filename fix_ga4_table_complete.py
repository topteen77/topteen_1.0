#!/usr/bin/env python
"""
Complete fix script for GA4Session table.
This script will:
1. Add missing created column (from BaseModel)
2. Add all missing indexes
3. Verify everything works
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
from user_analytics.models import GA4Session
from datetime import date

def fix_ga4_table():
    """Complete fix for GA4Session table"""
    print("=" * 80)
    print("GA4Session Table Complete Fix")
    print("=" * 80)
    
    errors = []
    
    # Step 1: Check if table exists
    print("\nStep 1: Checking if table exists...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            if cursor.fetchone()[0] == 0:
                print("✗ Table does not exist. Please run CREATE TABLE script first.")
                return False
            print("✓ Table exists")
    except Exception as e:
        print(f"✗ Error checking table: {e}")
        return False
    
    # Step 2: Add missing created column
    print("\nStep 2: Checking created column...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'user_analytics_ga4session' 
                AND COLUMN_NAME = 'created'
            """)
            if cursor.fetchone()[0] == 0:
                print("  Adding created column...")
                cursor.execute("""
                    ALTER TABLE user_analytics_ga4session 
                    ADD COLUMN created DATETIME(6) NOT NULL 
                    DEFAULT CURRENT_TIMESTAMP(6)
                    AFTER id
                """)
                print("  ✓ Created column added")
            else:
                print("  ✓ Created column already exists")
    except Exception as e:
        error_msg = str(e)
        if 'Duplicate column' in error_msg:
            print("  ⚠ Created column already exists (different error)")
        else:
            print(f"  ✗ Error: {e}")
            errors.append(f"Created column: {e}")
    
    # Step 3: Add missing indexes
    print("\nStep 3: Adding missing indexes...")
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
    
    created = 0
    skipped = 0
    for idx in indexes:
        try:
            with connection.cursor() as cursor:
                cursor.execute(idx['sql'])
                print(f"  ✓ {idx['name']}")
                created += 1
        except Exception as e:
            error_msg = str(e)
            if 'Duplicate key' in error_msg or 'already exists' in error_msg.lower():
                print(f"  ⚠ {idx['name']} (already exists)")
                skipped += 1
            else:
                print(f"  ✗ {idx['name']}: {error_msg[:100]}")
                errors.append(f"{idx['name']}: {e}")
    
    print(f"\n  Created: {created}, Skipped: {skipped}")
    
    # Step 4: Test model functionality
    print("\nStep 4: Testing model functionality...")
    try:
        # Test create
        test_session = GA4Session.objects.create(
            ga4_client_id='test_fix_script',
            date=date.today(),
            source='test',
            country='Test',
            device='desktop',
            entry_page='/test',
            sessions_count=1,
            pageviews=1,
            users=1
        )
        print(f"  ✓ Can create records (ID: {test_session.id})")
        
        # Test query
        found = GA4Session.objects.filter(ga4_client_id='test_fix_script').first()
        if found:
            print(f"  ✓ Can query records")
        
        # Test unique constraint
        session2, created = GA4Session.objects.update_or_create(
            ga4_client_id='test_fix_script',
            date=date.today(),
            source='test',
            country='Test',
            device='desktop',
            entry_page='/test',
            defaults={'sessions_count': 2}
        )
        if not created:
            print(f"  ✓ Unique constraint works")
        
        # Clean up
        test_session.delete()
        if not created:
            session2.delete()
        print(f"  ✓ Can delete records")
        
    except Exception as e:
        print(f"  ✗ Model test failed: {e}")
        errors.append(f"Model test: {e}")
        import traceback
        traceback.print_exc()
    
    # Commit all changes
    connection.commit()
    
    # Summary
    print("\n" + "=" * 80)
    if errors:
        print("Fix completed with errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ All fixes applied successfully!")
        print("=" * 80)
        return True

if __name__ == '__main__':
    success = fix_ga4_table()
    sys.exit(0 if success else 1)
