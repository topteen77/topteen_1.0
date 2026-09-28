"""Tests for psychometric grade track resolution."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.models import DashboardRuleAppliesTo
from core.psychometric_grade import (
    CLASS10_TRACK,
    POST_MATRIC_TRACK,
    dashboard_grade_bucket,
    get_rule_applies_to_label,
    get_student_psychometric_track,
    hides_undergraduate_college_tools,
    rule_applies_to_user,
    student_class_display,
)


class _BareUser:
    """Plain user so missing cache attributes are not auto-created."""

    pk = 1
    user_profile = None


class PsychometricGradeTests(SimpleTestCase):
    def test_class_display_uses_school_class_and_not_the_word_none(self):
        user = _BareUser()
        user.user_profile = MagicMock(grade='None')
        section = MagicMock()
        section.class_and_section = '12 A'
        sm = MagicMock()
        sm.class_and_section_id = 4
        sm.class_and_section = section
        sm.education_audience = 'school'
        self.assertEqual(student_class_display(user, sm), '12 A')
        section.class_and_section = '12th'
        self.assertEqual(student_class_display(user, sm), 'Class 12')

    def test_grade_form_follows_matric_postmatric_or_college(self):
        from core.psychometric_grade import student_grade_form

        user = _BareUser()
        user.user_profile = MagicMock(grade=None)
        sm = MagicMock()
        sm.class_and_section_id = 4
        sm.class_and_section.class_and_section = '12th'
        sm.education_audience = 'school'
        with patch('institute.models.get_cached_student_management', return_value=sm):
            form = student_grade_form(user)
        values = [opt['value'] for opt in form['options']]
        self.assertEqual(values, ['12', '11'])
        self.assertTrue(form['options'][0]['selected'])
        self.assertFalse(form['options'][1]['selected'])

        sm.class_and_section.class_and_section = '10th'
        with patch('institute.models.get_cached_student_management', return_value=sm):
            matric = student_grade_form(user)
        matric_values = [int(opt['value']) for opt in matric['options']]
        self.assertIn(10, matric_values)
        self.assertNotIn(12, matric_values)
        selected = [opt for opt in matric['options'] if opt['selected']]
        self.assertEqual(selected[0]['value'], '10')

        sm.class_and_section_id = None
        sm.education_audience = 'graduate'
        with patch('institute.models.get_cached_student_management', return_value=sm):
            college = student_grade_form(user)
        self.assertEqual(
            [opt['value'] for opt in college['options']],
            ['class12_passout', 'graduate', 'postgraduate', 'professional'],
        )
        self.assertEqual(
            [opt['value'] for opt in college['options'] if opt['selected']],
            ['graduate'],
        )

    def test_class_display_uses_education_level_when_class_is_empty(self):
        user = _BareUser()
        user.user_profile = MagicMock(grade=None)
        sm = MagicMock()
        sm.class_and_section_id = None
        sm.education_audience = 'graduate'
        self.assertEqual(student_class_display(user, sm), 'Graduate')
        sm.education_audience = 'class12_passout'
        self.assertEqual(student_class_display(user, sm), 'Class 12 passout')

    def test_blank_grade_is_not_shown_as_class_none(self):
        user = _BareUser()
        user.user_profile = MagicMock(grade='None')
        with patch('institute.models.get_cached_student_management', return_value=None):
            self.assertEqual(student_class_display(user), '')

    def test_school_display_uses_institute_when_profile_school_is_empty(self):
        from core.psychometric_grade import student_school_display

        user = _BareUser()
        user.user_profile = MagicMock(schoolname=None)
        sm = MagicMock()
        sm.institute.name = 'test-personality-only'
        self.assertEqual(student_school_display(user, sm), 'test-personality-only')
        user.user_profile.schoolname = 'My School'
        self.assertEqual(student_school_display(user, sm), 'My School')

    def test_defaults_to_class10_without_profile(self):
        user = _BareUser()
        with patch('institute.models.get_cached_student_management', return_value=None):
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
        user = _BareUser()

        class_and_section = MagicMock()
        class_and_section.class_and_section = '12 A'

        student_management = MagicMock()
        student_management.class_and_section = class_and_section
        student_management.education_audience = 'school'

        with patch('institute.models.get_cached_student_management', return_value=student_management):
            self.assertEqual(get_student_psychometric_track(user), POST_MATRIC_TRACK)

    def test_empty_class_stays_class10_for_school(self):
        user = _BareUser()
        student_management = MagicMock()
        student_management.class_and_section = None
        student_management.education_audience = 'school'
        with patch('institute.models.get_cached_student_management', return_value=student_management):
            self.assertEqual(get_student_psychometric_track(user), CLASS10_TRACK)

    def test_graduate_with_empty_class_is_post_matric(self):
        user = _BareUser()
        student_management = MagicMock()
        student_management.class_and_section = None
        student_management.education_audience = 'graduate'
        with patch('institute.models.get_cached_student_management', return_value=student_management):
            self.assertEqual(get_student_psychometric_track(user), POST_MATRIC_TRACK)

    def test_known_class10_is_not_overridden_by_audience_lookup(self):
        user = MagicMock()
        user.user_profile.grade = '10'
        self.assertEqual(get_student_psychometric_track(user), CLASS10_TRACK)
        self.assertEqual(
            dashboard_grade_bucket(user, '10', class_number_known=True),
            '10',
        )

    def test_dashboard_bucket_empty_school_stays_10(self):
        user = MagicMock()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='school',
        ):
            self.assertEqual(
                dashboard_grade_bucket(user, '10', class_number_known=False),
                '10',
            )

    def test_dashboard_bucket_graduate_without_class_is_12(self):
        user = MagicMock()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='graduate',
        ):
            self.assertEqual(
                dashboard_grade_bucket(user, '10', class_number_known=False),
                '12',
            )

    def test_dashboard_bucket_keeps_non_numeric_school_grade(self):
        user = MagicMock()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='school',
        ):
            self.assertEqual(
                dashboard_grade_bucket(user, 'Graduate', class_number_known=False),
                'Graduate',
            )

    def test_graduate_hides_college_tools_and_skill_lab(self):
        from users.skilllab_dashboard import skilllab_is_career_readiness_grade_student

        user = _BareUser()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='graduate',
        ), patch('users.skilllab_dashboard._extract_grade_number', return_value=None):
            self.assertTrue(hides_undergraduate_college_tools(user))
            self.assertFalse(skilllab_is_career_readiness_grade_student(user))

    def test_class10_still_shows_skill_lab_section(self):
        from users.skilllab_dashboard import skilllab_is_career_readiness_grade_student

        user = _BareUser()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='school',
        ), patch('users.skilllab_dashboard._extract_grade_number', return_value=10):
            self.assertFalse(hides_undergraduate_college_tools(user))
            self.assertTrue(skilllab_is_career_readiness_grade_student(user))

    def test_passout_keeps_college_tools(self):
        user = _BareUser()
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='class12_passout',
        ):
            self.assertFalse(hides_undergraduate_college_tools(user))

    def test_graduate_does_not_get_school_career_or_college_match(self):
        from app_post_matric.views import get_career_recommendations_from_tests
        from colleges.psychometric_match import _latest_riasec_scores

        user = _BareUser()
        user.is_authenticated = True
        with patch(
            'core.psychometric_grade.get_student_education_audience',
            return_value='graduate',
        ):
            self.assertEqual(get_career_recommendations_from_tests(user), [])
            self.assertIsNone(_latest_riasec_scores(user))


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
