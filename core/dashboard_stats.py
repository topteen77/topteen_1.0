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

RULE_LABELS = {
    'profile_complete': 'Complete your profile',
    'test1_complete': 'Personality test (Part 1)',
    'test2_complete': 'Interest test (Part 2)',
    'test3_complete': 'Aptitude test (Part 3)',
    'numerical_complete': 'Numerical reasoning',
    'verbal_complete': 'Verbal reasoning',
    'logical_complete': 'Logical reasoning',
    'emotional_complete': 'Emotional intelligence',
    'machanical_complete': 'Mechanical reasoning',  # rule_key spelling kept for DB compatibility
    'language_complete': 'Language & spelling',
    'spatial_complete': 'Spatial reasoning',
    'career_direction_complete': 'Career direction test',
    'payment_success': 'Psychometric test payment',
    'psychometric_test_completed': 'Psychometric test completed',
    'registration': 'Account registration',
}


def _rule_label(rule_key, admin_label=None):
    if admin_label:
        return admin_label
    return RULE_LABELS.get(rule_key, rule_key.replace('_', ' ').title())


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


def _compute_streak(user):
    """
    Return (streak_days, streak_dates) where streak_dates are consecutive active days
    ending today or yesterday.
    """
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

    dates = _fetch_dates_from_source(use_events)
    if not dates:
        dates = _fetch_dates_from_source(not use_events)

    if not dates:
        return 0, []
    first_date = dates[0]
    if first_date != today and first_date != today - timedelta(days=1):
        return 0, []

    streak_dates = []
    expect = first_date
    for d in dates:
        if d != expect:
            break
        streak_dates.append(d)
        expect = expect - timedelta(days=1)
    return len(streak_dates), streak_dates


def _get_streak_days(user):
    days, _ = _compute_streak(user)
    return days


def _get_trophy_details(user):
    from core.models import DashboardTrophyDefinition
    rows = list(
        DashboardTrophyDefinition.objects.filter(active=True).values('rule_key', 'label')
    )
    if not rows:
        items = [{'rule_key': k, 'label': ''} for k in DEFAULT_TROPHY_KEYS]
    else:
        items = rows
    details = []
    for row in items:
        rule_key = row['rule_key']
        unlocked = _rule_condition_met(user, rule_key)
        admin_label = (row.get('label') or '').strip()
        # Prefer friendly labels for known rule keys (avoids typos like "Machanical")
        label = RULE_LABELS.get(rule_key) or _rule_label(rule_key, admin_label or None)
        details.append({
            'rule_key': rule_key,
            'label': label,
            'unlocked': unlocked,
        })
    details.sort(key=lambda x: (not x['unlocked'], x['label']))
    return details


def _get_points_details(user):
    from core.models import DashboardPointRule
    from user_analytics.models import UserEvent
    rules = list(DashboardPointRule.objects.filter(active=True).values_list('rule_key', 'points'))
    if not rules:
        point_map = DEFAULT_POINT_RULES.copy()
    else:
        point_map = {k: p for k, p in rules}

    details = []
    earned_total = 0
    for rule_key in ONE_OFF_RULE_KEYS:
        if rule_key not in point_map:
            continue
        pts = point_map[rule_key]
        earned = _rule_condition_met(user, rule_key)
        row_pts = pts if earned else 0
        earned_total += row_pts
        details.append({
            'rule_key': rule_key,
            'label': _rule_label(rule_key),
            'points': pts,
            'earned_points': row_pts,
            'earned': earned,
            'count': 1 if earned else 0,
        })

    event_points_keys = [k for k in point_map if k not in ONE_OFF_RULE_KEYS]
    if event_points_keys:
        counts = UserEvent.objects.filter(user=user).values('event_type').annotate(c=Count('id'))
        count_map = {row['event_type']: row['c'] for row in counts}
        for rule_key in sorted(event_points_keys):
            pts = point_map[rule_key]
            count = count_map.get(rule_key, 0)
            row_pts = pts * count
            earned_total += row_pts
            details.append({
                'rule_key': rule_key,
                'label': _rule_label(rule_key),
                'points': pts,
                'earned_points': row_pts,
                'earned': count > 0,
                'count': count,
            })

    details.sort(key=lambda x: (-x['earned_points'], x['label']))
    return details, earned_total


def _resolve_level_progress(total_points):
    """
    Level progress within the current band (not total XP vs next threshold).
    Example: 25 XP, Rookie→Explorer (0–500 band) = 5% and 475 XP to Explorer.
    """
    from core.models import DashboardLevelBand
    bands = list(DashboardLevelBand.objects.order_by('order', 'min_points').values('name', 'min_points', 'order'))
    if not bands:
        bands = DEFAULT_LEVEL_BANDS
    if not bands:
        return {
            'current_level': 'Rookie',
            'next_level_min_points': None,
            'next_level_name': None,
            'current_level_min_points': 0,
            'level_progress_percent': 0,
            'points_in_band': 0,
            'band_span_points': 0,
            'points_to_next': 0,
            'is_max_level': True,
        }

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
    current_min = current['min_points'] if current else bands[0]['min_points']
    next_min = next_band['min_points'] if next_band else None
    next_level_name = next_band['name'] if next_band else None

    band_span = (next_min - current_min) if next_min is not None else 0
    points_in_band = max(0, int(total_points) - int(current_min))
    points_to_next = max(0, int(next_min) - int(total_points)) if next_min is not None else 0

    progress = 0
    if band_span > 0:
        progress = int(round(100 * points_in_band / band_span))
        progress = min(100, max(0, progress))

    return {
        'current_level': level_name,
        'next_level_min_points': next_min,
        'next_level_name': next_level_name,
        'current_level_min_points': current_min,
        'level_progress_percent': progress,
        'points_in_band': points_in_band,
        'band_span_points': band_span,
        'points_to_next': points_to_next,
        'is_max_level': next_min is None,
    }


def _get_level_details(total_points):
    from core.models import DashboardLevelBand
    bands = list(DashboardLevelBand.objects.order_by('order', 'min_points').values('name', 'min_points', 'order'))
    if not bands:
        bands = DEFAULT_LEVEL_BANDS

    progress_data = _resolve_level_progress(total_points)
    level_name = progress_data['current_level']
    band_rows = []
    for b in bands:
        band_rows.append({
            'name': b['name'],
            'min_points': b['min_points'],
            'is_current': b['name'] == level_name,
            'reached': total_points >= b['min_points'],
        })

    return {
        'bands': band_rows,
        'total_points': total_points,
        **progress_data,
    }


def _get_streak_details(user):
    days, streak_dates = _compute_streak(user)
    formatted = [d.strftime('%d %b %Y') for d in streak_dates]
    return {
        'streak_days': days,
        'active_dates': formatted,
        'latest_activity': formatted[0] if formatted else None,
    }


def _get_level_band(total_points):
    """Return (level_name, next_min_points, progress_percent) from DashboardLevelBand or defaults."""
    data = _resolve_level_progress(total_points)
    return data['current_level'], data['next_level_min_points'], data['level_progress_percent']


def get_student_dashboard_stats(profile_user):
    """
    Return dict: trophies_unlocked, total_points, streak_days, current_level,
    next_level_min_points, level_progress_percent, and detail breakdowns for popups.
    """
    trophies = _get_trophy_count(profile_user)
    points = _get_total_points(profile_user)
    streak = _get_streak_days(profile_user)
    level_name, next_min, progress = _get_level_band(points)
    points_details, _ = _get_points_details(profile_user)
    return {
        'trophies_unlocked': trophies,
        'total_points': points,
        'streak_days': streak,
        'current_level': level_name,
        'next_level_min_points': next_min,
        'level_progress_percent': progress,
        'trophy_details': _get_trophy_details(profile_user),
        'points_details': points_details,
        'streak_details': _get_streak_details(profile_user),
        'level_details': _get_level_details(points),
    }
