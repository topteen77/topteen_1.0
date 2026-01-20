#!/usr/bin/env python
"""
Script to run GA4Session migration manually.
This can be used when Django migration cannot run due to missing dependencies.
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
    print(f"Warning: Could not setup Django: {e}")
    print("You may need to run the SQL manually. See RUN_MIGRATION.md")
    sys.exit(1)

from django.db import connection

def run_migration_sql():
    """Run the migration SQL commands"""
    print("=" * 80)
    print("GA4Session Migration Script")
    print("=" * 80)
    
    sql_file = os.path.join(
        os.path.dirname(__file__),
        'user_analytics/migrations/manual_sql_0002_ga4_session_simple.sql'
    )
    
    if not os.path.exists(sql_file):
        print(f"Error: SQL file not found: {sql_file}")
        return False
    
    # Read SQL file
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    # Remove comments and split into statements
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        line = line.strip()
        # Skip comments and empty lines
        if line.startswith('--') or not line:
            continue
        # Skip USE statement (we'll use Django's connection)
        if line.upper().startswith('USE '):
            continue
        
        current_statement.append(line)
        
        # Check if statement is complete
        if line.endswith(';'):
            statement = ' '.join(current_statement)
            if statement:
                statements.append(statement)
            current_statement = []
    
    print(f"\nFound {len(statements)} SQL statements to execute\n")
    
    try:
        with connection.cursor() as cursor:
            for i, statement in enumerate(statements, 1):
                try:
                    print(f"Executing statement {i}/{len(statements)}...")
                    cursor.execute(statement)
                    print(f"  ✓ Success")
                except Exception as e:
                    error_msg = str(e)
                    # Check if it's a "already exists" error (which is OK)
                    if 'already exists' in error_msg.lower() or 'Duplicate key' in error_msg:
                        print(f"  ⚠ Skipped (already exists): {error_msg[:100]}")
                    else:
                        print(f"  ✗ Error: {error_msg[:200]}")
                        raise
        
        # Commit transaction
        connection.commit()
        
        print("\n" + "=" * 80)
        print("Migration completed successfully!")
        print("=" * 80)
        
        # Verify
        print("\nVerifying migration...")
        with connection.cursor() as cursor:
            # Check column
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'user_analytics_userjourney' 
                AND COLUMN_NAME = 'ga4_client_id'
            """)
            col_exists = cursor.fetchone()[0] > 0
            print(f"  ga4_client_id column: {'✓ EXISTS' if col_exists else '✗ MISSING'}")
            
            # Check table
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            table_exists = cursor.fetchone()[0] > 0
            print(f"  GA4Session table: {'✓ EXISTS' if table_exists else '✗ MISSING'}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print("\nYou can try running the SQL manually:")
        print(f"  mysql -u username -p database_name < {sql_file}")
        return False

if __name__ == '__main__':
    success = run_migration_sql()
    sys.exit(0 if success else 1)
