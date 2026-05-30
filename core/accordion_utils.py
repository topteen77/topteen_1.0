"""
Centralized accordion parsing and section building for careers, vocational courses,
entrance exams, extra-curricular content, and admin previews.

Split HTML by every <h2> in document order (string positions) so nested <h2> inside
divs each become their own panel — same logic as admin JS preview and public pages.
"""
import html as html_module
import re

from django.utils.html import strip_tags

# Keyword → Boxicons class (without leading "bx"; templates add class "bx {icon}")
_HEADING_ICON_PATTERNS = [
    (r"\b(overview|about|introduction|intro)\b", "bx-id-card"),
    (r"\b(roles|responsibilities|duties)\b", "bx-task"),
    (r"\b(study route|eligibility|education path)\b", "bx-book-reader"),
    (r"\b(observations?|significant)\b", "bx-bulb"),
    (r"\b(internships?|practical exposure)\b", "bx-briefcase-alt-2"),
    (r"\b(courses?|specializations?)\b", "bx-book-content"),
    (r"\b(institutes?|colleges?)\b", "bx-building-house"),
    (r"\b(international)\b", "bx-globe"),
    (r"\b(entrance tests?|exams? required)\b", "bx-edit-alt"),
    (r"\b(career path|progressing)\b", "bx-trending-up"),
    (r"\b(employment|job areas?)\b", "bx-map-alt"),
    (r"\b(employers?|recruiters?|prominent)\b", "bx-building"),
    (r"\b(pros and cons|advantages)\b", "bx-traffic-cone"),
    (r"\b(industry trends?|future outlook|skills required)\b", "bx-line-chart"),
    (r"\b(notable|designers?|contributions)\b", "bx-user-voice"),
    (r"\b(software tools?|key tools?)\b", "bx-chip"),
    (r"\b(organizations?|networks?)\b", "bx-network-chart"),
    (r"\b(advice|aspiring)\b", "bx-message-dots"),
    (r"\b(conclusion|summary)\b", "bx-check-shield"),
    (r"\b(related courses?)\b", "bx-book-open"),
    (r"\b(resources?|media)\b", "bx-folder-open"),
    (r"\b(faq|frequently asked)\b", "bx-help-circle"),
    (r"\b(syllabus|syllabi)\b", "bx-book-open"),
    (r"\b(eligibility|eligible)\b", "bx-id-card"),
    (r"\b(exam pattern|pattern|structure)\b", "bx-layout"),
    (r"\b(reservation|seat|quota)\b", "bx-group"),
    (r"\b(application|apply)\b", "bx-send"),
    (r"\b(preparation|prep|tips?)\b", "bx-heart-circle"),
    (r"\b(official links?)\b", "bx-link-external"),
    (r"\b(highlights?|key points?)\b", "bx-star"),
    (r"\b(fee|fees|payment|cost|salary)\b", "bx-dollar"),
]

# JSON section keys → icon (vocational / career description_json)
_JSON_KEY_ICON_MAP = {
    "overview": "bx-id-card",
    "career_description": "bx-id-card",
    "roles_and_responsibilities": "bx-task",
    "study_route_and_eligibility_criteria": "bx-book-reader",
    "significant_observations": "bx-bulb",
    "internships_and_practical_exposure": "bx-briefcase-alt-2",
    "courses_and_specializations": "bx-book-content",
    "prominent_employers": "bx-building",
    "salary_expectations": "bx-dollar",
    "skills_required_industry_trends": "bx-line-chart",
    "advice_for_aspiring": "bx-message-dots",
    "top_institutes": "bx-building-house",
}


def icon_for_heading(text, section_key=None):
    """Return a Boxicons suffix for Quick links / accordion headers."""
    if section_key and section_key in _JSON_KEY_ICON_MAP:
        return _JSON_KEY_ICON_MAP[section_key]
    if not text:
        return "bx-layer"
    lower = str(text).lower()
    for pattern, icon in _HEADING_ICON_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return icon
    return "bx-layer"


def strip_heading_numbers(text):
    """Remove leading numbers from titles, e.g. '1. Overview' -> 'Overview'."""
    if not text or not isinstance(text, str):
        return text or ""
    return re.sub(r"^\s*\d+\.?\s*", "", text.strip()).strip() or text


def is_intro_heading(text):
    if not text or not isinstance(text, str):
        return False
    t = strip_heading_numbers(text).strip().lower()
    return t in ("overview", "about", "introduction", "intro")


def section_html_is_blank(html):
    """True if section body has no meaningful visible text."""
    if html is None:
        return True
    s = str(html).strip()
    if not s:
        return True

    def _normalize_visible_text(t):
        if not t:
            return ""
        t = t.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
        t = re.sub(r"[\u200c\u200d\u2060\ufeff]", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    try:
        from bs4 import BeautifulSoup, Comment

        soup = BeautifulSoup(s, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        text = soup.get_text(separator=" ", strip=True)
        if _normalize_visible_text(text):
            return False
        plain = strip_tags(str(soup))
        plain = html_module.unescape(plain)
        return not _normalize_visible_text(plain)
    except Exception:
        plain = strip_tags(s)
        plain = html_module.unescape(plain)
        return not _normalize_visible_text(plain)


def filter_blank_sections(sections):
    return [s for s in sections if not section_html_is_blank(s.get("content_html"))]


def merge_leading_intro_sections(sections):
    """Merge consecutive intro-type headings into one Overview panel."""
    if not sections:
        return []
    intro_run = []
    i = 0
    while i < len(sections) and is_intro_heading(sections[i].get("title")):
        intro_run.append(sections[i])
        i += 1
    rest = sections[i:]
    if not intro_run:
        return list(sections)
    merged_html = "".join((s.get("content_html") or "") for s in intro_run)
    section_id = None
    for s in intro_run:
        sid = (s.get("section_id") or "").strip()
        if sid.lower() == "overview":
            section_id = "overview"
            break
    if section_id is None:
        for s in intro_run:
            sid = (s.get("section_id") or "").strip()
            if sid:
                section_id = sid
                break
    if not section_id:
        section_id = "overview"
    merged = {
        "section_id": section_id,
        "title": "Overview",
        "content_html": merged_html,
        "icon": icon_for_heading("Overview"),
    }
    return [merged] + rest


def normalize_entrance_exam_sections(sections):
    merged = merge_leading_intro_sections(sections)
    return filter_blank_sections(merged)


def count_h2_in_html(html_content):
    if not html_content or not str(html_content).strip():
        return 0
    return len(re.findall(r"<h2\b", str(html_content), re.IGNORECASE))


def sections_from_html(html_content, *, include_preamble_overview=True):
    """
    Split HTML by every <h2> in document order. Preamble before first h2 becomes
    Overview unless the first heading is intro-type (then preamble is merged in).
    """
    if not html_content or not str(html_content).strip():
        return []
    try:
        from bs4 import BeautifulSoup

        html_content = str(html_content).strip()
        h2_opens = list(re.finditer(r"<h2\b[^>]*>", html_content, re.IGNORECASE))
        if not h2_opens:
            return [{
                "section_id": "overview",
                "title": "Overview",
                "content_html": html_content,
                "icon": icon_for_heading("Overview"),
            }]

        used = set()
        sections = []
        preamble = html_content[: h2_opens[0].start()].strip()

        for i, m in enumerate(h2_opens):
            title_start = m.end()
            tail = html_content[title_start:]
            close_m = re.search(r"</h2>", tail, re.IGNORECASE)
            if not close_m:
                continue
            close_pos = title_start + close_m.start()
            title_html = html_content[title_start:close_pos]
            title_text = BeautifulSoup(title_html, "html.parser").get_text(separator=" ", strip=True)
            if not title_text:
                title_text = "Section"
            body_start = close_pos + len(close_m.group(0))
            body_end = h2_opens[i + 1].start() if i + 1 < len(h2_opens) else len(html_content)
            body_html = html_content[body_start:body_end].strip()

            if i == 0 and preamble and include_preamble_overview:
                if not is_intro_heading(title_text):
                    sections.append({
                        "section_id": "overview",
                        "title": "Overview",
                        "content_html": preamble,
                        "icon": icon_for_heading("Overview"),
                    })
                    used.add("overview")
                else:
                    body_html = (preamble + body_html).strip()

            existing_id = None
            try:
                frag = html_content[m.start() : close_pos + len(close_m.group(0))]
                soup_tag = BeautifulSoup(frag, "html.parser")
                h2tag = soup_tag.find("h2")
                if h2tag and h2tag.get("id", "").strip():
                    existing_id = h2tag.get("id", "").strip()
            except Exception:
                pass

            if existing_id and existing_id not in used:
                sid = existing_id
            else:
                sid = re.sub(r"[^a-z0-9]+", "-", title_text.lower())[:80].strip("-") or "section"
                base, c = sid, 1
                while sid in used:
                    sid = f"{base}-{c}"
                    c += 1
            used.add(sid)

            sections.append({
                "section_id": sid,
                "title": title_text,
                "content_html": body_html,
                "icon": icon_for_heading(title_text),
            })

        return sections if sections else [{
            "section_id": "overview",
            "title": "Overview",
            "content_html": html_content,
            "icon": icon_for_heading("Overview"),
        }]
    except Exception:
        return [{
            "section_id": "overview",
            "title": "Overview",
            "content_html": html_content,
            "icon": icon_for_heading("Overview"),
        }]


def sections_from_json_dict(json_sections, section_order=None):
    """
    Build section list from description_json-style dict: {key: {title, html}}.
    Preserves section_order when provided.
    """
    if not json_sections or not isinstance(json_sections, dict):
        return []
    ordered_keys = []
    if isinstance(section_order, list):
        for key in section_order:
            if key in json_sections and key not in ordered_keys:
                ordered_keys.append(key)
    for key in json_sections.keys():
        if key not in ordered_keys:
            ordered_keys.append(key)

    sections = []
    used_ids = set()
    for key in ordered_keys:
        data = json_sections.get(key)
        if not isinstance(data, dict):
            continue
        title = (data.get("title") or key.replace("_", " ").title()).strip()
        html = data.get("html") or data.get("content") or data.get("body") or ""
        if section_html_is_blank(html):
            continue
        sid = re.sub(r"[^a-z0-9]+", "-", key.lower())[:80].strip("-") or "section"
        base, c = sid, 1
        while sid in used_ids:
            sid = f"{base}-{c}"
            c += 1
        used_ids.add(sid)
        sections.append({
            "section_id": sid,
            "title": title,
            "content_html": html,
            "icon": icon_for_heading(title, section_key=key),
            "source_key": key,
        })
    return sections


def build_description_accordion_sections(html, json_sections=None, section_order=None, *, prefer_html=False):
    """
    Unified builder for career / vocational / similar rich HTML content.

    - prefer_html=True: always split live HTML (admin editor preview).
    - Otherwise: use JSON when it has at least as many panels as HTML; if JSON is
      incomplete (fewer sections), fall back to full HTML so all content appears.
    """
    json_built = sections_from_json_dict(json_sections, section_order) if json_sections else []
    html_built = sections_from_html(html) if html else []

    h2_count = count_h2_in_html(html) if html else 0

    if prefer_html:
        sections = html_built or json_built
    elif not json_built:
        sections = html_built
    elif not html_built:
        sections = json_built
    elif len(html_built) > len(json_built):
        sections = html_built
    elif h2_count and len(json_built) < h2_count:
        # Stale/incomplete description_json — use full HTML split by H2
        sections = html_built
    else:
        json_chars = sum(len(s.get("content_html") or "") for s in json_built)
        html_chars = sum(len(s.get("content_html") or "") for s in html_built)
        if html_chars > json_chars * 1.1:
            sections = html_built
        else:
            sections = json_built
    sections = filter_blank_sections(sections)
    for s in sections:
        s["display_title"] = strip_heading_numbers(s.get("title") or "")
    return sections


_UNTITLED_SECTION_TITLES = frozenset({
    "",
    "section",
    "untitled",
    "untitled section",
})


def is_untitled_section_title(title):
    """True for empty H2 / placeholder headings (e.g. CKEditor 'Section')."""
    if title is None:
        return True
    t = strip_heading_numbers(str(title)).strip().lower()
    if not t:
        return True
    if t in _UNTITLED_SECTION_TITLES:
        return True
    return t.startswith("untitled")


def split_trailing_untitled_section_for_frontend(sections):
    """
    Career detail only: if the last panel is untitled, render its body below the
    accordion as a plain paragraph (no accordion header).
    Returns (accordion_sections, footer_html).
    """
    if not sections:
        return [], ""
    last = sections[-1]
    title = last.get("display_title") or last.get("title") or ""
    if not is_untitled_section_title(title):
        return list(sections), ""
    content = last.get("content_html") or ""
    if section_html_is_blank(content):
        return list(sections), ""
    return list(sections[:-1]), content


def toc_from_sections(sections):
    """Quick-links TOC from accordion sections."""
    return [
        {
            "id": s["section_id"],
            "text": s.get("display_title", s.get("title", "")),
            "level": 2,
            "icon": s.get("icon", "bx-info-circle"),
        }
        for s in sections
    ]


def content_json_from_html(html_content, program_title=None):
    """
    Build VocationalCourse.content_json from H2-split HTML (same panels as public page).
    """
    sections_list = filter_blank_sections(sections_from_html(html_content or ""))
    overview_html = ""
    sections_dict = {}
    section_order = []

    for section in sections_list:
        title = section.get("title") or ""
        body = section.get("content_html") or ""
        sid = (section.get("section_id") or "").strip().lower()
        key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or sid.replace("-", "_") or "section"

        if is_intro_heading(title) or sid == "overview":
            if not overview_html:
                overview_html = body
            sections_dict.setdefault(
                "overview",
                {"title": "Overview", "html": body},
            )
            if "overview" not in section_order:
                section_order.append("overview")
            continue

        if key in sections_dict:
            base, c = key, 1
            while f"{base}_{c}" in sections_dict:
                c += 1
            key = f"{base}_{c}"

        sections_dict[key] = {
            "title": strip_heading_numbers(title) or title,
            "html": body,
        }
        section_order.append(key)

    return {
        "programtitle": (program_title or "").strip(),
        "overview": overview_html,
        "sections": sections_dict,
        "section_order": section_order,
    }


def build_vocational_accordion_sections(html_content, json_sections=None, section_order=None):
    """
    Vocational course detail: prefer live HTML (one accordion panel per H2), same as careers.
    Overview is shown in the hero, not duplicated in the accordion.
    """
    sections = build_description_accordion_sections(
        html_content or "",
        json_sections=json_sections,
        section_order=section_order,
        prefer_html=True,
    )
    sections = [
        s
        for s in sections
        if (s.get("section_id") or "").strip().lower() != "overview"
        and not is_intro_heading(s.get("title"))
    ]
    return sections


def vocational_accordion_blank_section_names(html_content, content_json=None):
    """Section titles that are blank on the public page (for admin validation)."""
    errors = []
    data = content_json if isinstance(content_json, dict) else {}
    overview = data.get("overview")
    if overview is None or section_html_is_blank(str(overview or "")):
        if not html_content or section_html_is_blank(
            _extract_preamble_overview(html_content)
        ):
            errors.append("Overview: blank")

    for section in build_vocational_accordion_sections(
        html_content or "",
        json_sections=(data.get("sections") if data else None),
        section_order=data.get("section_order") if data else None,
    ):
        title = section.get("display_title") or section.get("title") or "Section"
        if section_html_is_blank(section.get("content_html")):
            errors.append(f"{title}: blank")
    return errors


def _extract_preamble_overview(html_content):
    """Content before the first H2 when the first H2 is not an intro heading."""
    if not html_content or not str(html_content).strip():
        return ""
    sections = sections_from_html(html_content)
    for section in sections:
        if (section.get("section_id") or "").lower() == "overview":
            return section.get("content_html") or ""
    return ""


def accordion_sections_for_api(career_or_html):
    """
    API-friendly section metadata (title, id, icon) from HTML h2 headings.
    Replaces legacy H4-only extraction.
    """
    html = career_or_html
    json_sections = None
    section_order = None
    if hasattr(career_or_html, "description"):
        html = getattr(career_or_html, "description", None)
        desc_json = getattr(career_or_html, "description_json", None)
        if isinstance(desc_json, dict):
            json_sections = desc_json.get("sections")
            section_order = desc_json.get("section_order")
    sections = build_description_accordion_sections(
        html or "",
        json_sections=json_sections,
        section_order=section_order,
    )
    return [
        {
            "title": s.get("display_title", s.get("title", "")),
            "id": s.get("section_id", ""),
            "icon": s.get("icon", "bx-layer"),
        }
        for s in sections
    ]
