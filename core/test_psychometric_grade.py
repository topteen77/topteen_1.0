"""Tests for psychometric grade track resolution."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.models import DashboardRuleAppliesTo
from core.psychometric_grade import (
    CLASS10_TRACK,
    POST_MATRIC_TRACK,
    get_rule_applies_to_label,
    get_student_psychometric_track,
    rule_applies_to_user,
)


class PsychometricGradeTests(SimpleTestCase):
    def test_defaults_to_class10_without_profile(self):
        user = MagicMock()
        user.user_profile = None
        with patch('institute.models.StudentManagement', create=True) as mock_sm:
            mock_sm.objects.filter.return_value.select_related.return_value.first.return_value = None
            self.assertEqual(get_student_psychometric_track(user), CLASS10_TRACK)

    def test_class10_from_numeric_grade(self):
        user = MagicMock()
        user.user_profile.grade = '10'
        self.assertEqual(get_student_psychometric_track(user), CLASS10_TRACK)

    def test_class10_from_class_label(self):
        user = MagicMock()
        user.user_profile.grade = 'Class 9'
        self.assertEqual(get_student_psychometric_track(user), CLASS10_TRACK)

    def test_post_matric_from_grade_11(self):
        user = MagicMock()
        user.user_profile.grade = 'Class 11'
        self.assertEqual(get_student_psychometric_track(user), POST_MATRIC_TRACK)

    def test_post_matric_from_grade_12(self):
        user = MagicMock()
        user.user_profile.grade = '12'
        self.assertEqual(get_student_psychometric_track(user), POST_MATRIC_TRACK)

    def test_post_matric_from_student_management_when_profile_missing(self):
        user = MagicMock()
        user.user_profile = None

        class_and_section = MagicMock()
        class_and_section.class_and_section = '12 A'

        student_management = MagicMock()
        student_management.class_and_section = class_and_section

        with patch('institute.models.StudentManagement') as mock_sm:
            mock_sm.objects.filter.return_value.select_related.return_value.first.return_value = (
                student_management
            )
            self.assertEqual(get_student_psychometric_track(user), POST_MATRIC_TRACK)


class RuleAppliesToTests(SimpleTestCase):
    def test_all_students_applies_to_both_tracks(self):
        self.assertTrue(rule_applies_to_user(DashboardRuleAppliesTo.ALL, CLASS10_TRACK))
        self.assertTrue(rule_applies_to_user(DashboardRuleAppliesTo.ALL, POST_MATRIC_TRACK))

    def test_post_matric_rule_only_for_class_11_12(self):
        self.assertFalse(rule_applies_to_user(DashboardRuleAppliesTo.CLASS_11_12_PLUS, CLASS10_TRACK))
        self.assertTrue(rule_applies_to_user(DashboardRuleAppliesTo.CLASS_11_12_PLUS, POST_MATRIC_TRACK))

    def test_class10_rule_only_for_class_10(self):
        self.assertTrue(rule_applies_to_user(DashboardRuleAppliesTo.CLASS_10_AND_BELOW, CLASS10_TRACK))
        self.assertFalse(rule_applies_to_user(DashboardRuleAppliesTo.CLASS_10_AND_BELOW, POST_MATRIC_TRACK))

    @patch('core.psychometric_grade.get_point_rule_applies_to')
    def test_default_motivation_label(self, mock_applies):
        mock_applies.return_value = DashboardRuleAppliesTo.CLASS_11_12_PLUS
        self.assertEqual(
            get_rule_applies_to_label('motivation_test_complete'),
            DashboardRuleAppliesTo.CLASS_11_12_PLUS.label,
        )

    @patch('core.psychometric_grade.get_point_rule_applies_to')
    def test_shared_rules_apply_to_all(self, mock_applies):
        mock_applies.return_value = DashboardRuleAppliesTo.ALL
        self.assertEqual(get_rule_applies_to_label('registration'), DashboardRuleAppliesTo.ALL.label)
