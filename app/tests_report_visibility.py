"""Tests for report visibility (below-average vs extended pathways)."""

from django.test import TestCase

from app.report_visibility import (
    should_show_extended_career_pathways,
    student_all_growth_areas,
    student_has_below_average_areas,
)


class ReportVisibilityTest(TestCase):
    def test_below_average_detection(self):
        self.assertFalse(student_has_below_average_areas([]))
        self.assertFalse(student_has_below_average_areas(None))
        self.assertTrue(student_has_below_average_areas(['VERBAL', 'LOGICAL']))

    def test_all_growth_areas_only_when_every_result_is_below(self):
        self.assertTrue(student_all_growth_areas(['LOGICAL', 'SPATIAL'], [], []))
        self.assertFalse(student_all_growth_areas(['LOGICAL'], ['MECHANICAL'], []))
        self.assertFalse(student_all_growth_areas(['LOGICAL'], [], ['VERBAL']))
        self.assertFalse(student_all_growth_areas([], [], []))
        self.assertFalse(student_all_growth_areas(None, None, None))

    def test_extended_pathways_hidden_only_for_all_growth_students(self):
        self.assertFalse(should_show_extended_career_pathways(['LOGICAL', 'SPATIAL'], [], []))
        self.assertTrue(should_show_extended_career_pathways(['LOGICAL'], ['MECHANICAL'], ['VERBAL']))
        self.assertTrue(should_show_extended_career_pathways([], [], []))
        self.assertTrue(should_show_extended_career_pathways(None, None, None))
