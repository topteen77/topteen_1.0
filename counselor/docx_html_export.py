"""
Convert counselor course .docx trees to HTML (used by export_course_mindmap_json).

Writes parallel layout: <out>/html/attachments/…, <out>/html/Quiz/…
Requires mammoth (Word → HTML).
"""
from __future__ import annotations

import html
from pathlib import Path


def _wrap_html5(title: str, body_fragment: str) -> str:
    safe_title = html.escape(title, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{safe_title}</title>
<style>
body {{ font-family: system-ui, "Segoe UI", Arial, sans-serif; max-width: 50rem; margin: 1.5rem auto; padding: 0 1rem 3rem; line-height: 1.55; color: #222; }}
p {{ margin: 0.85em 0; }}
h1, h2, h3, h4 {{ margin: 1.1em 0 0.5em; font-weight: 600; }}
ul, ol {{ margin: 0.75em 0; padding-left: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.95em; }}
td, th {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; vertical-align: top; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
{body_fragment}
</body>
</html>
"""


def export_docx_tree_to_html(
    content_root: Path,
    html_out_root: Path,
    *,
    subfolders: tuple[str, ...] = ("attachments", "Quiz"),
) -> tuple[int, list[str]]:
    """
    Convert each .docx under content_root/<subfolder>/ to html_out_root/<subfolder>/…/*.html.

    Returns (count_written, error_messages).
    """
    try:
        import mammoth
    except ImportError as e:  # pragma: no cover
        raise ImportError("Install mammoth for HTML export: pip install mammoth") from e

    errors: list[str] = []
    count = 0
    html_out_root.mkdir(parents=True, exist_ok=True)

    for folder in subfolders:
        src_root = content_root / folder
        if not src_root.is_dir():
            continue
        for docx_path in sorted(src_root.rglob("*.docx")):
            name = docx_path.name
            if name.startswith("~$") or name.startswith("."):
                continue
            try:
                with open(docx_path, "rb") as f:
                    result = mammoth.convert_to_html(f)
                body = result.value
                title = docx_path.stem
                full = _wrap_html5(title, body)
                rel = docx_path.relative_to(src_root)
                dest = html_out_root / folder / rel.with_suffix(".html")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(full, encoding="utf-8")
                count += 1
            except Exception as ex:
                errors.append(f"{docx_path}: {ex}")

    return count, errors
