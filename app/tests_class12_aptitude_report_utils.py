"""Tests for Class 12 consolidated aptitude report context helpers."""
from django.test import SimpleTestCase, override_settings

from app.class12_aptitude_report_utils import (
    aptitude_assessment_report_context,
    build_aptitude_interpretations,
    build_class12_consolidated_aptitude_mapping,
    build_combination_key,
    build_consolidated_profile,
    build_consolidated_profile_for_student,
    enrich_interpretation,
    lookup_student_consolidated_row,
    resolve_class12_consolidated_tiers,
)
from core.choices import (
    CLASS10_APTITUDE_STREAM_MODE_COMBINED,
    CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
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
            mode=CLASS10_APTITUDE_STREAM_MODE_COMBINED,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row['reasoning_combination'], 'AR + NR')
        self.assertTrue(row['interpretation_narrative'])
        self.assertTrue(row.get('real_life_signs'))
        self.assertTrue(row.get('daily_life_impact'))

    def test_tier_priority_uses_above_only(self):
        hc = {
            'Above Average': ['Clerical speed & Accuracy', 'Mechanical Reasoning'],
            'Average': ['Abstract Reasoning', 'Numerical Reasoning'],
            'Below Average': [],
        }
        tier_ctx = resolve_class12_consolidated_tiers(
            hc,
            mode=CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
        )
        self.assertEqual(tier_ctx['tier_used'], 'above_avg')
        self.assertEqual(tier_ctx['combination_key'], 'CR + MR')
        self.assertEqual(tier_ctx['primary_area'], 'Clerical speed & Accuracy')

    def test_tier_priority_falls_back_to_average(self):
        hc = {
            'Above Average': [],
            'Average': ['Abstract Reasoning', 'Numerical Reasoning'],
            'Below Average': ['Spatial Reasoning'],
        }
        tier_ctx = resolve_class12_consolidated_tiers(
            hc,
            mode=CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
        )
        self.assertEqual(tier_ctx['tier_used'], 'average')
        self.assertEqual(tier_ctx['combination_key'], 'AR + NR')

    def test_combined_mode_uses_both_tiers(self):
        hc = {
            'Above Average': ['Clerical speed & Accuracy', 'Mechanical Reasoning'],
            'Average': ['Abstract Reasoning'],
            'Below Average': [],
        }
        tier_ctx = resolve_class12_consolidated_tiers(
            hc,
            mode=CLASS10_APTITUDE_STREAM_MODE_COMBINED,
        )
        self.assertEqual(tier_ctx['tier_used'], 'combined')
        self.assertEqual(tier_ctx['combination_key'], 'AR + CR + MR')

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
                    'Real life signs': ['Legacy sign'],
                    'Daily life impact': ['Legacy impact'],
                }
            ]
        }
        consolidated = lookup_student_consolidated_row(['Clerical speed & Accuracy'], [])
        profile = build_consolidated_profile_for_student(high_categories, interpretation_data)
        self.assertIsNotNone(profile)
        self.assertEqual(profile['combination_key'], 'CR')
        self.assertEqual(profile['title'], 'CLERICAL SPEED & ACCURACY')
        self.assertEqual(profile['real_life_signs'], consolidated['real_life_signs'])
        self.assertEqual(profile['daily_life_impact'], consolidated['daily_life_impact'])

    def test_consolidated_signs_use_combination_row_content(self):
        high_categories = {
            'Above Average': ['Clerical speed & Accuracy', 'Mechanical Reasoning'],
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
                    'Area': 'Mechanical Reasoning',
                    'Title': 'MECHANICAL',
                    'Real life signs': ['Mechanical sign'],
                    'Daily life impact': ['Mechanical impact'],
                },
            ]
        }
        consolidated = lookup_student_consolidated_row(
            ['Clerical speed & Accuracy', 'Mechanical Reasoning'],
            [],
            mode=CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
        )
        profile = build_consolidated_profile_for_student(high_categories, interpretation_data)
        self.assertEqual(profile['combination_key'], 'CR + MR')
        self.assertEqual(profile['real_life_signs'], consolidated['real_life_signs'])
        self.assertEqual(profile['daily_life_impact'], consolidated['daily_life_impact'])

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

    def test_consolidated_aptitude_mapping_tier_priority_uses_above_only(self):
        hc = {
            'Above Average': ['Numerical Reasoning'],
            'Average': [
                'Abstract Reasoning',
                'Logical Reasoning',
                'Language and Verbal Reasoning',
                'Spatial Reasoning',
            ],
            'Below Average': ['Clerical speed & Accuracy', 'Mechanical Reasoning'],
        }
        mapping = build_class12_consolidated_aptitude_mapping(
            hc,
            mode=CLASS10_APTITUDE_STREAM_MODE_TIER_PRIORITY,
        )
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping['aptitude_code'], 'NR')
        self.assertEqual(mapping['aptitude_areas'], ['Numerical Reasoning'])

    def test_consolidated_aptitude_mapping_combined_mode(self):
        hc = {
            'Above Average': ['Numerical Reasoning'],
            'Average': ['Abstract Reasoning', 'Logical Reasoning'],
            'Below Average': [],
        }
        mapping = build_class12_consolidated_aptitude_mapping(
            hc,
            mode=CLASS10_APTITUDE_STREAM_MODE_COMBINED,
        )
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping['aptitude_code'], 'AR + LR + NR')
        self.assertIn('clusters', mapping)
        self.assertIn('roles', mapping)
        self.assertIn('pathways', mapping)
