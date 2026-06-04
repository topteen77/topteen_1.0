"""Report / dashboard visibility rules for aptitude tiers."""

from __future__ import annotations


def student_has_below_average_areas(below) -> bool:
    """True when the student has at least one below-average reasoning area."""
    return isinstance(below, list) and len(below) > 0


def should_show_extended_career_pathways(below) -> bool:
    """Extended stream-sorter pathways are hidden for below-average students."""
    return not student_has_below_average_areas(below)
