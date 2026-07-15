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
            from institute.models import StudentManagement

            student_management = (
                StudentManagement.objects.filter(student=user)
                .select_related('class_and_section')
                .first()
            )
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


def get_point_rules_with_applies_to(active_only: bool = True) -> List[Dict]:
    """Load active dashboard point rules including applies_to from admin."""
    from core.models import DashboardPointRule

    qs = DashboardPointRule.objects.all()
    if active_only:
        qs = qs.filter(active=True)
    rows = list(qs.order_by('order', 'rule_key').values('rule_key', 'points', 'order', 'applies_to'))
    if rows:
        return rows

    defaults = _default_point_rules_with_applies_to()
    if active_only:
        return defaults
    return defaults


def get_point_rule_applies_to(rule_key: str) -> str:
    from core.models import DashboardPointRule

    applies_to = (
        DashboardPointRule.objects.filter(rule_key=rule_key, active=True)
        .values_list('applies_to', flat=True)
        .first()
    )
    if applies_to:
        return applies_to
    applies_to = (
        DashboardPointRule.objects.filter(rule_key=rule_key)
        .values_list('applies_to', flat=True)
        .first()
    )
    if applies_to:
        return applies_to
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
