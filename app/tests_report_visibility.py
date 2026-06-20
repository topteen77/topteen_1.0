"""Tests for report visibility (below-average vs extended pathways)."""

from django.test import TestCase

from app.report_visibility import (
    should_show_aptitude_improvement_note,
    should_show_extended_career_pathways,
    student_all_growth_areas,
    student_has_below_average_areas,
)
from core.choices import ReasoningArea

ALL_GROWTH = list(ReasoningArea.ALL)


class ReportVisibilityTest(TestCase):
    def test_below_average_detection(self):
        self.assertFalse(student_has_below_average_areas([]))
        self.assertFalse(student_has_below_average_areas(None))
        self.assertTrue(student_has_below_average_areas(['VERBAL', 'LOGICAL']))

    def test_all_growth_areas_only_when_all_seven_are_development_tier(self):
        self.assertTrue(student_all_growth_areas(ALL_GROWTH, [], []))
        self.assertTrue(should_show_aptitude_improvement_note(ALL_GROWTH, [], []))
        self.assertFalse(student_all_growth_areas(['LOGICAL', 'SPATIAL'], [], []))
        self.assertFalse(student_all_growth_areas(['LOGICAL'], ['MECHANICAL'], []))
        self.assertFalse(student_all_growth_areas(['LOGICAL'], [], ['VERBAL']))
        self.assertFalse(student_all_growth_areas([], [], []))
        self.assertFalse(student_all_growth_areas(None, None, None))

    def test_extended_pathways_hidden_only_for_all_growth_students(self):
        self.assertFalse(should_show_extended_career_pathways(ALL_GROWTH, [], []))
        self.assertTrue(should_show_extended_career_pathways(['LOGICAL'], ['MECHANICAL'], ['VERBAL']))
        self.assertTrue(should_show_extended_career_pathways([], [], []))
        self.assertTrue(should_show_extended_career_pathways(None, None, None))
