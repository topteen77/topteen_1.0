#!/usr/bin/env python
"""
Browser Verification Helper
Creates a test student and provides verification URLs
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from users.models import User
from institute.models import Institute
from scripts.test_students_manager import TestStudentsManager

def main():
    print('=' * 70)
    print('BROWSER VERIFICATION HELPER')
    print('=' * 70)
    
    # Get institute
    try:
        inst = Institute.objects.get(name='testshanti')
    except Institute.DoesNotExist:
        print('❌ ERROR: testshanti institute not found!')
        return
    
    # Check for existing test students
    existing_students = User.objects.filter(
        student_management__institute=inst,
        email__endswith='@testshanti.test'
    )
    
    if existing_students.exists():
        print(f'\n✅ Found {existing_students.count()} existing test student(s)')
        print('\n' + '=' * 70)
        print('VERIFICATION URLs')
        print('=' * 70)
        
        for student in existing_students[:5]:
            print(f'\n📋 Student: {student.name}')
            print(f'   ID: {student.id}')
            print(f'   Email: {student.email}')
            print(f'\n   🌐 URLs:')
            print(f'   1. Institute Dashboard:')
            print(f'      http://localhost:8000/institute/{inst.slug}/')
            print(f'\n   2. Class 10 Report:')
            print(f'      http://localhost:8000/app/Assessment_pdf_inst_user/{student.id}/')
            print(f'\n   3. Class 12 Report:')
            print(f'      http://localhost:8000/app_post_matric/web/test_results/{student.id}/')
    else:
        print('\n⚠️  No test students found. Creating one now...\n')
        
        # Create a test student
        manager = TestStudentsManager()
        count = manager.create_students(limit=1)
        
        if count > 0:
            # Get the newly created student
            new_student = User.objects.filter(
                student_management__institute=inst,
                email__endswith='@testshanti.test'
            ).first()
            
            if new_student:
                print('\n' + '=' * 70)
                print('✅ TEST STUDENT CREATED!')
                print('=' * 70)
                print(f'\n📋 Student: {new_student.name}')
                print(f'   ID: {new_student.id}')
                print(f'   Email: {new_student.email}')
                print(f'\n   🌐 VERIFICATION URLs:')
                print(f'\n   1. Institute Dashboard:')
                print(f'      http://localhost:8000/institute/{inst.slug}/')
                print(f'\n   2. Class 10 Report:')
                print(f'      http://localhost:8000/app/Assessment_pdf_inst_user/{new_student.id}/')
                print(f'\n   3. Class 12 Report:')
                print(f'      http://localhost:8000/app_post_matric/web/test_results/{new_student.id}/')
                print('\n' + '=' * 70)
                print('NEXT STEPS:')
                print('=' * 70)
                print('1. Start Django server: python manage.py runserver')
                print('2. Login as institute user')
                print('3. Navigate to the URLs above')
                print('4. Verify results match checklist expectations')
                print('=' * 70)
            else:
                print('❌ Student created but not found. Please check manually.')
        else:
            print('❌ Failed to create test student. Check errors above.')
    
    print()

if __name__ == '__main__':
    main()

