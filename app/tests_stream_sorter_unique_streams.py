"""Tests for unique stream careers JSON builder."""

import json
from pathlib import Path

from django.test import TestCase

from app.stream_sorter_unique_streams import build_unique_streams_payload

GUIDANCE_PATH = Path(__file__).resolve().parent / 'data' / 'class10_stream_sorter_guidance.json'


class UniqueStreamCareersJsonTest(TestCase):
    def test_builds_unique_streams_and_dedupes_within_stream(self):
        if not GUIDANCE_PATH.exists():
            self.skipTest('Guidance JSON missing')
        payload = build_unique_streams_payload(GUIDANCE_PATH)
        streams = payload['stream_wise_premium_careers']
        self.assertEqual(payload['stats']['unique_streams'], len(streams))
        self.assertGreaterEqual(len(streams), 5)
        pcm = next(s for s in streams if 'PCM' in s['stream'])
        self.assertEqual(len(pcm['careers']), len(set(c.strip() for c in pcm['careers'])))
        future = payload['future_relevant_careers']
        self.assertEqual(len(future), len(set(c.strip() for c in future)))

    def test_career_may_repeat_across_streams(self):
        if not GUIDANCE_PATH.exists():
            self.skipTest('Guidance JSON missing')
        payload = build_unique_streams_payload(GUIDANCE_PATH)
        names_by_stream = [
            set(c.strip() for c in s['careers'])
            for s in payload['stream_wise_premium_careers']
        ]
        if len(names_by_stream) >= 2:
            all_names = [c for s in payload['stream_wise_premium_careers'] for c in s['careers']]
            # At least allow cross-stream duplicates in principle (not required to exist)
            self.assertGreater(len(all_names), 0)
