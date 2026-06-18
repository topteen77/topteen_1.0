"""
Seed dashboard point rules: deactivate legacy rules and activate the current set.
Point values remain editable in Admin > Core > Dashboard Point Rules.
"""
from django.core.management.base import BaseCommand
from core.models import DashboardPointRule


ACTIVE_POINT_RULES = [
    ('registration', 50),
    ('profile_complete', 50),
    ('payment_success', 150),
    ('personality_test_complete', 100),
    ('motivation_test_complete', 70),
    ('interest_test_complete', 70),
    ('aptitude_test_complete', 200),
    ('report_reading', 150),
]


class Command(BaseCommand):
    help = 'Deactivate legacy dashboard point rules and seed the current active rule set'

    def handle(self, *args, **options):
        deactivated = DashboardPointRule.objects.filter(active=True).update(active=False)
        self.stdout.write(self.style.WARNING(f'Deactivated {deactivated} existing rule(s).'))

        for rule_key, points in ACTIVE_POINT_RULES:
            rule, created = DashboardPointRule.objects.update_or_create(
                rule_key=rule_key,
                defaults={'points': points, 'active': True},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(f'{action} {rule.rule_key}: {rule.points} pts (active)')
            )

        self.stdout.write(self.style.SUCCESS('Dashboard point rules seeded successfully.'))
