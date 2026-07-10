from decimal import Decimal

from django.core.management.base import BaseCommand

from core import choices
from psychometric_tests.models import Assessment, PackageAssessment, PsychometricPackage
from psychometric_tests.package_catalog import (
    CLASS10_ASSESSMENTS,
    DEFAULT_PACKAGES,
    POST_MATRIC_ASSESSMENTS,
)


class Command(BaseCommand):
    help = 'Seed psychometric assessments and default packages.'

    def handle(self, *args, **options):
        for item in CLASS10_ASSESSMENTS:
            Assessment.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name': item['name'],
                    'track': choices.PsychometricTrack.CLASS10,
                    'engine_key': item['engine_key'],
                    'is_active': True,
                },
            )
        for item in POST_MATRIC_ASSESSMENTS:
            Assessment.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name': item['name'],
                    'track': choices.PsychometricTrack.POST_MATRIC,
                    'engine_key': item['engine_key'],
                    'is_active': True,
                },
            )

        for pkg in DEFAULT_PACKAGES:
            package, _ = PsychometricPackage.objects.update_or_create(
                code=pkg['code'],
                defaults={
                    'name': pkg['name'],
                    'track': pkg['track'],
                    'credit_cost': pkg['credit_cost'],
                    'list_price': Decimal(pkg['list_price']),
                    'is_legacy_bundle': pkg.get('is_legacy_bundle', False),
                    'is_active': True,
                },
            )
            desired_codes = set(pkg['assessment_codes'])
            for order, code in enumerate(pkg['assessment_codes']):
                assessment = Assessment.objects.get(code=code)
                pa, _ = PackageAssessment.objects.complete().update_or_create(
                    package=package,
                    assessment=assessment,
                    defaults={
                        'sort_order': order,
                        'object_status': choices.ObjectStatus.ACTIVE,
                    },
                )
            stale = PackageAssessment.objects.complete().filter(package=package).exclude(
                assessment__code__in=desired_codes
            )
            for pa in stale:
                pa.delete(hard_delete=True)

        self.stdout.write(self.style.SUCCESS('Psychometric package catalog seeded.'))
