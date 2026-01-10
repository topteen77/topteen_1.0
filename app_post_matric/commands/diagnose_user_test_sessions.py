"""
Django management command to diagnose user-test session mismatches.

This command checks for:
1. Duplicate users with the same email
2. Test sessions linked to users that don't match authenticated user
3. Orphaned test sessions (user deleted but sessions remain)
4. Specific user analysis (e.g., latika2010@gmail.com)

Usage:
    python manage.py diagnose_user_test_sessions
    python manage.py diagnose_user_test_sessions --email latika2010@gmail.com
    python manage.py diagnose_user_test_sessions --fix-duplicates --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.conf import settings
from users.models import User
from app_post_matric.models import TestSession, TestTopCategories, TestResult
from app.models import Results as OldResults


class Command(BaseCommand):
    help = 'Diagnose user-test session mismatches and duplicate users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Check specific email address (e.g., latika2010@gmail.com)'
        )
        parser.add_argument(
            '--check-duplicates',
            action='store_true',
            help='Check for duplicate users with same email'
        )
        parser.add_argument(
            '--check-sessions',
            action='store_true',
            help='Check for test session mismatches'
        )
        parser.add_argument(
            '--check-orphaned',
            action='store_true',
            help='Check for orphaned test sessions (user deleted)'
        )
        parser.add_argument(
            '--fix-duplicates',
            action='store_true',
            help='Fix duplicate users by merging test sessions (use with --dry-run first)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        email = options.get('email')
        check_duplicates = options.get('check_duplicates', True)
        check_sessions = options.get('check_sessions', True)
        check_orphaned = options.get('check_orphaned', True)
        fix_duplicates = options.get('fix_duplicates', False)
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)

        self.stdout.write(self.style.SUCCESS('\n=== User-Test Session Diagnostic ===\n'))

        # Check specific email if provided
        if email:
            self.check_specific_user(email, verbose)
            return

        # Check for duplicate users
        if check_duplicates:
            self.check_duplicate_users(verbose, fix_duplicates, dry_run)

        # Check for test session mismatches
        if check_sessions:
            self.check_test_session_mismatches(verbose)

        # Check for orphaned sessions
        if check_orphaned:
            self.check_orphaned_sessions(verbose)

        self.stdout.write(self.style.SUCCESS('\n=== Diagnostic Complete ===\n'))

    def check_specific_user(self, email, verbose):
        """Check a specific user by email."""
        self.stdout.write(self.style.WARNING(f'\n--- Checking User: {email} ---\n'))

        # Find all users with this email (case-insensitive)
        users = User.objects.filter(email__iexact=email)
        user_count = users.count()

        if user_count == 0:
            self.stdout.write(self.style.ERROR(f'❌ No user found with email: {email}'))
            return

        if user_count > 1:
            self.stdout.write(self.style.WARNING(f'⚠️  Found {user_count} users with email: {email}'))
            self.stdout.write(self.style.WARNING('This is a duplicate user issue!\n'))

        for user in users:
            self.stdout.write(f'\n📧 User ID: {user.id}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Mobile: {user.mobile}')
            self.stdout.write(f'   Name: {user.name}')
            self.stdout.write(f'   Created: {user.created}')
            self.stdout.write(f'   Is Active: {user.is_active}')

            # Check TestSession records (new system)
            test_sessions = TestSession.objects.filter(user=user)
            completed_sessions = test_sessions.filter(is_completed=True)
            
            self.stdout.write(f'\n   Test Sessions (app_post_matric):')
            self.stdout.write(f'      Total: {test_sessions.count()}')
            self.stdout.write(f'      Completed: {completed_sessions.count()}')

            if verbose and completed_sessions.exists():
                self.stdout.write(f'      Completed Sessions:')
                for session in completed_sessions[:5]:
                    self.stdout.write(f'         - Test: {session.test.title} (ID: {session.test.id})')
                    self.stdout.write(f'           Completed: {session.end_time}')
                    self.stdout.write(f'           Session ID: {session.id}')

            # Check TestTopCategories
            categories = TestTopCategories.objects.filter(user=user)
            self.stdout.write(f'      TestTopCategories: {categories.count()}')

            # Check TestResult
            test_results = TestResult.objects.filter(session__user=user)
            self.stdout.write(f'      TestResults: {test_results.count()}')

            # Check old Results model (app.Results)
            old_results = OldResults.objects.filter(user=user)
            self.stdout.write(f'\n   Old Results (app.Results):')
            self.stdout.write(f'      Total: {old_results.count()}')

            if verbose and old_results.exists():
                for result in old_results[:3]:
                    self.stdout.write(f'         - {result.test_paper} (Modified: {result.modified})')

            # Check if this user would be found by authentication
            auth_user = User.objects.filter(Q(email__iexact=email) | Q(mobile=email)).first()
            if auth_user:
                if auth_user.id != user.id:
                    self.stdout.write(self.style.ERROR(
                        f'\n   ⚠️  AUTHENTICATION MISMATCH!'
                    ))
                    self.stdout.write(f'      Authentication would return User ID: {auth_user.id}')
                    self.stdout.write(f'      But this user has ID: {user.id}')
                    self.stdout.write(self.style.WARNING(
                        f'      This means test sessions may not be found!'
                    ))

    def check_duplicate_users(self, verbose, fix_duplicates, dry_run):
        """Check for duplicate users with same email."""
        self.stdout.write(self.style.WARNING('\n--- Checking for Duplicate Users ---\n'))

        # Find emails with multiple users
        duplicate_emails = User.objects.values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1, email__isnull=False)

        duplicate_count = duplicate_emails.count()

        if duplicate_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No duplicate users found'))
            return

        self.stdout.write(self.style.ERROR(f'❌ Found {duplicate_count} emails with duplicate users:\n'))

        total_duplicates = 0
        for item in duplicate_emails:
            email = item['email']
            users = User.objects.filter(email__iexact=email).order_by('id')
            user_count = users.count()
            total_duplicates += (user_count - 1)

            self.stdout.write(f'📧 Email: {email} ({user_count} users)')
            
            primary_user = users.first()
            duplicate_users = users[1:]

            if verbose:
                self.stdout.write(f'   Primary User ID: {primary_user.id} (Created: {primary_user.created})')
                for dup_user in duplicate_users:
                    self.stdout.write(f'   Duplicate User ID: {dup_user.id} (Created: {dup_user.created})')

            # Count test sessions for each user
            for user in users:
                sessions = TestSession.objects.filter(user=user, is_completed=True)
                old_results = OldResults.objects.filter(user=user)
                if sessions.exists() or old_results.exists():
                    self.stdout.write(f'      User {user.id}: {sessions.count()} sessions, {old_results.count()} old results')

            if fix_duplicates:
                self.stdout.write(self.style.WARNING(f'\n   🔧 Fixing duplicates for {email}...'))
                if not dry_run:
                    self.merge_duplicate_users(primary_user, duplicate_users)
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Merged {len(duplicate_users)} duplicate users'))
                else:
                    self.stdout.write(self.style.WARNING(f'   [DRY RUN] Would merge {len(duplicate_users)} duplicate users'))

        self.stdout.write(f'\n📊 Total duplicate users to fix: {total_duplicates}')

    def merge_duplicate_users(self, primary_user, duplicate_users):
        """Merge test sessions from duplicate users to primary user."""
        for dup_user in duplicate_users:
            # Migrate TestSession records
            TestSession.objects.filter(user=dup_user).update(user=primary_user)
            
            # Migrate TestTopCategories
            TestTopCategories.objects.filter(user=dup_user).update(user=primary_user)
            
            # Migrate TestCompletionPopup (if exists)
            from app_post_matric.models import TestCompletionPopup
            TestCompletionPopup.objects.filter(user=dup_user).update(user=primary_user)
            
            # Migrate old Results
            OldResults.objects.filter(user=dup_user).update(user=primary_user)
            
            # Note: We don't delete the duplicate user as it might have other relationships
            # The user can be manually deleted after verification

    def check_test_session_mismatches(self, verbose):
        """Check for test sessions that might not match authenticated user."""
        self.stdout.write(self.style.WARNING('\n--- Checking Test Session Mismatches ---\n'))

        # Find users with test sessions
        users_with_sessions = User.objects.filter(
            test_sessions__is_completed=True
        ).distinct().annotate(
            session_count=Count('test_sessions', filter=Q(test_sessions__is_completed=True))
        ).order_by('-session_count')[:20]

        if not users_with_sessions.exists():
            self.stdout.write('ℹ️  No users with completed test sessions found')
            return

        self.stdout.write(f'Found {users_with_sessions.count()} users with test sessions\n')

        mismatch_count = 0
        for user in users_with_sessions:
            # Check if authentication would find this user
            if user.email:
                auth_user = User.objects.filter(
                    Q(email__iexact=user.email) | Q(mobile=user.email)
                ).first()
                
                if auth_user and auth_user.id != user.id:
                    mismatch_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'❌ Mismatch for email: {user.email}'
                    ))
                    self.stdout.write(f'   User with sessions: ID {user.id}')
                    self.stdout.write(f'   User found by auth: ID {auth_user.id}')
                    self.stdout.write(f'   Sessions: {user.session_count}')

        if mismatch_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No authentication mismatches found'))
        else:
            self.stdout.write(self.style.ERROR(f'\n⚠️  Found {mismatch_count} potential mismatches'))

    def check_orphaned_sessions(self, verbose):
        """Check for test sessions with deleted users."""
        self.stdout.write(self.style.WARNING('\n--- Checking for Orphaned Sessions ---\n'))

        # This would require raw SQL to check for foreign key violations
        # Django ORM won't show orphaned records due to foreign key constraints
        
        # Check if any test sessions have user_id that doesn't exist
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ts.id, ts.user_id, ts.test_id, ts.is_completed
                FROM app_post_matric_testsession ts
                LEFT JOIN users_user u ON ts.user_id = u.id
                WHERE u.id IS NULL
                LIMIT 10
            """)
            
            orphaned = cursor.fetchall()
            
            if orphaned:
                self.stdout.write(self.style.ERROR(f'❌ Found {len(orphaned)} orphaned test sessions:'))
                for row in orphaned:
                    self.stdout.write(f'   Session ID: {row[0]}, User ID: {row[1]} (user deleted)')
            else:
                self.stdout.write(self.style.SUCCESS('✅ No orphaned test sessions found'))
