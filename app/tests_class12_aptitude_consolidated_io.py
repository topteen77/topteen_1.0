"""Tests for Class 12 aptitude consolidated report Excel validation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from app.class12_aptitude_consolidated_io import (
    DEFAULT_JSON_PATH,
    EXPECTED_ROW_COUNT,
    VALID_CODES,
    load_and_validate,
    load_json_payload,
    lookup_combination,
    normalize_combination_key,
    split_comma_list,
    split_semicolon_list,
    validate_rows,
)

DEFAULT_EXCEL = (
    Path(settings.BASE_DIR).parent
    / 'final CONSOLIDATED REPORT FOR 11TH-12TH.xlsx'
)


class NormalizeKeyTests(SimpleTestCase):
    def test_single_code(self):
        self.assertEqual(normalize_combination_key('CR'), 'CR')

    def test_combination_with_spaces(self):
        self.assertEqual(normalize_combination_key('AR + NR'), 'AR + NR')
        self.assertEqual(normalize_combination_key('NR+AR'), 'AR + NR')

    def test_trailing_space_on_key(self):
        self.assertEqual(
            normalize_combination_key('NR + LR + LVR + CR + MR + SR '),
            'CR + LR + LVR + MR + NR + SR',
        )


class SplitListTests(SimpleTestCase):
    def test_semicolon_clusters(self):
        raw = 'A; B; C'
        self.assertEqual(split_semicolon_list(raw), ['A', 'B', 'C'])

    def test_comma_pathways(self):
        raw = 'Role A, Role B, Role C'
        self.assertEqual(split_comma_list(raw), ['Role A', 'Role B', 'Role C'])


class ValidateRowsTests(SimpleTestCase):
    def _valid_row(self, key='CR', row_num=2):
        return {
            'row_num': row_num,
            'reasoning_combination_raw': key,
            'reasoning_combination': normalize_combination_key(key),
            'codes': normalize_combination_key(key).split(' + '),
            'aptitude_description': 'A' * 50,
            'interpretation_narrative': 'B' * 80,
            'career_clusters': ['Cluster A'],
            'career_pathways': ['Path A'],
            'degree_pathways': ['Degree A'],
        }

    def test_valid_single_row(self):
        rows = [self._valid_row(code, i + 2) for i, code in enumerate(sorted(VALID_CODES))]
        result = validate_rows(rows, expected_count=None)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_empty_description_fails(self):
        row = self._valid_row()
        row['aptitude_description'] = ''
        result = validate_rows([row], expected_count=None)
        self.assertFalse(result.ok)
        self.assertTrue(any('Aptitude Description' in e for e in result.errors))

    def test_duplicate_key_fails(self):
        rows = [self._valid_row('CR', 2), self._valid_row('CR', 3)]
        result = validate_rows(rows, expected_count=None)
        self.assertFalse(result.ok)
        self.assertTrue(any('duplicate' in e.lower() for e in result.errors))

    def test_invalid_code_fails(self):
        row = self._valid_row('XX')
        result = validate_rows([row], expected_count=None)
        self.assertFalse(result.ok)
        self.assertTrue(any('invalid code' in e.lower() for e in result.errors))


@unittest.skipUnless(DEFAULT_EXCEL.is_file(), 'Consolidated Excel file not present')
class ExcelIntegrationTests(SimpleTestCase):
    def test_excel_parses_127_rows(self):
        result = load_and_validate(DEFAULT_EXCEL)
        self.assertEqual(len(result.rows), EXPECTED_ROW_COUNT)

    def test_excel_all_single_codes_present(self):
        result = load_and_validate(DEFAULT_EXCEL)
        singles = {
            r['codes'][0]
            for r in result.rows
            if len(r['codes']) == 1
        }
        self.assertEqual(singles, VALID_CODES)

    def test_excel_validation_passes(self):
        result = load_and_validate(DEFAULT_EXCEL)
        self.assertTrue(result.ok, msg='\n'.join(result.errors))

    def test_no_duplicate_normalized_keys(self):
        result = load_and_validate(DEFAULT_EXCEL)
        keys = [r['reasoning_combination'] for r in result.rows]
        self.assertEqual(len(keys), len(set(keys)))


@unittest.skipUnless(DEFAULT_JSON_PATH.is_file(), 'Generated JSON not present')
class GeneratedJsonTests(SimpleTestCase):
    def test_json_has_127_combinations(self):
        payload = load_json_payload()
        self.assertEqual(payload['version'], 1)
        self.assertEqual(len(payload['combinations']), EXPECTED_ROW_COUNT)

    def test_json_lookup_cr_and_combo(self):
        cr = lookup_combination('CR')
        self.assertIsNotNone(cr)
        self.assertEqual(cr['codes'], ['CR'])
        self.assertTrue(cr['aptitude_description'])

        combo = lookup_combination('NR+AR')
        self.assertIsNotNone(combo)
        self.assertEqual(combo['reasoning_combination'], 'AR + NR')
        self.assertIn('<strong>', combo['interpretation_narrative'])
        self.assertIn('Abstract and Numerical Reasoning', combo['interpretation_narrative'])

    def test_json_all_rows_have_required_fields(self):
        payload = load_json_payload()
        for key, row in payload['combinations'].items():
            for field in (
                'aptitude_description',
                'interpretation_narrative',
                'career_clusters',
                'career_pathways',
                'degree_pathways',
            ):
                self.assertTrue(row.get(field), f'{key}: missing {field}')
