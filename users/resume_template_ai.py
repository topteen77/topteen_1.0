"""
Google Font metadata for resume PDF/HTML rendering (legacy AI shell paths).
"""
from __future__ import annotations

from typing import Optional

# Curated Google Fonts for PDF (whitelist only).
GOOGLE_RESUME_FONT_CHOICES: tuple[dict[str, str], ...] = (
    {
        "id": "source_sans_3",
        "label": "Source Sans 3",
        "href": "https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'Source Sans 3', system-ui, sans-serif",
    },
    {
        "id": "inter",
        "label": "Inter",
        "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        "stack": "'Inter', system-ui, sans-serif",
    },
    {
        "id": "dm_sans",
        "label": "DM Sans",
        "href": "https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&display=swap",
        "stack": "'DM Sans', system-ui, sans-serif",
    },
    {
        "id": "open_sans",
        "label": "Open Sans",
        "href": "https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'Open Sans', system-ui, sans-serif",
    },
    {
        "id": "ibm_plex_sans",
        "label": "IBM Plex Sans",
        "href": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'IBM Plex Sans', system-ui, sans-serif",
    },
    {
        "id": "lora",
        "label": "Lora",
        "href": "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'Lora', Georgia, 'Times New Roman', serif",
    },
    {
        "id": "merriweather",
        "label": "Merriweather",
        "href": "https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,400;0,700;1,400&display=swap",
        "stack": "'Merriweather', Georgia, 'Times New Roman', serif",
    },
    {
        "id": "crimson_pro",
        "label": "Crimson Pro",
        "href": "https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'Crimson Pro', Georgia, 'Times New Roman', serif",
    },
    {
        "id": "playfair_display",
        "label": "Playfair Display",
        "href": "https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        "stack": "'Playfair Display', Georgia, 'Times New Roman', serif",
    },
    {
        "id": "outfit",
        "label": "Outfit",
        "href": "https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap",
        "stack": "'Outfit', system-ui, sans-serif",
    },
)

DEFAULT_GOOGLE_FONT_ID = "inter"
_GOOGLE_FONT_BY_ID = {f["id"]: f for f in GOOGLE_RESUME_FONT_CHOICES}


def normalize_google_font_id(raw: Optional[str]) -> str:
    s = (raw or "").strip().lower().replace("-", "_")
    if s in _GOOGLE_FONT_BY_ID:
        return s
    return DEFAULT_GOOGLE_FONT_ID


def google_font_context_for_template(row) -> dict[str, str]:
    """Link href + CSS stack for the dynamic AI shell (whitelist only)."""
    if not row:
        return {"ai_google_font_url": "", "ai_google_font_stack": ""}
    fid = normalize_google_font_id(getattr(row, "ai_google_font", None))
    meta = _GOOGLE_FONT_BY_ID[fid]
    return {
        "ai_google_font_url": meta["href"],
        "ai_google_font_stack": meta["stack"],
    }
