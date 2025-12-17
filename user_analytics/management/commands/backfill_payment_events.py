"""
Management command to backfill UserEvent records from existing Payment records.
This is useful when signals weren't firing or Celery wasn't running.
"""
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from payments.models import Payment
from psychometric_tests.models import PsychometricTestPayment
from skilllab.models import SkilllabCoursePayment
from user_analytics.models import UserEvent
from core import choices
from decimal import Decimal


class Command(BaseCommand):
    help = 'Backfill UserEvent records from existing Payment records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('Backfilling Payment Events'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No records will be created'))
        
        # Backfill Payment model records
        self.backfill_payment_model(dry_run)
        
        # Backfill PsychometricTestPayment records
        self.backfill_psychometric_payments(dry_run)
        
        # Backfill SkilllabCoursePayment records
        self.backfill_skilllab_payments(dry_run)
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Backfill Complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

    def backfill_payment_model(self, dry_run):
        """Backfill from Payment model"""
        self.stdout.write('\nProcessing Payment model...')
        
        payments = Payment.objects.all().select_related('user')
        total = payments.count()
        successful = payments.filter(is_success=choices.YesNoChoices.YES).count()
        
        self.stdout.write(f'  Total Payments: {total}')
        self.stdout.write(f'  Successful: {successful}')
        
        created_count = 0
        skipped_count = 0
        
        for payment in payments:
            # Check if event already exists
            content_type = ContentType.objects.get_for_model(Payment)
            existing = UserEvent.objects.filter(
                content_type=content_type,
                object_id=payment.id,
                event_type__in=['payment_success', 'payment_failed', 'payment_pending']
            ).exists()
            
            if existing:
                skipped_count += 1
                continue
            
            # Determine event type
            if payment.is_success == choices.YesNoChoices.YES:
                event_type = 'payment_success'
                event_name = f'Payment Success - {payment.get_obj_type_display()}'
                event_value = Decimal(str(payment.amount / 100))  # Convert paise to rupees
            else:
                # Check if payment was created recently (likely pending)
                # For backfill, we'll mark old failed payments as failed
                event_type = 'payment_failed'
                event_name = f'Payment Failed - {payment.get_obj_type_display()}'
                event_value = Decimal('0')
            
            if not dry_run:
                UserEvent.objects.create(
                    user=payment.user,
                    event_type=event_type,
                    event_name=event_name,
                    event_value=event_value,
                    content_type=content_type,
                    object_id=payment.id,
                    metadata={
                        'gateway': payment.get_gateway_display() if hasattr(payment, 'get_gateway_display') else 'Unknown',
                        'obj_type': payment.get_obj_type_display(),
                        'obj_id': payment.obj_id,
                        'gateway_order_id': payment.gateway_order_id or '',
                        'source': 'backfill',
                    },
                    created=payment.created,  # Use original payment date
                )
            
            created_count += 1
            
            if created_count % 10 == 0:
                self.stdout.write(f'  Processed {created_count} payments...')
        
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} events'))
        self.stdout.write(self.style.WARNING(f'  Skipped (already exists): {skipped_count} events'))

    def backfill_psychometric_payments(self, dry_run):
        """Backfill from PsychometricTestPayment model"""
        self.stdout.write('\nProcessing PsychometricTestPayment model...')
        
        payments = PsychometricTestPayment.objects.all().select_related('user')
        total = payments.count()
        successful = payments.filter(is_success=choices.YesNoChoices.YES).count()
        
        self.stdout.write(f'  Total Payments: {total}')
        self.stdout.write(f'  Successful: {successful}')
        
        created_count = 0
        skipped_count = 0
        
        for payment in payments:
            content_type = ContentType.objects.get_for_model(PsychometricTestPayment)
            existing = UserEvent.objects.filter(
                content_type=content_type,
                object_id=payment.id,
                event_type__in=['payment_success', 'payment_failed', 'payment_pending']
            ).exists()
            
            if existing:
                skipped_count += 1
                continue
            
            if payment.is_success == choices.YesNoChoices.YES:
                event_type = 'payment_success'
                event_name = f'Psychometric Test Payment - {payment.get_test_name()}'
                event_value = Decimal(str(payment.amount / 100))
            else:
                event_type = 'payment_failed'
                event_name = f'Psychometric Test Payment - {payment.get_test_name()}'
                event_value = Decimal('0')
            
            if not dry_run:
                UserEvent.objects.create(
                    user=payment.user,
                    event_type=event_type,
                    event_name=event_name,
                    event_value=event_value,
                    content_type=content_type,
                    object_id=payment.id,
                    metadata={
                        'test_type': payment.get_test_type_display(),
                        'test_name': payment.get_test_name(),
                        'source': 'backfill',
                    },
                    created=payment.created,
                )
            
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} events'))
        self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count} events'))

    def backfill_skilllab_payments(self, dry_run):
        """Backfill from SkilllabCoursePayment model"""
        self.stdout.write('\nProcessing SkilllabCoursePayment model...')
        
        payments = SkilllabCoursePayment.objects.all().select_related('user', 'skilllab_course')
        total = payments.count()
        successful = payments.filter(is_success=choices.YesNoChoices.YES).count()
        
        self.stdout.write(f'  Total Payments: {total}')
        self.stdout.write(f'  Successful: {successful}')
        
        created_count = 0
        skipped_count = 0
        
        for payment in payments:
            content_type = ContentType.objects.get_for_model(SkilllabCoursePayment)
            existing = UserEvent.objects.filter(
                content_type=content_type,
                object_id=payment.id,
                event_type='skilllab_enrolled'
            ).exists()
            
            if existing:
                skipped_count += 1
                continue
            
            if payment.is_success == choices.YesNoChoices.YES:
                if not dry_run:
                    UserEvent.objects.create(
                        user=payment.user,
                        event_type='skilllab_enrolled',
                        event_name='SkillLab Course Enrolled',
                        event_value=Decimal(str(payment.amount / 100)),
                        content_type=content_type,
                        object_id=payment.id,
                    metadata={
                        'course_id': payment.skilllab_course.id if payment.skilllab_course else None,
                        'course_name': getattr(payment.skilllab_course, 'title', getattr(payment.skilllab_course, 'name', 'Unknown')) if payment.skilllab_course else 'Unknown',
                        'source': 'backfill',
                    },
                        created=payment.created,
                    )
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} events'))
        self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count} events'))

