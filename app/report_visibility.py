"""Report / dashboard visibility rules for aptitude tiers."""

from __future__ import annotations

from core.choices import ReasoningArea


def _as_area_list(value) -> list:
    return value if isinstance(value, list) else []


def student_has_below_average_areas(below) -> bool:
    """True when the student has at least one below-average reasoning area."""
    return isinstance(below, list) and len(below) > 0


def student_all_growth_areas(below, avg=None, above_avg=None) -> bool:
    """
    True only when every aptitude area is in Growth Area (below average):
    all seven reasoning areas scored as development tier, with no average
    or above-average areas.
    """
    below_list = _as_area_list(below)
    if _as_area_list(avg) or _as_area_list(above_avg):
        return False
    if not below_list:
        return False
    return len(below_list) >= len(ReasoningArea.ALL)


def should_show_aptitude_improvement_note(below, avg=None, above_avg=None) -> bool:
    """Show vocational improvement NOTE only when all seven areas are growth tier."""
    return student_all_growth_areas(below, avg, above_avg)


def should_show_extended_career_pathways(below, avg=None, above_avg=None) -> bool:
    """Extended stream-sorter pathways unless all aptitude results are growth area."""
    return not student_all_growth_areas(below, avg, above_avg)
