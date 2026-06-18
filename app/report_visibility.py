"""Report / dashboard visibility rules for aptitude tiers."""

from __future__ import annotations


def _as_area_list(value) -> list:
    return value if isinstance(value, list) else []


def student_has_below_average_areas(below) -> bool:
    """True when the student has at least one below-average reasoning area."""
    return isinstance(below, list) and len(below) > 0


def student_all_growth_areas(below, avg=None, above_avg=None) -> bool:
    """
    True only when every scored aptitude area is in Growth Area (below average):
    at least one below-area and no average or above-average areas.
    """
    below_list = _as_area_list(below)
    if not below_list:
        return False
    return not _as_area_list(avg) and not _as_area_list(above_avg)


def should_show_extended_career_pathways(below, avg=None, above_avg=None) -> bool:
    """Extended stream-sorter pathways unless all aptitude results are growth area."""
    return not student_all_growth_areas(below, avg, above_avg)

