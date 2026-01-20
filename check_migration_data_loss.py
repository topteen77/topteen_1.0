#!/usr/bin/env python
"""
Script to check if migrations will delete any data from the database.
Run this before running migrations to see what data would be lost.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.db import connection

def check_career_fields_data():
    """Check if career fields that will be removed contain any data"""
    fields_to_check = [
        'description_en',
        'eligibility',
        'eligibility_en',
        'name_en',
        'pros_cons',
        'pros_cons_en',
        'role_description',
        'role_description_en',
        'summary_en',
    ]
    
    print("\n" + "="*80)
    print("CHECKING: careers_career table - Fields to be removed")
    print("="*80)
    
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'careers_career'
        """)
        if cursor.fetchone()[0] == 0:
            print("⚠️  Table 'careers_career' does not exist - no data to check")
            return
        
        # Check each field
        cursor.execute("DESCRIBE careers_career")
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        data_found = False
        for field in fields_to_check:
            if field in existing_columns:
                # Check if field has any non-null data
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM careers_career 
                    WHERE {field} IS NOT NULL 
                    AND {field} != ''
                """)
                count = cursor.fetchone()[0]
                if count > 0:
                    data_found = True
                    print(f"⚠️  Field '{field}': {count} records with data (WILL BE DELETED)")
                else:
                    print(f"✓  Field '{field}': No data (safe to remove)")
            else:
                print(f"✓  Field '{field}': Does not exist (already removed)")
        
        if data_found:
            print("\n⚠️  WARNING: Some fields contain data that will be permanently deleted!")
            return True
        else:
            print("\n✓  All fields are empty or don't exist - safe to remove")
            return False

def check_ebook_fields_data():
    """Check if ebook fields that will be removed contain any data"""
    fields_to_remove = ['cover_image_url', 'pdf_file_url']
    fields_to_add = ['cover_image_s3_url', 'pdf_file_s3_url']
    
    print("\n" + "="*80)
    print("CHECKING: core_ebook table - Field replacements")
    print("="*80)
    print("Note: This migration REPLACES fields (cover_image_url -> cover_image_s3_url)")
    print("      Data in old fields will be lost if not migrated manually")
    print("="*80)
    
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'core_ebook'
        """)
        if cursor.fetchone()[0] == 0:
            print("⚠️  Table 'core_ebook' does not exist - no data to check")
            return False
        
        cursor.execute("DESCRIBE core_ebook")
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        data_found = False
        for field in fields_to_remove:
            if field in existing_columns:
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM core_ebook 
                    WHERE {field} IS NOT NULL 
                    AND {field} != ''
                """)
                count = cursor.fetchone()[0]
                if count > 0:
                    data_found = True
                    print(f"⚠️  Field '{field}': {count} records with data")
                    print(f"   → Will be replaced by '{fields_to_add[fields_to_remove.index(field)]}'")
                    print(f"   → Data in '{field}' will be LOST if not migrated manually!")
                else:
                    print(f"✓  Field '{field}': No data (safe to replace)")
            else:
                print(f"✓  Field '{field}': Does not exist")
        
        if data_found:
            print("\n⚠️  WARNING: Old fields contain data that will be lost!")
            print("   Consider migrating data from old fields to new fields before running migration")
            return True
        else:
            print("\n✓  No data in fields to be removed - safe to proceed")
            return False

if __name__ == '__main__':
    print("\n" + "="*80)
    print("MIGRATION DATA LOSS CHECK")
    print("="*80)
    print("\nThis script checks if migrations will delete any data from the database.")
    print("Review the results below before proceeding with migrations.\n")
    
    career_data_loss = check_career_fields_data()
    ebook_data_loss = check_ebook_fields_data()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if career_data_loss or ebook_data_loss:
        print("⚠️  WARNING: Some migrations will DELETE DATA from the database!")
        print("\nPlease review the fields listed above.")
        print("If you want to preserve this data, you need to:")
        print("1. Export the data before running migrations")
        print("2. Or modify the migrations to preserve the data")
        print("\nDo you want to proceed with migrations? (This will delete the data)")
        sys.exit(1)
    else:
        print("✓  No data loss detected - migrations are safe to run")
        print("\nYou can proceed with: python manage.py migrate")
        sys.exit(0)
