from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from docx import Document

RIASEC_NAMES = {
    "R": "Realistic",
    "I": "Investigative",
    "A": "Artistic",
    "S": "Social",
    "E": "Enterprising",
    "C": "Conventional",
}

DOCX_FILES = [
    "Realistic.docx",
    "Investigative.docx",
    "Enterprising.docx",
    "Conventional.docx",
    "Artistic.docx",
    "social.docx",
]

STREAM_LABELS = {
    "pcm": "Physics Chemistry Mathematics",
    "pcb": "Physics Chemistry Biology",
    "cwm": "Commerce With Mathematics",
    "commerce with maths": "Commerce With Mathematics",
    "commerce with math": "Commerce With Mathematics",
    "commerce with mathematics": "Commerce With Mathematics",
    "cwom": "Commerce Without Mathematics",
    "commerce without maths": "Commerce Without Mathematics",
    "commerce without math": "Commerce Without Mathematics",
    "hum": "Humanities",
    "humanities": "Humanities",
    "humanities / arts": "Humanities",
    "humanities with arts": "Humanities with Arts",
    "humanities / commerce": "Humanities / Commerce",
    "fine arts / design": "Fine Arts / Design",
    "fine arts / humanities": "Fine Arts / Humanities",
    "science": "Science",
    "pcm / pcb": "Physics Chemistry Mathematics / Physics Chemistry Biology",
    "pcb / pcm": "Physics Chemistry Biology / Physics Chemistry Mathematics",
    "pcm/pcb": "Physics Chemistry Mathematics / Physics Chemistry Biology",
    "pcb/pcm": "Physics Chemistry Biology / Physics Chemistry Mathematics",
}


def normalize_stream_key(stream_text: str) -> str:
    text = stream_text.strip()
    lower = re.sub(r"\s*\([^)]*\)", "", text).strip().lower()
    lower = re.sub(r"\s+", " ", lower)
    mapping = {
        "pcm": "PCM",
        "pcb": "PCB",
        "cwm": "CWM",
        "commerce with maths": "CWM",
        "commerce with math": "CWM",
        "cwom": "CWOM",
        "commerce without maths": "CWOM",
        "commerce without math": "CWOM",
        "hum": "HUM",
        "humanities": "HUM",
        "humanities / arts": "HUM",
        "humanities with arts": "HUM",
        "fine arts / design": "Fine Arts / Design",
        "fine arts / humanities": "Fine Arts / Design",
        "pcm / pcb": "PCM / PCB",
        "pcb / pcm": "PCB / PCM",
        "pcm/pcb": "PCM / PCB",
        "pcb/pcm": "PCB / PCM",
        "humanities / commerce": "Humanities / Commerce",
    }
    if lower in mapping:
        return mapping[lower]
    cleaned = re.sub(r"\s*\([^)]*\)", "", text).strip()
    return cleaned if cleaned else text


def stream_label(stream_raw: str) -> str:
    text = stream_raw.strip()
    if "(Set 2)" in text:
        base = text.replace("(Set 2)", "").strip()
        return f"{stream_label(base)} (Set 2)"
    lower = re.sub(r"\s*\([^)]*\)", "", text).strip().lower()
    lower = re.sub(r"\s+", " ", lower)
    if lower in STREAM_LABELS:
        return STREAM_LABELS[lower]
    key = normalize_stream_key(text)
    if key.lower() in STREAM_LABELS:
        return STREAM_LABELS[key.lower()]
    if "(" in text and ")" in text:
        inner = re.search(r"\(([^)]+)\)", text)
        if inner:
            inner_key = inner.group(1).strip().lower()
            if inner_key in STREAM_LABELS:
                return STREAM_LABELS[inner_key]
    return key


def make_fullname(code: str) -> str:
    names = [RIASEC_NAMES[c] for c in code.upper()]
    return f"{code.upper()} ({', '.join(names)})"


def parse_career_segments(career_text: str) -> list[tuple[str, list[str]]]:
    segments: list[tuple[str, list[str]]] = []
    if not career_text:
        return segments

    marker_re = re.compile(
        r"([A-Za-z/][^:\n]{0,80}?)\s+Careers(?:\s*\(([^)]*)\))?:\s*",
        re.IGNORECASE,
    )
    matches = list(marker_re.finditer(career_text.strip()))
    for i, match in enumerate(matches):
        label = match.group(1).strip()
        set_tag = match.group(2)
        if set_tag:
            label = f"{label} ({set_tag.strip()})"
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(career_text)
        careers_raw = career_text[start:end].strip().rstrip(".")
        careers = [item.strip() for item in careers_raw.split(",") if item.strip()]
        segments.append((label, careers))
    return segments


def parse_flat_career_pathways(career_text: str) -> list[str]:
    """Parse comma-separated Career Pathways column (new docx format)."""
    if not career_text:
        return []
    return [item.strip() for item in career_text.strip().rstrip(".").split(",") if item.strip()]


def label_to_key(label: str) -> str:
    label = label.strip()
    base_label = re.sub(r"\s*\(Set\s*\d+\)\s*$", "", label, flags=re.I).strip()
    replacements = {
        "PCM/PCB": "PCM / PCB",
        "PCB/PCM": "PCB / PCM",
    }
    upper = base_label.upper().replace(" ", "")
    for source, target in replacements.items():
        if upper == source.replace(" ", ""):
            return target
    return normalize_stream_key(base_label)


def assign_stream_careers(stream1_raw: str, stream2_raw: str, segments: list[tuple[str, list[str]]]) -> dict[str, list[str]]:
    s1_key = normalize_stream_key(stream1_raw)
    s2_key = normalize_stream_key(stream2_raw)
    result: dict[str, list[str]] = {s1_key: [], s2_key: []}

    if not segments:
        return result

    if s1_key == s2_key:
        for index, (_label, careers) in enumerate(segments):
            key = s1_key if index == 0 else f"{s2_key} (Set 2)"
            result[key] = careers
        return result

    used: set[int] = set()
    for stream_raw, stream_key in ((stream1_raw, s1_key), (stream2_raw, s2_key)):
        matched = False
        for index, (label, careers) in enumerate(segments):
            if index in used:
                continue
            label_key = label_to_key(label)
            if (
                label_key == stream_key
                or label_key.replace(" ", "").lower() == stream_key.replace(" ", "").lower()
                or stream_key.split()[0].lower() in label_key.lower()
                or label_key.split()[0].lower() in stream_key.lower()
            ):
                result[stream_key] = careers
                used.add(index)
                matched = True
                break
        if not matched:
            for index, (_label, careers) in enumerate(segments):
                if index not in used:
                    result[stream_key] = careers
                    used.add(index)
                    break

    return result


def load_best_colleges(backup_path: Path) -> dict[str, str]:
    if not backup_path.exists():
        return {}
    with backup_path.open(encoding="utf-8") as handle:
        entries = json.load(handle)
    return {
        entry["category"].upper(): entry.get("best_colleges") or ""
        for entry in entries
        if entry.get("category")
    }


class Command(BaseCommand):
    help = (
        "Generate RIASEC.json from source .docx files. "
        "Keeps legacy streams format and adds stream_careers for per-stream job titles."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(Path(settings.BASE_DIR).parent / "RIASEC"),
            help="Directory containing the six RIASEC .docx files",
        )
        parser.add_argument(
            "--output",
            default=str(Path(settings.BASE_DIR) / "RIASEC.json"),
            help="Output JSON path (default: project root RIASEC.json)",
        )
        parser.add_argument(
            "--backup",
            default=str(Path(settings.BASE_DIR) / "RIASEC-backup.json"),
            help="Backup JSON path used to preserve best_colleges values",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source"])
        output_path = Path(options["output"])
        best_colleges_map = load_best_colleges(Path(options["backup"]))
        entries: list[dict] = []

        for filename in DOCX_FILES:
            docx_path = source_dir / filename
            if not docx_path.exists():
                raise SystemExit(f"Missing source file: {docx_path}")

            doc = Document(str(docx_path))
            table = doc.tables[0]
            for row in table.rows[1:]:
                cells = [cell.text.strip() for cell in row.cells]
                if not cells[0]:
                    continue

                code = cells[0].upper()
                stream1_raw = cells[1]
                stream2_raw = cells[2]
                summary = cells[3]
                career_text = cells[4]

                segments = parse_career_segments(career_text)
                stream_keys: list[str] = []
                streams: dict[str, list[str]] = {}
                for stream_raw in (stream1_raw, stream2_raw):
                    stream_key = normalize_stream_key(stream_raw)
                    if stream_key in streams:
                        continue
                    stream_keys.append(stream_key)
                    streams[stream_key] = [stream_label(stream_key if "(Set 2)" in stream_key else stream_raw)]

                if segments:
                    stream_careers = assign_stream_careers(stream1_raw, stream2_raw, segments)
                    for extra_key in stream_careers:
                        if extra_key not in streams:
                            stream_keys.append(extra_key)
                            streams[extra_key] = [stream_label(extra_key)]
                    ordered_streams = {key: streams[key] for key in stream_keys if key in streams}
                    ordered_stream_careers = {
                        key: stream_careers.get(key, [])
                        for key in ordered_streams
                    }
                    all_careers: list[str] = []
                    for careers in ordered_stream_careers.values():
                        all_careers.extend(careers)
                else:
                    flat_careers = parse_flat_career_pathways(career_text)
                    ordered_streams = {key: streams[key] for key in stream_keys if key in streams}
                    ordered_stream_careers = {
                        key: list(flat_careers) for key in ordered_streams
                    }
                    all_careers = list(flat_careers)
                    career_pathways_mode = "combined"
                if segments:
                    career_pathways_mode = "individual"

                entries.append(
                    {
                        "category": code,
                        "fullname": make_fullname(code),
                        "summary": summary,
                        "fields": ", ".join(all_careers),
                        "courses": all_careers,
                        "best_colleges": best_colleges_map.get(code, ""),
                        "streams": ordered_streams,
                        "stream_careers": ordered_stream_careers,
                        "career_pathways_mode": career_pathways_mode,
                    }
                )

        entries.sort(key=lambda item: item["category"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(entries, handle, indent=4, ensure_ascii=False)

        colleges_count = sum(1 for entry in entries if entry.get("best_colleges"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {len(entries)} RIASEC entries -> {output_path} "
                f"(best_colleges preserved for {colleges_count} codes)"
            )
        )
