"""Unit tests for vocational reasoning import/export (no DB migration required)."""

import json
import zipfile
import io
from unittest import TestCase

from django.test import SimpleTestCase, TestCase as DjangoTestCase

from core.choices import ReasoningArea
from core.vocational_reasoning_io import (
    _normalize_mapping_rows,
    _parse_mappings_from_csv,
    _parse_mappings_from_json,
    export_csv_zip_bytes,
    export_json_bytes,
)


class ReasoningAreaChoicesTest(SimpleTestCase):
    def test_all_seven_areas_present(self):
        self.assertEqual(len(ReasoningArea.ALL), 7)
        self.assertIn('VERBAL', ReasoningArea.ALL)
        self.assertIn('CRITICAL', ReasoningArea.ALL)

    def test_label(self):
        self.assertEqual(ReasoningArea.label('VERBAL'), 'Verbal')
        self.assertEqual(ReasoningArea.label('UNKNOWN'), 'Unknown')

    def test_is_valid(self):
        self.assertTrue(ReasoningArea.is_valid('LOGICAL'))
        self.assertFalse(ReasoningArea.is_valid('EMOTIONAL'))


class ParseMappingsTest(SimpleTestCase):
    def test_parse_json_with_mappings_key(self):
        payload = {'mappings': [{'course_id': 1, 'reasoning_area': 'VERBAL', 'priority': 1}]}
        rows = _parse_mappings_from_json(json.dumps(payload).encode('utf-8'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reasoning_area'], 'VERBAL')

    def test_parse_json_list(self):
        payload = [{'course_id': 2, 'reasoning_area': 'LOGICAL', 'priority': 2}]
        rows = _parse_mappings_from_json(json.dumps(payload).encode('utf-8'))
        self.assertEqual(rows[0]['course_id'], 2)

    def test_parse_csv(self):
        csv_text = 'course_id,course_name,reasoning_area,priority\n12,Business Comm,VERBAL,1\n'
        rows = _parse_mappings_from_csv(csv_text.encode('utf-8'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reasoning_area'], 'VERBAL')
        self.assertEqual(rows[0]['course_id'], '12')


class NormalizeMappingsTest(SimpleTestCase):
    def test_valid_row(self):
        rows = _normalize_mapping_rows([
            {'course_id': '10', 'reasoning_area': 'verbal', 'priority': '1', '_line': 2},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['course_id'], 10)
        self.assertEqual(rows[0]['reasoning_area'], 'VERBAL')

    def test_invalid_area(self):
        rows = _normalize_mapping_rows([
            {'course_id': '10', 'reasoning_area': 'BAD', 'priority': '1', '_line': 2},
        ])
        self.assertIn('error', rows[0])

    def test_duplicate_pair_rejected(self):
        rows = _normalize_mapping_rows([
            {'course_id': '10', 'reasoning_area': 'VERBAL', 'priority': '1', '_line': 2},
            {'course_id': '10', 'reasoning_area': 'VERBAL', 'priority': '2', '_line': 3},
        ])
        errors = [r for r in rows if 'error' in r]
        self.assertEqual(len(errors), 1)
        self.assertIn('duplicate', errors[0]['error'].lower())


class ExportStructureTest(DjangoTestCase):
    """Uses Django test DB (migrations applied to test DB only, not production)."""
    def test_export_json_has_version_and_choices(self):
        payload = json.loads(export_json_bytes().decode('utf-8'))
        self.assertEqual(payload['version'], 1)
        self.assertEqual(payload['reasoning_area_choices'], ReasoningArea.ALL)
        self.assertIn('courses', payload)
        self.assertIn('mappings', payload)
        self.assertIn('unmapped_course_ids', payload)

    def test_export_csv_zip_contains_expected_files(self):
        raw = export_csv_zip_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
        self.assertIn('vocational_courses_catalog.csv', names)
        self.assertIn('vocational_reasoning_mappings.csv', names)
