"""Build a canonical unique stream → careers list from stream sorter guidance JSON."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

DEFAULT_SOURCE = Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_guidance.json'
DEFAULT_OUTPUT = Path(settings.BASE_DIR) / 'app' / 'data' / 'class10_stream_sorter_unique_streams.json'

STREAM_CODES = ('PCM', 'PCB', 'CWM', 'CWOM', 'HUM')


def _extract_stream_codes(text: str) -> frozenset[str]:
    if not text:
        return frozenset()
    upper = text.upper()
    found = {code for code in STREAM_CODES if code in upper}
    if 'COMMERCE WITH' in upper and 'WITHOUT' not in upper:
        found.add('CWM')
    if 'COMMERCE WITHOUT' in upper or ('COMMERCE' in upper and 'WITHOUT' in upper):
        found.add('CWOM')
    if 'HUMANITIES' in upper:
        found.add('HUM')
    if 'FINE ARTS' in upper:
        found.add('FINEARTS')
    return frozenset(found)


def _stream_group_key(stream_label: str) -> str:
    codes = _extract_stream_codes(stream_label)
    if codes:
        return '|'.join(sorted(codes))
    return stream_label.strip().lower()


def _dedupe_careers_preserve_order(careers: list[str]) -> list[str]:
    """Unique career names within one stream; exact text preserved (trim edges only)."""
    seen: set[str] = set()
    result: list[str] = []
    for name in careers:
        if not name:
            continue
        key = name.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(name.strip() if name == name.strip() else name)
    return result


def _dedupe_future_careers(all_careers: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in all_careers:
        if not name:
            continue
        key = name.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(name.strip() if name == name.strip() else name)
    return result


def build_unique_streams_payload(
    source_path: Path | None = None,
) -> dict:
    """
    Merge stream_wise_premium_careers and future_relevant_careers from all RIASEC files.

    - Streams are unique by stream identity (PCM, PCB, CWM, …).
    - Careers are unique within each stream only (same name may appear in other streams).
    - Future-relevant careers are unique globally by career name.
    """
    from app.stream_sorter_guidance import load_stream_sorter_guidance

    guidance = load_stream_sorter_guidance(
        str(source_path) if source_path else None,
    )
    if not guidance:
        guidance_path = source_path or DEFAULT_SOURCE
        if not guidance_path.exists():
            return {
                'version': 1,
                'error': f'Source not found: {guidance_path}',
                'stream_wise_premium_careers': [],
                'future_relevant_careers': [],
            }
        with guidance_path.open(encoding='utf-8') as handle:
            guidance = json.load(handle)

    stream_map: dict[str, dict] = {}
    future_accum: list[str] = []

    for file_data in (guidance.get('files') or {}).values():
        for group in file_data.get('stream_wise_premium_careers') or []:
            stream_label = (group.get('stream') or '').strip()
            if not stream_label:
                continue
            key = _stream_group_key(stream_label)
            careers = group.get('careers') or []
            if key not in stream_map:
                stream_map[key] = {
                    'stream': stream_label,
                    'careers': [],
                    '_seen': set(),
                }
            bucket = stream_map[key]
            for career in careers:
                ckey = (career or '').strip()
                if not ckey or ckey in bucket['_seen']:
                    continue
                bucket['_seen'].add(ckey)
                bucket['careers'].append(career if isinstance(career, str) else str(career))

        future_accum.extend(file_data.get('future_relevant_careers') or [])

    stream_order = ('PCM', 'PCB', 'CWM', 'CWOM', 'HUM', 'FINEARTS')

    def sort_key(item):
        codes = _extract_stream_codes(item['stream'])
        for code in stream_order:
            if code in codes:
                return stream_order.index(code)
        return len(stream_order)

    stream_wise = []
    for item in sorted(stream_map.values(), key=sort_key):
        stream_wise.append({
            'stream': item['stream'],
            'careers': item['careers'],
        })

    future_relevant = _dedupe_future_careers(future_accum)
    titles = guidance.get('section_titles') or {}

    total_careers = sum(len(s['careers']) for s in stream_wise)
    return {
        'version': 1,
        'generated_from': str(source_path or DEFAULT_SOURCE),
        'section_titles': {
            'stream_wise': titles.get('stream_wise', 'Stream-Wise Premium Career Options'),
            'future_relevant': titles.get(
                'future_relevant',
                'Most Future-Relevant Careers Across All Streams',
            ),
        },
        'stream_wise_premium_careers': stream_wise,
        'future_relevant_careers': future_relevant,
        'stats': {
            'unique_streams': len(stream_wise),
            'total_stream_career_entries': total_careers,
            'unique_future_relevant_careers': len(future_relevant),
            'source_riasec_files_merged': len(guidance.get('files') or {}),
        },
    }


def write_unique_streams_json(
    output_path: Path | None = None,
    source_path: Path | None = None,
) -> Path:
    output_path = output_path or DEFAULT_OUTPUT
    payload = build_unique_streams_payload(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return output_path
