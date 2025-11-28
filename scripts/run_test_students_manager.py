#!/usr/bin/env python
"""
Wrapper script to run test_students_manager.py
Usage: 
    python scripts/run_test_students_manager.py create --limit 1
    python scripts/run_test_students_manager.py remove --dry-run
"""

import os
import sys
import django

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

# Import and run
from scripts.test_students_manager import TestStudentsManager

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python scripts/run_test_students_manager.py create [--limit N] [--class10-only] [--class12-only]')
        print('  python scripts/run_test_students_manager.py remove [--dry-run] [--confirm]')
        sys.exit(1)
    
    command = sys.argv[1]
    manager = TestStudentsManager()
    
    if command == 'create':
        class10_only = '--class10-only' in sys.argv
        class12_only = '--class12-only' in sys.argv
        limit = None
        if '--limit' in sys.argv:
            try:
                limit_idx = sys.argv.index('--limit')
                limit = int(sys.argv[limit_idx + 1])
            except (IndexError, ValueError):
                pass
        
        manager.create_students(class10_only=class10_only, class12_only=class12_only, limit=limit)
    
    elif command == 'remove':
        dry_run = '--dry-run' in sys.argv
        confirm = '--confirm' in sys.argv
        manager.remove_students(dry_run=dry_run, confirm=confirm)
    
    else:
        print(f'Unknown command: {command}')
        print('Use "create" or "remove"')
        sys.exit(1)

