"""Tests for report visibility (below-average vs extended pathways)."""

from django.test import TestCase

from app.report_visibility import (
    should_show_extended_career_pathways,
    student_has_below_average_areas,
)


class ReportVisibilityTest(TestCase):
    def test_below_average_detection(self):
        self.assertFalse(student_has_below_average_areas([]))
        self.assertFalse(student_has_below_average_areas(None))
        self.assertTrue(student_has_below_average_areas(['VERBAL', 'LOGICAL']))

    def test_extended_pathways_hidden_for_below_average(self):
        self.assertFalse(should_show_extended_career_pathways(['NUMERICAL']))
        self.assertTrue(should_show_extended_career_pathways([]))
        self.assertTrue(should_show_extended_career_pathways(None))
