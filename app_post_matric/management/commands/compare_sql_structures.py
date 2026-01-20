"""
Django management command to compare two SQL structure files and generate a report.

Usage:
    python manage.py compare_sql_structures --file1 path/to/file1.sql --file2 path/to/file2.sql
    python manage.py compare_sql_structures --file1 file1.sql --file2 file2.sql --output report.txt
"""

from django.core.management.base import BaseCommand
import re
import sys


class Command(BaseCommand):
    help = 'Compare two SQL structure files and show differences'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file1',
            type=str,
            required=True,
            help='First SQL structure file path'
        )
        parser.add_argument(
            '--file2',
            type=str,
            required=True,
            help='Second SQL structure file path'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for report'
        )
        parser.add_argument(
            '--db1',
            type=str,
            default='topteen12',
            help='Name for first database (default: topteen12)'
        )
        parser.add_argument(
            '--db2',
            type=str,
            default='topteen12-old',
            help='Name for second database (default: topteen12-old)'
        )

    def handle(self, *args, **options):
        file1_path = options.get('file1')
        file2_path = options.get('file2')
        output_file = options.get('output')
        db1_name = options.get('db1')
        db2_name = options.get('db2')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('SQL STRUCTURE COMPARISON REPORT'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        try:
            # Parse SQL files
            self.stdout.write(f'Parsing {file1_path}...')
            tables1, fields1 = self.parse_sql_file(file1_path)
            
            self.stdout.write(f'Parsing {file2_path}...')
            tables2, fields2 = self.parse_sql_file(file2_path)
            
            # Generate report
            report_lines = []
            report_lines.append('=' * 80)
            report_lines.append('SQL STRUCTURE COMPARISON REPORT')
            report_lines.append('=' * 80)
            report_lines.append('')
            report_lines.append(f'File 1: {file1_path} ({db1_name})')
            report_lines.append(f'File 2: {file2_path} ({db2_name})')
            report_lines.append('')
            report_lines.append('=' * 80)
            report_lines.append('')
            
            # Table count comparison
            count1 = len(tables1)
            count2 = len(tables2)
            diff = count1 - count2
            
            report_lines.append('TABLE COUNT COMPARISON')
            report_lines.append('-' * 80)
            report_lines.append(f'{db1_name}: {count1} tables')
            report_lines.append(f'{db2_name}: {count2} tables')
            if diff > 0:
                report_lines.append(f'Difference: {diff} tables ({db1_name} has {diff} more than {db2_name})')
            elif diff < 0:
                report_lines.append(f'Difference: {abs(diff)} tables ({db1_name} has {abs(diff)} fewer than {db2_name})')
            else:
                report_lines.append(f'Difference: 0 tables (both have same count)')
            report_lines.append('')
            
            self.stdout.write(f'\nTable Count:')
            self.stdout.write(f'  {db1_name}: {count1} tables')
            self.stdout.write(f'  {db2_name}: {count2} tables')
            self.stdout.write(f'  Difference: {abs(diff)} tables')
            
            # Find missing tables
            missing_in_db2 = set(tables1.keys()) - set(tables2.keys())
            missing_in_db1 = set(tables2.keys()) - set(tables1.keys())
            
            # Missing tables section
            report_lines.append('=' * 80)
            report_lines.append('MISSING TABLES')
            report_lines.append('=' * 80)
            report_lines.append('')
            
            if missing_in_db2:
                report_lines.append(f'Missing in {db2_name}:')
                for table in sorted(missing_in_db2):
                    report_lines.append(f'  {db2_name}: {table}')
                report_lines.append('')
                self.stdout.write(self.style.WARNING(f'\n⚠️  Missing in {db2_name}: {len(missing_in_db2)} tables'))
            else:
                report_lines.append(f'No tables missing in {db2_name}')
                report_lines.append('')
                self.stdout.write(self.style.SUCCESS(f'\n✅ No tables missing in {db2_name}'))
            
            if missing_in_db1:
                report_lines.append(f'Missing in {db1_name}:')
                for table in sorted(missing_in_db1):
                    report_lines.append(f'  {db1_name}: {table}')
                report_lines.append('')
                self.stdout.write(self.style.WARNING(f'⚠️  Missing in {db1_name}: {len(missing_in_db1)} tables'))
            else:
                report_lines.append(f'No tables missing in {db1_name}')
                report_lines.append('')
                self.stdout.write(self.style.SUCCESS(f'✅ No tables missing in {db1_name}'))
            
            # Find common tables and compare fields
            common_tables = set(tables1.keys()) & set(tables2.keys())
            
            if common_tables:
                report_lines.append('')
                report_lines.append('=' * 80)
                report_lines.append('MISSING FIELDS OR MISMATCHES')
                report_lines.append('=' * 80)
                report_lines.append('')
                
                missing_fields_db2 = []
                missing_fields_db1 = []
                field_mismatches = []
                
                self.stdout.write(f'\nComparing fields in {len(common_tables)} common tables...')
                
                for table in sorted(common_tables):
                    table_fields1 = fields1.get(table, {})
                    table_fields2 = fields2.get(table, {})
                    
                    # Find missing fields
                    missing_in_table2 = set(table_fields1.keys()) - set(table_fields2.keys())
                    missing_in_table1 = set(table_fields2.keys()) - set(table_fields1.keys())
                    
                    for field in missing_in_table2:
                        missing_fields_db2.append({
                            'db': db2_name,
                            'table': table,
                            'field': field,
                            'type': table_fields1[field].get('type', 'N/A')
                        })
                    
                    for field in missing_in_table1:
                        missing_fields_db1.append({
                            'db': db1_name,
                            'table': table,
                            'field': field,
                            'type': table_fields2[field].get('type', 'N/A')
                        })
                    
                    # Find type mismatches in common fields
                    common_fields = set(table_fields1.keys()) & set(table_fields2.keys())
                    for field in common_fields:
                        type1 = table_fields1[field].get('type', '').lower()
                        type2 = table_fields2[field].get('type', '').lower()
                        
                        # Normalize types for comparison
                        if type1 != type2 and not self.types_compatible(type1, type2):
                            field_mismatches.append({
                                'db1': db1_name,
                                'db2': db2_name,
                                'table': table,
                                'field': field,
                                'type1': table_fields1[field].get('type', 'N/A'),
                                'type2': table_fields2[field].get('type', 'N/A')
                            })
                
                # Report missing fields in db2
                if missing_fields_db2:
                    report_lines.append(f'Missing fields in {db2_name}:')
                    for item in sorted(missing_fields_db2, key=lambda x: (x['table'], x['field'])):
                        report_lines.append(f'  {item["db"]}: {item["table"]}: {item["field"]}')
                    report_lines.append('')
                    self.stdout.write(self.style.WARNING(f'⚠️  Missing fields in {db2_name}: {len(missing_fields_db2)}'))
                else:
                    report_lines.append(f'No missing fields in {db2_name}')
                    report_lines.append('')
                    self.stdout.write(self.style.SUCCESS(f'✅ No missing fields in {db2_name}'))
                
                # Report missing fields in db1
                if missing_fields_db1:
                    report_lines.append(f'Missing fields in {db1_name}:')
                    for item in sorted(missing_fields_db1, key=lambda x: (x['table'], x['field'])):
                        report_lines.append(f'  {item["db"]}: {item["table"]}: {item["field"]}')
                    report_lines.append('')
                    self.stdout.write(self.style.WARNING(f'⚠️  Missing fields in {db1_name}: {len(missing_fields_db1)}'))
                else:
                    report_lines.append(f'No missing fields in {db1_name}')
                    report_lines.append('')
                    self.stdout.write(self.style.SUCCESS(f'✅ No missing fields in {db1_name}'))
                
                # Report field type mismatches
                if field_mismatches:
                    report_lines.append(f'Field type mismatches:')
                    for item in sorted(field_mismatches, key=lambda x: (x['table'], x['field'])):
                        report_lines.append(f'  {item["table"]}: {item["field"]}')
                        report_lines.append(f'    {item["db1"]}: {item["type1"]}')
                        report_lines.append(f'    {item["db2"]}: {item["type2"]}')
                    report_lines.append('')
                    self.stdout.write(self.style.WARNING(f'⚠️  Field type mismatches: {len(field_mismatches)}'))
                else:
                    report_lines.append('No field type mismatches')
                    report_lines.append('')
                    self.stdout.write(self.style.SUCCESS(f'✅ No field type mismatches'))
            
            report_lines.append('')
            report_lines.append('=' * 80)
            report_lines.append('END OF REPORT')
            report_lines.append('=' * 80)
            
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
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())

    def parse_sql_file(self, file_path):
        """Parse SQL structure file and extract tables and fields"""
        tables = {}
        fields = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all CREATE TABLE statements
            # Pattern: CREATE TABLE `table_name` ( ... )
            create_table_pattern = r'CREATE TABLE `([^`]+)`\s*\((.*?)\)\s*ENGINE'
            
            matches = re.finditer(create_table_pattern, content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                table_name = match.group(1)
                table_def = match.group(2)
                
                tables[table_name] = True
                fields[table_name] = {}
                
                # Parse fields from table definition
                # Pattern: `field_name` type constraints
                field_pattern = r'`([^`]+)`\s+([^\s,]+(?:\s*\([^)]+\))?[^,]*?)(?:,|$)'
                
                field_matches = re.finditer(field_pattern, table_def, re.MULTILINE)
                
                for field_match in field_matches:
                    field_name = field_match.group(1)
                    field_def = field_match.group(2).strip()
                    
                    # Extract field type (first part before any constraints)
                    # Handle types like: varchar(200), bigint, datetime(6), etc.
                    type_match = re.match(r'([a-z]+(?:\([^)]+\))?)', field_def, re.IGNORECASE)
                    if type_match:
                        field_type = type_match.group(1)
                    else:
                        field_type = field_def.split()[0] if field_def.split() else 'unknown'
                    
                    fields[table_name][field_name] = {
                        'type': field_type,
                        'definition': field_def
                    }
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error parsing {file_path}: {str(e)}'))
        
        return tables, fields

    def types_compatible(self, type1, type2):
        """Check if two MySQL types are compatible (simplified check)"""
        # Normalize types
        type1 = type1.lower()
        type2 = type2.lower()
        
        # Extract base type (remove length/precision)
        base_type1 = re.sub(r'\([^)]+\)', '', type1).strip()
        base_type2 = re.sub(r'\([^)]+\)', '', type2).strip()
        
        # Exact match
        if base_type1 == base_type2:
            return True
        
        # Compatible types
        compatible_groups = [
            ['int', 'bigint', 'smallint', 'tinyint'],
            ['varchar', 'char', 'text', 'longtext', 'mediumtext'],
            ['datetime', 'timestamp'],
            ['decimal', 'numeric', 'float', 'double'],
        ]
        
        for group in compatible_groups:
            if base_type1 in group and base_type2 in group:
                return True
        
        # Check for varchar length differences
        if 'varchar' in base_type1 and 'varchar' in base_type2:
            return True
        
        return False
