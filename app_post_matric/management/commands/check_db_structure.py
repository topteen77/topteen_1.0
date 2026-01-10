"""
Django management command to check database structure compatibility.

This command performs comprehensive database structure checks:
1. Missing tables - Tables defined in models but not in database
2. Missing fields - Fields defined in models but not in database tables
3. Field mismatches - Field types, constraints, or properties that don't match

Usage:
    python manage.py check_db_structure
    python manage.py check_db_structure --app app_post_matric
    python manage.py check_db_structure --all-apps
    python manage.py check_db_structure --output report.txt
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.conf import settings
import sys
from collections import defaultdict


class Command(BaseCommand):
    help = 'Check database structure for missing tables, fields, and mismatches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='App to check (e.g., app_post_matric). If not specified, checks all apps.'
        )
        parser.add_argument(
            '--all-apps',
            action='store_true',
            help='Check all installed apps'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for report (e.g., db_structure_report.txt)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed field information'
        )

    def handle(self, *args, **options):
        app_name = options.get('app')
        all_apps = options.get('all_apps', False)
        output_file = options.get('output')
        detailed = options.get('detailed', False)
        
        # Determine which apps to check
        apps_to_check = []
        if app_name:
            try:
                app_config = apps.get_app_config(app_name)
                apps_to_check = [app_config]
            except LookupError:
                self.stdout.write(self.style.ERROR(f'App "{app_name}" not found'))
                return
        elif all_apps:
            apps_to_check = [apps.get_app_config(app) for app in settings.INSTALLED_APPS 
                           if '.' not in app]  # Only Django apps, not third-party
        else:
            # Default: check app_post_matric
            try:
                app_config = apps.get_app_config('app_post_matric')
                apps_to_check = [app_config]
            except LookupError:
                self.stdout.write(self.style.ERROR('Default app "app_post_matric" not found'))
                return
        
        # Collect all issues
        all_issues = {
            'missing_tables': [],
            'missing_fields': [],
            'field_mismatches': []
        }
        
        # Generate report
        report_lines = []
        report_lines.append('=' * 80)
        report_lines.append('DATABASE STRUCTURE CHECK REPORT')
        report_lines.append('=' * 80)
        report_lines.append('')
        
        for app_config in apps_to_check:
            app_name = app_config.name
            report_lines.append(f'Checking app: {app_name}')
            report_lines.append('-' * 80)
            report_lines.append('')
            
            models = app_config.get_models()
            
            for model in models:
                model_name = model.__name__
                table_name = model._meta.db_table
                
                self.stdout.write(f'Checking model: {model_name} (table: {table_name})')
                
                # Part 1: Check if table exists
                table_exists = self.check_table_exists(table_name)
                
                if not table_exists:
                    issue = {
                        'app': app_name,
                        'model': model_name,
                        'table': table_name,
                        'severity': 'HIGH'
                    }
                    all_issues['missing_tables'].append(issue)
                    report_lines.append(f'❌ MISSING TABLE: {table_name}')
                    report_lines.append(f'   Model: {model_name}')
                    report_lines.append(f'   App: {app_name}')
                    report_lines.append('')
                    self.stdout.write(self.style.ERROR(f'  ❌ Table does not exist!'))
                    continue
                
                self.stdout.write(self.style.SUCCESS(f'  ✅ Table exists'))
                
                # Part 2 & 3: Check fields (missing and mismatches)
                field_issues = self.check_model_fields(model, table_name, detailed)
                
                for issue in field_issues:
                    if issue['type'] == 'missing_field':
                        all_issues['missing_fields'].append(issue)
                        report_lines.append(f'⚠️  MISSING FIELD: {issue["field"]}')
                        report_lines.append(f'   Table: {table_name}')
                        report_lines.append(f'   Model: {model_name}')
                        report_lines.append(f'   Expected Type: {issue.get("expected_type", "N/A")}')
                        report_lines.append('')
                        self.stdout.write(self.style.WARNING(f'  ⚠️  Missing field: {issue["field"]}'))
                    elif issue['type'] == 'field_mismatch':
                        all_issues['field_mismatches'].append(issue)
                        report_lines.append(f'⚠️  FIELD MISMATCH: {issue["field"]}')
                        report_lines.append(f'   Table: {table_name}')
                        report_lines.append(f'   Model: {model_name}')
                        report_lines.append(f'   Expected: {issue.get("expected", "N/A")}')
                        report_lines.append(f'   Actual: {issue.get("actual", "N/A")}')
                        report_lines.append(f'   Issue: {issue.get("message", "N/A")}')
                        report_lines.append('')
                        self.stdout.write(self.style.WARNING(f'  ⚠️  Field mismatch: {issue["field"]}'))
                
                if not field_issues:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ All fields OK'))
                
                report_lines.append('')
        
        # Summary
        report_lines.append('')
        report_lines.append('=' * 80)
        report_lines.append('SUMMARY')
        report_lines.append('=' * 80)
        report_lines.append('')
        
        total_issues = (len(all_issues['missing_tables']) + 
                       len(all_issues['missing_fields']) + 
                       len(all_issues['field_mismatches']))
        
        if total_issues == 0:
            report_lines.append('✅ No issues found! Database structure matches models.')
            self.stdout.write(self.style.SUCCESS('\n✅ No issues found!'))
        else:
            report_lines.append(f'Total Issues Found: {total_issues}')
            report_lines.append('')
            report_lines.append(f'1. Missing Tables: {len(all_issues["missing_tables"])}')
            report_lines.append(f'2. Missing Fields: {len(all_issues["missing_fields"])}')
            report_lines.append(f'3. Field Mismatches: {len(all_issues["field_mismatches"])}')
            report_lines.append('')
            
            # Detailed breakdown
            if all_issues['missing_tables']:
                report_lines.append('MISSING TABLES:')
                for issue in all_issues['missing_tables']:
                    report_lines.append(f'  - {issue["table"]} (Model: {issue["model"]}, App: {issue["app"]})')
                report_lines.append('')
            
            if all_issues['missing_fields']:
                report_lines.append('MISSING FIELDS:')
                for issue in all_issues['missing_fields']:
                    report_lines.append(f'  - {issue["table"]}.{issue["field"]} (Model: {issue["model"]}, Expected: {issue.get("expected_type", "N/A")})')
                report_lines.append('')
            
            if all_issues['field_mismatches']:
                report_lines.append('FIELD MISMATCHES:')
                for issue in all_issues['field_mismatches']:
                    report_lines.append(f'  - {issue["table"]}.{issue["field"]}: {issue.get("message", "N/A")}')
                report_lines.append('')
            
            self.stdout.write(f'\n❌ Found {total_issues} issues:')
            self.stdout.write(self.style.ERROR(f'  Missing Tables: {len(all_issues["missing_tables"])}'))
            self.stdout.write(self.style.WARNING(f'  Missing Fields: {len(all_issues["missing_fields"])}'))
            self.stdout.write(self.style.WARNING(f'  Field Mismatches: {len(all_issues["field_mismatches"])}'))
        
        report_lines.append('=' * 80)
        report_lines.append('')
        
        # Output report
        report_text = '\n'.join(report_lines)
        
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report_text)
                self.stdout.write(self.style.SUCCESS(f'\n✅ Report saved to: {output_file}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n❌ Error saving report: {str(e)}'))
        else:
            # Print to console
            self.stdout.write('\n' + report_text)
        
        self.stdout.write('\n' + '=' * 80 + '\n')

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

    def check_model_fields(self, model, table_name, detailed=False):
        """Check if all model fields exist and match in the table"""
        issues = []
        
        try:
            with connection.cursor() as cursor:
                # Get table structure
                cursor.execute(f"DESCRIBE `{table_name}`")
                db_columns = {}
                for row in cursor.fetchall():
                    column_name = row[0]
                    column_type = row[1]
                    is_null = row[2]
                    key = row[3]
                    default = row[4]
                    extra = row[5]
                    
                    db_columns[column_name] = {
                        'type': column_type,
                        'null': is_null == 'YES',
                        'key': key,
                        'default': default,
                        'extra': extra
                    }
                
                # Check each model field
                for field in model._meta.get_fields():
                    if not hasattr(field, 'column'):
                        continue  # Skip non-database fields (e.g., ManyToMany)
                    
                    field_name = field.column
                    field_type = type(field).__name__
                    
                    # Check if field exists in database
                    if field_name not in db_columns:
                        issues.append({
                            'type': 'missing_field',
                            'model': model.__name__,
                            'table': table_name,
                            'field': field_name,
                            'expected_type': field_type,
                            'severity': 'HIGH'
                        })
                        continue
                    
                    # Field exists - check for mismatches
                    db_column = db_columns[field_name]
                    db_type = db_column['type']
                    
                    # Check field type mismatch
                    type_mismatch = self.check_field_type_mismatch(field, db_type, db_column)
                    if type_mismatch:
                        issues.append({
                            'type': 'field_mismatch',
                            'model': model.__name__,
                            'table': table_name,
                            'field': field_name,
                            'expected': type_mismatch['expected'],
                            'actual': type_mismatch['actual'],
                            'message': type_mismatch['message'],
                            'severity': 'MEDIUM'
                        })
                    
                    # Check null constraint mismatch
                    null_mismatch = self.check_null_constraint(field, db_column)
                    if null_mismatch:
                        issues.append({
                            'type': 'field_mismatch',
                            'model': model.__name__,
                            'table': table_name,
                            'field': field_name,
                            'expected': null_mismatch['expected'],
                            'actual': null_mismatch['actual'],
                            'message': null_mismatch['message'],
                            'severity': 'MEDIUM'
                        })
                    
                    # Check default value mismatch (if detailed)
                    if detailed:
                        default_mismatch = self.check_default_value(field, db_column)
                        if default_mismatch:
                            issues.append({
                                'type': 'field_mismatch',
                                'model': model.__name__,
                                'table': table_name,
                                'field': field_name,
                                'expected': default_mismatch['expected'],
                                'actual': default_mismatch['actual'],
                                'message': default_mismatch['message'],
                                'severity': 'LOW'
                            })
        
        except Exception as e:
            issues.append({
                'type': 'check_error',
                'model': model.__name__,
                'table': table_name,
                'message': f'Error checking fields: {str(e)}',
                'severity': 'HIGH'
            })
        
        return issues

    def check_field_type_mismatch(self, field, db_type, db_column):
        """Check if Django field type matches database column type"""
        field_type = type(field).__name__
        
        # Map Django field types to expected MySQL types
        type_mapping = {
            'CharField': 'varchar',
            'TextField': 'text',
            'IntegerField': 'int',
            'BigIntegerField': 'bigint',
            'SmallIntegerField': 'smallint',
            'PositiveIntegerField': 'int',
            'BooleanField': 'tinyint',
            'DateTimeField': 'datetime',
            'DateField': 'date',
            'TimeField': 'time',
            'DecimalField': 'decimal',
            'FloatField': 'double',
            'EmailField': 'varchar',
            'URLField': 'varchar',
            'JSONField': 'json',
            'ForeignKey': 'bigint',  # Foreign keys are stored as bigint
            'OneToOneField': 'bigint',
            'AutoField': 'int',
            'BigAutoField': 'bigint',
        }
        
        expected_base_type = type_mapping.get(field_type, 'unknown')
        db_type_lower = db_type.lower()
        
        # Check for type mismatch
        if expected_base_type == 'unknown':
            return None  # Skip unknown types
        
        # Special handling for CharField with max_length
        if field_type == 'CharField' and hasattr(field, 'max_length'):
            if 'varchar' not in db_type_lower:
                return {
                    'expected': f'VARCHAR({field.max_length})',
                    'actual': db_type,
                    'message': f'Expected VARCHAR but got {db_type}'
                }
            # Check max_length matches
            import re
            match = re.search(r'varchar\((\d+)\)', db_type_lower)
            if match:
                db_max_length = int(match.group(1))
                if db_max_length != field.max_length:
                    return {
                        'expected': f'VARCHAR({field.max_length})',
                        'actual': db_type,
                        'message': f'Max length mismatch: expected {field.max_length}, got {db_max_length}'
                    }
        
        # Check for TextField
        if field_type == 'TextField':
            if 'text' not in db_type_lower and 'longtext' not in db_type_lower:
                return {
                    'expected': 'TEXT or LONGTEXT',
                    'actual': db_type,
                    'message': f'Expected TEXT but got {db_type}'
                }
        
        # Check for IntegerField vs BigIntegerField
        if field_type == 'IntegerField':
            if 'bigint' in db_type_lower:
                return {
                    'expected': 'INT',
                    'actual': db_type,
                    'message': 'Expected INT but got BIGINT (may cause issues)'
                }
        
        if field_type == 'BigIntegerField':
            if 'int' in db_type_lower and 'bigint' not in db_type_lower:
                return {
                    'expected': 'BIGINT',
                    'actual': db_type,
                    'message': f'Expected BIGINT but got {db_type}'
                }
        
        # Check for BooleanField
        if field_type == 'BooleanField':
            if 'tinyint' not in db_type_lower:
                return {
                    'expected': 'TINYINT(1)',
                    'actual': db_type,
                    'message': f'Expected TINYINT(1) but got {db_type}'
                }
        
        # Check for DateTimeField
        if field_type == 'DateTimeField':
            if 'datetime' not in db_type_lower and 'timestamp' not in db_type_lower:
                return {
                    'expected': 'DATETIME or TIMESTAMP',
                    'actual': db_type,
                    'message': f'Expected DATETIME but got {db_type}'
                }
        
        # Check for DecimalField
        if field_type == 'DecimalField' and hasattr(field, 'max_digits') and hasattr(field, 'decimal_places'):
            if 'decimal' not in db_type_lower:
                return {
                    'expected': f'DECIMAL({field.max_digits},{field.decimal_places})',
                    'actual': db_type,
                    'message': f'Expected DECIMAL but got {db_type}'
                }
        
        return None  # No mismatch

    def check_null_constraint(self, field, db_column):
        """Check if null constraint matches"""
        # Django field null vs database null
        field_null = getattr(field, 'null', False)
        db_null = db_column['null']
        
        if field_null != db_null:
            return {
                'expected': 'NULL' if field_null else 'NOT NULL',
                'actual': 'NULL' if db_null else 'NOT NULL',
                'message': f'Null constraint mismatch: model allows null={field_null}, DB allows null={db_null}'
            }
        
        return None

    def check_default_value(self, field, db_column):
        """Check if default value matches (if applicable)"""
        # This is a simplified check - default values can be complex
        field_default = getattr(field, 'default', None)
        db_default = db_column.get('default')
        
        # Skip if both are None or if field has a callable default
        if field_default is None and (db_default is None or db_default == 'NULL'):
            return None
        
        if callable(field_default):
            return None  # Skip callable defaults
        
        # Compare string representations (simplified)
        if str(field_default) != str(db_default):
            return {
                'expected': str(field_default),
                'actual': str(db_default) if db_default else 'NULL',
                'message': f'Default value mismatch: model={field_default}, DB={db_default}'
            }
        
        return None
