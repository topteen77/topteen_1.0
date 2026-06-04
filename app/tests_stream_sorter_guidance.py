"""Tests for Class 10 stream sorter guidance extraction and lookup."""

from pathlib import Path

from django.test import TestCase

from app.stream_sorter_extraction import (
    build_guidance_payload,
    extract_guidance_from_docx,
)
from app.stream_sorter_guidance import (
    get_stream_sorter_guidance_for_category,
    load_stream_sorter_guidance,
)

SOURCE_DIR = Path('/home/itpc6/Documents/arvinder/new/10 CLASS RIASAC- STREAM SORTER')
JSON_PATH = Path(__file__).resolve().parent / 'data' / 'class10_stream_sorter_guidance.json'


class StreamSorterExtractionTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not SOURCE_DIR.exists():
            cls.skip_source = True
            return
        cls.skip_source = False

    def test_extract_artistic_docx_sections(self):
        if self.skip_source:
            self.skipTest('Source docx directory not available')
        data = extract_guidance_from_docx(SOURCE_DIR / 'Artistic.docx')
        self.assertIn('ASE', data['category_codes'])
        self.assertGreaterEqual(len(data['stream_wise_premium_careers']), 4)
        self.assertGreaterEqual(len(data['future_relevant_careers']), 5)
        pcm = data['stream_wise_premium_careers'][0]
        self.assertIn('PCM', pcm['stream'])
        self.assertIn('Software Engineer', pcm['careers'])

    def test_json_lookup_ase(self):
        if not JSON_PATH.exists():
            self.skipTest('Generated JSON not present; run extract_class10_stream_sorter_guidance')
        guidance = get_stream_sorter_guidance_for_category('ASE', path=str(JSON_PATH))
        self.assertIsNotNone(guidance)
        self.assertEqual(guidance['riasec_letter'], 'A')
        self.assertTrue(guidance['stream_wise_premium_careers'])
        self.assertTrue(guidance['future_relevant_careers'])

    def test_build_payload_maps_120_codes(self):
        if self.skip_source:
            self.skipTest('Source docx directory not available')
        payload = build_guidance_payload(SOURCE_DIR)
        self.assertEqual(len(payload['files']), 6)
        self.assertEqual(len(payload['category_code_to_letter']), 120)
