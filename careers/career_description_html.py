"""
Shared helpers for career description HTML: conclusion paragraph and bold-line → H2 conversion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    BeautifulSoup = None  # type: ignore
    NavigableString = None  # type: ignore
    Tag = None  # type: ignore

CONCLUSION_WRAPPER_CLASS = "career-description-conclusion"

# Bold-only sub-labels under sections like Entrance Tests Required (not real H2 sections).
# Matches: India:, International:, International (for …):
_SKIP_BOLD_HEADING_RE = re.compile(
    r"^(?:india|international)(?:\s*\([^)]+\))?\s*:?\s*$",
    re.IGNORECASE,
)

_LIST_LIKE_PREFIX_RE = re.compile(
    r"^\s*(?:\d+[\.\)]|[a-z][\.\)]|[-•*])\s+",
    re.IGNORECASE,
)

# e.g. "Entrance Tests RequiredIndia:" -> H2 + bold "India:"
_GLUED_REQUIRED_REGION_RE = re.compile(
    r"^(.+?\bRequired)\s*(India|International)\s*:?\s*$",
    re.IGNORECASE,
)


@dataclass
class CareerHtmlChange:
    """One before/after transformation for management command output."""

    kind: str
    before_display: str
    after_display: str

    def format_block(self, indent: str = "    ", *, title: str = "") -> str:
        header = f"{indent}{title}" if title else ""
        lines = []
        if header:
            lines.append(header)
        lines.extend([
            f"{indent}  existing:",
            f"{indent}    {self.before_display}",
            f"{indent}  Into:",
        ])
        for line in self.after_display.splitlines():
            lines.append(f"{indent}    {line}")
        return "\n".join(lines)


def format_career_html_changes(changes: List[CareerHtmlChange], indent: str = "    ") -> str:
    return "\n\n".join(c.format_block(indent=indent) for c in changes)


def _bold_paragraph_html(text: str) -> str:
    return f"<p><strong>{text}</strong></p>"


def preview_change_for_bold_candidate(candidate: BoldHeadingCandidate) -> CareerHtmlChange:
    """Dry-run preview: what the line is now and what would happen."""
    before = candidate.html_snippet.strip()
    if not before.startswith("<"):
        before = _bold_paragraph_html(candidate.text)

    if candidate.skipped:
        reason = candidate.skip_reason or "skipped"
        after = (
            f"(no change — stays bold paragraph, NOT converted to H2; {reason})\n"
            f"{_bold_paragraph_html(candidate.text)}"
        )
        kind = "bold_skip"
    else:
        after = f"<h2>{candidate.text}</h2>"
        kind = "bold_to_h2"

    return CareerHtmlChange(
        kind=kind,
        before_display=before,
        after_display=after,
    )


def format_bold_candidates_preview(
    candidates: List[BoldHeadingCandidate],
    *,
    glue_changes: Optional[List[CareerHtmlChange]] = None,
    indent: str = "    ",
) -> str:
    """Full per-career dry-run report with existing / Into for every bold line."""
    blocks: List[str] = []
    if glue_changes:
        blocks.append(f"{indent}Glued Entrance Tests Required + region label:")
        blocks.append(format_career_html_changes(glue_changes, indent=indent))
    for c in candidates:
        preview = preview_change_for_bold_candidate(c)
        label = "convert to H2" if c.convertible else f"skip ({c.skip_reason})"
        blocks.append(
            preview.format_block(indent=indent, title=f"Line [{c.index}] — {label}:")
        )
    return "\n\n".join(blocks)


@dataclass
class BoldHeadingCandidate:
    """A <p> whose visible text is entirely bold (strong/b)."""

    index: int
    text: str
    html_snippet: str
    skipped: bool
    skip_reason: str = ""

    @property
    def convertible(self) -> bool:
        return not self.skipped


def _normalize_visible_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def should_skip_bold_heading(text: str) -> Tuple[bool, str]:
    """Return (skip, reason) for bold-only lines that must not become H2."""
    t = _normalize_visible_text(text)
    if not t:
        return True, "empty"
    if len(t) < 3:
        return True, "too short"
    if len(t) > 200:
        return True, "too long"
    if _SKIP_BOLD_HEADING_RE.match(t):
        return True, "india/international sub-label"
    if _LIST_LIKE_PREFIX_RE.match(t):
        return True, "list-like prefix"
    # Subsection labels under an H2 panel (e.g. Core Subjects:, Technical Skills:, Pros:)
    if t.endswith(":"):
        return True, "subsection label (ends with colon)"
    return False, ""


def _match_glued_required_region(text: str) -> Optional[re.Match[str]]:
    t = _normalize_visible_text(text)
    if not t:
        return None
    return _GLUED_REQUIRED_REGION_RE.match(t)


def _replace_tag_with_h2_and_region_label(tag, soup, heading_text: str, label_text: str) -> None:
    """Replace h2 or p with <h2>heading</h2><p><strong>label</strong></p>."""
    h2_tag = soup.new_tag("h2")
    h2_tag.string = heading_text

    p_tag = soup.new_tag("p")
    strong = soup.new_tag("strong")
    strong.string = label_text if label_text.endswith(":") else f"{label_text}:"
    p_tag.append(strong)

    tag.replace_with(h2_tag)
    h2_tag.insert_after(p_tag)


def _glue_split_after_display(heading: str, region_label: str) -> str:
    return f"<h2>{heading}</h2>\n<p><strong>{region_label}</strong></p>"


def split_glued_required_region_labels(
    html_content: str,
) -> Tuple[str, List[CareerHtmlChange]]:
    """
    Fix glued headings like "Entrance Tests RequiredIndia:" into:
      <h2>Entrance Tests Required</h2>
      <p><strong>India:</strong></p>
    """
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    changes: List[CareerHtmlChange] = []

    for h2 in list(soup.find_all("h2")):
        m = _match_glued_required_region(h2.get_text())
        if not m:
            continue
        original = m.group(0)
        heading, region = m.group(1).strip(), m.group(2).strip()
        label = f"{region}:"
        changes.append(
            CareerHtmlChange(
                kind="glue_split",
                before_display=original,
                after_display=_glue_split_after_display(heading, label),
            )
        )
        _replace_tag_with_h2_and_region_label(h2, soup, heading, label)

    for p in list(soup.find_all("p")):
        strong = p.find("strong") or p.find("b")
        if not strong:
            continue
        p_text = _normalize_visible_text(p.get_text())
        emph_text = _normalize_visible_text(strong.get_text())
        if p_text != emph_text:
            continue
        m = _match_glued_required_region(emph_text)
        if not m:
            continue
        original = m.group(0)
        heading, region = m.group(1).strip(), m.group(2).strip()
        label = f"{region}:"
        changes.append(
            CareerHtmlChange(
                kind="glue_split",
                before_display=original,
                after_display=_glue_split_after_display(heading, label),
            )
        )
        _replace_tag_with_h2_and_region_label(p, soup, heading, label)

    return str(soup), changes


def _tag_is_completely_blank(tag) -> bool:
    """True for empty <p>, blank headings, or spacer <div> with no visible text."""
    if not tag or not getattr(tag, "name", None):
        return False
    if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return not _normalize_visible_text(tag.get_text())
    if tag.name == "p":
        text = _normalize_visible_text(tag.get_text())
        if text:
            return False
        if tag.find(["img", "table", "ul", "ol", "iframe", "video", "svg"]):
            return False
        return True
    if tag.name == "div":
        if tag.find_parent("div", class_=CONCLUSION_WRAPPER_CLASS):
            return False
        if tag.get("class") and CONCLUSION_WRAPPER_CLASS in tag.get("class", []):
            return False
        if tag.find(["table", "ul", "ol", "h1", "h2", "h3", "h4", "img"]):
            return False
        text = _normalize_visible_text(tag.get_text())
        if text:
            return False
        element_children = [
            c for c in tag.children if getattr(c, "name", None)
        ]
        if not element_children:
            return True
        return all(c.name == "br" for c in element_children)
    return False


def audit_blank_lines(html_content: str) -> dict:
    """
    Count blank-like tags in description HTML (for manual verification vs dry-run).
    Returns counts keyed by tag kind, e.g. empty_p, empty_h2.
    """
    counts: dict = {
        "empty_p": 0,
        "empty_heading": 0,
        "empty_div": 0,
        "total_removable": 0,
    }
    if not html_content or not BeautifulSoup:
        return counts

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return counts

    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
        if not _tag_is_completely_blank(tag):
            continue
        counts["total_removable"] += 1
        if tag.name == "p":
            counts["empty_p"] += 1
        elif tag.name == "div":
            counts["empty_div"] += 1
        else:
            counts["empty_heading"] += 1
    return counts


def _blank_tag_location_hint(tag) -> str:
    """Human-readable position for empty spacer tags (admin verification)."""
    prev = tag.find_previous_sibling()
    nxt = tag.find_next_sibling()

    def _heading_label(node) -> str:
        if not node or not getattr(node, "name", None):
            return ""
        if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = _normalize_visible_text(node.get_text())
            return t[:60] if t else "(empty heading)"
        return ""

    if prev is None:
        return "at start of description (blank line before first text)"
    if nxt is None:
        return "at end of description"
    prev_h = _heading_label(prev)
    next_h = _heading_label(nxt)
    if prev_h:
        return f"after section heading «{prev_h}»"
    if next_h:
        return f"before section heading «{next_h}»"
    return "between content blocks"


def remove_completely_blank_lines(html_content: str) -> Tuple[str, List[str]]:
    """Remove empty <p>, blank headings (h1–h6), and blank spacer <div>s from career HTML."""
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    changes: List[str] = []
    for tag in list(soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"])):
        if not _tag_is_completely_blank(tag):
            continue
        preview = str(tag)[:80]
        hint = _blank_tag_location_hint(tag)
        changes.append(f"removed empty <{tag.name}> ({hint}): {preview!r}")
        tag.decompose()

    return str(soup), changes


def find_bold_heading_candidates(html_content: str) -> List[BoldHeadingCandidate]:
    """
    Find <p> elements whose text is entirely a single <strong> or <b> (heading-like).
    """
    if not html_content or not BeautifulSoup:
        return []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return []

    candidates: List[BoldHeadingCandidate] = []
    idx = 0

    for p in soup.find_all("p"):
        strong = p.find("strong")
        bold = p.find("b")
        emphasis = strong or bold
        if not emphasis:
            continue

        p_text = _normalize_visible_text(p.get_text())
        emph_text = _normalize_visible_text(emphasis.get_text())
        if not p_text or p_text != emph_text:
            continue

        skipped, reason = should_skip_bold_heading(emph_text)
        snippet = str(p)[:120] + ("..." if len(str(p)) > 120 else "")
        candidates.append(
            BoldHeadingCandidate(
                index=idx,
                text=emph_text,
                html_snippet=snippet,
                skipped=skipped,
                skip_reason=reason,
            )
        )
        idx += 1

    return candidates


def convert_bold_candidates_to_h2(
    html_content: str,
    *,
    only_indices: Optional[set[int]] = None,
) -> Tuple[str, List[CareerHtmlChange]]:
    """
    Convert selected bold-only <p> tags to <h2>. If only_indices is None, convert all non-skipped.
    Returns (new_html, change_log).
    """
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    changes: List[CareerHtmlChange] = []
    candidate_index = 0

    for p in list(soup.find_all("p")):
        strong = p.find("strong")
        bold = p.find("b")
        emphasis = strong or bold
        if not emphasis:
            continue

        p_text = _normalize_visible_text(p.get_text())
        emph_text = _normalize_visible_text(emphasis.get_text())
        if not p_text or p_text != emph_text:
            continue

        this_index = candidate_index
        candidate_index += 1

        skipped, reason = should_skip_bold_heading(emph_text)
        if skipped:
            continue

        if only_indices is not None and this_index not in only_indices:
            continue

        h2_tag = soup.new_tag("h2")
        for child in list(emphasis.children):
            if hasattr(child, "extract"):
                h2_tag.append(child.extract())
            else:
                h2_tag.append(str(child))
        if not h2_tag.contents:
            h2_tag.string = emph_text

        before = emph_text
        after = f"<h2>{emph_text}</h2>"
        changes.append(
            CareerHtmlChange(
                kind="bold_to_h2",
                before_display=before,
                after_display=after,
            )
        )
        p.replace_with(h2_tag)

    return str(soup), changes


def should_revert_h2_subheading(text: str) -> Tuple[bool, str]:
    """True when an <h2> should be reverted to a bold paragraph (india/international sub-labels)."""
    t = _normalize_visible_text(text)
    if not t:
        return False, ""
    if _SKIP_BOLD_HEADING_RE.match(t):
        return True, "india/international sub-label"
    return False, ""


def revert_invalid_h2_subheadings(
    html_content: str,
) -> Tuple[str, List[CareerHtmlChange]]:
    """
    Convert mistaken <h2> back to <p><strong>…</strong></p> for india/international sub-labels.
    """
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    changes: List[CareerHtmlChange] = []
    for h2 in list(soup.find_all("h2")):
        title = _normalize_visible_text(h2.get_text())
        skip, reason = should_revert_h2_subheading(title)
        if not skip:
            continue

        p_tag = soup.new_tag("p")
        strong = soup.new_tag("strong")
        for child in list(h2.children):
            if hasattr(child, "extract"):
                strong.append(child.extract())
            else:
                strong.append(str(child))
        if not strong.contents:
            strong.string = title
        p_tag.append(strong)

        before = f"<h2>{title}</h2>"
        after = f"<p><strong>{title}</strong></p>"
        changes.append(
            CareerHtmlChange(
                kind="h2_revert",
                before_display=before,
                after_display=after,
            )
        )
        h2.replace_with(p_tag)

    return str(soup), changes


def _meaningful_paragraphs(soup) -> List:
    """Top-level or document-order <p> with visible text."""
    paragraphs = []
    for p in soup.find_all("p"):
        if p.find_parent("div", class_=CONCLUSION_WRAPPER_CLASS):
            continue
        text = _normalize_visible_text(p.get_text())
        if len(text) >= 40:
            paragraphs.append(p)
    return paragraphs


def find_conclusion_wrapper(soup) -> Optional[Tag]:
    if not soup:
        return None
    return soup.find("div", class_=CONCLUSION_WRAPPER_CLASS)


def split_trailing_conclusion_from_description(
    html_content: str,
) -> Tuple[str, str]:
    """
    Split trailing conclusion paragraph from description for accordion rendering.

    Returns (body_html, conclusion_html). conclusion_html may be empty.
    - If a conclusion wrapper div exists, body excludes it and conclusion is the div inner HTML.
    - Else the last meaningful <p> is treated as conclusion and removed from body.
    """
    if not html_content or not str(html_content).strip():
        return "", ""

    if not BeautifulSoup:
        return html_content, ""

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, ""

    wrapper = find_conclusion_wrapper(soup)
    if wrapper:
        conclusion_html = "".join(str(c) for c in wrapper.contents).strip()
        wrapper.decompose()
        return str(soup).strip(), conclusion_html

    paragraphs = _meaningful_paragraphs(soup)
    if len(paragraphs) < 2:
        return html_content, ""

    last_p = paragraphs[-1]
    first_p = paragraphs[0]
    if last_p is first_p:
        return html_content, ""

    conclusion_html = str(last_p)
    last_p.decompose()
    return str(soup).strip(), conclusion_html


def wrap_last_paragraph_as_conclusion(html_content: str) -> Tuple[str, List[str]]:
    """
    Persist conclusion: wrap the last meaningful <p> in career-description-conclusion div.
    Idempotent if wrapper already exists.
    """
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    if find_conclusion_wrapper(soup):
        return html_content, []

    paragraphs = _meaningful_paragraphs(soup)
    if len(paragraphs) < 2:
        return html_content, ["skip: fewer than 2 meaningful paragraphs"]

    last_p = paragraphs[-1]
    first_p = paragraphs[0]
    if last_p is first_p:
        return html_content, ["skip: only one paragraph"]

    wrapper = soup.new_tag("div", attrs={"class": CONCLUSION_WRAPPER_CLASS})
    last_p.wrap(wrapper)
    text_preview = _normalize_visible_text(last_p.get_text())[:80]
    changes = [f"wrapped last paragraph as conclusion: {text_preview!r}…"]
    return str(soup), changes


def conclusion_text_normalized(conclusion_html: str) -> str:
    if not conclusion_html or not BeautifulSoup:
        return ""
    try:
        return _normalize_visible_text(
            BeautifulSoup(conclusion_html, "html.parser").get_text()
        )
    except Exception:
        return _normalize_visible_text(conclusion_html)


def strip_conclusion_from_html(html_content: str, conclusion_html: str) -> str:
    """Remove paragraph(s) whose text matches the conclusion block (avoid duplicate display)."""
    concl_norm = conclusion_text_normalized(conclusion_html)
    if not html_content or not concl_norm or not BeautifulSoup:
        return html_content

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content

    for p in list(soup.find_all("p")):
        if _normalize_visible_text(p.get_text()) == concl_norm:
            p.decompose()

    return str(soup).strip()


def strip_conclusion_from_accordion_sections(
    sections: list,
    conclusion_html: str,
) -> list:
    """Remove matching conclusion paragraph(s) from each accordion panel body."""
    if not sections or not conclusion_html:
        return list(sections)

    out = []
    for section in sections:
        s = dict(section)
        content = s.get("content_html") or ""
        s["content_html"] = strip_conclusion_from_html(content, conclusion_html)
        out.append(s)
    return out


def unwrap_conclusion_wrapper(html_content: str) -> Tuple[str, List[str]]:
    """Remove conclusion wrapper div but keep inner content (undo wrap)."""
    if not html_content or not BeautifulSoup:
        return html_content, []

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content, []

    wrapper = find_conclusion_wrapper(soup)
    if not wrapper:
        return html_content, []

    wrapper.unwrap()
    return str(soup), ["unwrapped career-description-conclusion div"]
