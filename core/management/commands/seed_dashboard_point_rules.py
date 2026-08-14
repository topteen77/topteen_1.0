"""
Seed dashboard point rules: deactivate legacy rules and activate the current set.
Point values and applies-to track remain editable in Admin > Core > Dashboard Point Rules.
"""
from django.core.management.base import BaseCommand
from core.dashboard_stats import RULE_LABELS
from core.models import DashboardPointRule, DashboardRuleAppliesTo


ACTIVE_POINT_RULES = [
    ('registration', 50, 1, DashboardRuleAppliesTo.ALL),
    ('profile_complete', 50, 2, DashboardRuleAppliesTo.ALL),
    ('payment_success', 150, 3, DashboardRuleAppliesTo.ALL),
    ('personality_test_complete', 100, 4, DashboardRuleAppliesTo.ALL),
    ('motivation_test_complete', 70, 5, DashboardRuleAppliesTo.CLASS_11_12_PLUS),
    ('interest_test_complete', 70, 6, DashboardRuleAppliesTo.ALL),
    ('aptitude_test_complete', 200, 7, DashboardRuleAppliesTo.ALL),
    ('report_reading', 150, 8, DashboardRuleAppliesTo.ALL),
]


class Command(BaseCommand):
    help = 'Deactivate legacy dashboard point rules and seed the current active rule set'

    def handle(self, *args, **options):
        deactivated = DashboardPointRule.objects.filter(active=True).update(active=False)
        self.stdout.write(self.style.WARNING(f'Deactivated {deactivated} existing rule(s).'))

        for rule_key, points, order, applies_to in ACTIVE_POINT_RULES:
            label = RULE_LABELS.get(rule_key, rule_key.replace('_', ' ').title())
            rule, created = DashboardPointRule.objects.update_or_create(
                rule_key=rule_key,
                defaults={
                    'label': label,
                    'points': points,
                    'order': order,
                    'applies_to': applies_to,
                    'active': True,
                },
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{action} {rule.rule_key} ({rule.label}): {rule.points} pts, {rule.applies_to} (active)'
                )
            )

        self.stdout.write(self.style.SUCCESS('Dashboard point rules seeded successfully.'))
