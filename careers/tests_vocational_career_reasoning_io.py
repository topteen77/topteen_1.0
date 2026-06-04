"""Unit tests for vocational career reasoning import/export."""

import json
import zipfile
import io
from unittest import TestCase
from unittest.mock import patch

from django.test import TestCase as DjangoTestCase

from careers.vocational_career_reasoning_io import (
    _career_lookup_tables,
    _normalize_mapping_rows,
    _parse_mappings_from_csv,
    _resolve_career_by_name,
    export_csv_zip_bytes,
    export_json_bytes,
)
from core.choices import ReasoningArea


class StrictCareerNameMatchTest(TestCase):
    def test_exact_and_normalized_match_only(self):
        careers = [
            type('Career', (), {'pk': 1, 'name': 'Biotech Laboratory Technician'})(),
            type('Career', (), {'pk': 2, 'name': 'AI-ML (Artificial Intelligence & Machine Learning) Technician'})(),
        ]
        by_exact, by_norm = _career_lookup_tables(careers)
        self.assertEqual(
            _resolve_career_by_name('Biotech Laboratory Technician', careers, by_exact, by_norm).pk,
            1,
        )
        self.assertIsNone(
            _resolve_career_by_name('Laboratory Technician', careers, by_exact, by_norm),
        )
        self.assertIsNone(
            _resolve_career_by_name('AI-ML Technician', careers, by_exact, by_norm),
        )


class ParseCareerMappingsTest(TestCase):
    def test_parse_csv(self):
        csv_text = 'career_id,career_name,reasoning_area,priority\n12,Electrician,VERBAL,1\n'
        rows, errors, name_format = _parse_mappings_from_csv(csv_text.encode('utf-8'))
        self.assertEqual(errors, [])
        self.assertFalse(name_format)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reasoning_area'], 'VERBAL')

    def test_normalize_valid_row(self):
        rows = _normalize_mapping_rows([
            {'career_id': '10', 'reasoning_area': 'verbal', 'priority': '1', '_line': 2},
        ])
        self.assertEqual(rows[0]['career_id'], 10)
        self.assertEqual(rows[0]['reasoning_area'], 'VERBAL')


class ExportCareerStructureTest(DjangoTestCase):
    @patch('careers.vocational_career_reasoning_io.vocational_career_cluster_id', return_value=99999)
    def test_export_json_has_version_and_choices(self, _mock_cluster_id):
        payload = json.loads(export_json_bytes().decode('utf-8'))
        self.assertEqual(payload['version'], 1)
        self.assertEqual(payload['reasoning_area_choices'], ReasoningArea.ALL)
        self.assertIn('careers', payload)
        self.assertIn('mappings', payload)
        self.assertEqual(payload['vocational_cluster_id'], 99999)

    @patch('careers.vocational_career_reasoning_io.vocational_career_cluster_id', return_value=99999)
    def test_export_csv_zip_contains_expected_files(self, _mock_cluster_id):
        raw = export_csv_zip_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
        self.assertIn('vocational_careers_catalog.csv', names)
        self.assertIn('vocational_career_reasoning_mappings.csv', names)
