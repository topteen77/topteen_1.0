"""Resolve a student's psychometric track and which dashboard rules apply."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from core.models import DashboardRuleAppliesTo

POST_MATRIC_TRACK = 'post_matric'
CLASS10_TRACK = 'class10'

# Fallback when no DashboardPointRule rows exist in the database.
DEFAULT_RULE_APPLIES_TO = {
    'motivation_test_complete': DashboardRuleAppliesTo.CLASS_11_12_PLUS,
}


def get_applies_to_display(applies_to: str) -> str:
    if not applies_to:
        return DashboardRuleAppliesTo.ALL.label
    for value, label in DashboardRuleAppliesTo.choices:
        if value == applies_to:
            return label
    return applies_to.replace('_', ' ').title()


def rule_applies_to_user(applies_to: str, user_track: str) -> bool:
    if not applies_to or applies_to == DashboardRuleAppliesTo.ALL:
        return True
    return applies_to == user_track


def _parse_class_number(value) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    match = re.search(r'(\d{1,2})', text)
    if match:
        return int(match.group(1))
    return None


def get_student_psychometric_track(user) -> str:
    """
    Return POST_MATRIC_TRACK for class 11+, else CLASS10_TRACK.
    Matches dashboard routing in users/views.py and app/views.py.
    """
    if not user:
        return CLASS10_TRACK

    # Memoize on the user instance: this is called many times per dashboard
    # render and resolves to the same value for a user within one request.
    cached = getattr(user, '_psychometric_track_cache', None)
    if cached is not None:
        return cached

    class_number = None
    try:
        profile = getattr(user, 'user_profile', None)
        if profile and getattr(profile, 'grade', None):
            class_number = _parse_class_number(profile.grade)
    except Exception:
        pass

    if class_number is None:
        try:
            from institute.models import get_cached_student_management

            student_management = get_cached_student_management(user)
            if student_management and student_management.class_and_section:
                class_name = student_management.class_and_section.class_and_section
                class_number = _parse_class_number(class_name)
        except Exception:
            pass

    result = POST_MATRIC_TRACK if (class_number is not None and class_number >= 11) else CLASS10_TRACK
    try:
        user._psychometric_track_cache = result
    except Exception:
        pass
    return result


def _default_point_rules_with_applies_to() -> List[Dict]:
    from core.dashboard_stats import DEFAULT_POINT_RULES

    return [
        {
            'rule_key': rule_key,
            'points': points,
            'applies_to': DEFAULT_RULE_APPLIES_TO.get(rule_key, DashboardRuleAppliesTo.ALL),
        }
        for rule_key, points in DEFAULT_POINT_RULES.items()
    ]


def _load_active_point_rules() -> List[Dict]:
    from core.models import DashboardPointRule

    return list(
        DashboardPointRule.objects.filter(active=True)
        .order_by('order', 'rule_key')
        .values('rule_key', 'label', 'points', 'order', 'applies_to')
    )


def get_active_point_rule_rows() -> List[Dict]:
    """Cached raw active point-rule rows (no defaults fallback)."""
    from core.dashboard_cache import cached_config

    return cached_config('point_rules_active', _load_active_point_rules)


def get_point_rules_with_applies_to(active_only: bool = True) -> List[Dict]:
    """Load active dashboard point rules including applies_to from admin."""
    from core.models import DashboardPointRule

    if active_only:
        # Small admin-config table read many times per dashboard render; cache it.
        from core.dashboard_cache import cached_config
        rows = cached_config('point_rules_active', _load_active_point_rules)
    else:
        rows = list(
            DashboardPointRule.objects.all()
            .order_by('order', 'rule_key')
            .values('rule_key', 'label', 'points', 'order', 'applies_to')
        )
    if rows:
        return rows

    return _default_point_rules_with_applies_to()


def _build_point_rule_applies_to_map() -> Dict[str, Dict[str, str]]:
    from core.models import DashboardPointRule

    active_map: Dict[str, str] = {}
    any_map: Dict[str, str] = {}
    for row in DashboardPointRule.objects.all().values('rule_key', 'applies_to', 'active'):
        applies_to = row['applies_to']
        if not applies_to:
            continue
        if row['active']:
            active_map.setdefault(row['rule_key'], applies_to)
        any_map.setdefault(row['rule_key'], applies_to)
    return {'active': active_map, 'any': any_map}


def get_point_rule_applies_to(rule_key: str) -> str:
    # Cache the whole {rule_key: applies_to} map so per-key resolution during
    # dashboard rendering does not issue a query each time.
    from core.dashboard_cache import cached_config

    resolved = cached_config('point_rule_applies_to', _build_point_rule_applies_to_map)
    if rule_key in resolved['active']:
        return resolved['active'][rule_key]
    if rule_key in resolved['any']:
        return resolved['any'][rule_key]
    return DEFAULT_RULE_APPLIES_TO.get(rule_key, DashboardRuleAppliesTo.ALL)


def resolve_rule_applies_to(rule_key: str, explicit_applies_to: str = '') -> str:
    if explicit_applies_to:
        return explicit_applies_to
    return get_point_rule_applies_to(rule_key)


def get_rule_applies_to_label(rule_key: str, explicit_applies_to: str = '') -> str:
    return get_applies_to_display(resolve_rule_applies_to(rule_key, explicit_applies_to))


def get_excluded_rule_keys_for_track(track: str) -> frozenset:
    excluded = set()
    for rule in get_point_rules_with_applies_to(active_only=True):
        applies_to = resolve_rule_applies_to(rule['rule_key'], rule.get('applies_to') or '')
        if not rule_applies_to_user(applies_to, track):
            excluded.add(rule['rule_key'])
    return frozenset(excluded)


def rule_applies_to_user_track(user, rule_key: str, explicit_applies_to: str = '') -> bool:
    applies_to = resolve_rule_applies_to(rule_key, explicit_applies_to)
    return rule_applies_to_user(applies_to, get_student_psychometric_track(user))
