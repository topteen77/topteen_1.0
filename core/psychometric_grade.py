"""Resolve a student's psychometric track and which dashboard rules apply."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from core import choices
from core.models import DashboardRuleAppliesTo

POST_MATRIC_TRACK = 'post_matric'
CLASS10_TRACK = 'class10'
HIGHER_EDUCATION_AUDIENCES = frozenset(choices.EducationAudience.HIGHER)

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


def _normalize_education_audience(raw) -> str:
    if raw in HIGHER_EDUCATION_AUDIENCES or raw == choices.EducationAudience.SCHOOL:
        return raw
    return choices.EducationAudience.SCHOOL


def education_audience_label(raw) -> str:
    for value, label in choices.EducationAudience.CHOICES:
        if value == raw:
            return label
    return ''


def student_class_display(user, student_management=None) -> str:
    """
    Label for sidebar, profile, and rosters.
    A real class wins. Above Class 12 with no class shows the education level.
    Blank or the word None is not shown as "Class None".
    """
    blank = {'', 'none', 'null', 'not set', 'class none'}
    sm = student_management
    if sm is None and user:
        try:
            from institute.models import get_cached_student_management

            sm = get_cached_student_management(user)
        except Exception:
            sm = None

    class_text = ''
    if sm is not None and getattr(sm, 'class_and_section_id', None):
        section = getattr(sm, 'class_and_section', None)
        class_text = (getattr(section, 'class_and_section', None) or '').strip()
    if class_text and class_text.lower() not in blank:
        return _pretty_class_label(class_text)

    audience = _normalize_education_audience(
        getattr(sm, 'education_audience', None) if sm is not None else None
    )
    if audience in HIGHER_EDUCATION_AUDIENCES:
        return education_audience_label(audience)

    grade = ''
    try:
        profile = getattr(user, 'user_profile', None) if user else None
        grade = (getattr(profile, 'grade', None) or '').strip()
    except Exception:
        grade = ''
    if grade.lower() in blank:
        return ''
    return _pretty_class_label(grade)


def _pretty_class_label(text: str) -> str:
    """Turn 12 or 12th into Class 12. Keep a section such as 12 A as stored."""
    raw = (text or '').strip()
    number = _parse_class_number(raw)
    if number is None:
        return raw
    leftover = re.sub(r'\d+', '', raw.lower())
    for token in ('class', 'th', 'st', 'nd', 'rd'):
        leftover = leftover.replace(token, '')
    if leftover.strip(' -_/'):
        return raw
    return f'Class {number}'


def _is_blank_label(value) -> bool:
    return (value or '').strip().lower() in {'', 'none', 'null', 'not set'}


def student_school_display(user, student_management=None) -> str:
    """School on the profile, or the institute name when that field was never set."""
    school = ''
    try:
        profile = getattr(user, 'user_profile', None) if user else None
        school = (getattr(profile, 'schoolname', None) or '').strip()
    except Exception:
        school = ''
    if not _is_blank_label(school):
        return school

    sm = student_management
    if sm is None and user:
        try:
            from institute.models import get_cached_student_management

            sm = get_cached_student_management(user)
        except Exception:
            sm = None
    institute = getattr(sm, 'institute', None) if sm is not None else None
    name = (getattr(institute, 'name', None) or '').strip()
    if _is_blank_label(name):
        return ''
    return name


def _class_number_for_student(user, student_management) -> Optional[int]:
    if student_management is not None and getattr(student_management, 'class_and_section_id', None):
        section = getattr(student_management, 'class_and_section', None)
        number = _parse_class_number(getattr(section, 'class_and_section', None))
        if number is not None:
            return number
    try:
        profile = getattr(user, 'user_profile', None) if user else None
        return _parse_class_number(getattr(profile, 'grade', None))
    except Exception:
        return None


def student_grade_form(user) -> dict:
    """
    Grade/Class choices for profile add and edit.
    Matric students see classes 6–10, post-matric see 11–12,
    and college/professional students see their education level.
    """
    sm = None
    if user:
        try:
            from institute.models import get_cached_student_management

            sm = get_cached_student_management(user)
        except Exception:
            sm = None

    audience = _normalize_education_audience(
        getattr(sm, 'education_audience', None) if sm is not None else None
    )
    class_number = _class_number_for_student(user, sm)
    if audience in HIGHER_EDUCATION_AUDIENCES and class_number is None:
        return {
            'placeholder': 'Select education level',
            'options': [
                {
                    'value': value,
                    'label': education_audience_label(value),
                    'selected': value == audience,
                }
                for value in choices.EducationAudience.HIGHER
            ],
        }

    if class_number is not None and class_number >= 11:
        low, high = 11, 12
    else:
        low, high = 6, 10
    try:
        from core.context_processors import _fetch_master_classes

        rows = list(_fetch_master_classes(low, high))
    except Exception:
        rows = [{'value': value, 'label': f'Class {value}'} for value in range(high, low - 1, -1)]

    options = []
    for row in rows:
        if isinstance(row, dict):
            value = row.get('value')
            label = row.get('label') or f'Class {value}'
        else:
            value = getattr(row, 'value', None)
            label = getattr(row, 'label', None) or f'Class {value}'
        number = _parse_class_number(value)
        if number is None or number < low or number > high:
            continue
        options.append({
            'value': str(value),
            'label': label,
            'selected': class_number is not None and number == class_number,
        })
    return {'placeholder': 'Select Grade/Class', 'options': options}


def apply_profile_grade_choice(user, user_profile, raw) -> None:
    """Save a Grade/Class choice. Education levels update the student record, not a school class."""
    text = (raw or '').strip()
    if not text or user_profile is None:
        return
    if text in choices.EducationAudience.HIGHER:
        try:
            from institute.models import get_cached_student_management

            student_management = get_cached_student_management(user)
            if student_management is not None and student_management.education_audience != text:
                student_management.education_audience = text
                student_management.save(update_fields=['education_audience'])
            if user is not None:
                user._education_audience_cache = text
        except Exception:
            pass
        user_profile.grade = ''
        return
    user_profile.grade = text


def get_student_education_audience(user) -> str:
    """
    School unless the student record says Class 12 passout, graduate,
    postgraduate, or professional. Unknown values stay school.
    """
    if not user:
        return choices.EducationAudience.SCHOOL

    cached = getattr(user, '_education_audience_cache', None)
    if isinstance(cached, str):
        return cached

    audience = choices.EducationAudience.SCHOOL
    try:
        from institute.models import get_cached_student_management

        student_management = get_cached_student_management(user)
        raw = getattr(student_management, 'education_audience', None) if student_management else None
        audience = _normalize_education_audience(raw)
    except Exception:
        audience = choices.EducationAudience.SCHOOL

    try:
        user._education_audience_cache = audience
    except Exception:
        pass
    return audience


def is_higher_education_student(user) -> bool:
    return get_student_education_audience(user) in HIGHER_EDUCATION_AUDIENCES


def hides_undergraduate_college_tools(user) -> bool:
    """Graduate, postgraduate, and professional dashboards do not use school college tools."""
    return get_student_education_audience(user) in (
        choices.EducationAudience.GRADUATE,
        choices.EducationAudience.POSTGRADUATE,
        choices.EducationAudience.PROFESSIONAL,
    )


def dashboard_grade_bucket(user, resolved_grade, *, class_number_known: bool) -> str:
    """
    Dashboard bucket used to choose Stream Sorter ('10') or Career Direction ('12').

    A known class number is unchanged. Above-Class-12 audience is '12' only when
    no class number was found, so an empty class is not treated as Class 10.
    """
    if class_number_known and resolved_grade in ('10', '12'):
        return resolved_grade
    if is_higher_education_student(user):
        return '12'
    if resolved_grade in ('10', '12'):
        return resolved_grade
    return resolved_grade or '10'


def get_student_psychometric_track(user) -> str:
    """
    Return POST_MATRIC_TRACK for class 11+, else CLASS10_TRACK.
    Above-Class-12 audience with no class number also uses POST_MATRIC_TRACK.
    A known class number still wins, so Class 10 and Class 12 stay unchanged.
    """
    if not user:
        return CLASS10_TRACK

    # Memoize on the user instance: this is called many times per dashboard
    # render and resolves to the same value for a user within one request.
    cached = getattr(user, '_psychometric_track_cache', None)
    if cached in (CLASS10_TRACK, POST_MATRIC_TRACK):
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

    if class_number is None and is_higher_education_student(user):
        result = POST_MATRIC_TRACK
    else:
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
