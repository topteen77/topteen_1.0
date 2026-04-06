"""
Site-wide counselor mindmap display type from Core Configuration (DEFAULT_course_MINDMAP_TYPE).

Numeric strings map to counselor_mindmap_widget map_type. URL ?map_type= still overrides in the widget.

Named values (e.g. "classic mindmap") select classic layouts from static/counselor/classic-mindmap/.
Value 9 / "classic vertical" = top-down; value 8 = horizontal (doc-md/mindmap style).
"""
from __future__ import annotations

from core.models import Configuration

_NUM_TO_WIDGET_MAP_TYPE: dict[str, str] = {
    "1": "tree",
    "2": "concept",
    "3": "radial",
    "4": "cluster",
    "5": "career_radial",
    "6": "radial",
    "7": "career_radial",
    "8": "classic",
    "9": "classic_vertical",
}


def _normalize_name_key(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_").replace("-", "_")


def get_counselor_mindmap_map_type() -> str:
    val = Configuration.get("DEFAULT_course_MINDMAP_TYPE", "9", editable=True)
    raw = (str(val).strip() if val is not None else "") or "9"
    name_key = _normalize_name_key(raw)
    if name_key in ("classic_mindmap", "classic", "horizontal_classic"):
        return "classic"
    if name_key in ("classic_vertical", "classic_vertical_mindmap", "vertical_classic", "classic_mindmap_vertical"):
        return "classic_vertical"
    mapped = _NUM_TO_WIDGET_MAP_TYPE.get(raw)
    if mapped:
        return mapped
    return "tree"
