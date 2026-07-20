"""
Student dashboard statistics: trophies, points, streak, level.
Reads from admin-configurable models (DashboardLevelBand, DashboardPointRule,
DashboardTrophyDefinition, DashboardStreakConfig) and existing user/test data.
"""

from django.utils import timezone
from django.db.models import Count

from core.psychometric_grade import (
    CLASS10_TRACK,
    POST_MATRIC_TRACK,
    get_active_point_rule_rows,
    get_excluded_rule_keys_for_track,
    get_point_rules_with_applies_to,
    get_student_psychometric_track,
    resolve_rule_applies_to,
    rule_applies_to_user,
    rule_applies_to_user_track,
)


# Rule keys that are evaluated as one-off conditions (not event counts)
ONE_OFF_RULE_KEYS = frozenset({
    'profile_complete', 'payment_success',
    'personality_test_complete', 'motivation_test_complete',
    'interest_test_complete', 'aptitude_test_complete', 'report_reading',
    # Legacy keys kept for backward compatibility if still active in admin
    'test1_complete', 'test2_complete', 'test3_complete',
    'numerical_complete', 'verbal_complete', 'logical_complete', 'emotional_complete',
    'machanical_complete', 'language_complete', 'spatial_complete',
    'career_direction_complete',
})

# Default level bands if none in DB
DEFAULT_LEVEL_BANDS = [
    {'name': 'Rookie', 'min_points': 50, 'order': 0},
    {'name': 'Explorer', 'min_points': 250, 'order': 1},
    {'name': 'Champion', 'min_points': 490, 'order': 2},
    {'name': 'Legend', 'min_points': 840, 'order': 3},
]

# Default point rules if none in DB (rule_key -> points)
DEFAULT_POINT_RULES = {
    "registration": 50,
    'profile_complete': 50,
    'payment_success': 150,
    'personality_test_complete': 100,
    'motivation_test_complete': 70,
    'interest_test_complete': 70,
    'aptitude_test_complete': 200,
    'report_reading': 150,
}

# Default trophy rule keys (same as point rules that are one-off + payment)
DEFAULT_TROPHY_KEYS = [
    'profile_complete', 'test1_complete', 'test2_complete', 'test3_complete',
    'numerical_complete', 'verbal_complete', 'logical_complete', 'emotional_complete',
    'machanical_complete', 'language_complete', 'spatial_complete',
    'career_direction_complete', 'payment_success',
]

RULE_LABELS = {
    'registration': 'Account registration',
    'profile_complete': 'Profile completion',
    'payment_success': 'Test payment',
    'personality_test_complete': 'Personality test completion',
    'motivation_test_complete': 'Motivation test completion',
    'interest_test_complete': 'Interest test completion',
    'aptitude_test_complete': 'Aptitude test completion',
    'report_reading': 'Report reading',
    # Legacy labels
    'test1_complete': 'Personality test (Part 1)',
    'test2_complete': 'Interest test (Part 2)',
    'test3_complete': 'Aptitude test (Part 3)',
    'numerical_complete': 'Numerical reasoning',
    'verbal_complete': 'Verbal reasoning',
    'logical_complete': 'Logical reasoning',
    'emotional_complete': 'Emotional intelligence',
    'machanical_complete': 'Mechanical reasoning',
    'language_complete': 'Language & spelling',
    'spatial_complete': 'Spatial reasoning',
    'career_direction_complete': 'Career direction test',
    'psychometric_test_completed': 'Psychometric test completed',
}


def _active_trophy_rows():
    """Cached active DashboardTrophyDefinition rows (admin config, tiny table)."""
    from core.dashboard_cache import cached_config

    def build():
        from core.models import DashboardTrophyDefinition
        return list(
            DashboardTrophyDefinition.objects.filter(active=True)
            .values('rule_key', 'label', 'applies_to')
        )
    return cached_config('trophy_rows', build)


def _cached_level_bands():
    """Cached DashboardLevelBand rows (admin config, tiny table)."""
    from core.dashboard_cache import cached_config

    def build():
        from core.models import DashboardLevelBand
        return list(
            DashboardLevelBand.objects.order_by('order', 'min_points')
            .values('name', 'min_points', 'order')
        )
    return cached_config('level_bands', build)


def _load_point_map():
    return {
        rule['rule_key']: rule['points']
        for rule in get_point_rules_with_applies_to(active_only=True)
    }


def _get_applicable_point_map(user):
    track = get_student_psychometric_track(user)
    return {
        rule['rule_key']: rule['points']
        for rule in get_point_rules_with_applies_to(active_only=True)
        if rule_applies_to_user(resolve_rule_applies_to(rule['rule_key'], rule.get('applies_to') or ''), track)
    }


def _filter_trophy_keys_for_user(user, keys):
    track = get_student_psychometric_track(user)
    # Trophy applies_to comes from the (cached) active trophy rows; when blank it
    # falls back to the point-rule applies_to (also cached) — no per-key query.
    trophy_applies_to_map = {
        row['rule_key']: (row.get('applies_to') or '')
        for row in _active_trophy_rows()
    }
    kept = []
    for key in keys:
        applies_to = resolve_rule_applies_to(key, trophy_applies_to_map.get(key, ''))
        if rule_applies_to_user(applies_to, track):
            kept.append(key)
    return kept


def _milestone_total(milestones, rule_key, fallback=None):
    for milestone in milestones:
        if milestone['rule_key'] == rule_key:
            return milestone['cumulative']
    return fallback


def _bands_from_milestones(milestones):
    if not milestones:
        return DEFAULT_LEVEL_BANDS

    registration_pts = _milestone_total(milestones, 'registration', milestones[0]['cumulative'])
    payment_pts = _milestone_total(milestones, 'payment_success', registration_pts)
    interest_pts = _milestone_total(milestones, 'interest_test_complete', milestones[-1]['cumulative'])
    legend_pts = milestones[-1]['cumulative']
    return [
        {'name': 'Rookie', 'min_points': registration_pts, 'order': 0},
        {'name': 'Explorer', 'min_points': payment_pts, 'order': 1},
        {'name': 'Champion', 'min_points': interest_pts, 'order': 2},
        {'name': 'Legend', 'min_points': legend_pts, 'order': 3},
    ]


def _load_db_level_bands():
    bands = _cached_level_bands()
    if bands:
        return bands
    return DEFAULT_LEVEL_BANDS


def _get_level_bands_for_user(user):
    from core.dashboard_points import get_cumulative_point_milestones

    if get_student_psychometric_track(user) == CLASS10_TRACK:
        excluded = get_excluded_rule_keys_for_track(CLASS10_TRACK)
        milestones = get_cumulative_point_milestones(excluded_rule_keys=excluded)
        return _bands_from_milestones(milestones)

    bands = _cached_level_bands()
    if bands:
        return bands

    milestones = get_cumulative_point_milestones()
    return _bands_from_milestones(milestones)


def _user_dashboard_flags(user):
    """Fetch per-user test flags once and memoize them on the user instance.

    get_student_dashboard_stats evaluates the same conditions many times
    (trophy count, total points, detail breakdowns). Without this cache each
    check would re-run the same TestCompletion / TestSession queries.
    """
    cache = getattr(user, '_dashboard_flags_cache', None)
    if cache is not None:
        return cache
    from app.models import TestCompletion
    from app_post_matric.models import TestSession
    cache = {
        'test_completion': TestCompletion.objects.filter(user=user).first(),
        # test_id set of completed post-matric sessions; membership matches the
        # old .filter(test__id=..., is_completed=True).exists() semantics, and a
        # non-empty set matches the "any completed session" check.
        'completed_pm_test_ids': set(
            TestSession.objects.filter(user=user, is_completed=True)
            .values_list('test_id', flat=True)
        ),
    }
    try:
        user._dashboard_flags_cache = cache
    except Exception:
        pass
    return cache


def _class10_test_flag(user, field_name):
    tc = _user_dashboard_flags(user)['test_completion']
    if not tc:
        return False
    return bool(getattr(tc, field_name, False))


def _post_matric_test_completed(user, test_id):
    return test_id in _user_dashboard_flags(user)['completed_pm_test_ids']


def _user_event_exists(user, event_type):
    from user_analytics.models import UserEvent
    return UserEvent.objects.filter(user=user, event_type=event_type).exists()


def _rule_label(rule_key, admin_label=None):
    if admin_label:
        return admin_label
    return RULE_LABELS.get(rule_key, rule_key.replace('_', ' ').title())


def _rule_condition_met(user, rule_key):
    """Memoized wrapper: the same one-off conditions are evaluated repeatedly
    across trophy/points aggregation within a single dashboard render."""
    cache = getattr(user, '_dash_rule_cache', None)
    if cache is None:
        cache = {}
        try:
            user._dash_rule_cache = cache
        except Exception:
            pass
    if rule_key not in cache:
        cache[rule_key] = _evaluate_rule_condition(user, rule_key)
    return cache[rule_key]


def _evaluate_rule_condition(user, rule_key):
    """Return True if the one-off rule_key condition is met for user."""
    try:
        if rule_key == 'profile_complete':
            return user.get_profile_completion_percentage() == 100

        if rule_key == 'personality_test_complete':
            return (
                _class10_test_flag(user, 'test1_complete')
                or _post_matric_test_completed(user, 1)
            )

        if rule_key == 'motivation_test_complete':
            if not rule_applies_to_user_track(user, rule_key):
                return False
            return _post_matric_test_completed(user, 2)

        if rule_key == 'interest_test_complete':
            return (
                _class10_test_flag(user, 'test2_complete')
                or _post_matric_test_completed(user, 3)
            )

        if rule_key == 'aptitude_test_complete':
            return (
                _class10_test_flag(user, 'test3_complete')
                or _post_matric_test_completed(user, 4)
            )

        if rule_key == 'report_reading':
            return _user_event_exists(user, 'result_generated')

        if rule_key in ('test1_complete', 'test2_complete', 'test3_complete',
                        'numerical_complete', 'verbal_complete', 'logical_complete',
                        'emotional_complete', 'machanical_complete', 'language_complete', 'spatial_complete'):
            return _class10_test_flag(user, rule_key)

        if rule_key == 'career_direction_complete':
            return bool(_user_dashboard_flags(user)['completed_pm_test_ids'])

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
    rows = [row['rule_key'] for row in _active_trophy_rows()]
    if not rows:
        keys = DEFAULT_TROPHY_KEYS
    else:
        keys = rows
    keys = _filter_trophy_keys_for_user(user, keys)
    return sum(1 for k in keys if _rule_condition_met(user, k))


def _get_total_points(user):
    """Sum points from DashboardPointRule (one-off + event-based) or defaults."""
    from user_analytics.models import UserEvent
    point_map = _get_applicable_point_map(user)

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
    rows = [
        {'rule_key': row['rule_key'], 'label': row.get('label') or ''}
        for row in _active_trophy_rows()
    ]
    if not rows:
        items = [{'rule_key': k, 'label': ''} for k in DEFAULT_TROPHY_KEYS]
    else:
        items = rows
    allowed_keys = set(_filter_trophy_keys_for_user(user, [row['rule_key'] for row in items]))
    items = [row for row in items if row['rule_key'] in allowed_keys]
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
    from user_analytics.models import UserEvent
    rule_rows = get_active_point_rule_rows()
    point_map = _get_applicable_point_map(user)
    if not rule_rows:
        rule_order = {k: i for i, k in enumerate(point_map.keys())}
    else:
        applicable_keys = set(point_map.keys())
        rule_order = {
            r['rule_key']: r['order']
            for r in rule_rows
            if r['rule_key'] in applicable_keys
        }

    details = []
    earned_total = 0

    def _append_rule(rule_key, pts, earned, count=1):
        nonlocal earned_total
        if rule_key in ONE_OFF_RULE_KEYS:
            row_pts = pts if earned else 0
            row_count = 1 if earned else 0
        else:
            row_pts = pts * count
            row_count = count
        earned_total += row_pts
        details.append({
            'rule_key': rule_key,
            'label': _rule_label(rule_key),
            'points': pts,
            'earned_points': row_pts,
            'earned': earned,
            'count': row_count,
        })

    counts = {}
    event_points_keys = [k for k in point_map if k not in ONE_OFF_RULE_KEYS]
    if event_points_keys:
        event_counts = UserEvent.objects.filter(user=user).values('event_type').annotate(c=Count('id'))
        counts = {row['event_type']: row['c'] for row in event_counts}

    for rule_key in sorted(point_map.keys(), key=lambda k: (rule_order.get(k, 9999), k)):
        pts = point_map[rule_key]
        if rule_key in ONE_OFF_RULE_KEYS:
            earned = _rule_condition_met(user, rule_key)
            _append_rule(rule_key, pts, earned)
        else:
            count = counts.get(rule_key, 0)
            _append_rule(rule_key, pts, count > 0, count=count)

    return details, earned_total


def _resolve_level_progress(total_points, user=None):
    """
    Level progress within the current band (not total XP vs next threshold).
    Example: 25 XP, Rookie→Explorer (0–500 band) = 5% and 475 XP to Explorer.
    """
    if user is not None:
        bands = _get_level_bands_for_user(user)
    else:
        bands = _load_db_level_bands()
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


def _get_level_details(total_points, user=None):
    bands = _get_level_bands_for_user(user) if user is not None else _load_db_level_bands()
    progress_data = _resolve_level_progress(total_points, user=user)
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


def _get_level_band(total_points, user=None):
    """Return (level_name, next_min_points, progress_percent) from DashboardLevelBand or defaults."""
    data = _resolve_level_progress(total_points, user=user)
    return data['current_level'], data['next_level_min_points'], data['level_progress_percent']


def get_student_dashboard_stats(profile_user):
    """
    Return dict: trophies_unlocked, total_points, streak_days, current_level,
    next_level_min_points, level_progress_percent, and detail breakdowns for popups.
    """
    from django.core.cache import cache

    uid = int(getattr(profile_user, "id", 0) or 0)
    cache_key = f"dash:stats:v1:{uid}" if uid else None
    if cache_key:
        try:
            cached = cache.get(cache_key)
            if isinstance(cached, dict) and "trophies_unlocked" in cached:
                return cached
        except Exception:
            pass

    trophies = _get_trophy_count(profile_user)
    points = _get_total_points(profile_user)
    streak = _get_streak_days(profile_user)
    level_name, next_min, progress = _get_level_band(points, user=profile_user)
    points_details, _ = _get_points_details(profile_user)
    data = {
        'trophies_unlocked': trophies,
        'total_points': points,
        'streak_days': streak,
        'current_level': level_name,
        'next_level_min_points': next_min,
        'level_progress_percent': progress,
        'trophy_details': _get_trophy_details(profile_user),
        'points_details': points_details,
        'streak_details': _get_streak_details(profile_user),
        'level_details': _get_level_details(points, user=profile_user),
        'psychometric_track': get_student_psychometric_track(profile_user),
    }
    if cache_key:
        try:
            cache.set(cache_key, data, 90)
        except Exception:
            pass
    return data


def invalidate_student_dashboard_stats_cache(user_id: int) -> None:
    try:
        from django.core.cache import cache

        cache.delete(f"dash:stats:v1:{int(user_id)}")
    except Exception:
        pass
