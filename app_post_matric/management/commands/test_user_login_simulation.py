"""
Test script to simulate user login and check if test sessions are found.

This simulates what happens when latika2010@gmail.com logs in and
checks if test sessions are properly retrieved.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q
from app_post_matric.models import TestSession, TestTopCategories
from users.backends import CustomUserBackend

User = get_user_model()


class Command(BaseCommand):
    help = 'Simulate user login and check test session retrieval'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='latika2010@gmail.com',
            help='Email to test'
        )

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Simulating Login for: {email} ===\n'))
        
        # Step 1: Simulate authentication (like CustomUserBackend does)
        self.stdout.write('Step 1: Authentication (CustomUserBackend logic)')
        self.stdout.write('-' * 50)
        
        # This is how CustomUserBackend finds the user
        try:
            user = User.objects.filter(Q(email__iexact=email) | Q(mobile=email)).first()
        except (ValueError, TypeError):
            user = User.objects.filter(Q(email__iexact=email) | Q(mobile=email)).first()
        
        if not user:
            self.stdout.write(self.style.ERROR(f'❌ User not found: {email}'))
            return
        
        self.stdout.write(f'✅ User found:')
        self.stdout.write(f'   ID: {user.id}')
        self.stdout.write(f'   Email: {user.email}')
        self.stdout.write(f'   Mobile: {user.mobile}')
        self.stdout.write(f'   Name: {user.name}')
        self.stdout.write(f'   Is Active: {user.is_active}')
        
        # Step 2: Check what request.user would be (simulated)
        self.stdout.write(f'\nStep 2: Simulating request.user (logged in user)')
        self.stdout.write('-' * 50)
        self.stdout.write(f'request.user.id = {user.id}')
        self.stdout.write(f'request.user.email = {user.email}')
        
        # Step 3: Query test sessions (like Results view does)
        self.stdout.write(f'\nStep 3: Querying Test Sessions (Results view logic)')
        self.stdout.write('-' * 50)
        
        # This is the exact query from Results view line 1030-1038
        query = {
            'user': user,  # This is request.user
            'is_completed': True
        }
        
        self.stdout.write(f'Query: {query}')
        
        latest_session = TestSession.objects.filter(**query).order_by('-end_time').first()
        
        if latest_session:
            self.stdout.write(self.style.SUCCESS(f'✅ Test session found!'))
            self.stdout.write(f'   Session ID: {latest_session.id}')
            self.stdout.write(f'   Test: {latest_session.test.title} (ID: {latest_session.test.id})')
            self.stdout.write(f'   Completed: {latest_session.end_time}')
            self.stdout.write(f'   User ID in session: {latest_session.user.id}')
            self.stdout.write(f'   User email in session: {latest_session.user.email}')
            
            # Verify user IDs match
            if latest_session.user.id == user.id:
                self.stdout.write(self.style.SUCCESS('   ✅ User IDs match!'))
            else:
                self.stdout.write(self.style.ERROR(
                    f'   ❌ User ID MISMATCH! Session user ID: {latest_session.user.id}, Logged in user ID: {user.id}'
                ))
        else:
            self.stdout.write(self.style.ERROR('❌ No test session found!'))
            self.stdout.write('   This would show "No completed test found" error')
            
            # Debug: Check if sessions exist for this user
            all_sessions = TestSession.objects.filter(user=user)
            self.stdout.write(f'\n   Debug: Total sessions for user {user.id}: {all_sessions.count()}')
            
            completed_sessions = all_sessions.filter(is_completed=True)
            self.stdout.write(f'   Debug: Completed sessions: {completed_sessions.count()}')
            
            if completed_sessions.exists():
                self.stdout.write(self.style.WARNING('   ⚠️  Sessions exist but query returned None!'))
                for session in completed_sessions[:3]:
                    self.stdout.write(f'      - Session {session.id}: {session.test.title}, Completed: {session.is_completed}')
        
        # Step 4: Check TestTopCategories
        self.stdout.write(f'\nStep 4: Checking TestTopCategories')
        self.stdout.write('-' * 50)
        
        if latest_session:
            categories = TestTopCategories.objects.filter(
                user=user,
                test_paper=latest_session.test
            )
            self.stdout.write(f'   Found {categories.count()} categories for test {latest_session.test.title}')
        else:
            categories = TestTopCategories.objects.filter(user=user)
            self.stdout.write(f'   Found {categories.count()} total categories for user')
        
        # Step 5: Check all test completion status
        self.stdout.write(f'\nStep 5: Checking All Test Completion Status')
        self.stdout.write('-' * 50)
        
        test1_completed = TestSession.objects.filter(
            user=user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        self.stdout.write(f'   Test 1 (Personality): {"✅" if test1_completed else "❌"}')
        self.stdout.write(f'   Test 2 (Motivation): {"✅" if test2_completed else "❌"}')
        self.stdout.write(f'   Test 3 (Career Interest): {"✅" if test3_completed else "❌"}')
        self.stdout.write(f'   Test 4 (Aptitude): {"✅" if test4_completed else "❌"}')
        
        all_completed = test1_completed and test2_completed and test3_completed and test4_completed
        self.stdout.write(f'\n   All tests completed: {"✅ YES" if all_completed else "❌ NO"}')
        
        # Step 6: Check if there are other users with same email
        self.stdout.write(f'\nStep 6: Checking for Other Users with Same Email')
        self.stdout.write('-' * 50)
        
        all_users_with_email = User.objects.filter(email__iexact=email)
        if all_users_with_email.count() > 1:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Found {all_users_with_email.count()} users with email {email}:'))
            for u in all_users_with_email:
                sessions_count = TestSession.objects.filter(user=u, is_completed=True).count()
                self.stdout.write(f'      - User ID {u.id}: {sessions_count} completed sessions')
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ Only one user with this email'))
        
        self.stdout.write(self.style.SUCCESS('\n=== Simulation Complete ===\n'))
