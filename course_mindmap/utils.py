from __future__ import annotations

import re
from html import unescape


def strip_html(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", text)
    t = unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def html_to_markdown_bullets(html: str, *, max_items: int = 25) -> list[str]:
    """Extract h2/h3/li text from HTML for mindmap leaves."""
    if not html or not str(html).strip():
        return []
    items: list[str] = []
    for pattern in (
        r"<h2[^>]*>(.*?)</h2>",
        r"<h3[^>]*>(.*?)</h3>",
        r"<li[^>]*>(.*?)</li>",
    ):
        for m in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
            line = strip_html(m.group(1))
            if line and line not in items:
                items.append(line)
            if len(items) >= max_items:
                return items
    return items


def markdown_outline(root_title: str, children: list[str | tuple[str, list[str]]]) -> str:
    """
    Build Markmap markdown.
    children: list of str labels or (label, sub_bullets).
    """
    lines = [f"# {root_title.strip() or 'Untitled'}"]
    for child in children:
        if isinstance(child, str):
            label = child.strip()
            if label:
                lines.append(f"- {label}")
        else:
            label, subs = child
            label = (label or "").strip()
            if not label:
                continue
            lines.append(f"- {label}")
            for sub in subs or []:
                sub = (sub or "").strip()
                if sub:
                    lines.append(f"  - {sub}")
    return "\n".join(lines) + "\n"
