from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from app.management.commands.generate_riasec_json import (
    load_best_colleges,
    make_fullname,
    normalize_stream_key,
    stream_label,
)

SHEET_NAMES = ("R", "I", "A", "S", "E", "C")


def _expl_column(columns) -> str:
    for col in columns:
        text = str(col)
        if "Alignment" in text or "Explanation" in text:
            return col
    raise ValueError("Could not find Personality/Career Alignment Explanation column")


def _parse_career_pathways(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [
        item.strip()
        for item in str(value).strip().rstrip(".").split(",")
        if item.strip()
    ]


def _build_entry(row, expl_col: str, best_colleges_map: dict[str, str]) -> dict:
    code = str(row["Code"]).strip().upper()
    stream1_raw = str(row["Recommended Stream 1"]).strip()
    stream2_raw = str(row["Recommended Stream 2"]).strip()
    summary = str(row[expl_col]).strip()
    careers = _parse_career_pathways(row["Career Pathways"])

    stream_keys: list[str] = []
    streams: dict[str, list[str]] = {}
    for stream_raw in (stream1_raw, stream2_raw):
        stream_key = normalize_stream_key(stream_raw)
        if stream_key in streams:
            continue
        stream_keys.append(stream_key)
        streams[stream_key] = [stream_label(stream_raw)]

    ordered_streams = {key: streams[key] for key in stream_keys if key in streams}
    ordered_stream_careers = {key: list(careers) for key in ordered_streams}

    return {
        "category": code,
        "fullname": make_fullname(code),
        "summary": summary,
        "fields": ", ".join(careers),
        "courses": careers,
        "best_colleges": best_colleges_map.get(code, ""),
        "streams": ordered_streams,
        "stream_careers": ordered_stream_careers,
        "career_pathways_mode": "combined",
    }


class Command(BaseCommand):
    help = "Import RIASEC.json from the Class 10 RIASEC Personality Excel workbook."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(
                Path.home() / "Desktop" / "RIASEC- Personality- 10.xlsx"
            ),
            help="Path to RIASEC Personality Excel file",
        )
        parser.add_argument(
            "--output",
            default=str(Path(settings.BASE_DIR) / "RIASEC.json"),
            help="Output JSON path (default: project root RIASEC.json)",
        )
        parser.add_argument(
            "--backup",
            default=str(Path(settings.BASE_DIR) / "RIASEC.json"),
            help="Existing RIASEC.json used to preserve best_colleges values",
        )

    def handle(self, *args, **options):
        source_path = Path(options["source"])
        output_path = Path(options["output"])
        backup_path = Path(options["backup"])

        if not source_path.exists():
            raise SystemExit(f"Excel file not found: {source_path}")

        best_colleges_map = load_best_colleges(backup_path)
        entries: list[dict] = []

        for sheet_name in SHEET_NAMES:
            df = pd.read_excel(source_path, sheet_name=sheet_name)
            expl_col = _expl_column(df.columns)
            for _, row in df.iterrows():
                if not str(row.get("Code", "")).strip():
                    continue
                entries.append(_build_entry(row, expl_col, best_colleges_map))

        entries.sort(key=lambda item: item["category"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(entries, handle, indent=4, ensure_ascii=False)

        colleges_count = sum(1 for entry in entries if entry.get("best_colleges"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(entries)} RIASEC entries -> {output_path} "
                f"(best_colleges preserved for {colleges_count} codes)"
            )
        )
