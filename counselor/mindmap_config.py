"""
Site-wide counselor mindmap display type from Core Configuration (DEFAULT_course_MINDMAP_TYPE).

Numeric strings map to counselor_mindmap_widget map_type. URL ?map_type= still overrides in the widget.
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
}


def get_counselor_mindmap_map_type() -> str:
    raw = (Configuration.get("DEFAULT_course_MINDMAP_TYPE", "7", editable=True) or "7").strip()
    return _NUM_TO_WIDGET_MAP_TYPE.get(raw, "tree")
