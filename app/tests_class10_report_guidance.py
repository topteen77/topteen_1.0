"""Tests for Class 10 combined report career guidance (DB + filtering)."""

import json
from pathlib import Path

from django.test import TestCase

from app.career_resolve import career_report_entry, career_report_url
from app.models import Class10PremiumStream, Class10ReportGuidanceSettings
from app.stream_sorter_guidance import (
    build_report_stream_guidance,
    clear_stream_sorter_guidance_cache,
    import_catalog_from_json_file,
    load_catalog_from_database,
)

JSON_PATH = Path(__file__).resolve().parent / 'data' / 'class10_stream_sorter_unique_streams.json'


class Class10ReportGuidanceDbTest(TestCase):
    def setUp(self):
        clear_stream_sorter_guidance_cache()

    def tearDown(self):
        clear_stream_sorter_guidance_cache()

    def test_import_and_load_from_database(self):
        if not JSON_PATH.exists():
            self.skipTest('unique streams JSON missing')
        result = import_catalog_from_json_file(json_path=JSON_PATH, replace=True)
        self.assertTrue(result.get('ok'))
        catalog = load_catalog_from_database()
        self.assertIsNotNone(catalog)
        self.assertEqual(catalog['source'], 'database')
        self.assertGreaterEqual(len(catalog['stream_wise_premium_careers']), 5)

    def test_filter_one_recommended_stream(self):
        if not JSON_PATH.exists():
            self.skipTest('unique streams JSON missing')
        import_catalog_from_json_file(json_path=JSON_PATH, replace=True)
        clear_stream_sorter_guidance_cache()
        guidance = build_report_stream_guidance([('PCM', 'Physics Chemistry Mathematics')])
        self.assertIsNotNone(guidance)
        self.assertEqual(guidance['filter_mode'], 'recommended')
        self.assertEqual(len(guidance['stream_wise_premium_careers']), 1)
        self.assertIn('PCM', guidance['stream_wise_premium_careers'][0]['stream'])
        self.assertTrue(guidance.get('show_other_streams_toggle'))
        self.assertTrue(guidance['has_other_streams'])
        self.assertEqual(guidance['streams_total_count'], 5)
        self.assertEqual(guidance['other_streams_count'], 4)
        self.assertEqual(
            len(guidance['stream_wise_other_careers']),
            guidance['other_streams_count'],
        )
        other_labels = ' '.join(g['stream'] for g in guidance['stream_wise_other_careers'])
        self.assertIn('PCB', other_labels)
        self.assertIn('Humanities', other_labels)

    def test_filter_two_streams(self):
        if not JSON_PATH.exists():
            self.skipTest('unique streams JSON missing')
        import_catalog_from_json_file(json_path=JSON_PATH, replace=True)
        clear_stream_sorter_guidance_cache()
        guidance = build_report_stream_guidance([('HUM', 'Humanities'), ('CWM', 'Commerce')])
        self.assertEqual(len(guidance['stream_wise_premium_careers']), 2)

    def test_settings_singleton(self):
        settings = Class10ReportGuidanceSettings.get_solo()
        self.assertTrue(settings.stream_wise_title)

    def test_report_entry_shows_name_without_url_for_unknown_label(self):
        entry = career_report_entry(name='Nonexistent Career XYZ 999')
        self.assertEqual(entry['name'], 'Nonexistent Career XYZ 999')
        self.assertIsNone(entry['url'])

    def test_import_lists_all_careers_from_json(self):
        if not JSON_PATH.exists():
            self.skipTest('unique streams JSON missing')
        import_catalog_from_json_file(json_path=JSON_PATH, replace=True)
        clear_stream_sorter_guidance_cache()
        catalog = load_catalog_from_database()
        pcm = next(
            g for g in catalog['stream_wise_premium_careers']
            if g.get('stream_code') == 'PCM'
        )
        with JSON_PATH.open(encoding='utf-8') as handle:
            json_pcm = next(
                g for g in json.load(handle)['stream_wise_premium_careers']
                if 'PCM' in g.get('stream', '')
            )
        self.assertEqual(len(pcm['careers']), len(json_pcm['careers']))
