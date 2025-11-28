"""
Unified Test Students Manager
Handles both creation and removal of test students with integrated checklist management.

Usage:
    python scripts/run_test_students_manager.py create --limit 1
    python scripts/run_test_students_manager.py remove --dry-run
    python scripts/run_test_students_manager.py remove --confirm
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

import json
import random
import csv
import re
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from users.models import User
from institute.models import Institute, ClassAndSection, StudentManagement
from app.models import Results, TestCompletion
from app_post_matric.models import (
    TestCategory, Test, Sections,
    TestSession, SectionSession, UserResponse, TestResult, TestTopCategories
)

# Import checklist manager
from scripts.checklist_manager import ChecklistManager


class TestStudentsManager:
    """Unified manager for creating and removing test students"""
    
    # RIASEC order for tie-breaking
    RIASEC_ORDER = ['R', 'I', 'A', 'S', 'E', 'C']
    RIASEC_NAMES = {
        'R': 'Realistic', 'I': 'Investigative', 'A': 'Artistic',
        'S': 'Social', 'E': 'Enterprising', 'C': 'Conventional'
    }
    
    # HEXACO order for tie-breaking
    HEXACO_ORDER = ['H', 'E', 'X', 'A', 'C', 'O']
    HEXACO_NAMES = {
        'H': 'Honesty-Humility', 'E': 'Emotionality', 'X': 'eXtraversion',
        'A': 'Agreeableness', 'C': 'Conscientiousness', 'O': 'Openness'
    }
    
    def __init__(self):
        self.checklist_manager = ChecklistManager()
        self.base_url = "http://localhost:8002"
    
    # ==================== CREATE OPERATIONS ====================
    
    def create_students(self, class10_only=False, class12_only=False, limit=None):
        """Create test students"""
        print('=' * 60)
        print('Test Student Creation')
        print('=' * 60)
        print('Starting test student creation...')
        
        # Get or create institute
        institute = self.get_or_create_institute()
        print(f'Using institute: {institute.name}')
        
        # Check credits before starting
        required_students = self.estimate_required_students(class10_only, class12_only, limit)
        print(f'\nEstimated students to create: {required_students}')
        print(f'Current credits available: {institute.get_current_credits_count()}')
        
        if not self.check_credits_available(institute, required_students):
            return 0
        
        # Get or create class sections
        class10_section = self.get_or_create_class_section('10-A')
        class12_section = self.get_or_create_class_section('12-A')
        
        # Load existing checklist
        self.checklist_manager.load_checklist()
        
        student_count = 0
        
        if not class12_only:
            print('\n=== Creating Class 10 Test Students ===')
            count = self.create_class10_students(institute, class10_section, limit)
            student_count += count
            print(f'Created {count} Class 10 students')
        
        if not class10_only:
            print('\n=== Creating Class 12 Test Students ===')
            count = self.create_class12_students(institute, class12_section, limit)
            student_count += count
            print(f'Created {count} Class 12 students')
        
        print(f'\n=== Total students created: {student_count} ===')
        print(f'Remaining credits: {institute.get_current_credits_count()}')
        
        # Save checklist
        if student_count > 0:
            self.checklist_manager.write_checklist()
            print(f'\n✅ Checklist saved: {len(self.checklist_manager.checklist_items)} items')
            print(f'   File: scripts/verification_checklist.csv')
        
        return student_count
    
    def check_credits_available(self, institute, required_count):
        """Check if institute has enough credits"""
        current_credits = institute.get_current_credits_count()
        if current_credits < required_count:
            print(f'\nERROR: Insufficient credits!')
            print(f'  Required: {required_count} credits')
            print(f'  Available: {current_credits} credits')
            print(f'  Shortfall: {required_count - current_credits} credits')
            print(f'\nPlease add more credits to "{institute.name}" institute before creating test students.')
            return False
        return True
    
    def estimate_required_students(self, class10_only, class12_only, limit):
        """Estimate how many students will be created"""
        count = 0
        if not class12_only:
            count += limit if limit else 150
        if not class10_only:
            count += limit if limit else 50
        return count
    
    def get_or_create_institute(self):
        """Get or create testshanti institute"""
        institute, created = Institute.objects.get_or_create(
            name='testshanti',
            defaults={
                'credit_counts': 10000,
                'institute_status': 1,
            }
        )
        if created:
            print('Created institute: testshanti with 10000 credits')
        else:
            institute.refresh_from_db()
            current_credits = institute.get_current_credits_count()
            print(f'Using existing institute: testshanti')
            print(f'  Total credits: {institute.credit_counts}')
            print(f'  Used credits: {institute.credit_counts - current_credits}')
            print(f'  Available credits: {current_credits}')
        return institute
    
    def get_or_create_class_section(self, class_name):
        """Get or create class and section"""
        section, created = ClassAndSection.objects.get_or_create(
            class_and_section=class_name
        )
        return section
    
    def create_class10_students(self, institute, class_section, limit=None):
        """Create Class 10 test students"""
        count = 0
        riasec_combinations = self.generate_riasec_combinations(limit)
        
        for idx, combo in enumerate(riasec_combinations, start=1):
            student_name = f"st{idx}-{combo['code'].lower()}-{combo.get('stream', 'pcm')}"
            email = f"{student_name}@testshanti.test"
            
            if User.objects.filter(email=email).exists():
                print(f'Skipping duplicate: {email}')
                continue
            
            if not institute.is_valid_credit_count():
                print(f'\nWARNING: Insufficient credits! Stopping student creation.')
                print(f'  Created {count} students before running out of credits.')
                break
            
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        name=student_name,
                        password='12345'
                    )
                    
                    StudentManagement.objects.create(
                        institute=institute,
                        student=user,
                        class_and_section=class_section
                    )
                    
                    test_completion = TestCompletion.objects.create(user=user)
                    
                    if combo.get('test1_complete', True):
                        self.create_class10_test1_results(user, combo['scores'])
                        test_completion.test1_complete = True
                    
                    if combo.get('test2_complete', True):
                        self.create_class10_test2_results(user, combo.get('interest_scores', combo['scores']))
                        test_completion.test2_complete = True
                    
                    if combo.get('test3_complete', True):
                        self.create_class10_test3_results(user, combo.get('aptitude_scores', {}))
                        test_completion.test3_complete = True
                        test_completion.numerical_complete = True
                        test_completion.verbal_complete = True
                        test_completion.logical_complete = True
                        test_completion.emotional_complete = True
                        test_completion.machanical_complete = True
                        test_completion.language_complete = True
                        test_completion.spatial_complete = True
                    
                    test_completion.save()
                    count += 1
                    
                    # Generate checklist items
                    self.generate_checklist_for_class10_student(user, combo)
                    
            except Exception as e:
                print(f'ERROR: Error creating {student_name}: {str(e)}')
                continue
        
        return count
    
    def create_class12_students(self, institute, class_section, limit=None):
        """Create Class 12 test students"""
        count = 0
        
        # Search by test title instead of category name
        personality_test = Test.objects.filter(title__icontains='Personality').first()
        motivation_test = Test.objects.filter(title__icontains='Motivation').first()
        career_test = Test.objects.filter(title__icontains='Career Interest').first()
        aptitude_test = Test.objects.filter(title__icontains='Aptitude').first()
        
        if not all([personality_test, motivation_test, career_test, aptitude_test]):
            print('WARNING: Some Class 12 tests not found. Please ensure tests are created in database.')
            missing = []
            if not personality_test:
                missing.append('Personality Assessment')
            if not motivation_test:
                missing.append('Motivation Assessment')
            if not career_test:
                missing.append('Career Interest Inventory')
            if not aptitude_test:
                missing.append('Aptitude Assessment')
            print(f'   Missing tests: {", ".join(missing)}')
            return 0
        
        print(f'✅ Found all Class 12 tests:')
        print(f'   - Personality: {personality_test.title}')
        print(f'   - Motivation: {motivation_test.title}')
        print(f'   - Career Interest: {career_test.title}')
        print(f'   - Aptitude: {aptitude_test.title}')
        
        combinations = self.generate_class12_combinations(limit)
        
        for idx, combo in enumerate(combinations, start=1):
            student_name = combo.get('name', f"st{idx}-{combo.get('code', 'unknown')}")
            email = f"{student_name}@testshanti.test"
            
            if User.objects.filter(email=email).exists():
                continue
            
            if not institute.is_valid_credit_count():
                print(f'\nWARNING: Insufficient credits! Stopping student creation.')
                print(f'  Created {count} students before running out of credits.')
                break
            
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        name=student_name,
                        password='12345'
                    )
                    
                    StudentManagement.objects.create(
                        institute=institute,
                        student=user,
                        class_and_section=class_section
                    )
                    
                    if combo.get('personality_complete', True):
                        self.create_class12_personality_test(user, personality_test, combo.get('hexaco_scores', {}))
                    
                    if combo.get('motivation_complete', True):
                        self.create_class12_motivation_test(user, motivation_test, combo.get('motivation_scores', {}))
                    
                    if combo.get('career_complete', True):
                        self.create_class12_career_test(user, career_test, combo.get('riasec_scores', {}))
                    
                    if combo.get('aptitude_complete', True):
                        self.create_class12_aptitude_test(user, aptitude_test, combo.get('aptitude_data', {}))
                    
                    count += 1
                    
                    # Generate checklist items
                    self.generate_checklist_for_class12_student(user, combo)
                    
            except Exception as e:
                print(f'ERROR: Error creating {student_name}: {str(e)}')
                continue
        
        return count
    
    # ==================== REMOVE OPERATIONS ====================
    
    def remove_students(self, dry_run=False, confirm=False):
        """Remove test students based on checklist - PERMANENT DELETE (hard_delete=True)"""
        print('=' * 60)
        print('Test Student Removal (PERMANENT DELETE)')
        print('=' * 60)
        
        if dry_run:
            print('\n🔍 DRY RUN MODE - No data will be deleted')
        
        try:
            institute = Institute.objects.get(name='testshanti')
        except Institute.DoesNotExist:
            print('\n❌ ERROR: testshanti institute not found!')
            return
        
        print(f'\n📋 Institute: {institute.name}')
        print(f'   Total credits: {institute.credit_counts}')
        
        # Load checklist
        self.checklist_manager.load_checklist()
        student_ids = self.checklist_manager.get_student_ids_from_checklist()
        
        if not student_ids:
            print('\n⚠️  No students found in checklist!')
            print('   Falling back to pattern-based filtering...')
            # Fallback filtering
            all_students = User.objects.filter(student_management__institute=institute).distinct()
            student_id_list = []
            for student in all_students:
                if student.email and student.email.endswith('@testshanti.test'):
                    student_id_list.append(student.id)
                elif student.name and (re.match(r'^st\d+-', student.name) or student.name.startswith('st-')):
                    student_id_list.append(student.id)
            student_ids = student_id_list
        
        if not student_ids:
            print('\n✅ No test script students found. Nothing to delete.')
            return
        
        # Always use QuerySet for consistency
        students = User.objects.filter(id__in=student_ids, student_management__institute=institute).distinct()
        
        if student_ids and len(student_ids) == len([s.id for s in students]):
            print(f'\n📋 Loaded checklist: {len(student_ids)} student IDs found')
        
        print(f'\n📊 Found {students.count()} test script students to delete')
        print('\n📝 Students to be deleted:')
        for student in students[:5]:
            print(f'   - {student.name} (ID: {student.id})')
        if students.count() > 5:
            print(f'   ... and {students.count() - 5} more')
        
        if not dry_run:
            if not confirm:
                response = input('\n⚠️  WARNING: This will PERMANENTLY DELETE test students (hard delete)!\n'
                               '   This cannot be undone. Type "DELETE" to confirm: ')
                if response != 'DELETE':
                    print('\n❌ Deletion cancelled.')
                    return
            print('\n🗑️  Starting PERMANENT deletion (hard_delete=True)...')
        else:
            print('\n🔍 DRY RUN: Would delete the following:')
        
        # Delete data
        stats = self.delete_student_data(students, dry_run)
        
        if not dry_run:
            # Always reload checklist to get latest data
            self.checklist_manager.load_checklist()
            
            # Get actual student IDs that were deleted
            deleted_student_ids = [str(s.id) for s in students]
            
            # Count items before removal
            items_before = len(self.checklist_manager.checklist_items)
            
            # Remove all checklist items for deleted students
            remaining_items = [
                item for item in self.checklist_manager.checklist_items
                if item.get('Student ID', '') not in deleted_student_ids
            ]
            
            items_removed = items_before - len(remaining_items)
            
            # Update checklist
            self.checklist_manager.checklist_items = remaining_items
            self.checklist_manager.write_checklist()
            
            print(f'\n📝 Checklist updated:')
            print(f'   Items before: {items_before}')
            print(f'   Items removed: {items_removed}')
            print(f'   Items remaining: {len(remaining_items)}')
            print(f'   Checklist file: {self.checklist_manager.checklist_file}')
            
            # If checklist is empty, show message
            if len(remaining_items) == 0:
                print(f'\n   ℹ️  Checklist is now empty (all items removed)')
        
        # Show statistics
        self.show_deletion_stats(stats, institute)
    
    def delete_student_data(self, students, dry_run):
        """Delete all data for students - PERMANENT DELETE (hard_delete=True)"""
        stats = {
            'results': 0,
            'test_completions': 0,
            'test_sessions': 0,
            'section_sessions': 0,
            'user_responses': 0,
            'test_results': 0,
            'test_top_categories': 0,
            'student_managements': 0,
            'users': 0,
        }
        
        print('\n📚 Deleting Class 10 data (PERMANENT)...')
        results = Results.objects.filter(user__in=students)
        stats['results'] = results.count()
        if not dry_run:
            results.delete()  # Results doesn't inherit BaseModel, regular delete is permanent
        print(f'   Results: {stats["results"]} permanently deleted')
        
        test_completions = TestCompletion.objects.filter(user__in=students)
        stats['test_completions'] = test_completions.count()
        if not dry_run:
            test_completions.delete()  # TestCompletion doesn't inherit BaseModel, regular delete is permanent
        print(f'   Test Completions: {stats["test_completions"]} permanently deleted')
        
        print('\n📚 Deleting Class 12 data (PERMANENT)...')
        test_sessions = TestSession.objects.filter(user__in=students)
        
        section_sessions = SectionSession.objects.filter(session__in=test_sessions)
        stats['section_sessions'] = section_sessions.count()
        if not dry_run:
            section_sessions.delete()  # SectionSession doesn't inherit BaseModel, regular delete is permanent
        print(f'   Section Sessions: {stats["section_sessions"]} permanently deleted')
        
        user_responses = UserResponse.objects.filter(session__in=test_sessions)
        stats['user_responses'] = user_responses.count()
        if not dry_run:
            user_responses.delete()  # UserResponse doesn't inherit BaseModel, regular delete is permanent
        print(f'   User Responses: {stats["user_responses"]} permanently deleted')
        
        test_results = TestResult.objects.filter(session__in=test_sessions)
        stats['test_results'] = test_results.count()
        if not dry_run:
            test_results.delete()  # TestResult doesn't inherit BaseModel, regular delete is permanent
        print(f'   Test Results: {stats["test_results"]} permanently deleted')
        
        test_top_categories = TestTopCategories.objects.filter(user__in=students)
        stats['test_top_categories'] = test_top_categories.count()
        if not dry_run:
            test_top_categories.delete()  # TestTopCategories doesn't inherit BaseModel, regular delete is permanent
        print(f'   Test Top Categories: {stats["test_top_categories"]} permanently deleted')
        
        stats['test_sessions'] = test_sessions.count()
        if not dry_run:
            test_sessions.delete()  # TestSession doesn't inherit BaseModel, regular delete is permanent
        print(f'   Test Sessions: {stats["test_sessions"]} permanently deleted')
        
        print('\n👥 Deleting Student Management records (PERMANENT)...')
        student_managements = StudentManagement.objects.filter(
            institute__name='testshanti',
            student__in=students
        )
        stats['student_managements'] = student_managements.count()
        if not dry_run:
            # StudentManagement inherits from BaseModel (soft delete), use hard_delete=True for permanent removal
            for sm in student_managements:
                sm.delete(hard_delete=True)
        print(f'   Student Managements: {stats["student_managements"]} permanently deleted')
        
        print('\n👤 Deleting User records (PERMANENT DELETE)...')
        stats['users'] = students.count() if hasattr(students, 'count') else len(students)
        if not dry_run:
            with transaction.atomic():
                # User inherits from BaseModel (soft delete), use hard_delete=True for permanent removal
                if isinstance(students, list):
                    student_ids = [s.id for s in students]
                    user_queryset = User.objects.filter(id__in=student_ids)
                    for user in user_queryset:
                        user.delete(hard_delete=True)
                else:
                    for user in students:
                        user.delete(hard_delete=True)
        print(f'   Users: {stats["users"]} permanently deleted')
        
        return stats
    
    def show_deletion_stats(self, stats, institute):
        """Show deletion statistics"""
        print('\n' + '=' * 60)
        print('📊 Deletion Statistics')
        print('=' * 60)
        for key, value in stats.items():
            print(f'   {key.replace("_", " ").title()}: {value}')
        print('=' * 60)
        institute.refresh_from_db()
        print(f'\n💳 Remaining credits: {institute.get_current_credits_count()}')
    
    # ==================== HELPER METHODS ====================
    
    def generate_riasec_combinations(self, limit=None):
        """Generate RIASEC combinations"""
        combinations = []
        riasec_letters = self.RIASEC_ORDER
        
        for i, first in enumerate(riasec_letters):
            for j, second in enumerate(riasec_letters):
                if j == i:
                    continue
                for k, third in enumerate(riasec_letters):
                    if k == i or k == j:
                        continue
                    
                    code = first + second + third
                    scores = {}
                    scores[first] = 45
                    scores[second] = 40
                    scores[third] = 35
                    for letter in riasec_letters:
                        if letter not in scores:
                            scores[letter] = random.randint(10, 30)
                    
                    combinations.append({
                        'code': code,
                        'scores': scores,
                        'stream': self.get_stream_from_code(code),
                        'test1_complete': True,
                        'test2_complete': True,
                        'test3_complete': True,
                    })
        
        if limit:
            combinations = combinations[:limit]
        
        return combinations
    
    def get_stream_from_code(self, code):
        """Get stream from RIASEC code"""
        if 'R' in code and 'I' in code:
            return 'pcm'
        elif 'R' in code and 'S' in code:
            return 'pcb'
        elif 'A' in code and 'S' in code:
            return 'arts'
        elif 'E' in code and 'C' in code:
            return 'commerce'
        return 'pcm'
    
    def generate_class12_combinations(self, limit=None):
        """Generate Class 12 combinations"""
        combinations = []
        
        # HEXACO combinations
        for i, first in enumerate(self.HEXACO_ORDER[:3]):
            for j, second in enumerate(self.HEXACO_ORDER[i+1:4], start=i+1):
                code = first + second
                scores = {first: 45, second: 40}
                for letter in self.HEXACO_ORDER:
                    if letter not in scores:
                        scores[letter] = random.randint(20, 35)
                
                combinations.append({
                    'name': f"st{len(combinations)+1}-{code.lower()}-medical",
                    'code': code,
                    'hexaco_scores': scores,
                    'personality_complete': True,
                    'motivation_complete': True,
                    'career_complete': True,
                    'aptitude_complete': True,
                })
        
        # Aptitude test cases
        combinations.extend([
            {
                'name': 'st-apt-all-above',
                'aptitude_data': {
                    'sections': {
                        'Logical Reasoning': {'correct': 12, 'total': 15},
                        'Spatial Reasoning': {'correct': 13, 'total': 15},
                        'Abstract Reasoning': {'correct': 11, 'total': 15},
                        'Numerical Reasoning': {'correct': 12, 'total': 15},
                        'Mechanical Reasoning': {'correct': 11, 'total': 15},
                        'Clerical speed & Accuracy': {'correct': 13, 'total': 15},
                        'Language & Verbal Reasoning': {'correct': 12, 'total': 15},
                    }
                }
            },
            {
                'name': 'st-apt-all-average',
                'aptitude_data': {
                    'sections': {
                        'Logical Reasoning': {'correct': 8, 'total': 15},
                        'Spatial Reasoning': {'correct': 7, 'total': 15},
                        'Abstract Reasoning': {'correct': 9, 'total': 15},
                        'Numerical Reasoning': {'correct': 8, 'total': 15},
                        'Mechanical Reasoning': {'correct': 7, 'total': 15},
                        'Clerical speed & Accuracy': {'correct': 8, 'total': 15},
                        'Language & Verbal Reasoning': {'correct': 9, 'total': 15},
                    }
                }
            },
        ])
        
        if limit:
            combinations = combinations[:limit]
        
        return combinations
    
    def create_class10_test1_results(self, user, scores):
        """Create test1 results"""
        sum_scores = {}
        for letter, score in scores.items():
            sum_scores[f'sum_{letter}'] = int((score / 100) * 50)
        
        results = {}
        for letter, name in self.RIASEC_NAMES.items():
            results[name] = round(scores.get(letter, 0), 2)
        
        variable_indices = {
            'R': [1, 7, 13, 19, 25, 31, 37, 43, 49, 55],
            'I': [2, 8, 14, 20, 26, 32, 38, 44, 50, 56],
            'A': [3, 9, 15, 21, 27, 33, 39, 45, 51, 57],
            'S': [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
            'E': [5, 11, 17, 23, 29, 35, 41, 47, 53, 59],
            'C': [6, 12, 18, 24, 30, 36, 42, 48, 54, 60],
        }
        
        all_answers = [3] * 60
        for letter, indices in variable_indices.items():
            target_sum = sum_scores.get(f'sum_{letter}', 25)
            avg_answer = max(1, min(5, target_sum // len(indices)))
            for idx in indices:
                all_answers[idx - 1] = avg_answer
        
        submitted_answers = {}
        for i, ans in enumerate(all_answers, start=1):
            submitted_answers[f'Question_{i}'] = ans
        
        Results.objects.update_or_create(
            user=user,
            test_paper='test1',
            defaults={
                'scores': sum_scores,
                'results': results,
                'selected_answers': {'submitted_answers': submitted_answers}
            }
        )
    
    def create_class10_test2_results(self, user, scores):
        """Create test2 results"""
        Results.objects.update_or_create(
            user=user,
            test_paper='test2',
            defaults={
                'scores': {name: int(score) for letter, name in self.RIASEC_NAMES.items() 
                          for score in [scores.get(letter, 10)]},
                'results': {},
                'selected_answers': {}
            }
        )
    
    def create_class10_test3_results(self, user, aptitude_scores):
        """Create test3 results"""
        if not aptitude_scores:
            aptitude_scores = {
                'numerical': 12, 'verbal': 10, 'logical': 8,
                'emotional': 7, 'machanical': 6, 'language': 5, 'spatial': 4,
            }
        
        subtests = ['numerical', 'verbal', 'logical', 'emotional', 'machanical', 'language', 'spatial']
        for subtest in subtests:
            score = aptitude_scores.get(subtest, 10)
            Results.objects.update_or_create(
                user=user,
                test_paper=f'test3_{subtest}',
                defaults={
                    'scores': {'score': score},
                    'results': {},
                    'selected_answers': {}
                }
            )
    
    def create_class12_personality_test(self, user, test, scores):
        """Create Personality test"""
        if not scores:
            scores = {letter: random.randint(20, 45) for letter in self.HEXACO_ORDER}
        
        start_time = timezone.now() - timedelta(minutes=30)
        end_time = timezone.now() - timedelta(minutes=5)
        
        session = TestSession.objects.create(
            user=user,
            test=test,
            start_time=start_time,
            end_time=end_time,
            is_completed=True,
            attempt_count=1
        )
        
        result_data = {}
        for letter, score in scores.items():
            result_data[letter] = {
                'score': score,
                'count': 10,
                'average': score / 10,
                'name': self.HEXACO_NAMES.get(letter, letter)
            }
        
        sorted_dims = sorted(
            scores.items(),
            key=lambda x: (-x[1], self.HEXACO_ORDER.index(x[0]) if x[0] in self.HEXACO_ORDER else 999)
        )
        top_2 = [d[0] for d in sorted_dims[:2]]
        lowest = sorted_dims[-1][0] if sorted_dims else None
        
        TestResult.objects.update_or_create(
            session=session,
            defaults={'result_data': result_data, 'category_counts': {}}
        )
        
        TestTopCategories.objects.update_or_create(
            user=user,
            test_paper=test,
            defaults={
                'high_category': f"[{''.join(top_2)}]",
                'low_category': lowest
            }
        )
    
    def create_class12_motivation_test(self, user, test, scores):
        """Create Motivation test"""
        if not scores:
            scores = {'Achievement': 5, 'Power': 3, 'Affiliation': 2}
        
        start_time = timezone.now() - timedelta(minutes=20)
        end_time = timezone.now() - timedelta(minutes=3)
        
        session = TestSession.objects.create(
            user=user,
            test=test,
            start_time=start_time,
            end_time=end_time,
            is_completed=True,
            attempt_count=1
        )
        
        TestResult.objects.update_or_create(
            session=session,
            defaults={'category_counts': scores, 'result_data': {}}
        )
    
    def create_class12_career_test(self, user, test, scores):
        """Create Career Interest test"""
        if not scores:
            scores = {letter: random.randint(10, 20) for letter in self.RIASEC_ORDER}
        
        start_time = timezone.now() - timedelta(minutes=25)
        end_time = timezone.now() - timedelta(minutes=4)
        
        session = TestSession.objects.create(
            user=user,
            test=test,
            start_time=start_time,
            end_time=end_time,
            is_completed=True,
            attempt_count=1
        )
        
        result_data = {}
        for letter, score in scores.items():
            result_data[letter] = {
                'score': score,
                'count': 10,
                'average': score / 10,
                'name': self.RIASEC_NAMES.get(letter, letter)
            }
        
        sorted_dims = sorted(
            scores.items(),
            key=lambda x: (-x[1], self.RIASEC_ORDER.index(x[0]) if x[0] in self.RIASEC_ORDER else 999)
        )
        top_3 = [d[0] for d in sorted_dims[:3]]
        lowest = sorted_dims[-1][0] if sorted_dims else None
        
        TestResult.objects.update_or_create(
            session=session,
            defaults={'result_data': result_data, 'category_counts': {}}
        )
        
        TestTopCategories.objects.update_or_create(
            user=user,
            test_paper=test,
            defaults={
                'high_category': f"[{''.join(top_3)}]",
                'low_category': lowest
            }
        )
    
    def create_class12_aptitude_test(self, user, test, aptitude_data):
        """Create Aptitude test"""
        start_time = timezone.now() - timedelta(minutes=60)
        end_time = timezone.now() - timedelta(minutes=2)
        
        session = TestSession.objects.create(
            user=user,
            test=test,
            start_time=start_time,
            end_time=end_time,
            is_completed=True,
            attempt_count=1
        )
        
        sections_data = aptitude_data.get('sections', {})
        performance_levels = {
            'Above Average': [],
            'Average': [],
            'Below Average': []
        }
        
        result_data = {}
        
        for section_name, section_info in sections_data.items():
            section, _ = Sections.objects.get_or_create(
                test=test,
                title=section_name,
                defaults={'order': len(result_data) + 1}
            )
            
            section_start = start_time + timedelta(minutes=len(result_data) * 8)
            section_end = section_start + timedelta(minutes=7)
            
            section_session = SectionSession.objects.create(
                session=session,
                section=section,
                start_time=section_start,
                end_time=section_end,
                is_completed=True
            )
            
            correct = section_info.get('correct', 10)
            total = section_info.get('total', 15)
            accuracy = (correct / total) * 100 if total > 0 else 0
            score = round((correct / total) * 10, 2)
            
            result_data[section_name] = score
            
            if accuracy >= 70:
                performance_levels['Above Average'].append(section_name)
            elif accuracy >= 40:
                performance_levels['Average'].append(section_name)
            else:
                performance_levels['Below Average'].append(section_name)
            
            submitted_answers = {}
            for q_num in range(1, total + 1):
                is_correct = q_num <= correct
                submitted_answers[f'Question_{q_num}'] = {
                    'selected_answer': 'A' if is_correct else 'B',
                    'correct_answer': 'A',
                }
            
            UserResponse.objects.create(
                session=session,
                session_section=section_session,
                test=test,
                selected_answer={
                    'sections': {
                        section_name: {
                            'submitted_answers': submitted_answers,
                            'score': score,
                            'correct_count': correct,
                            'total_questions': total
                        }
                    }
                },
                attempt_number=1
            )
        
        result_data['performance_levels'] = performance_levels
        
        TestResult.objects.update_or_create(
            session=session,
            defaults={'result_data': result_data, 'category_counts': {}}
        )
        
        TestTopCategories.objects.update_or_create(
            user=user,
            test_paper=test,
            defaults={
                'high_category': json.dumps(performance_levels),
                'low_category': None
            }
        )
    
    def generate_checklist_for_class10_student(self, user, combo):
        """Generate checklist for Class 10 student"""
        test1_result = Results.objects.filter(user=user, test_paper='test1').first()
        
        if test1_result:
            scores = test1_result.scores
            riasec_scores = {}
            for letter in ['R', 'I', 'A', 'S', 'E', 'C']:
                riasec_scores[letter] = scores.get(f'sum_{letter}', 0)
            
            sorted_items = sorted(
                riasec_scores.items(),
                key=lambda x: (-x[1], self.RIASEC_ORDER.index(x[0]) if x[0] in self.RIASEC_ORDER else 999)
            )
            expected_code = ''.join([item[0] for item in sorted_items[:3]])
            
            self.checklist_manager.add_checklist_item(
                student_id=user.id,
                student_name=user.name,
                test_case='RIASEC 3-letter code generation (test1)',
                test_category='Class 10',
                specific_check='RIASEC Code',
                expected_result=f'Code should be: {expected_code}',
                verification_steps=(
                    f"1. Navigate to student report for {user.name}\n"
                    f"2. Check test1 (Personality/RIASEC) results\n"
                    f"3. Verify 3-letter code matches: {expected_code}\n"
                    f"4. Verify code is generated from top 3 scores\n"
                    f"5. If scores are tied, verify code uses RIASEC order (R, I, A, S, E, C)"
                ),
                report_url=f"{self.base_url}/app/Assessment_pdf_inst_user/{user.id}/"
            )
    
    def generate_checklist_for_class12_student(self, user, combo):
        """Generate checklist for Class 12 student"""
        test_sessions = TestSession.objects.filter(user=user)
        
        personality_session = test_sessions.filter(test__title__icontains='Personality').first()
        if personality_session:
            test_result = TestResult.objects.filter(session=personality_session).first()
            if test_result:
                result_data = test_result.result_data
                hexaco_scores = {}
                for letter in ['H', 'E', 'X', 'A', 'C', 'O']:
                    if letter in result_data:
                        hexaco_scores[letter] = result_data[letter].get('score', 0)
                
                sorted_items = sorted(
                    hexaco_scores.items(),
                    key=lambda x: (-x[1], self.HEXACO_ORDER.index(x[0]) if x[0] in self.HEXACO_ORDER else 999)
                )
                expected_code = ''.join([item[0] for item in sorted_items[:2]])
                
                self.checklist_manager.add_checklist_item(
                    student_id=user.id,
                    student_name=user.name,
                    test_case='HEXACO 2-letter code generation (Personality)',
                    test_category='Class 12',
                    specific_check='HEXACO Code',
                    expected_result=f'Code should be: {expected_code}',
                    verification_steps=(
                        f"1. Navigate to student report for {user.name}\n"
                        f"2. Check Personality Assessment results\n"
                        f"3. Verify 2-letter code matches: {expected_code}\n"
                        f"4. Verify code is generated from top 2 scores\n"
                        f"5. If scores are tied, verify code uses HEXACO order (H, E, X, A, C, O)"
                    ),
                    report_url=f"{self.base_url}/app_post_matric/web/test_results/{user.id}/"
                )
        
        career_session = test_sessions.filter(test__title__icontains='Career Interest').first()
        if career_session:
            test_result = TestResult.objects.filter(session=career_session).first()
            if test_result:
                result_data = test_result.result_data
                riasec_scores = {}
                for letter in ['R', 'I', 'A', 'S', 'E', 'C']:
                    if letter in result_data:
                        riasec_scores[letter] = result_data[letter].get('score', 0)
                
                sorted_items = sorted(
                    riasec_scores.items(),
                    key=lambda x: (-x[1], self.RIASEC_ORDER.index(x[0]) if x[0] in self.RIASEC_ORDER else 999)
                )
                expected_code = ''.join([item[0] for item in sorted_items[:3]])
                
                self.checklist_manager.add_checklist_item(
                    student_id=user.id,
                    student_name=user.name,
                    test_case='RIASEC 3-letter code generation (Career Interest)',
                    test_category='Class 12',
                    specific_check='RIASEC Code',
                    expected_result=f'Code should be: {expected_code}',
                    verification_steps=(
                        f"1. Navigate to student report\n"
                        f"2. Check Career Interest Inventory results\n"
                        f"3. Verify 3-letter code matches: {expected_code}\n"
                        f"4. Verify code is generated from top 3 scores\n"
                        f"5. If scores are tied, verify code uses RIASEC order (R, I, A, S, E, C)"
                    ),
                    report_url=f"{self.base_url}/app_post_matric/web/test_results/{user.id}/"
                )
        
        aptitude_session = test_sessions.filter(test__title__icontains='Aptitude').first()
        if aptitude_session:
            test_result = TestResult.objects.filter(session=aptitude_session).first()
            if test_result:
                result_data = test_result.result_data
                performance_levels = result_data.get('performance_levels', {})
                
                self.checklist_manager.add_checklist_item(
                    student_id=user.id,
                    student_name=user.name,
                    test_case='Aptitude Categorization',
                    test_category='Class 12',
                    specific_check='Above/Average/Below Average Categorization',
                    expected_result=f'Categories: Above={len(performance_levels.get("Above Average", []))}, '
                                   f'Average={len(performance_levels.get("Average", []))}, '
                                   f'Below={len(performance_levels.get("Below Average", []))}',
                    verification_steps=(
                        f"1. Navigate to student report\n"
                        f"2. Check Aptitude Assessment results\n"
                        f"3. Verify sections are categorized correctly\n"
                        f"4. Verify empty categories are handled gracefully"
                    ),
                    report_url=f"{self.base_url}/app_post_matric/web/test_results/{user.id}/"
                )


# Main execution
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python scripts/test_students_manager.py create [--limit N] [--class10-only] [--class12-only]')
        print('  python scripts/test_students_manager.py remove [--dry-run] [--confirm]')
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

