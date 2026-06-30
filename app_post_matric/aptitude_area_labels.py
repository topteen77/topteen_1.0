"""Canonical aptitude area names; resolves legacy DB/JSON spellings for lookups."""

import re

LANGUAGE_VERBAL_REASONING = "Language and Verbal Reasoning"

_LANGUAGE_VERBAL_ALIASES = frozenset({
    "language & verbal reasoning",
    "verbal & language reasoning",
    "language and verbal reasoning",
})

CLERICAL_SPEED_ACCURACY = "Clerical speed & Accuracy"

_CLERICAL_ALIASES = frozenset({
    "clerical speed & accuracy",
    "clerical speed and accuracy",
})


def resolve_aptitude_json_area(area):
    """
    Map any stored or legacy label to the key used in static JSON (Area / Areas).
    """
    if not area or not isinstance(area, str):
        return area
    cleaned = re.sub(r"\s+", " ", area.strip())
    if cleaned.lower() in _LANGUAGE_VERBAL_ALIASES:
        return LANGUAGE_VERBAL_REASONING
    if cleaned.upper() == "VERBAL & LANGUAGE REASONING":
        return LANGUAGE_VERBAL_REASONING
    if cleaned.lower() in _CLERICAL_ALIASES:
        return CLERICAL_SPEED_ACCURACY
    return cleaned


def normalize_aptitude_categories(categories):
    """Normalize tier lists from TestTopCategories for templates and JSON lookups."""
    if not isinstance(categories, dict):
        return categories
    return {
        tier: [resolve_aptitude_json_area(a) for a in (areas or [])]
        for tier, areas in categories.items()
    }


# Display labels only; backend/DB keys stay "Below Average" / "Below"
APTITUDE_TIER_BELOW = "Below Average"
APTITUDE_TIER_GROWTH_AREA_LABEL = "Growth Area"

APTITUDE_TIER_DISPLAY_LABELS = {
    "Above Average": "Above Average",
    "Average": "Average",
    APTITUDE_TIER_BELOW: APTITUDE_TIER_GROWTH_AREA_LABEL,
    "Below": APTITUDE_TIER_GROWTH_AREA_LABEL,
    "Below Avg": APTITUDE_TIER_GROWTH_AREA_LABEL,
}


def aptitude_tier_label(tier_key):
    """Return display label for an aptitude tier key (e.g. Below Average → Growth Area)."""
    if tier_key is None:
        return tier_key
    key = str(tier_key).strip()
    return APTITUDE_TIER_DISPLAY_LABELS.get(key, tier_key)


# changes required by management (01-Jun-2025): Below Average → professional copy (display only)
APTITUDE_DEVELOPMENT_ALERT_TITLE = "Growth areas"

APTITUDE_DEVELOPMENT_ALERT_BODY_SINGULAR = (
    "1 reasoning area offers opportunities for growth. "
    "Strengthen these skills with the personalized recommendations below before selecting your stream."
)

APTITUDE_DEVELOPMENT_ALERT_BODY_PLURAL = (
    "{count} reasoning areas offer opportunities for growth. "
    "Strengthen these skills with the personalized recommendations below before selecting your stream."
)


def aptitude_development_alert_body(count):
    """Format dashboard alert body for the number of development/growth areas."""
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 0
    if n == 1:
        return APTITUDE_DEVELOPMENT_ALERT_BODY_SINGULAR
    return APTITUDE_DEVELOPMENT_ALERT_BODY_PLURAL.format(count=n)


APTITUDE_VOCATIONAL_SECTION_TITLE = "Vocational guidance for skill development"

APTITUDE_NO_DEVELOPMENT_AREAS = "No development areas identified."

APTITUDE_EMPTY_STATE_SKILL_AREAS = (
    "Please complete your aptitude assessments to unlock personalized insights for "
    "above average, average, and development areas."
)

APTITUDE_IMPROVEMENT_NOTE = (
    "If you have growth areas for skill strengthening in your profile, vocational training "
    "and guidance can help you develop your other reasoning areas."
)
