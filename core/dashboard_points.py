"""Helpers for admin-configurable dashboard point rules and level band caps."""

from django.db.models import Sum

from core.psychometric_grade import (
    CLASS10_TRACK,
    POST_MATRIC_TRACK,
    get_point_rules_with_applies_to,
    resolve_rule_applies_to,
    rule_applies_to_user,
)


def get_active_point_rules_queryset():
    from core.models import DashboardPointRule
    return DashboardPointRule.objects.filter(active=True).order_by('order', 'rule_key')


def _active_rules_list(excluded_rule_keys=None, track=None):
    rules = get_point_rules_with_applies_to(active_only=True)
    if track is not None:
        rules = [
            rule for rule in rules
            if rule_applies_to_user(
                resolve_rule_applies_to(rule['rule_key'], rule.get('applies_to') or ''),
                track,
            )
        ]
    elif excluded_rule_keys:
        excluded = set(excluded_rule_keys)
        rules = [rule for rule in rules if rule['rule_key'] not in excluded]
    return rules


def get_active_point_rules_total(excluded_rule_keys=None, track=None):
    """Maximum achievable points for a rule set (optionally filtered by track)."""
    if track is not None or excluded_rule_keys:
        milestones = get_cumulative_point_milestones(
            excluded_rule_keys=excluded_rule_keys,
            track=track,
        )
        if milestones:
            return int(milestones[-1]['cumulative'])
        return 0

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


def get_cumulative_point_milestones(excluded_rule_keys=None, track=None):
    """
    Cumulative point totals after each active rule in order.
    Level band min_points must match one of these values (starting at registration).
    """
    from core.dashboard_stats import RULE_LABELS

    milestones = []
    total = 0
    for rule in _active_rules_list(excluded_rule_keys=excluded_rule_keys, track=track):
        total += int(rule['points'])
        applies_to = resolve_rule_applies_to(rule['rule_key'], rule.get('applies_to') or '')
        milestones.append({
            'rule_key': rule['rule_key'],
            'label': RULE_LABELS.get(rule['rule_key'], rule['rule_key'].replace('_', ' ').title()),
            'step_points': int(rule['points']),
            'cumulative': total,
            'applies_to': get_applies_to_display_label(applies_to),
        })
    return milestones


def get_applies_to_display_label(applies_to: str) -> str:
    from core.psychometric_grade import get_applies_to_display
    return get_applies_to_display(applies_to)


def get_valid_level_band_min_points(excluded_rule_keys=None):
    """Allowed min_points values: cumulative milestones from active point rules."""
    if excluded_rule_keys is not None:
        return {milestone['cumulative'] for milestone in get_cumulative_point_milestones(excluded_rule_keys)}

    post_matric = {
        milestone['cumulative']
        for milestone in get_cumulative_point_milestones(track=POST_MATRIC_TRACK)
    }
    class10 = {
        milestone['cumulative']
        for milestone in get_cumulative_point_milestones(track=CLASS10_TRACK)
    }
    return post_matric | class10


def get_min_level_band_points():
    """Lowest allowed min_points (account registration milestone)."""
    milestones = get_cumulative_point_milestones()
    if milestones:
        return milestones[0]['cumulative']
    return get_registration_points()


def get_max_achievable_points_by_track():
    """Return max XP caps for each psychometric track."""
    return {
        'post_matric': get_active_point_rules_total(track=POST_MATRIC_TRACK),
        'class10': get_active_point_rules_total(track=CLASS10_TRACK),
    }


def validate_level_band_min_points(min_points):
    """Return an error message if min_points is outside allowed range, else None."""
    valid = sorted(get_valid_level_band_min_points())
    min_allowed = get_min_level_band_points()
    max_pts = get_active_point_rules_total(track=POST_MATRIC_TRACK)

    if min_points > max_pts:
        return (
            f'Minimum points cannot exceed the total from active point rules ({max_pts} pts).'
        )
    if min_points < min_allowed:
        return (
            f'Minimum points cannot be below account registration ({min_allowed} pts).'
        )
    if min_points not in valid:
        post_matric_labels = [
            f"{m['cumulative']} ({m['label']})"
            for m in get_cumulative_point_milestones(track=POST_MATRIC_TRACK)
        ]
        class10_labels = [
            f"{m['cumulative']} ({m['label']})"
            for m in get_cumulative_point_milestones(track=CLASS10_TRACK)
        ]
        return (
            'Min points must match a cumulative milestone from active point rules. '
            f'Class 11-12+: {", ".join(post_matric_labels)}. '
            f'Class 10 and below: {", ".join(class10_labels)}.'
        )
    return None
