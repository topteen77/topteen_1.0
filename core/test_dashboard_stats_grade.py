"""Tests for grade-aware dashboard points, levels, and trophies."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.dashboard_points import get_active_point_rules_total, get_valid_level_band_min_points
from core.dashboard_stats import (
    DEFAULT_POINT_RULES,
    _get_applicable_point_map,
    _get_level_band,
    _get_points_details,
    _rule_condition_met,
)
from core.models import DashboardRuleAppliesTo
from core.psychometric_grade import CLASS10_TRACK, POST_MATRIC_TRACK


CLASS10_BANDS = [
    {'name': 'Rookie', 'min_points': 50, 'order': 0},
    {'name': 'Explorer', 'min_points': 250, 'order': 1},
    {'name': 'Champion', 'min_points': 420, 'order': 2},
    {'name': 'Legend', 'min_points': 770, 'order': 3},
]

POST_MATRIC_BANDS = [
    {'name': 'Rookie', 'min_points': 50, 'order': 0},
    {'name': 'Explorer', 'min_points': 250, 'order': 1},
    {'name': 'Champion', 'min_points': 490, 'order': 2},
    {'name': 'Legend', 'min_points': 840, 'order': 3},
]

SAMPLE_RULES = [
    {'rule_key': 'registration', 'points': 50, 'order': 1, 'applies_to': DashboardRuleAppliesTo.ALL},
    {'rule_key': 'profile_complete', 'points': 50, 'order': 2, 'applies_to': DashboardRuleAppliesTo.ALL},
    {'rule_key': 'payment_success', 'points': 150, 'order': 3, 'applies_to': DashboardRuleAppliesTo.ALL},
    {'rule_key': 'personality_test_complete', 'points': 100, 'order': 4, 'applies_to': DashboardRuleAppliesTo.ALL},
    {
        'rule_key': 'motivation_test_complete',
        'points': 70,
        'order': 5,
        'applies_to': DashboardRuleAppliesTo.CLASS_11_12_PLUS,
    },
    {'rule_key': 'interest_test_complete', 'points': 70, 'order': 6, 'applies_to': DashboardRuleAppliesTo.ALL},
    {'rule_key': 'aptitude_test_complete', 'points': 200, 'order': 7, 'applies_to': DashboardRuleAppliesTo.ALL},
    {'rule_key': 'report_reading', 'points': 150, 'order': 8, 'applies_to': DashboardRuleAppliesTo.ALL},
]


class DashboardPointsTrackTests(SimpleTestCase):
    @patch('core.dashboard_points.get_point_rules_with_applies_to')
    def test_max_points_differ_by_track(self, mock_rules):
        mock_rules.return_value = SAMPLE_RULES
        self.assertEqual(get_active_point_rules_total(track=POST_MATRIC_TRACK), 840)
        self.assertEqual(get_active_point_rules_total(track=CLASS10_TRACK), 770)

    @patch('core.dashboard_points.get_point_rules_with_applies_to')
    def test_valid_milestones_include_both_tracks(self, mock_rules):
        mock_rules.return_value = SAMPLE_RULES
        valid = get_valid_level_band_min_points()
        self.assertIn(420, valid)
        self.assertIn(490, valid)
        self.assertIn(770, valid)
        self.assertIn(840, valid)


class DashboardStatsGradeTests(SimpleTestCase):
    @patch('core.dashboard_stats.get_point_rules_with_applies_to', return_value=SAMPLE_RULES)
    @patch('core.dashboard_stats.get_student_psychometric_track', return_value=CLASS10_TRACK)
    def test_class10_point_map_excludes_motivation(self, _mock_track, _mock_rules):
        user = MagicMock()
        point_map = _get_applicable_point_map(user)
        self.assertNotIn('motivation_test_complete', point_map)
        self.assertEqual(len(point_map), len(DEFAULT_POINT_RULES) - 1)

    @patch('core.dashboard_stats.get_point_rules_with_applies_to', return_value=SAMPLE_RULES)
    @patch('core.dashboard_stats.get_student_psychometric_track', return_value=POST_MATRIC_TRACK)
    def test_post_matric_point_map_includes_motivation(self, _mock_track, _mock_rules):
        user = MagicMock()
        point_map = _get_applicable_point_map(user)
        self.assertIn('motivation_test_complete', point_map)

    @patch('user_analytics.models.UserEvent')
    @patch('core.dashboard_stats._rule_condition_met', return_value=False)
    @patch('core.dashboard_stats._get_applicable_point_map')
    @patch('core.models.DashboardPointRule')
    @patch('core.dashboard_stats.get_student_psychometric_track', return_value=CLASS10_TRACK)
    def test_class10_points_details_hide_motivation(
        self, _mock_track, mock_rule_model, mock_point_map, _mock_met, mock_user_event,
    ):
        mock_rule_model.objects.filter.return_value.values.return_value = []
        mock_user_event.objects.filter.return_value.values.return_value.annotate.return_value = []
        class10_map = {
            key: value
            for key, value in DEFAULT_POINT_RULES.items()
            if key != 'motivation_test_complete'
        }
        mock_point_map.return_value = class10_map
        user = MagicMock()
        user.pk = 1
        details, _ = _get_points_details(user)
        rule_keys = [row['rule_key'] for row in details]
        self.assertNotIn('motivation_test_complete', rule_keys)

    @patch('core.dashboard_stats.rule_applies_to_user_track', return_value=False)
    @patch('core.dashboard_stats.get_student_psychometric_track', return_value=CLASS10_TRACK)
    def test_class10_cannot_earn_motivation_points(self, _mock_track, _mock_applies):
        user = MagicMock()
        self.assertFalse(_rule_condition_met(user, 'motivation_test_complete'))

    @patch('core.dashboard_stats.rule_applies_to_user_track', return_value=True)
    @patch('core.dashboard_stats._post_matric_test_completed', return_value=True)
    def test_post_matric_can_earn_motivation_points(self, _mock_completed, _mock_applies):
        user = MagicMock()
        self.assertTrue(_rule_condition_met(user, 'motivation_test_complete'))

    @patch('core.dashboard_stats._get_level_bands_for_user', return_value=CLASS10_BANDS)
    def test_class10_legend_at_770(self, _mock_bands):
        user = MagicMock()
        level, next_min, progress = _get_level_band(770, user=user)
        self.assertEqual(level, 'Legend')
        self.assertIsNone(next_min)
        self.assertEqual(progress, 0)

    @patch('core.dashboard_stats._get_level_bands_for_user', return_value=POST_MATRIC_BANDS)
    def test_post_matric_770_is_not_legend(self, _mock_bands):
        user = MagicMock()
        level, next_min, _progress = _get_level_band(770, user=user)
        self.assertEqual(level, 'Champion')
        self.assertEqual(next_min, 840)
