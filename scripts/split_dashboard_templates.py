#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "templates" / "template20"

BLOCK_START = re.compile(r"\{%\s*block\s+(\w+)\s*%\}")
BLOCK_END = re.compile(r"\{%\s*endblock(?:\s+[^%]+)?\s*%\}")

SPLITS = [
    {
        "rel": "institute/institute_dashboard.html",
        "marker": "{# Disable chatbot for institute dashboard #}",
        "assets": "institute/institute_dashboard_assets.html",
        "body": "institute/institute_dashboard_body.html",
    },
    {
        "rel": "institute/institute_group_dashboard.html",
        "marker": "{# Disable chatbot for institute group admin #}",
        "assets": "institute/institute_group_dashboard_assets.html",
        "body": "institute/institute_group_dashboard_body.html",
    },
    {
        "rel": "institute/marketing_group_dashboard.html",
        "marker": "{# Disable chatbot for marketing group dashboard #}",
        "assets": "institute/marketing_group_dashboard_assets.html",
        "body": "institute/marketing_group_dashboard_body.html",
    },
    {
        "rel": "counselor/counselor_dashboard.html",
        "marker": "{# Disable chatbot for counselor dashboard #}",
        "assets": "counselor/counselor_dashboard_assets.html",
        "body": "counselor/counselor_dashboard_body.html",
    },
]

def find_block_range(full: str, block_name: str) -> tuple[int, int]:
    m_open = re.search(
        r"\{%\s*block\s+" + re.escape(block_name) + r"\s*%\}",
        full,
    )
    if not m_open:
        raise ValueError(f"missing block {block_name}")
    start_open = m_open.end()

    i = start_open
    depth = 1
    end_close: int | None = None
    while i < len(full):
        ms = BLOCK_START.search(full, i)
        me = BLOCK_END.search(full, i)
        if me is None:
            raise ValueError(f"unclosed block {block_name}")
        if ms and ms.start() < me.start():
            depth += 1
            i = ms.end()
            continue
        depth -= 1
        if depth == 0:
            end_close = me.end()
            break
        i = me.end()

    if end_close is None:
        raise ValueError(f"unclosed block {block_name}")

    return m_open.start(), end_close


def split_one(cfg: dict) -> None:
    rel = cfg["rel"]
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines(True)

    add_start, add_end = find_block_range(text, "additionalhead")
    add_block = text[add_start:add_end]

    content_start, content_end = find_block_range(text, "content")
    if add_end > content_start:
        raise SystemExit(f"additionalhead overlaps content in {rel}")

    marker = cfg["marker"]
    if marker not in text:
        raise SystemExit(f"marker not found in {rel}: {marker}")
    marker_idx = text.index(marker)
    if marker_idx < content_end:
        raise SystemExit(f"marker appears before end of content block in {rel}")

    m_open = re.search(r"\{%\s*block\s+content\s*%\}", text[content_start:content_end])
    if not m_open:
        raise SystemExit(f"could not locate content open tag inside content range in {rel}")
    content_inner_open_abs = content_start + m_open.end()

    # Find the last {% endblock %} inside the content block range (should be the closing tag)
    m_close = None
    for m in BLOCK_END.finditer(text, content_start, content_end):
        m_close = m
    if not m_close:
        raise SystemExit(f"could not find closing endblock for content in {rel}")
    inner_body = text[content_inner_open_abs : m_close.start()].rstrip("\n") + "\n"

    tail = text[m_close.end() :]

    # assets inner: strip outer {% block additionalhead %} ... {% endblock %}
    m_inner_open = re.search(r"\{%\s*block\s+additionalhead\s*%\}\s*\n?", add_block)
    if not m_inner_open:
        raise SystemExit(f"additionalhead open missing in {rel}")
    inner_rest = add_block[m_inner_open.end() :]
    closes = list(BLOCK_END.finditer(inner_rest))
    if not closes:
        raise SystemExit(f"additionalhead has no endblock in {rel}")
    last = closes[-1]
    assets_inner = inner_rest[: last.start()].rstrip("\n") + "\n"

    alines = assets_inner.splitlines(True)
    if alines and alines[0].strip() == "{{ super() }}":
        alines = alines[1:]
        if alines and alines[0].strip() == "":
            alines = alines[1:]
    assets_inner = "".join(alines)

    (ROOT / cfg["assets"]).write_text(assets_inner, encoding="utf-8")
    (ROOT / cfg["body"]).write_text(inner_body, encoding="utf-8")

    include_assets = f"{{% include 'template20/{cfg['assets']}' %}}\n"
    include_body = f"{{% include 'template20/{cfg['body']}' %}}\n"

    add_open_line = text.count("\n", 0, add_start)
    add_close_line = text.count("\n", 0, add_end - 1)

    content_open_line = text.count("\n", 0, content_start)
    content_close_line = text.count("\n", 0, content_end - 1)

    rebuilt: list[str] = []
    rebuilt.extend(lines[:add_open_line])
    rebuilt.append(lines[add_open_line])  # {% block additionalhead %}
    rebuilt.append("{{ super() }}\n")
    rebuilt.append(include_assets)
    rebuilt.append("{% endblock %}\n")
    rebuilt.extend(lines[add_close_line + 1 : content_open_line + 1])  # through {% block content %} line
    rebuilt.append(include_body)
    rebuilt.append(lines[content_close_line])  # {% endblock %} that closed content
    rebuilt.append("\n")
    rebuilt.extend(lines[content_close_line + 1 :])  # tail (chatbot disables, additionaljs, etc.)

    p.write_text("".join(rebuilt), encoding="utf-8")


def main() -> None:
    for cfg in SPLITS:
        split_one(cfg)
        print("split OK:", cfg["rel"])


if __name__ == "__main__":
    main()
