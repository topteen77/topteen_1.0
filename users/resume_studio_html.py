"""
Resume studio (HTML prototype) template catalog — DB-backed with static fallback.

Each row maps to a renderer in static/resume-builder-prototype/app.js (RENDERERS).
"""

from __future__ import annotations

import json
from typing import Any

from django.utils.safestring import mark_safe

# Keys must exist in static/resume-builder-prototype/app.js RENDERERS.
ALLOWED_STUDIO_HTML_TEMPLATE_KEYS = frozenset(
    {
        "minimalist",
        "classic-sidebar",
        "colored-header",
        "modern-split",
        "professional-border",
        "bold-header",
        "tech-focus",
        "elegant-serif",
        "geometric",
        "high-contrast",
        "aurora",
        "magazine",
        "timeline",
        "executive",
        "studio",
        "nova",
        "ledger",
        "horizon",
        "folio",
        "vertex",
    }
)

# Shipped default when the table is empty (same ids as app.js DEFAULT_TEMPLATES).
DEFAULT_STUDIO_HTML_CATALOG: list[dict[str, str]] = [
    {"id": "minimalist", "name": "Minimalist", "category": "simple", "mock": "mock-minimalist"},
    {"id": "classic-sidebar", "name": "Classic Sidebar", "category": "professional", "mock": "mock-classic-sidebar"},
    {"id": "colored-header", "name": "Colored Header", "category": "modern", "mock": "mock-colored-header"},
    {"id": "modern-split", "name": "Modern Split", "category": "modern", "mock": "mock-modern-split"},
    {"id": "professional-border", "name": "Pro Border", "category": "professional", "mock": "mock-professional-border"},
    {"id": "bold-header", "name": "Bold Header", "category": "creative", "mock": "mock-bold-header"},
    {"id": "tech-focus", "name": "Tech Focus", "category": "professional", "mock": "mock-tech-focus"},
    {"id": "elegant-serif", "name": "Elegant Serif", "category": "simple", "mock": "mock-elegant-serif"},
    {"id": "geometric", "name": "Geometric", "category": "creative", "mock": "mock-geometric"},
    {"id": "high-contrast", "name": "High Contrast", "category": "modern", "mock": "mock-high-contrast"},
    {"id": "aurora", "name": "Aurora", "category": "creative", "mock": "mock-aurora"},
    {"id": "magazine", "name": "Magazine", "category": "creative", "mock": "mock-magazine"},
    {"id": "timeline", "name": "Timeline", "category": "modern", "mock": "mock-timeline"},
    {"id": "executive", "name": "Executive", "category": "professional", "mock": "mock-executive"},
    {"id": "studio", "name": "Studio", "category": "modern", "mock": "mock-studio"},
    {"id": "nova", "name": "Nova", "category": "creative", "mock": "mock-nova"},
    {"id": "ledger", "name": "Ledger", "category": "professional", "mock": "mock-ledger"},
    {"id": "horizon", "name": "Horizon", "category": "modern", "mock": "mock-horizon"},
    {"id": "folio", "name": "Folio", "category": "simple", "mock": "mock-folio"},
    {"id": "vertex", "name": "Vertex", "category": "creative", "mock": "mock-vertex"},
]

# Staff HTML preview (no UserResume required).
ADMIN_STUDIO_HTML_PREVIEW_SAMPLE: dict[str, Any] = {
    "fullName": "Preview Student",
    "headline": "Economics · Admissions resume",
    "email": "preview@example.com",
    "phone": "+91 90000 00000",
    "address": "New Delhi, India",
    "linkedin": "",
    "website": "",
    "summary": "Academic profile preview for admin. Quantitative strengths, leadership, and clear university goals.",
    "photo": "",
    "skills": [
        {"name": "Research & writing", "level": 4},
        {"name": "Data analysis (Excel, Stata)", "level": 4},
    ],
    "experience": [
        {
            "title": "Research intern",
            "company": "Example Institute",
            "location": "",
            "dates": "2024 — 2025",
            "bullets": ["Supported literature review and summary memos for policy briefs."],
        }
    ],
    "education": [
        {"degree": "Grade 12 — Science", "school": "Example Public School", "dates": "", "detail": "Strong academic record"}
    ],
    "certifications": [{"name": "MOOC: Behavioural Economics", "issuer": "Online", "date": "2024"}],
    "languages": [{"name": "English", "level": "Fluent"}, {"name": "Hindi", "level": "Native"}],
    "interests": "Debate, reading, cricket",
}


def _row_to_catalog_dict(row) -> dict[str, str]:
    tid = (row.template_key or "").strip()
    mock = (row.mock_class or "").strip() or f"mock-{tid}"
    cat = (row.category or "professional").strip().lower()
    return {
        "id": tid,
        "name": (row.name or tid).strip(),
        "category": cat,
        "mock": mock,
    }


def studio_html_template_catalog_rows() -> list[dict[str, str]]:
    from users.models import ResumeStudioHtmlTemplate

    qs = ResumeStudioHtmlTemplate.objects.filter(is_active=True).order_by("sort_order", "id")
    if not qs.exists():
        return [dict(x) for x in DEFAULT_STUDIO_HTML_CATALOG]
    return [_row_to_catalog_dict(r) for r in qs]


def studio_html_template_catalog_json() -> Any:
    rows = studio_html_template_catalog_rows()
    raw = json.dumps(rows, ensure_ascii=False, default=str).translate(
        str.maketrans({"<": "\\u003c", ">": "\\u003e"})
    )
    return mark_safe(raw)


def admin_studio_html_preview_initial_json() -> Any:
    raw = json.dumps(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE, ensure_ascii=False, default=str).translate(
        str.maketrans({"<": "\\u003c", ">": "\\u003e"})
    )
    return mark_safe(raw)
