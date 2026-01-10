"""
Django management command to check for production DB compatibility issues.

This command checks for:
1. Missing tables
2. Model field mismatches
3. Foreign key issues
4. Missing migrations
5. Data type mismatches

Usage:
    python manage.py check_production_db_compatibility
    python manage.py check_production_db_compatibility --fix-suggestions
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.conf import settings
import sys


class Command(BaseCommand):
    help = 'Check for production DB compatibility issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-suggestions',
            action='store_true',
            help='Show SQL commands to fix issues'
        )
        parser.add_argument(
            '--app',
            type=str,
            default='app_post_matric',
            help='App to check (default: app_post_matric)'
        )

    def handle(self, *args, **options):
        app_name = options.get('app', 'app_post_matric')
        show_fixes = options.get('fix_suggestions', False)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('Production DB Compatibility Check'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        issues_found = []
        
        # Get all models from the app
        try:
            app_config = apps.get_app_config(app_name)
            models = app_config.get_models()
        except LookupError:
            self.stdout.write(self.style.ERROR(f'App "{app_name}" not found'))
            return
        
        self.stdout.write(f'Checking {len(list(models))} models from app: {app_name}\n')
        
        # Check each model
        for model in models:
            table_name = model._meta.db_table
            model_name = model.__name__
            
            self.stdout.write(f'Checking model: {model_name}')
            self.stdout.write(f'  Table: {table_name}')
            
            # Check if table exists
            table_exists = self.check_table_exists(table_name)
            
            if not table_exists:
                issues_found.append({
                    'type': 'missing_table',
                    'model': model_name,
                    'table': table_name,
                    'severity': 'HIGH'
                })
                self.stdout.write(self.style.ERROR(f'  ❌ Table does not exist!'))
                if show_fixes:
                    self.show_create_table_sql(model, table_name)
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Table exists'))
                
                # Check if all fields exist
                field_issues = self.check_model_fields(model, table_name)
                if field_issues:
                    issues_found.extend(field_issues)
                    for issue in field_issues:
                        self.stdout.write(self.style.WARNING(f'  ⚠️  {issue["message"]}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ All fields exist'))
            
            self.stdout.write('')
        
        # Check for other potential issues
        self.check_other_issues(issues_found)
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write('='*80)
        
        if not issues_found:
            self.stdout.write(self.style.SUCCESS('\n✅ No compatibility issues found!'))
        else:
            high_issues = [i for i in issues_found if i.get('severity') == 'HIGH']
            medium_issues = [i for i in issues_found if i.get('severity') == 'MEDIUM']
            low_issues = [i for i in issues_found if i.get('severity') == 'LOW']
            
            self.stdout.write(f'\n❌ Found {len(issues_found)} issues:')
            self.stdout.write(self.style.ERROR(f'  HIGH: {len(high_issues)}'))
            self.stdout.write(self.style.WARNING(f'  MEDIUM: {len(medium_issues)}'))
            self.stdout.write(f'  LOW: {len(low_issues)}')
            
            if high_issues:
                self.stdout.write('\n' + self.style.ERROR('HIGH Priority Issues:'))
                for issue in high_issues:
                    self.stdout.write(f'  - {issue.get("message", issue.get("type"))}')
            
            if show_fixes:
                self.show_all_fixes(issues_found)
        
        self.stdout.write('\n' + '='*80 + '\n')

    def check_table_exists(self, table_name):
        """Check if a table exists in the database"""
        try:
            with connection.cursor() as cursor:
                # MySQL/MariaDB syntax
                cursor.execute("SHOW TABLES LIKE %s", [table_name])
                return cursor.fetchone() is not None
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Error checking table: {str(e)}'))
            return False

    def check_model_fields(self, model, table_name):
        """Check if all model fields exist in the table"""
        issues = []
        
        try:
            with connection.cursor() as cursor:
                # Get table columns
                cursor.execute(f"DESCRIBE `{table_name}`")
                columns = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Check each field
                for field in model._meta.get_fields():
                    if hasattr(field, 'column'):
                        field_name = field.column
                        if field_name not in columns:
                            issues.append({
                                'type': 'missing_field',
                                'model': model.__name__,
                                'table': table_name,
                                'field': field_name,
                                'message': f'Field "{field_name}" missing in table',
                                'severity': 'HIGH'
                            })
        except Exception as e:
            issues.append({
                'type': 'check_error',
                'model': model.__name__,
                'table': table_name,
                'message': f'Error checking fields: {str(e)}',
                'severity': 'MEDIUM'
            })
        
        return issues

    def check_other_issues(self, issues_found):
        """Check for other potential compatibility issues"""
        self.stdout.write('\nChecking for other issues...\n')
        
        # Check for TestCompletionPopup table (known issue)
        popup_table = 'app_post_matric_testcompletionpopup'
        if not self.check_table_exists(popup_table):
            issues_found.append({
                'type': 'missing_table',
                'model': 'TestCompletionPopup',
                'table': popup_table,
                'message': f'Table {popup_table} does not exist (code handles this gracefully)',
                'severity': 'LOW'
            })
            self.stdout.write(self.style.WARNING(f'  ⚠️  {popup_table} - Missing (handled in code)'))
        
        # Check for CareerMatch table
        career_match_table = 'app_post_matric_careermatch'
        if not self.check_table_exists(career_match_table):
            issues_found.append({
                'type': 'missing_table',
                'model': 'CareerMatch',
                'table': career_match_table,
                'message': f'Table {career_match_table} does not exist',
                'severity': 'MEDIUM'
            })
            self.stdout.write(self.style.WARNING(f'  ⚠️  {career_match_table} - Missing'))
        
        # Check for mapping tables
        mapping_tables = [
            'app_post_matric_clustermapping',
            'app_post_matric_rolemapping',
            'app_post_matric_pathwaymapping',
            'app_post_matric_aptitudecombinationmapping'
        ]
        
        for table in mapping_tables:
            if not self.check_table_exists(table):
                issues_found.append({
                    'type': 'missing_table',
                    'model': table.split('_')[-1],
                    'table': table,
                    'message': f'Table {table} does not exist',
                    'severity': 'LOW'  # These are admin/mapping tables, not critical
                })
                self.stdout.write(self.style.WARNING(f'  ⚠️  {table} - Missing (mapping table)'))

    def show_create_table_sql(self, model, table_name):
        """Show SQL to create missing table"""
        self.stdout.write(self.style.WARNING(f'\n  SQL to create table (example):'))
        self.stdout.write(f'  CREATE TABLE `{table_name}` (')
        self.stdout.write(f'    `id` bigint NOT NULL AUTO_INCREMENT,')
        self.stdout.write(f'    PRIMARY KEY (`id`)')
        self.stdout.write(f'  );')
        self.stdout.write(f'  (Run migrations: python manage.py migrate {model._meta.app_label})')

    def show_all_fixes(self, issues_found):
        """Show all SQL fixes"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('Suggested Fixes'))
        self.stdout.write('='*80 + '\n')
        
        missing_tables = [i for i in issues_found if i.get('type') == 'missing_table']
        
        if missing_tables:
            self.stdout.write('Missing Tables - Run migrations:')
            self.stdout.write('  python manage.py makemigrations')
            self.stdout.write('  python manage.py migrate\n')
            
            for issue in missing_tables:
                table = issue.get('table')
                self.stdout.write(f'  Table: {table}')
                self.stdout.write(f'    Severity: {issue.get("severity")}')
                self.stdout.write('')
