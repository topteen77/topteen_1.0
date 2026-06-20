"""
Import Class 10 aptitude combination profiles from Excel into JSON.

Source: aptitude reasoning combinations updated.xlsx (Sheets 1–7)
Output: app/data/class10_aptitude_combinations.json
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

ALL_CODES = frozenset({'CR', 'NR', 'VR', 'LR', 'LA', 'SR', 'MR'})


def parse_codes(code_str):
    s = str(code_str or '').strip()
    if not s or s == 'nan':
        return None
    parts = sorted(p.strip() for p in s.replace(' ', '').split('+') if p.strip())
    if not parts:
        return None
    return '+'.join(parts)


def split_pipe(text):
    s = str(text or '').strip()
    if not s or s == 'nan':
        return []
    return [x.strip() for x in s.split('|') if x.strip()]


def split_slash_subjects(text):
    s = str(text or '').strip()
    if not s or s == 'nan':
        return []
    return [x.strip() for x in s.split('/') if x.strip()]


def get_col(row, *names):
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and str(value).strip() not in ('', 'nan'):
                return value
    return ''


class Command(BaseCommand):
    help = 'Build class10_aptitude_combinations.json from the aptitude combinations Excel file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default=str(
                Path(settings.BASE_DIR).parent
                / 'aptitude reasoning combinations updated.xlsx'
            ),
            help='Path to aptitude combinations Excel workbook',
        )
        parser.add_argument(
            '--output',
            type=str,
            default=str(Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_aptitude_combinations.json'),
            help='Output JSON path',
        )

    def handle(self, *args, **options):
        import pandas as pd

        excel_path = Path(options['excel_file'])
        output_path = Path(options['output'])
        if not excel_path.is_file():
            self.stderr.write(self.style.ERROR(f'Excel file not found: {excel_path}'))
            return

        combinations = {}
        for sheet_idx in range(1, 8):
            header_row = 3 if sheet_idx == 7 else 2
            df = pd.read_excel(excel_path, sheet_name=f'Sheet{sheet_idx}', header=header_row)
            for _, row in df.iterrows():
                code_key = parse_codes(row.get('Code'))
                if not code_key:
                    continue
                combinations[code_key] = {
                    'code': code_key,
                    'section': sheet_idx,
                    'profile': str(get_col(row, 'Aptitude Profile') or '').strip(),
                    'strong_fit_stream': str(get_col(row, 'Strong Fit') or '').strip(),
                    'good_fit_stream': str(get_col(row, 'Good Fit') or '').strip(),
                    'strong_fit_careers': split_pipe(
                        get_col(row, 'Strong Fit  Career Pathways', 'Strong Fit Career Pathways')
                    ),
                    'good_fit_careers': split_pipe(get_col(row, 'Good Fit Career Pathways')),
                    'strong_fit_subjects': split_slash_subjects(
                        get_col(row, 'Strong Fit  Subject Combinations', 'Strong Fit Subject Combinations')
                    ),
                    'good_fit_subjects': split_slash_subjects(
                        get_col(row, 'Good Fit Subject Combinations')
                    ),
                }

        six_area_present_keys = {}
        for key in combinations:
            codes = set(key.split('+'))
            if len(codes) == 6:
                missing = next(iter(ALL_CODES - codes))
                six_area_present_keys[missing] = key

        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'version': 1,
            'source': excel_path.name,
            'combinations': combinations,
            'six_area_present_keys': six_area_present_keys,
        }
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {len(combinations)} combinations to {output_path}'
            )
        )
