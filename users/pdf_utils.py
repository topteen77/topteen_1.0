"""HTML → PDF helpers with wkhtmltopdf (pdfkit) or WeasyPrint fallback."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_WKHTMLTOPDF_CANDIDATES = (
    r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
    r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
)


def resolve_wkhtmltopdf_path() -> str | None:
    """Return an existing wkhtmltopdf binary path, or None."""
    candidates: list[str] = []
    for src in (
        os.environ.get("WKHTMLTOPDF_PATH"),
        getattr(settings, "WKHTMLTOPDF_PATH", None),
    ):
        if src and str(src).strip():
            candidates.append(str(src).strip())
    which = shutil.which("wkhtmltopdf")
    if which:
        candidates.append(which)
    candidates.extend(_WKHTMLTOPDF_CANDIDATES)
    seen: set[str] = set()
    for raw in candidates:
        path = str(Path(raw))
        if path in seen:
            continue
        seen.add(path)
        if Path(path).is_file():
            return path
    return None


def html_to_pdf_bytes(
    html: str,
    *,
    options: dict | None = None,
    base_url: str | None = None,
) -> bytes:
    """
    Render HTML to PDF bytes.

    Uses pdfkit/wkhtmltopdf when available; otherwise WeasyPrint (already in requirements).
    """
    wk_path = resolve_wkhtmltopdf_path()
    opts = options or {}
    if wk_path:
        import pdfkit

        config = pdfkit.configuration(wkhtmltopdf=wk_path)
        return pdfkit.from_string(html, False, options=opts, configuration=config)

    logger.info("wkhtmltopdf not found; using WeasyPrint for PDF generation")
    import weasyprint

    url = base_url or getattr(settings, "SITE_BASE_URL", None) or "http://localhost/"
    return weasyprint.HTML(string=html, base_url=url).write_pdf()
