"""Helpers for admin-configurable dashboard point rules and level band caps."""

from django.db.models import Sum


def get_active_point_rules_queryset():
    from core.models import DashboardPointRule
    return DashboardPointRule.objects.filter(active=True).order_by('order', 'rule_key')


def get_active_point_rules_total():
    """Maximum achievable points: sum of all active DashboardPointRule rows."""
    total = get_active_point_rules_queryset().aggregate(total=Sum('points'))['total']
    if total is not None:
        return int(total)

    from core.dashboard_stats import DEFAULT_POINT_RULES
    return sum(DEFAULT_POINT_RULES.values())


def get_registration_points():
    """Points for account registration — minimum milestone for level bands."""
    from core.models import DashboardPointRule
    rule = get_active_point_rules_queryset().filter(rule_key='registration').first()
    if rule:
        return int(rule.points)
    from core.dashboard_stats import DEFAULT_POINT_RULES
    return int(DEFAULT_POINT_RULES.get('registration', 50))


def get_cumulative_point_milestones():
    """
    Cumulative point totals after each active rule in order.
    Level band min_points must match one of these values (starting at registration).
    """
    from core.dashboard_stats import DEFAULT_POINT_RULES, RULE_LABELS

    rules = list(get_active_point_rules_queryset().values('rule_key', 'points', 'order'))
    if not rules:
        rules = [
            {'rule_key': key, 'points': points, 'order': index}
            for index, (key, points) in enumerate(DEFAULT_POINT_RULES.items(), start=1)
        ]

    milestones = []
    total = 0
    for rule in rules:
        total += int(rule['points'])
        milestones.append({
            'rule_key': rule['rule_key'],
            'label': RULE_LABELS.get(rule['rule_key'], rule['rule_key'].replace('_', ' ').title()),
            'step_points': int(rule['points']),
            'cumulative': total,
        })
    return milestones


def get_valid_level_band_min_points():
    """Allowed min_points values: each cumulative milestone from active point rules."""
    return {milestone['cumulative'] for milestone in get_cumulative_point_milestones()}


def get_min_level_band_points():
    """Lowest allowed min_points (account registration milestone)."""
    milestones = get_cumulative_point_milestones()
    if milestones:
        return milestones[0]['cumulative']
    return get_registration_points()


def validate_level_band_min_points(min_points):
    """Return an error message if min_points is outside allowed range, else None."""
    valid = sorted(get_valid_level_band_min_points())
    min_allowed = get_min_level_band_points()
    max_pts = get_active_point_rules_total()

    if min_points > max_pts:
        return (
            f'Minimum points cannot exceed the total from active point rules ({max_pts} pts).'
        )
    if min_points < min_allowed:
        return (
            f'Minimum points cannot be below account registration ({min_allowed} pts).'
        )
    if min_points not in valid:
        labels = [
            f"{m['cumulative']} ({m['label']})"
            for m in get_cumulative_point_milestones()
        ]
        return (
            'Min points must match a cumulative milestone from active point rules: '
            f'{", ".join(labels)}.'
        )
    return None
