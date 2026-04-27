"""
Student dashboard statistics: trophies, points, streak, level.
Reads from admin-configurable models (DashboardLevelBand, DashboardPointRule,
DashboardTrophyDefinition, DashboardStreakConfig) and existing user/test data.
"""

from django.utils import timezone
from django.db.models import Count


# Rule keys that are evaluated as one-off conditions (not event counts)
ONE_OFF_RULE_KEYS = frozenset({
    'profile_complete', 'test1_complete', 'test2_complete', 'test3_complete',
    'numerical_complete', 'verbal_complete', 'logical_complete', 'emotional_complete',
    'machanical_complete', 'language_complete', 'spatial_complete',
    'career_direction_complete', 'payment_success',
})

# Default level bands if none in DB
DEFAULT_LEVEL_BANDS = [
    {'name': 'Rookie', 'min_points': 0, 'order': 0},
    {'name': 'Explorer', 'min_points': 500, 'order': 1},
    {'name': 'Champion', 'min_points': 1000, 'order': 2},
    {'name': 'Legend', 'min_points': 2000, 'order': 3},
]

# Default point rules if none in DB (rule_key -> points)
DEFAULT_POINT_RULES = {
    'profile_complete': 100,
    'test1_complete': 150,
    'test2_complete': 150,
    'test3_complete': 200,
    'numerical_complete': 50,
    'verbal_complete': 50,
    'logical_complete': 50,
    'emotional_complete': 50,
    'machanical_complete': 50,
    'language_complete': 50,
    'spatial_complete': 50,
    'career_direction_complete': 200,
    'payment_success': 50,
    'psychometric_test_completed': 200,
    'registration': 25,
}

# Default trophy rule keys (same as point rules that are one-off + payment)
DEFAULT_TROPHY_KEYS = [
    'profile_complete', 'test1_complete', 'test2_complete', 'test3_complete',
    'numerical_complete', 'verbal_complete', 'logical_complete', 'emotional_complete',
    'machanical_complete', 'language_complete', 'spatial_complete',
    'career_direction_complete', 'payment_success',
]


def _rule_condition_met(user, rule_key):
    """Return True if the one-off rule_key condition is met for user."""
    try:
        if rule_key == 'profile_complete':
            return user.get_profile_completion_percentage() == 100

        if rule_key in ('test1_complete', 'test2_complete', 'test3_complete',
                        'numerical_complete', 'verbal_complete', 'logical_complete',
                        'emotional_complete', 'machanical_complete', 'language_complete', 'spatial_complete'):
            from app.models import TestCompletion
            tc = TestCompletion.objects.filter(user=user).first()
            if not tc:
                return False
            return getattr(tc, rule_key, False)

        if rule_key == 'career_direction_complete':
            from app_post_matric.models import TestSession
            return TestSession.objects.filter(user=user, is_completed=True).exists()

        if rule_key == 'payment_success':
            from psychometric_tests.models import PsychometricTestPayment
            from core import choices
            return PsychometricTestPayment.objects.filter(
                user=user, is_success=choices.YesNoChoices.YES
            ).exists()

        return False
    except Exception:
        return False


def _get_trophy_count(user):
    """Count trophies from DashboardTrophyDefinition or default keys."""
    from core.models import DashboardTrophyDefinition
    rows = list(DashboardTrophyDefinition.objects.filter(active=True).values_list('rule_key', flat=True))
    if not rows:
        keys = DEFAULT_TROPHY_KEYS
    else:
        keys = rows
    return sum(1 for k in keys if _rule_condition_met(user, k))


def _get_total_points(user):
    """Sum points from DashboardPointRule (one-off + event-based) or defaults."""
    from core.models import DashboardPointRule
    from user_analytics.models import UserEvent
    rules = list(DashboardPointRule.objects.filter(active=True).values_list('rule_key', 'points'))
    if not rules:
        point_map = DEFAULT_POINT_RULES.copy()
    else:
        point_map = {k: p for k, p in rules}

    total = 0
    for rule_key in ONE_OFF_RULE_KEYS:
        if rule_key in point_map and _rule_condition_met(user, rule_key):
            total += point_map[rule_key]

    # Event-based: count UserEvent by event_type and add points (e.g. psychometric_test_completed)
    event_points_keys = [k for k in point_map if k not in ONE_OFF_RULE_KEYS]
    if event_points_keys:
        event_types = list(event_points_keys)
        counts = UserEvent.objects.filter(user=user).values('event_type').annotate(c=Count('id'))
        for row in counts:
            et = row['event_type']
            if et in point_map:
                total += point_map[et] * row['c']

    return total


def _get_streak_days(user):
    """Consecutive calendar days with activity. Streak valid if latest activity is today or yesterday."""
    from core.models import DashboardStreakConfig
    from user_analytics.models import UserActivity, UserEvent
    from datetime import timedelta
    today = timezone.now().date()

    use_events = False
    event_types_filter = None
    try:
        config = DashboardStreakConfig.objects.first()
        if config:
            use_events = config.activity_source == 'UserEvent'
            if config.event_types:
                event_types_filter = [x.strip() for x in config.event_types.split(',') if x.strip()]
    except Exception:
        pass

    def _fetch_dates_from_source(use_events_flag: bool):
        if use_events_flag:
            qs = UserEvent.objects.filter(user=user)
            if event_types_filter:
                qs = qs.filter(event_type__in=event_types_filter)
            return list(qs.dates('created', 'day', order='DESC')[:500])
        return list(UserActivity.objects.filter(user=user).dates('created', 'day', order='DESC')[:500])

    # Primary configured source
    dates = _fetch_dates_from_source(use_events)

    # Fallback: if configured source has no rows, try the other one (helps demos where only one table is populated)
    if not dates:
        dates = _fetch_dates_from_source(not use_events)

    if not dates:
        return 0
    # First date must be today or yesterday for streak to count
    first_date = dates[0]
    if first_date != today and first_date != today - timedelta(days=1):
        return 0
    streak = 0
    # If latest activity is yesterday, streak should start at yesterday (not today).
    expect = first_date
    for d in dates:
        if d != expect:
            break
        streak += 1
        expect = expect - timedelta(days=1)
    return streak


def _get_level_band(total_points):
    """Return (level_name, next_min_points, progress_percent) from DashboardLevelBand or defaults."""
    from core.models import DashboardLevelBand
    bands = list(DashboardLevelBand.objects.order_by('order', 'min_points').values('name', 'min_points', 'order'))
    if not bands:
        bands = DEFAULT_LEVEL_BANDS
    if not bands:
        return 'Rookie', None, 0

    current = None
    next_band = None
    for b in bands:
        if total_points >= b['min_points']:
            current = b
    for b in bands:
        if b['min_points'] > total_points:
            next_band = b
            break

    level_name = current['name'] if current else bands[0]['name']
    next_min = next_band['min_points'] if next_band else None
    progress = 0
    if next_min is not None and current is not None:
        span = next_min - current['min_points']
        if span > 0:
            progress = int(100 * (total_points - current['min_points']) / span)
            progress = min(100, max(0, progress))
    return level_name, next_min, progress


def get_student_dashboard_stats(profile_user):
    """
    Return dict: trophies_unlocked, total_points, streak_days, current_level,
    next_level_min_points, level_progress_percent.
    """
    trophies = _get_trophy_count(profile_user)
    points = _get_total_points(profile_user)
    streak = _get_streak_days(profile_user)
    level_name, next_min, progress = _get_level_band(points)
    return {
        'trophies_unlocked': trophies,
        'total_points': points,
        'streak_days': streak,
        'current_level': level_name,
        'next_level_min_points': next_min,
        'level_progress_percent': progress,
    }
