"""
Management command to truncate existing career_* tables and restore from SQL file.

This script:
1. Checks if the SQL file exists
2. Extracts all career table names from the SQL file
3. Verifies tables exist in the database
4. Truncates all career_* tables
5. Restores data from the SQL file
"""

import os
import re
import subprocess
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Truncate existing career_* tables and restore from SQL file with updated H2 tags'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-file',
            type=str,
            default='/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/career-db/processed/career_all-tables_production.sql',
            help='Path to the SQL file to restore from',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually executing',
        )
        parser.add_argument(
            '--skip-truncate',
            action='store_true',
            help='Skip truncating tables (only restore data)',
        )

    def get_tables_from_sql_file(self, sql_file_path):
        """Extract all table names from SQL file."""
        tables = []
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Match CREATE TABLE statements
                    match = re.search(r'CREATE TABLE\s+`?(\w+)`?', line, re.IGNORECASE)
                    if match:
                        table_name = match.group(1)
                        if table_name.startswith('careers_'):
                            tables.append(table_name)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading SQL file: {str(e)}'))
            return []
        
        return sorted(set(tables))

    def check_tables_exist(self, table_names):
        """Check if tables exist in the database."""
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            existing_tables = {row[0] for row in cursor.fetchall()}
        
        missing_tables = []
        existing_career_tables = []
        
        for table in table_names:
            if table in existing_tables:
                existing_career_tables.append(table)
            else:
                missing_tables.append(table)
        
        return existing_career_tables, missing_tables

    def truncate_tables(self, table_names, dry_run=False):
        """Truncate all specified tables."""
        if not table_names:
            self.stdout.write(self.style.WARNING('No tables to truncate'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nTruncating {len(table_names)} tables...'))
        
        with connection.cursor() as cursor:
            # Disable foreign key checks temporarily
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            try:
                for table in table_names:
                    if dry_run:
                        self.stdout.write(f'  [DRY RUN] Would truncate: {table}')
                    else:
                        cursor.execute(f"TRUNCATE TABLE `{table}`")
                        self.stdout.write(f'  ✓ Truncated: {table}')
            finally:
                # Re-enable foreign key checks
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully truncated {len(table_names)} tables'))

    def restore_from_sql_file(self, sql_file_path, dry_run=False):
        """Restore data from SQL file using mysql command or Django connection."""
        db_config = settings.DATABASES['default']
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Would execute: mysql -h{db_config["HOST"]} -P{db_config["PORT"]} -u{db_config["USER"]} {db_config["NAME"]} < {sql_file_path}'))
            return True
        
        self.stdout.write(self.style.SUCCESS(f'\nRestoring data from SQL file...'))
        self.stdout.write(f'  File: {sql_file_path}')
        self.stdout.write(f'  Database: {db_config["NAME"]}')
        self.stdout.write(f'  Host: {db_config["HOST"]}')
        
        # Try using mysql command first (faster for large files)
        mysql_available = subprocess.run(['which', 'mysql'], capture_output=True).returncode == 0
        
        if mysql_available:
            return self._restore_with_mysql_command(sql_file_path, db_config)
        else:
            self.stdout.write(self.style.WARNING('  mysql command not found, using Django connection (slower)...'))
            return self._restore_with_django_connection(sql_file_path)
    
    def _restore_with_mysql_command(self, sql_file_path, db_config):
        """Restore using mysql command-line client (faster)."""
        # Set password via environment variable for security
        env = os.environ.copy()
        env['MYSQL_PWD'] = db_config['PASSWORD']
        
        # Build mysql command (without password in command line)
        mysql_cmd = [
            'mysql',
            f'-h{db_config["HOST"]}',
            f'-P{db_config["PORT"]}',
            f'-u{db_config["USER"]}',
            db_config['NAME']
        ]
        
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as sql_file:
                process = subprocess.Popen(
                    mysql_cmd,
                    stdin=sql_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    self.stdout.write(self.style.ERROR(f'\n✗ Error restoring SQL file:'))
                    self.stdout.write(self.style.ERROR(stderr))
                    return False
                
                self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully restored data from SQL file'))
                return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error executing mysql command: {str(e)}'))
            return False
    
    def _restore_with_django_connection(self, sql_file_path):
        """Restore using Django database connection (slower but works without mysql client)."""
        try:
            with connection.cursor() as cursor:
                # Read SQL file in chunks
                with open(sql_file_path, 'r', encoding='utf-8') as sql_file:
                    sql_content = sql_file.read()
                    
                    # Split by semicolon and execute statements
                    # Note: This is a simple approach, may need refinement for complex SQL
                    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                    
                    self.stdout.write(f'  Executing {len(statements)} SQL statements...')
                    
                    for i, statement in enumerate(statements, 1):
                        if statement.upper().startswith('CREATE TABLE') or statement.upper().startswith('INSERT'):
                            try:
                                cursor.execute(statement)
                                if i % 100 == 0:
                                    self.stdout.write(f'  Processed {i}/{len(statements)} statements...')
                            except Exception as e:
                                # Some errors are expected (e.g., table already exists)
                                if 'already exists' not in str(e).lower():
                                    self.stdout.write(self.style.WARNING(f'  Warning at statement {i}: {str(e)[:100]}'))
                    
                    self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully restored data from SQL file'))
                    return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error restoring SQL file: {str(e)}'))
            return False

    def handle(self, *args, **options):
        sql_file_path = options['sql_file']
        dry_run = options['dry_run']
        skip_truncate = options['skip_truncate']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CAREER TABLES RESTORATION SCRIPT'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠ DRY RUN MODE - No changes will be made\n'))
        
        # Step 1: Check if SQL file exists
        self.stdout.write('\n[Step 1] Checking SQL file...')
        if not os.path.exists(sql_file_path):
            self.stdout.write(self.style.ERROR(f'✗ SQL file not found: {sql_file_path}'))
            return
        
        file_size = os.path.getsize(sql_file_path)
        self.stdout.write(self.style.SUCCESS(f'✓ SQL file found: {sql_file_path}'))
        self.stdout.write(f'  File size: {file_size / (1024*1024):.2f} MB')
        
        # Step 2: Extract table names from SQL file
        self.stdout.write('\n[Step 2] Extracting table names from SQL file...')
        sql_tables = self.get_tables_from_sql_file(sql_file_path)
        
        if not sql_tables:
            self.stdout.write(self.style.ERROR('✗ No career tables found in SQL file'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✓ Found {len(sql_tables)} career tables in SQL file:'))
        for table in sql_tables:
            self.stdout.write(f'  - {table}')
        
        # Step 3: Check if tables exist in database
        self.stdout.write('\n[Step 3] Checking if tables exist in database...')
        existing_tables, missing_tables = self.check_tables_exist(sql_tables)
        
        if existing_tables:
            self.stdout.write(self.style.SUCCESS(f'✓ Found {len(existing_tables)} existing tables in database'))
            for table in existing_tables[:5]:  # Show first 5
                self.stdout.write(f'  - {table}')
            if len(existing_tables) > 5:
                self.stdout.write(f'  ... and {len(existing_tables) - 5} more')
        
        if missing_tables:
            self.stdout.write(self.style.WARNING(f'\n⚠ {len(missing_tables)} tables are missing in database:'))
            for table in missing_tables:
                self.stdout.write(self.style.WARNING(f'  - {table}'))
            self.stdout.write(self.style.WARNING('\n⚠ WARNING: Missing tables will be created by the SQL file'))
            self.stdout.write(self.style.WARNING('  The SQL file contains CREATE TABLE statements'))
        
        # Step 4: Truncate tables
        if not skip_truncate:
            self.stdout.write('\n[Step 4] Truncating existing tables...')
            if existing_tables:
                self.truncate_tables(existing_tables, dry_run=dry_run)
            else:
                self.stdout.write(self.style.WARNING('  No existing tables to truncate'))
        else:
            self.stdout.write('\n[Step 4] Skipping truncate (--skip-truncate flag set)')
        
        # Step 5: Restore from SQL file
        self.stdout.write('\n[Step 5] Restoring data from SQL file...')
        success = self.restore_from_sql_file(sql_file_path, dry_run=dry_run)
        
        if not success and not dry_run:
            self.stdout.write(self.style.ERROR('\n✗ Restoration failed. Please check the errors above.'))
            return
        
        # Step 6: Verify restoration
        if not dry_run:
            self.stdout.write('\n[Step 6] Verifying restoration...')
            with connection.cursor() as cursor:
                # Check record counts for main tables
                main_tables = ['careers_career', 'careers_careercluster', 'careers_skill', 'careers_careerpath']
                for table in main_tables:
                    if table in existing_tables or table in sql_tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                            count = cursor.fetchone()[0]
                            self.stdout.write(f'  ✓ {table}: {count} records')
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'  ⚠ {table}: Error checking count - {str(e)}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('RESTORATION SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'SQL file: {sql_file_path}')
        self.stdout.write(f'Tables in SQL file: {len(sql_tables)}')
        self.stdout.write(f'Existing tables: {len(existing_tables)}')
        self.stdout.write(f'Missing tables: {len(missing_tables)}')
        
        if missing_tables:
            self.stdout.write(self.style.WARNING('\n⚠ Missing tables will be created by the SQL file'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠ DRY RUN - No changes were made'))
            self.stdout.write('  Run without --dry-run to execute the restoration')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Restoration process completed!'))
        
        self.stdout.write('=' * 80)

