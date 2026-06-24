"""Tests for Class 12 consolidated aptitude report context helpers."""
from django.test import SimpleTestCase

from app.class12_aptitude_report_utils import (
    aptitude_assessment_report_context,
    build_aptitude_interpretations,
    build_combination_key,
    build_consolidated_profile,
    build_consolidated_profile_for_student,
    enrich_interpretation,
    lookup_student_consolidated_row,
)


class Class12AptitudeReportUtilsTests(SimpleTestCase):
    def test_build_combination_key_sorted(self):
        above = ['Numerical Reasoning', 'Abstract Reasoning']
        average = ['Clerical speed & Accuracy']
        self.assertEqual(build_combination_key(above, average), 'AR + CR + NR')

    def test_lookup_student_row_single_code(self):
        row = lookup_student_consolidated_row(['Clerical speed & Accuracy'], [])
        self.assertIsNotNone(row)
        self.assertIn('aptitude_description', row)

    def test_lookup_student_row_combination(self):
        row = lookup_student_consolidated_row(
            ['Abstract Reasoning'],
            ['Numerical Reasoning'],
        )
        self.assertIsNotNone(row)
        self.assertIn('<strong>', row['interpretation_narrative'])

    def test_enrich_interpretation_keeps_real_life_signs(self):
        base = {
            'Area': 'Clerical speed & Accuracy',
            'Description': 'old',
            'Real life signs': ['Sign one', 'Sign two'],
            'Daily life impact': ['Impact one'],
            'Career impact': ['Old career'],
        }
        consolidated = lookup_student_consolidated_row(['Clerical speed & Accuracy'], [])
        enriched = enrich_interpretation(base, consolidated)
        self.assertEqual(enriched['Real life signs'], ['Sign one', 'Sign two'])
        self.assertEqual(enriched['Daily life impact'], ['Impact one'])
        self.assertNotEqual(enriched['Description'], 'old')
        self.assertTrue(enriched['Career impact'])

    def test_build_aptitude_interpretations_empty_when_consolidated(self):
        interpretation_data = {
            'Aptitude_Interpretations': [
                {
                    'Area': 'Clerical speed & Accuracy',
                    'Title': 'CLERICAL',
                    'Description': 'legacy',
                    'Real life signs': ['a'],
                    'Daily life impact': ['b'],
                    'Career impact': ['legacy career'],
                }
            ]
        }
        high_categories = {
            'Above Average': ['Clerical speed & Accuracy'],
            'Average': [],
        }
        items = build_aptitude_interpretations(high_categories, interpretation_data)
        self.assertEqual(len(items), 0)

    def test_build_consolidated_profile_for_student(self):
        high_categories = {
            'Above Average': ['Clerical speed & Accuracy'],
            'Average': [],
            'Below Average': [],
        }
        interpretation_data = {
            'Aptitude_Interpretations': [
                {
                    'Area': 'Clerical speed & Accuracy',
                    'Title': 'CLERICAL SPEED & ACCURACY',
                    'Image': 'images/clerical-speed.png',
                    'Real life signs': ['Sign one'],
                    'Daily life impact': ['Impact one'],
                }
            ]
        }
        profile = build_consolidated_profile_for_student(high_categories, interpretation_data)
        self.assertIsNotNone(profile)
        self.assertEqual(profile['combination_key'], 'CR')
        self.assertEqual(profile['title'], 'CLERICAL SPEED & ACCURACY')
        self.assertEqual(profile['real_life_signs'], ['Sign one'])
        self.assertEqual(profile['daily_life_impact'], ['Impact one'])

    def test_consolidated_signs_use_primary_area_only(self):
        high_categories = {
            'Above Average': ['Clerical speed & Accuracy'],
            'Average': ['Numerical Reasoning', 'Logical Reasoning'],
            'Below Average': [],
        }
        interpretation_data = {
            'Aptitude_Interpretations': [
                {
                    'Area': 'Clerical speed & Accuracy',
                    'Title': 'CLERICAL',
                    'Real life signs': ['Clerical sign'],
                    'Daily life impact': ['Clerical impact'],
                },
                {
                    'Area': 'Numerical Reasoning',
                    'Title': 'NUMERICAL',
                    'Real life signs': ['Numerical sign'],
                    'Daily life impact': ['Numerical impact'],
                },
            ]
        }
        profile = build_consolidated_profile_for_student(high_categories, interpretation_data)
        self.assertEqual(profile['real_life_signs'], ['Clerical sign'])
        self.assertEqual(profile['daily_life_impact'], ['Clerical impact'])

    def test_build_consolidated_profile_default_heading(self):
        row = lookup_student_consolidated_row(['Clerical speed & Accuracy'], [])
        profile = build_consolidated_profile(row, 'CR')
        self.assertEqual(profile['title'], 'Recommendation')

    def test_aptitude_assessment_report_context_includes_tier_json(self):
        hc = {
            'Above Average': ['Mechanical Reasoning'],
            'Average': ['Logical Reasoning'],
            'Below Average': ['Spatial Reasoning'],
        }
        ctx = aptitude_assessment_report_context(hc, {}, {'aptitude_improvement_plan': []})
        self.assertEqual(ctx['above_list'], ['Mechanical Reasoning'])
        self.assertIn('aptitude_tier_data_json', ctx)
        self.assertIsNotNone(ctx['class12_aptitude_consolidated_profile'])
