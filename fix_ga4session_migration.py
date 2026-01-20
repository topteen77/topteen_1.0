#!/usr/bin/env python
"""
Script to fix GA4Session migration issue by providing default value for 'created' field.
Run this before creating forum migrations.
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
from django.utils import timezone
from django.core.management import call_command

def fix_ga4session_created_field():
    """Add default value to existing GA4Session records"""
    print("=" * 80)
    print("Fixing GA4Session 'created' field")
    print("=" * 80)
    
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
                print("✓ GA4Session table doesn't exist yet. No fix needed.")
                return True
            
            # Check if 'created' column exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
                AND column_name = 'created'
            """)
            
            if cursor.fetchone()[0] > 0:
                print("✓ 'created' column already exists. No fix needed.")
                return True
            
            # Get count of existing rows
            cursor.execute("SELECT COUNT(*) FROM user_analytics_ga4session")
            row_count = cursor.fetchone()[0]
            
            if row_count == 0:
                print("✓ No existing rows. Migration should work without issues.")
                return True
            
            print(f"\nFound {row_count} existing rows in GA4Session table.")
            print("Adding 'created' column with default value...")
            
            # Add the column with a default value
            current_time = timezone.now()
            cursor.execute(f"""
                ALTER TABLE user_analytics_ga4session 
                ADD COLUMN created DATETIME(6) DEFAULT '{current_time.strftime('%Y-%m-%d %H:%M:%S.%f')}'
            """)
            
            # Update any NULL values (shouldn't be any, but just in case)
            cursor.execute(f"""
                UPDATE user_analytics_ga4session 
                SET created = '{current_time.strftime('%Y-%m-%d %H:%M:%S.%f')}' 
                WHERE created IS NULL
            """)
            
            print("✓ Successfully added 'created' column with default value")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fix_ga4session_created_field()
    if success:
        print("\n" + "=" * 80)
        print("You can now run: python manage.py makemigrations forum")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("Fix failed. Please handle the migration manually.")
        print("=" * 80)
        sys.exit(1)
