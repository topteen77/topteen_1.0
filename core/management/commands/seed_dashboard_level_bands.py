"""
Seed dashboard level bands using cumulative point milestones from active point rules.
Minimum level starts at account registration; maximum level uses the full rules total.
"""
from django.core.management.base import BaseCommand
from core.models import DashboardLevelBand
from core.dashboard_points import get_cumulative_point_milestones, get_active_point_rules_total


def _milestone_total(rule_key):
    for milestone in get_cumulative_point_milestones():
        if milestone['rule_key'] == rule_key:
            return milestone['cumulative']
    return None


class Command(BaseCommand):
    help = 'Seed dashboard level bands from cumulative point rule milestones'

    def handle(self, *args, **options):
        max_pts = get_active_point_rules_total()
        registration_pts = _milestone_total('registration') or 50
        payment_pts = _milestone_total('payment_success') or registration_pts
        interest_pts = _milestone_total('interest_test_complete') or max_pts
        defaults = [
            ('Rookie', registration_pts, 0),
            ('Explorer', payment_pts, 1),
            ('Champion', interest_pts, 2),
            ('Legend', max_pts, 3),
        ]

        for name, min_points, order in defaults:
            band, created = DashboardLevelBand.objects.update_or_create(
                name=name,
                defaults={'min_points': min_points, 'order': order},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(f'{action} {band.name}: {band.min_points} pts (order {band.order})')
            )

        self.stdout.write(self.style.SUCCESS('Dashboard level bands seeded successfully.'))
