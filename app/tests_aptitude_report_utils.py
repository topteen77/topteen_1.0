"""Tests for Class 10 aptitude performance profile cards."""

from django.test import SimpleTestCase

from app.aptitude_report_utils import class10_aptitude_profile_sections


class Class10AptitudeProfileSectionsTest(SimpleTestCase):
    def test_builds_seven_sections_from_raw_scores(self):
        sections = class10_aptitude_profile_sections({
            'logical_score': 8,
            'spatial_score': 2,
            'critical_score': 8,
            'numerical_score': 7,
            'mechanical_score': 11,
            'language_score': 13,
            'verbal_score': 10,
        })
        self.assertEqual(len(sections), 7)
        self.assertEqual(sections[0]['name'], 'Logical Reasoning')
        self.assertEqual(sections[0]['correct_answers'], 8)
        self.assertEqual(sections[0]['accuracy'], 53.3)
        self.assertEqual(sections[0]['accent_color'], '#2E8AA6')
        self.assertEqual(sections[1]['accent_color'], '#C24E4E')
        self.assertEqual(sections[4]['accent_color'], '#3F37C9')

    def test_accepts_normalized_score_keys(self):
        sections = class10_aptitude_profile_sections({
            'LOGICAL': 12,
            'SPATIAL': 5,
            'CRITICAL': 6,
            'NUMERICAL': 9,
            'MECHANICAL': 10,
            'LANGUAGE': 11,
            'VERBAL': 7,
        })
        self.assertEqual(sections[3]['name'], 'Numerical Reasoning')
        self.assertEqual(sections[3]['correct_answers'], 9)

    def test_empty_scores_returns_empty_list(self):
        self.assertEqual(class10_aptitude_profile_sections(None), [])
        self.assertEqual(class10_aptitude_profile_sections({}), [])
