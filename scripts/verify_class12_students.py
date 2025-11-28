#!/usr/bin/env python
"""
Verify Class 12 students and generate browser testing URLs

Usage:
    python scripts/verify_class12_students.py
    python scripts/verify_class12_students.py --student-id 2423
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from users.models import User
from institute.models import Institute
from app_post_matric.models import TestSession, TestResult, TestTopCategories, Test


def verify_class12_students(student_id=None):
    """Verify Class 12 students and show browser URLs"""
    
    inst = Institute.objects.get(name='testshanti')
    
    if student_id:
        students = User.objects.filter(id=student_id, student_management__institute=inst)
    else:
        students = User.objects.filter(
            student_management__institute=inst,
            email__endswith='@testshanti.test'
        ).order_by('-id')
    
    class12_students = []
    for student in students:
        sessions = TestSession.objects.filter(user=student)
        if sessions.exists():
            class12_students.append((student, sessions))
    
    if not class12_students:
        print('❌ No Class 12 students found')
        print('\nTo create Class 12 students:')
        print('  python scripts/run_test_students_manager.py create --class12-only --limit 1')
        return
    
    print('=' * 70)
    print('Class 12 Students - Browser Testing')
    print('=' * 70)
    print(f'\nFound {len(class12_students)} Class 12 student(s)\n')
    
    for student, sessions in class12_students:
        print(f'📋 Student: {student.name}')
        print(f'   ID: {student.id}')
        print(f'   Email: {student.email}')
        print(f'\n   Test Sessions: {sessions.count()}/4')
        
        # Check each test
        required_tests = ['Personality', 'Motivation', 'Career Interest', 'Aptitude']
        test_status = {}
        
        # Tests that require TestTopCategories
        tests_requiring_top_cats = ['Personality Assessment', 'Career Interest Inventory', 'Aptitude Assessment']
        
        for session in sessions:
            test_name = session.test.title
            result = TestResult.objects.filter(session=session).first()
            top_cats = TestTopCategories.objects.filter(user=student, test_paper=session.test).first()
            
            has_result = result is not None
            requires_top_cats = test_name in tests_requiring_top_cats
            has_top_cats = top_cats is not None if requires_top_cats else True  # Motivation doesn't need it
            
            # Status is OK if result exists and (top_cats exists OR not required)
            is_ok = has_result and (has_top_cats or not requires_top_cats)
            status = '✅' if is_ok else '⚠️'
            
            test_status[test_name] = {
                'result': has_result,
                'top_cats': has_top_cats,
                'status': status,
                'requires_top_cats': requires_top_cats
            }
            
            print(f'     {status} {test_name}')
            if not has_result:
                print(f'        Missing: TestResult')
            if requires_top_cats and not has_top_cats:
                print(f'        Missing: TestTopCategories')
        
        # Check for missing tests
        session_test_names = [s.test.title for s in sessions]
        missing_tests = [t for t in required_tests if not any(t in name for name in session_test_names)]
        if missing_tests:
            print(f'     ❌ Missing tests: {", ".join(missing_tests)}')
        
        # Overall status - check if all tests have results and required top_cats
        all_complete = True
        for test_name in session_test_names:
            status_info = test_status.get(test_name, {})
            if not status_info.get('result', False):
                all_complete = False
                break
            # Only check top_cats if required
            if status_info.get('requires_top_cats', False) and not status_info.get('top_cats', False):
                all_complete = False
                break
        
        all_complete = all_complete and len(session_test_names) == 4
        
        print(f'\n   Status: {"✅ Ready for browser testing" if all_complete else "⚠️  Incomplete data"}')
        print(f'\n   🌐 Browser Testing URL:')
        print(f'      http://localhost:8002/app_post_matric/web/test_results/{student.id}/')
        print(f'\n   📋 What to Verify:')
        print(f'      1. HEXACO 2-letter code (Personality)')
        print(f'      2. RIASEC 3-letter code (Career Interest)')
        print(f'      3. RIASEC spider map (all 6 dimensions)')
        print(f'      4. Aptitude categorization (Above/Average/Below)')
        print(f'      5. Performance graphs display correctly')
        print(f'      6. Tabular data for all 4 tests')
        print('-' * 70)
        print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify Class 12 students for browser testing')
    parser.add_argument('--student-id', type=int, help='Specific student ID to verify')
    
    args = parser.parse_args()
    
    try:
        verify_class12_students(student_id=args.student_id)
    except Institute.DoesNotExist:
        print('❌ ERROR: testshanti institute not found!')
        print('   Create it first or check the institute name.')
    except Exception as e:
        print(f'❌ ERROR: {str(e)}')
        import traceback
        traceback.print_exc()

