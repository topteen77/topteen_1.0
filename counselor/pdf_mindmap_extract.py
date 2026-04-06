"""
Extract plain text from counselor Part PDFs for mindmap export (export_course_mindmap_json).

Uses pypdf when available; otherwise extraction returns empty string.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from counselor.models import Part

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[misc, assignment]


def _fetch_url_bytes(url: str, timeout: int = 45) -> bytes | None:
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TopTeen-counselor-mindmap-export/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def resolve_part_pdf_bytes(part: "Part", *, base_dir: Path | None = None) -> bytes | None:
    """
    Load PDF bytes for a Part: https URL, or local filesystem path (relative to base_dir / cwd).
    """
    raw = (getattr(part, "pdf_url", None) or "").strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://")):
        return _fetch_url_bytes(raw)
    path = Path(raw)
    if not path.is_absolute():
        roots: list[Path] = []
        if base_dir:
            roots.append(base_dir)
        try:
            from django.conf import settings

            roots.append(Path(settings.BASE_DIR))
        except Exception:
            pass
        for root in roots:
            cand = (root / path).resolve()
            if cand.is_file() and cand.suffix.lower() == ".pdf":
                try:
                    return cand.read_bytes()
                except OSError:
                    return None
    elif path.is_file() and path.suffix.lower() == ".pdf":
        try:
            return path.read_bytes()
        except OSError:
            return None
    return None


def extract_text_from_pdf_bytes(
    data: bytes,
    *,
    max_pages: int = 80,
    max_chars: int = 100_000,
) -> str:
    if not data or PdfReader is None:
        return ""
    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
    except Exception:
        return ""
    parts: list[str] = []
    n = min(len(reader.pages), max_pages)
    for i in range(n):
        try:
            t = reader.pages[i].extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if t:
            parts.append(t)
        if sum(len(p) for p in parts) >= max_chars:
            break
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars]
    return re.sub(r"\s+", " ", text).strip()


def text_to_outline_bullets(text: str | None, *, max_items: int = 10, max_len: int = 140) -> list[str]:
    """Turn prose into short lines for mindmap leaves (sentence-split, length cap)."""
    if not text:
        return []
    t = re.sub(r"\s+", " ", str(text).strip())
    if not t:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", t)
    out: list[str] = []
    for c in chunks:
        c = c.strip()
        if len(c) < 12:
            continue
        if len(c) > max_len:
            c = c[: max_len - 1] + "…"
        out.append(c)
        if len(out) >= max_items:
            break
    return out
