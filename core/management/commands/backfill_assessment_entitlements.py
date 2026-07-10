from django.core.management.base import BaseCommand

from core import choices
from core.psychometric_grade import CLASS10_TRACK, POST_MATRIC_TRACK, get_student_psychometric_track
from psychometric_tests.models import Assessment, StudentAssessmentEntitlement
from institute.models import StudentManagement
from psychometric_tests.models import PsychometricTestPayment


class Command(BaseCommand):
    help = 'Backfill assessment entitlements for legacy bundle users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report counts without writing entitlements.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        created = 0
        users_seen = set()

        payment_users = PsychometricTestPayment.objects.filter(
            is_success=choices.YesNoChoices.YES
        ).select_related('user')
        for payment in payment_users:
            user = payment.user
            if not user or user.id in users_seen:
                continue
            track = (
                POST_MATRIC_TRACK
                if payment.test_type == choices.PsychometricTestType.ADVANCED
                else CLASS10_TRACK
            )
            created += self._grant_track(user, track, dry_run)
            users_seen.add(user.id)

        full_bundle_institute_students = StudentManagement.objects.filter(
            institute__psychometric_access_mode=choices.PsychometricAccessMode.FULL_BUNDLE,
        ).select_related('student', 'institute')
        for sm in full_bundle_institute_students:
            user = sm.student
            if not user or user.id in users_seen:
                continue
            track = get_student_psychometric_track(user)
            created += self._grant_track(user, track, dry_run)
            users_seen.add(user.id)

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry run: would upsert {created} entitlements.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Backfilled {created} entitlements for {len(users_seen)} users.'))

    def _grant_track(self, user, track, dry_run):
        assessment_codes = list(
            Assessment.objects.filter(
                track=(
                    choices.PsychometricTrack.POST_MATRIC
                    if track == POST_MATRIC_TRACK
                    else choices.PsychometricTrack.CLASS10
                ),
                is_active=True,
            ).values_list('id', flat=True)
        )
        count = 0
        for assessment_id in assessment_codes:
            if dry_run:
                count += 1
                continue
            _, was_created = StudentAssessmentEntitlement.objects.update_or_create(
                user=user,
                assessment_id=assessment_id,
                defaults={
                    'source': choices.EntitlementSource.LEGACY_BUNDLE,
                    'package_assignment': None,
                    'is_active': True,
                    'revoked_at': None,
                },
            )
            count += 1
        return count
