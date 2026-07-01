"""
Server-side HTML for studio resumes (PDF + HTML preview).

Mirrors static/resume-builder-prototype/app.js RENDERERS + helpers so PDFs match
the template chosen in the studio (same tpl-* markup + styles.css).
"""

from __future__ import annotations

import base64
import html
import logging
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from users.resume_payload import STUDIO_PROTO_V1_KEY, _STUDIO_COLOR_HEX, _wizard_draft_dict

logger = logging.getLogger(__name__)

_GOOGLE_FONTS_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34 "
    "(KHTML, like Gecko) wkhtmltopdf Safari/534.34"
)
_FONTS_FETCH_CACHE_VERSION = 2


def _esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=True)


_EDUCATION_GRADE_RE = re.compile(
    r"^(?:(?:class|grade)\s+)?(\d{1,2})(?:\s*(?:st|nd|rd|th))?$",
    re.IGNORECASE,
)


def _ordinal_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _format_education_degree_html(text: Any) -> str:
    """Render school grades like 10 as 10<sup>th</sup> for education rows."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    m = _EDUCATION_GRADE_RE.match(raw)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            suffix = _ordinal_suffix(n)
            return f"{n}<sup>{suffix}</sup>"
    return _esc(raw)


_PLACEHOLDER_DASHES = frozenset({"—", "-", "–"})


def _has_display_text(value: Any) -> bool:
    s = str(value or "").strip()
    return bool(s) and s not in _PLACEHOLDER_DASHES


def _join_display(parts: list[Any], sep: str = " · ") -> str:
    bits = [_esc(p) for p in parts if _has_display_text(p)]
    return sep.join(bits)


def _photo_initial_letter(d: dict) -> str:
    initial = (d.get("photoInitial") or "").strip()
    if initial:
        return initial[0].upper()
    name = (d.get("fullName") or "").strip()
    if name:
        return name[0].upper()
    return "?"


def _photo_html(d: dict, class_name: str) -> str:
    ph = (d.get("photo") or "").strip()
    dims = {
        "tpl-pb-avatar": (100, 100),
        "tpl-ms-photo": (72, 72),
        "tpl-avatar": (88, 88),
        "tpl-geo-photo": (88, 88),
        "tpl-au-photo": (100, 100),
        "tpl-mz-photo": (80, 80),
        "tpl-ex-photo": (88, 88),
        "tpl-st-photo": (72, 72),
        "tpl-nv-photo": (80, 80),
        "tpl-fo-photo": (88, 88),
        "tpl-gg-photo": (88, 88),
    }
    w, h = dims.get(class_name, (88, 88))
    if ph:
        return (
            f'<img class="{class_name}" src="{_esc(ph)}" alt="" '
            f'width="{w}" height="{h}" />'
        )
    letter = _esc(_photo_initial_letter(d))
    return (
        f'<div class="{class_name} tpl-photo tpl-photo--placeholder" aria-hidden="true" '
        f'style="width:{w}px;height:{h}px;">'
        f'<span class="tpl-photo-initial">{letter}</span></div>'
    )


def _contact_parts(d: dict) -> list[str]:
    out: list[str] = []
    for k in ("phone", "email", "address", "linkedin", "website"):
        v = (d.get(k) or "").strip()
        if v:
            out.append(_esc(v))
    return out


_CONTACT_ICON_SVG: dict[str, str] = {
    "phone": (
        '<svg viewBox="0 0 16 16" aria-hidden="true">'
        '<path d="M3.654 1.328a.678.678 0 0 1 .737-.124l2.522 1.01c.289.116.445.423.365.723l-.547 2.05a.68.68 0 0 1-.59.5l-1.12.112a11.77 11.77 0 0 0 5.38 5.38l.112-1.12a.68.68 0 0 1 .5-.59l2.05-.547a.678.678 0 0 1 .723.365l1.01 2.522a.678.678 0 0 1-.124.737l-1.14 1.14a1.745 1.745 0 0 1-1.81.422c-1.93-.644-4.54-2.382-6.56-4.402-2.02-2.02-3.758-4.63-4.402-6.56a1.745 1.745 0 0 1 .422-1.81l1.14-1.14z"/>'
        "</svg>"
    ),
    "email": (
        '<svg viewBox="0 0 16 16" aria-hidden="true">'
        '<path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v.217L8 8.94.001 4.217V4z"/>'
        '<path d="M0 5.383v6.617a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5.383l-7.445 4.654a1 1 0 0 1-1.11 0L0 5.383z"/>'
        "</svg>"
    ),
    "location": (
        '<svg viewBox="0 0 16 16" aria-hidden="true">'
        '<path d="M8 16s6-5.686 6-10A6 6 0 1 0 2 6c0 4.314 6 10 6 10zm0-7.5A2.5 2.5 0 1 1 8 3a2.5 2.5 0 0 1 0 5.5z"/>'
        "</svg>"
    ),
    "linkedin": (
        '<svg viewBox="0 0 16 16" aria-hidden="true">'
        '<path d="M0 1.146C0 .513.526 0 1.175 0h13.65C15.474 0 16 .513 16 1.146v13.708c0 .633-.526 1.146-1.175 1.146H1.175A1.16 1.16 0 0 1 0 14.854V1.146zM4.943 13.5V6.169H2.542V13.5h2.401zM3.742 5.163c.837 0 1.358-.554 1.358-1.248-.015-.71-.52-1.248-1.342-1.248S2.4 3.205 2.4 3.915c0 .694.521 1.248 1.326 1.248h.016zM13.5 13.5V9.359c0-2.217-1.183-3.248-2.762-3.248-1.274 0-1.845.7-2.165 1.193v.026h-.016a5.54 5.54 0 0 1 .016-.026V6.169H6.17c.03.752 0 7.331 0 7.331h2.401V9.405c0-.219.016-.438.08-.594.176-.438.578-.892 1.253-.892.884 0 1.237.673 1.237 1.66V13.5H13.5z"/>'
        "</svg>"
    ),
    "website": (
        '<svg viewBox="0 0 16 16" aria-hidden="true">'
        '<path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0zm5.939 7h-2.027a13.54 13.54 0 0 0-.65-3.145A6.02 6.02 0 0 1 13.939 7zM8 1.018c.655 0 1.58 1.23 2.027 3.982H5.973C6.42 2.248 7.345 1.018 8 1.018zM4.738 3.855A13.54 13.54 0 0 0 4.088 7H2.061a6.02 6.02 0 0 1 2.677-3.145zM2.061 9h2.027c.112 1.118.34 2.19.65 3.145A6.02 6.02 0 0 1 2.061 9zM8 14.982c-.655 0-1.58-1.23-2.027-3.982h4.054C9.58 13.752 8.655 14.982 8 14.982zM10.26 12.145c.31-.955.538-2.027.65-3.145h2.028a6.02 6.02 0 0 1-2.678 3.145z"/>'
        "</svg>"
    ),
}

_CONTACT_ICON_FALLBACK: dict[str, str] = {
    "phone": "\u260e",
    "email": "@",
    "location": "\u25cf",
    "linkedin": "in",
    "website": "www",
}


def _contact_icon_html(kind: str) -> str:
    svg = _CONTACT_ICON_SVG.get(kind, "")
    fb = _esc(_CONTACT_ICON_FALLBACK.get(kind, "•"))
    return (
        f'<span class="tpl-contact-icon" data-icon-kind="{kind}" aria-hidden="true">'
        f'<span class="tpl-contact-fallback">{fb}</span>{svg}</span>'
    )


def _contact_item_html(kind: str, val: str) -> str:
    return (
        f'<span class="tpl-contact-item">{_contact_icon_html(kind)}'
        f'<span class="tpl-contact-text">{_esc(val)}</span></span>'
    )


def _contact_row_html(d: dict, wrap_class: str = "tpl-min-contact-row") -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(_contact_item_html(kind, val))
    if not items:
        return ""
    return f'<div class="{wrap_class}">{"".join(items)}</div>'


def _contact_geo_row_html(d: dict) -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(_contact_item_html(kind, val))
    if not items:
        return ""
    inner = '<span class="tpl-geo-contact-sep" aria-hidden="true"> · </span>'.join(items)
    return f'<div class="tpl-geo-contact-row">{inner}</div>'


def _contact_hc_row_html(d: dict) -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(_contact_item_html(kind, val))
    if not items:
        return ""
    inner = '<span class="tpl-hc-contact-sep" aria-hidden="true"> · </span>'.join(items)
    return f'<div class="tpl-hc-contact-row">{inner}</div>'


def _contact_au_row_html(d: dict) -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(_contact_item_html(kind, val))
    if not items:
        return ""
    inner = '<span class="tpl-au-contact-sep" aria-hidden="true"> · </span>'.join(items)
    return f'<div class="tpl-au-contact-row">{inner}</div>'


def _contact_mz_row_html(d: dict) -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(_contact_item_html(kind, val))
    if not items:
        return ""
    inner = '<span class="tpl-mz-contact-sep" aria-hidden="true"> · </span>'.join(items)
    return f'<div class="tpl-mz-contact-row">{inner}</div>'


def _contact_inline_html(d: dict, wrap_class: str = "tpl-geo-contact") -> str:
    """Legacy wrapper — geometric uses _contact_geo_row_html."""
    return _contact_geo_row_html(d)


def _contact_list_items_html(d: dict) -> str:
    items: list[str] = []
    for kind, key in (
        ("phone", "phone"),
        ("email", "email"),
        ("location", "address"),
        ("linkedin", "linkedin"),
        ("website", "website"),
    ):
        val = (d.get(key) or "").strip()
        if not val:
            continue
        items.append(f"<li>{_contact_item_html(kind, val)}</li>")
    return "".join(items)


def _languages_chips_html(d: dict) -> str:
    parts: list[str] = []
    for ln in d.get("languages") or []:
        if not isinstance(ln, dict) or not _has_display_text(ln.get("name")):
            continue
        name = _esc(ln.get("name") or "")
        level = _esc(ln.get("level") or "") if _has_display_text(ln.get("level")) else ""
        level_html = f'<span class="tpl-ch-lang-level">{level}</span>' if level else ""
        parts.append(
            f'<span class="tpl-ch-lang-chip"><span class="tpl-ch-lang-name">{name}</span>{level_html}</span>'
        )
    if not parts:
        return ""
    return f'<div class="tpl-ch-lang-list">{"".join(parts)}</div>'


def _languages_pills_html(d: dict) -> str:
    parts: list[str] = []
    for ln in d.get("languages") or []:
        if not isinstance(ln, dict) or not _has_display_text(ln.get("name")):
            continue
        name = _esc(ln.get("name") or "")
        level = _esc(ln.get("level") or "") if _has_display_text(ln.get("level")) else ""
        level_bit = f" · {level}" if level else ""
        parts.append(f'<span class="tpl-pill tpl-pill--lang">{name}{level_bit}</span>')
    return "".join(parts)


def _sec_min_skills_row(d: dict, h2_class: str = "tpl-h2") -> str:
    inner = _skills_pills_html(d)
    if not inner.strip():
        return ""
    return (
        f'<section class="tpl-sec"><h2 class="{h2_class}">Skills</h2>'
        f'<div class="tpl-min-tags">{inner}</div></section>'
    )


def _sec_min_languages_row(d: dict, h2_class: str = "tpl-h2") -> str:
    inner = _languages_pills_html(d)
    if not inner.strip():
        return ""
    return (
        f'<section class="tpl-sec"><h2 class="{h2_class}">Languages</h2>'
        f'<div class="tpl-min-tags">{inner}</div></section>'
    )


def _skills_list_html(d: dict, numbered: bool = False) -> str:
    parts: list[str] = []
    for i, s in enumerate(d.get("skills") or []):
        if not isinstance(s, dict):
            continue
        nm = _esc(s.get("name") or "")
        if not nm:
            continue
        if numbered:
            parts.append(f'<li><span class="tpl-skill-num">{i + 1}.</span> {nm}</li>')
        else:
            parts.append(f"<li>{nm}</li>")
    return "".join(parts)


def _skill_bars_html(d: dict) -> str:
    parts: list[str] = []
    for s in d.get("skills") or []:
        if not isinstance(s, dict):
            continue
        nm = _esc(s.get("name") or "")
        if not nm:
            continue
        try:
            lv = int(s.get("level"))
        except (TypeError, ValueError):
            lv = 3
        lv = max(1, min(5, lv))
        pct = (lv / 5.0) * 100.0
        parts.append(
            f'<div class="tpl-skill-row"><span class="tpl-skill-name">{nm}</span>'
            f'<div class="tpl-skill-bar" role="presentation"><span style="width:{pct:.0f}%"></span></div></div>'
        )
    return "".join(parts)


def _experience_html(d: dict, class_job: str = "tpl-job") -> str:
    items = d.get("achievements")
    if not isinstance(items, list):
        items = [
            exp
            for exp in (d.get("experience") or [])
            if isinstance(exp, dict) and (exp.get("company") or "").strip() != "Project"
        ]
    parts: list[str] = []
    for exp in items:
        if not isinstance(exp, dict):
            continue
        title = _esc(exp.get("title") or "")
        if not title:
            continue
        bullets = "".join(
            f"<li>{_esc(b)}</li>" for b in (exp.get("bullets") or []) if str(b).strip()
        )
        dates = (
            f'<span class="tpl-job-dates">{_esc(exp.get("dates") or "")}</span>'
            if _has_display_text(exp.get("dates"))
            else ""
        )
        sub = _join_display([exp.get("company"), exp.get("location")])
        sub_html = f'<div class="tpl-job-sub">{sub}</div>' if sub else ""
        bul_html = f'<ul class="tpl-bullets">{bullets}</ul>' if bullets else ""
        parts.append(
            f'<div class="{class_job}"><div class="tpl-job-head"><strong>{title}</strong>'
            f"{dates}</div>"
            f"{sub_html}{bul_html}</div>"
        )
    return "".join(parts)


def _education_html(d: dict) -> str:
    parts: list[str] = []
    for ed in d.get("education") or []:
        if not isinstance(ed, dict):
            continue
        deg = _format_education_degree_html(ed.get("degree") or "")
        sch = _esc(ed.get("school") or "") if _has_display_text(ed.get("school")) else ""
        if not deg and not sch:
            continue
        det = _esc(ed.get("detail") or "") if _has_display_text(ed.get("detail")) else ""
        det_bit = f" — {det}" if det and sch else det
        dates = (
            f'<span class="tpl-job-dates">{_esc(ed.get("dates") or "")}</span>'
            if _has_display_text(ed.get("dates"))
            else ""
        )
        sub_html = f'<div class="tpl-job-sub">{sch}{det_bit}</div>' if sch or det else ""
        parts.append(
            f'<div class="tpl-edu-block"><div class="tpl-job-head"><strong>{deg}</strong>'
            f"{dates}</div>"
            f"{sub_html}</div>"
        )
    return "".join(parts)


def _certifications_html(d: dict) -> str:
    parts: list[str] = []
    for c in d.get("certifications") or []:
        if not isinstance(c, dict):
            continue
        nm = _esc(c.get("name") or "")
        if not nm:
            continue
        meta = _join_display([c.get("issuer"), c.get("date")])
        meta_html = f'<span class="tpl-cert-meta">{meta}</span>' if meta else ""
        parts.append(f'<div class="tpl-cert"><strong>{nm}</strong>{meta_html}</div>')
    return "".join(parts)


def _languages_html(d: dict) -> str:
    parts: list[str] = []
    for ln in d.get("languages") or []:
        if not isinstance(ln, dict):
            continue
        if not _has_display_text(ln.get("name")):
            continue
        name = _esc(ln.get("name") or "")
        level = _esc(ln.get("level") or "") if _has_display_text(ln.get("level")) else ""
        level_bit = f" — {level}" if level else ""
        parts.append(f'<li><span class="tpl-lang-name">{name}</span>{level_bit}</li>')
    return "".join(parts)


def _skills_pills_html(d: dict) -> str:
    parts: list[str] = []
    for s in d.get("skills") or []:
        if not isinstance(s, dict):
            continue
        nm = _esc(s.get("name") or "")
        if nm:
            parts.append(f'<span class="tpl-pill">{nm}</span>')
    return "".join(parts)


def _is_project_block(exp: dict) -> bool:
    return (exp.get("company") or "").strip() == "Project"


def _is_work_experience_block(exp: dict) -> bool:
    company = (exp.get("company") or "").strip()
    if not company or company == "Project" or company == "Activity":
        return False
    return not company.startswith("Volunteer")


def _projects_from_data(d: dict) -> list[dict]:
    items = d.get("projects")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return [
        x
        for x in (d.get("experience") or [])
        if isinstance(x, dict) and _is_project_block(x)
    ]


def _achievements_from_data(d: dict) -> list[dict]:
    items = d.get("achievements")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return [
        x
        for x in (d.get("experience") or [])
        if isinstance(x, dict) and not _is_project_block(x) and not _is_work_experience_block(x)
    ]


def _work_experience_from_data(d: dict) -> list[dict]:
    items = d.get("workExperience")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return [
        x
        for x in (d.get("experience") or [])
        if isinstance(x, dict) and _is_work_experience_block(x)
    ]


def _job_blocks_html(items: list[dict], class_job: str = "tpl-job") -> str:
    parts: list[str] = []
    for exp in items:
        if not isinstance(exp, dict):
            continue
        title = _esc(exp.get("title") or "")
        if not title:
            continue
        bullets = "".join(
            f"<li>{_esc(b)}</li>" for b in (exp.get("bullets") or []) if str(b).strip()
        )
        dates = (
            f'<span class="tpl-job-dates">{_esc(exp.get("dates") or "")}</span>'
            if _has_display_text(exp.get("dates"))
            else ""
        )
        sub = _join_display([exp.get("company"), exp.get("location")])
        sub_html = f'<div class="tpl-job-sub">{sub}</div>' if sub else ""
        bul_html = f'<ul class="tpl-bullets">{bullets}</ul>' if bullets else ""
        parts.append(
            f'<div class="{class_job}"><div class="tpl-job-head"><strong>{title}</strong>'
            f"{dates}</div>"
            f"{sub_html}{bul_html}</div>"
        )
    return "".join(parts)


def _experience_timeline_html(items: list[dict]) -> str:
    parts: list[str] = []
    for exp in items:
        if not isinstance(exp, dict):
            continue
        title = _esc(exp.get("title") or "")
        if not title:
            continue
        bullets = "".join(
            f"<li>{_esc(b)}</li>" for b in (exp.get("bullets") or []) if str(b).strip()
        )
        dates = (
            f'<span class="tpl-job-dates">{_esc(exp.get("dates") or "")}</span>'
            if _has_display_text(exp.get("dates"))
            else ""
        )
        sub = _join_display([exp.get("company"), exp.get("location")])
        sub_html = f'<div class="tpl-job-sub">{sub}</div>' if sub else ""
        bul_html = f'<ul class="tpl-bullets">{bullets}</ul>' if bullets else ""
        parts.append(
            f'<div class="tpl-tl-item"><span class="tpl-tl-dot"></span><div class="tpl-tl-inner">'
            f'<div class="tpl-job-head"><strong>{title}</strong>'
            f"{dates}</div>"
            f"{sub_html}{bul_html}</div></div>"
        )
    return "".join(parts)


def _skills_join_text(d: dict) -> str:
    names = []
    for s in d.get("skills") or []:
        if isinstance(s, dict) and (s.get("name") or "").strip():
            names.append(_esc(s["name"].strip()))
    return " · ".join(names)


CAREER_OBJECTIVE_TITLE = "Career Objective"
ACHIEVEMENTS_ACTIVITIES_TITLE = "Achievements & Activities"
PROJECTS_TITLE = "Projects"
WORK_EXPERIENCE_TITLE = "Work Experience"


def _ch_jobs_column_html(d: dict, class_job: str = "tpl-job") -> str:
    parts: list[str] = []
    for title, items in (
        (PROJECTS_TITLE, _projects_from_data(d)),
        (ACHIEVEMENTS_ACTIVITIES_TITLE, _achievements_from_data(d)),
        (WORK_EXPERIENCE_TITLE, _work_experience_from_data(d)),
    ):
        inner = _job_blocks_html(items, class_job)
        if inner.strip():
            parts.append(f'<div class="tpl-ch-subsec"><h2 class="tpl-h2">{_esc(title)}</h2>{inner}</div>')
    if not parts:
        return ""
    return (
        f'<section class="tpl-sec tpl-sec--half"><div class="tpl-ch-stack">{"".join(parts)}</div></section>'
    )


def _ch_edu_skills_column_html(d: dict) -> str:
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    parts: list[str] = []
    if edu_html.strip():
        parts.append(f'<div class="tpl-ch-subsec"><h2 class="tpl-h2">Education</h2>{edu_html}</div>')
    if skills_html.strip():
        parts.append(
            f'<div class="tpl-ch-subsec"><h2 class="tpl-h2">Skills</h2>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{skills_html}</ul></div>'
        )
    if not parts:
        return ""
    return f'<section class="tpl-sec tpl-sec--half"><div class="tpl-ch-stack">{"".join(parts)}</div></section>'


def _ch_certs_langs_row_html(d: dict) -> str:
    certs = _certifications_html(d)
    langs = _languages_chips_html(d)
    sections: list[str] = []
    if certs.strip():
        sections.append(
            _sec_block(
                "Certifications",
                f'<div class="tpl-ch-cert-list">{certs}</div>',
                wrap_class="tpl-sec tpl-sec--half",
            )
        )
    if langs.strip():
        sections.append(_sec_block("Languages", langs, wrap_class="tpl-sec tpl-sec--half"))
    row = _join_visible(sections)
    if not row:
        return ""
    if len(sections) == 1:
        return row.replace("tpl-sec--half", "tpl-sec tpl-sec--full", 1)
    return f'<div class="tpl-ch-row tpl-ch-row--bottom">{row}</div>'


def _tpl_headline(class_name: str, d: dict) -> str:
    if not _has_display_text(d.get("headline")):
        return ""
    return f'<p class="{class_name}">{_esc(d.get("headline"))}</p>'


def _interests_text(d: dict) -> str:
    interests = str(d.get("interests") or "").strip()
    if interests:
        return interests
    return str(d.get("hobbies") or "").strip()


def _hobbies_text(d: dict) -> str:
    hobbies = str(d.get("hobbies") or "").strip()
    if hobbies:
        return hobbies
    return str(d.get("interests") or "").strip()


def _join_visible(parts: list[str], separator: str = "") -> str:
    return separator.join(p for p in parts if (p or "").strip())


def _ms_row_html(*sections: str) -> str:
    parts = [p for p in sections if (p or "").strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f'<div class="tpl-ms-row">{"".join(parts)}</div>'


def _sec_text(
    title: str,
    text: Any,
    *,
    h2_class: str = "tpl-h2",
    wrap_class: str = "tpl-sec",
    p_class: str = "tpl-p",
    title_html: str | None = None,
) -> str:
    if not _has_display_text(text):
        return ""
    th = title_html if title_html is not None else _esc(title)
    return (
        f'<section class="{wrap_class}"><h2 class="{h2_class}">{th}</h2>'
        f'<p class="{p_class}">{_esc(text)}</p></section>'
    )


def _sec_block(
    title: str,
    inner: str,
    *,
    h2_class: str = "tpl-h2",
    wrap_class: str = "tpl-sec",
    title_html: str | None = None,
) -> str:
    if not (inner or "").strip():
        return ""
    th = title_html if title_html is not None else _esc(title)
    return f'<section class="{wrap_class}"><h2 class="{h2_class}">{th}</h2>{inner}</section>'


def _aside_block(title: str, inner: str, *, h_class: str = "tpl-cs-h3", tag: str = "h3") -> str:
    if not (inner or "").strip():
        return ""
    return f"<{tag} class=\"{h_class}\">{_esc(title)}</{tag}>{inner}"


def _sec_summary(d: dict, **kwargs: Any) -> str:
    icon = kwargs.pop("icon", None)
    title_html = kwargs.pop("title_html", None)
    if title_html is None and icon:
        title_html = f'<span class="tpl-ico">{icon}</span> {CAREER_OBJECTIVE_TITLE}'
    return _sec_text(CAREER_OBJECTIVE_TITLE, d.get("summary"), title_html=title_html, **kwargs)


def _sec_experience(d: dict, class_job: str = "tpl-job", **kwargs: Any) -> str:
    return _sec_achievements(d, class_job=class_job, **kwargs)


def _prefixed_section_title(title: str, prefix: str = "") -> str | None:
    if prefix:
        return f"{prefix}{_esc(title)}"
    return None


def _sec_projects(d: dict, class_job: str = "tpl-job", title_prefix: str = "", **kwargs: Any) -> str:
    inner = _job_blocks_html(_projects_from_data(d), class_job)
    title_html = _prefixed_section_title(PROJECTS_TITLE, title_prefix)
    return _sec_block(PROJECTS_TITLE, inner, title_html=title_html, **kwargs)


def _sec_achievements(d: dict, class_job: str = "tpl-job", title_prefix: str = "", **kwargs: Any) -> str:
    inner = _job_blocks_html(_achievements_from_data(d), class_job)
    title_html = kwargs.pop("title_html", None) or _prefixed_section_title(
        ACHIEVEMENTS_ACTIVITIES_TITLE, title_prefix
    )
    return _sec_block(ACHIEVEMENTS_ACTIVITIES_TITLE, inner, title_html=title_html, **kwargs)


def _sec_work_experience(
    d: dict, class_job: str = "tpl-job", title_prefix: str = "", **kwargs: Any
) -> str:
    inner = _job_blocks_html(_work_experience_from_data(d), class_job)
    title_html = _prefixed_section_title(WORK_EXPERIENCE_TITLE, title_prefix)
    return _sec_block(WORK_EXPERIENCE_TITLE, inner, title_html=title_html, **kwargs)


def _resume_job_sections(
    d: dict, class_job: str = "tpl-job", title_prefix: str = "", **kwargs: Any
) -> str:
    return (
        _sec_projects(d, class_job=class_job, title_prefix=title_prefix, **kwargs)
        + _sec_achievements(d, class_job=class_job, title_prefix=title_prefix, **kwargs)
        + _sec_work_experience(d, class_job=class_job, title_prefix=title_prefix, **kwargs)
    )


def _sec_education(d: dict, **kwargs: Any) -> str:
    return _sec_block("Education", _education_html(d), **kwargs)


def _sec_certifications(d: dict, **kwargs: Any) -> str:
    return _sec_block("Certifications", _certifications_html(d), **kwargs)


def _sec_skills_list(d: dict, ul_class: str = "tpl-bullets", **kwargs: Any) -> str:
    inner = _skills_list_html(d)
    if not inner.strip():
        return ""
    return _sec_block("Skills", f'<ul class="{ul_class}">{inner}</ul>', **kwargs)


def _sec_languages(d: dict, ul_class: str = "tpl-bullets", **kwargs: Any) -> str:
    inner = _languages_html(d)
    if not inner.strip():
        return ""
    return _sec_block("Languages", f'<ul class="{ul_class}">{inner}</ul>', **kwargs)


def _sec_interests(d: dict, **kwargs: Any) -> str:
    return _sec_text("Interests", _interests_text(d), **kwargs)


def _sec_hobbies(d: dict, **kwargs: Any) -> str:
    return _sec_text("Hobbies", _hobbies_text(d), **kwargs)


def _aside_skills(
    d: dict, ul_class: str = "tpl-bullets tpl-bullets--tight", h_class: str = "tpl-cs-h3"
) -> str:
    inner = _skills_list_html(d)
    if not inner.strip():
        return ""
    return _aside_block("Skills", f'<ul class="{ul_class}">{inner}</ul>', h_class=h_class)


def _aside_languages(
    d: dict, ul_class: str = "tpl-bullets tpl-bullets--tight", h_class: str = "tpl-cs-h3"
) -> str:
    inner = _languages_html(d)
    if not inner.strip():
        return ""
    return _aside_block("Languages", f'<ul class="{ul_class}">{inner}</ul>', h_class=h_class)


def _sec_certs_and_langs(d: dict, ul_class: str = "tpl-bullets", **kwargs: Any) -> str:
    certs = _certifications_html(d)
    langs = _languages_html(d)
    if not certs.strip() and not langs.strip():
        return ""
    inner = ""
    if certs.strip():
        inner += f'<div class="tpl-two-col">{certs}</div>'
    if langs.strip():
        inner += f'<ul class="{ul_class}">{langs}</ul>'
    return _sec_block("Certifications & languages", inner, **kwargs)


def _hz_sec(title: str, inner: str) -> str:
    if not (inner or "").strip():
        return ""
    return (
        f'<section class="tpl-hz-sec"><div class="tpl-hz-bar"></div>'
        f'<h2 class="tpl-hz-h2">{title}</h2>{inner}</section>'
    )


def _tpl_minimalist(d: dict) -> str:
    h2 = "tpl-h2"
    hob_text = str(d.get("hobbies") or "").strip()
    intr_text = _interests_text(d)
    section_parts = [
        _sec_summary(d, h2_class=h2),
        _resume_job_sections(d, h2_class=h2, class_job="tpl-job tpl-job--min"),
        _sec_education(d, h2_class=h2),
        _sec_min_skills_row(d, h2_class=h2),
        _sec_certifications(d, h2_class=h2),
        _sec_min_languages_row(d, h2_class=h2),
        _sec_hobbies(d, h2_class=h2),
    ]
    if intr_text and (not hob_text or intr_text != hob_text):
        section_parts.append(_sec_interests(d, h2_class=h2))
    sections = _join_visible(section_parts, '<hr class="tpl-min-rule" />')
    body_block = f'<hr class="tpl-min-rule" />{sections}' if sections else ""
    contact_html = _contact_row_html(d)
    return (
        f'<div class="tpl tpl-minimalist"><header class="tpl-min-head">'
        f'<h1 class="tpl-min-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-min-title", d)}'
        f'{contact_html}</header>{body_block}</div>'
    )


def _tpl_classic_sidebar(d: dict) -> str:
    citems = _contact_list_items_html(d)
    return (
        f'<div class="tpl tpl-classic-sidebar"><aside class="tpl-cs-side">{_photo_html(d, "tpl-avatar")}'
        f'<h1 class="tpl-cs-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-cs-title", d)}'
        f'<ul class="tpl-cs-contact">{citems}</ul>'
        f'{_aside_skills(d)}{_aside_languages(d)}'
        f'</aside><div class="tpl-cs-main">'
        f'{_sec_summary(d)}{_resume_job_sections(d)}{_sec_education(d)}'
        f'{_sec_certifications(d)}{_sec_text("Hobbies", _hobbies_text(d))}'
        f"</div></div>"
    )


def _tpl_colored_header(d: dict) -> str:
    contact_html = _contact_row_html(d, "tpl-ch-contact-row")
    top_row = _join_visible([_ch_jobs_column_html(d), _ch_edu_skills_column_html(d)])
    top_row_html = f'<div class="tpl-ch-row">{top_row}</div>' if top_row else ""
    return (
        f'<div class="tpl tpl-colored-header"><div class="tpl-ch-bar">'
        f'<h1 class="tpl-ch-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-ch-title", d)}'
        f'{contact_html}</div><div class="tpl-ch-body">'
        f'{_sec_summary(d)}{top_row_html}{_ch_certs_langs_row_html(d)}'
        f'{_sec_text("Hobbies", _hobbies_text(d))}'
        f"</div></div>"
    )


def _tpl_modern_split(d: dict) -> str:
    contact_html = _contact_row_html(d, "tpl-ms-contact-row")
    ico_obj = f'<span class="tpl-ico">📋</span> {CAREER_OBJECTIVE_TITLE}'
    ico_edu = '<span class="tpl-ico">🎓</span> Education'
    ico_job = '<span class="tpl-ico">💼</span> '
    ico_skills = '<span class="tpl-ico">⚡</span> Skills'
    ico_langs = '<span class="tpl-ico">🌐</span> Languages'
    ico_certs = '<span class="tpl-ico">🏅</span> Certifications'
    ico_hobbies = '<span class="tpl-ico">🎯</span> Hobbies'
    hobbies_val = _hobbies_text(d)
    grid_parts: list[str] = []
    top_row = _ms_row_html(
        _sec_summary(d, title_html=ico_obj),
        _sec_education(d, title_html=ico_edu),
    )
    if top_row:
        grid_parts.append(top_row)
    jobs_html = _resume_job_sections(d, wrap_class="tpl-sec tpl-ms-span2", title_prefix=ico_job)
    if jobs_html.strip():
        grid_parts.append(jobs_html)
    skills_langs_row = _ms_row_html(
        _sec_skills_list(d, title_html=ico_skills),
        _sec_languages(d, title_html=ico_langs),
    )
    if skills_langs_row:
        grid_parts.append(skills_langs_row)
    certs_html = _sec_certifications(d, wrap_class="tpl-sec tpl-ms-span2", title_html=ico_certs)
    if certs_html.strip():
        grid_parts.append(certs_html)
    hobbies_html = _sec_text(
        "Hobbies",
        hobbies_val,
        wrap_class="tpl-sec tpl-ms-span2",
        title_html=ico_hobbies,
    )
    if hobbies_html.strip():
        grid_parts.append(hobbies_html)
    grid_html = "".join(grid_parts)
    return (
        f'<div class="tpl tpl-modern-split"><div class="tpl-ms-top"><div class="tpl-ms-brand">'
        f'{_photo_html(d, "tpl-ms-photo")}<div><h1 class="tpl-ms-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-ms-title", d)}</div></div>'
        f'{contact_html}</div><div class="tpl-ms-grid">{grid_html}</div></div>'
    )


def _tpl_professional_border(d: dict) -> str:
    contact_html = _contact_row_html(d, "tpl-pb-contact-row")
    hobbies_val = _hobbies_text(d)
    side_skills = _aside_skills(d, h_class="tpl-pb-h3")
    side_langs = _aside_languages(d, h_class="tpl-pb-h3")
    return (
        f'<div class="tpl tpl-professional-border"><div class="tpl-pb-main">'
        f'<div class="tpl-pb-header"><h1 class="tpl-pb-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-pb-title", d)}'
        f'{contact_html}</div>'
        f'{_sec_summary(d)}{_resume_job_sections(d)}{_sec_education(d)}'
        f'{_sec_certifications(d)}{_sec_text("Hobbies", hobbies_val)}'
        f'</div><aside class="tpl-pb-side">{_photo_html(d, "tpl-pb-avatar")}'
        f'{side_skills}{side_langs}'
        f"</aside></div>"
    )


def _tpl_bold_header(d: dict) -> str:
    contact_html = _contact_row_html(d, "tpl-bh-contact-row")
    body = _join_visible(
        [
            _sec_summary(d),
            _resume_job_sections(d),
            _sec_education(d),
            _sec_skills_list(d),
            _sec_certifications(d),
            _sec_languages(d),
            _sec_hobbies(d),
        ],
        "",
    )
    return (
        f'<div class="tpl tpl-bold-header"><header class="tpl-bh-bar">'
        f'<h1 class="tpl-bh-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-bh-title", d)}'
        f'{contact_html}</header><div class="tpl-bh-body">{body}</div></div>'
    )


def _tpl_tech_focus(d: dict) -> str:
    citems = _contact_list_items_html(d)
    skill_bars = _skill_bars_html(d)
    langs = _languages_html(d)
    side_parts: list[str] = []
    if skill_bars.strip():
        side_parts.append(f'<h2 class="tpl-tf-h2">Skills</h2>{skill_bars}')
    if langs.strip():
        side_parts.append(
            f'<h2 class="tpl-tf-h2">Languages</h2>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{langs}</ul>'
        )
    if citems:
        side_parts.append(
            f'<h2 class="tpl-tf-h2">Contact</h2>'
            f'<ul class="tpl-bullets tpl-bullets--tight tpl-tf-contact">{citems}</ul>'
        )
    body = _join_visible(
        [
            _sec_summary(d),
            _resume_job_sections(d),
            _sec_education(d),
            _sec_certifications(d),
            _sec_hobbies(d),
        ],
        "",
    )
    return (
        f'<div class="tpl tpl-tech-focus"><aside class="tpl-tf-side">{"".join(side_parts)}</aside>'
        f'<div class="tpl-tf-main"><header class="tpl-tf-head"><h1 class="tpl-tf-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-tf-title", d)}</header>{body}</div></div>'
    )


def _tpl_elegant_serif(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    skills_text = _skills_join_text(d)
    skills_sec = (
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Skills</h2>'
        f'<p class="tpl-el-p">{skills_text}</p></section>'
        if skills_text.strip()
        else ""
    )
    langs = _languages_html(d)
    langs_sec = (
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Languages</h2>'
        f'<ul class="tpl-bullets">{langs}</ul></section>'
        if langs.strip()
        else ""
    )
    return (
        f'<div class="tpl tpl-elegant-serif"><header class="tpl-el-head">'
        f'<h1 class="tpl-el-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-el-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-el-contact">{contact}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-el-h2", p_class="tpl-el-p")}'
        f'{_sec_experience(d, h2_class="tpl-el-h2", class_job="tpl-job tpl-job--elegant")}'
        f'{_sec_education(d, h2_class="tpl-el-h2")}'
        f'{skills_sec}{_sec_certifications(d, h2_class="tpl-el-h2")}{langs_sec}'
        f'{_sec_interests(d, h2_class="tpl-el-h2", p_class="tpl-el-p")}'
        f'{_sec_hobbies(d, h2_class="tpl-el-h2", p_class="tpl-el-p")}'
        f"</div>"
    )


def _tpl_geometric(d: dict) -> str:
    pills = _skills_pills_html(d)
    skills_aside = ""
    if pills.strip():
        skills_aside = (
            f'<aside class="tpl-geo-aside"><h2 class="tpl-geo-h2">Skills</h2>'
            f'<div class="tpl-geo-pills">{pills}</div></aside>'
        )
    main_parts = _join_visible(
        [
            _sec_education(d, h2_class="tpl-geo-h2"),
            _sec_certifications(d, h2_class="tpl-geo-h2"),
            _sec_languages(d, h2_class="tpl-geo-h2"),
            _sec_hobbies(d, h2_class="tpl-geo-h2"),
        ],
        "",
    )
    layout_html = ""
    if main_parts.strip() or skills_aside:
        layout_html = (
            f'<div class="tpl-geo-layout"><div class="tpl-geo-main">{main_parts}</div>'
            f"{skills_aside}</div>"
        )
    body = _join_visible(
        [
            _sec_summary(d, h2_class="tpl-geo-h2"),
            _resume_job_sections(d, h2_class="tpl-geo-h2"),
        ],
        "",
    )
    return (
        f'<div class="tpl tpl-geometric"><header class="tpl-geo-head">{_photo_html(d, "tpl-geo-photo")}'
        f'<div class="tpl-geo-text"><h1 class="tpl-geo-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-geo-title", d)}'
        f"{_contact_geo_row_html(d)}</div></header>"
        f"{body}{layout_html}</div>"
    )


def _tpl_high_contrast(d: dict) -> str:
    side_parts = [
        _aside_skills(d, h_class="tpl-hc-h3"),
        _aside_languages(d, h_class="tpl-hc-h3"),
    ]
    hobbies_val = _hobbies_text(d)
    if hobbies_val:
        side_parts.append(
            f'<h3 class="tpl-hc-h3">Hobbies</h3>'
            f'<p class="tpl-hc-small">{_esc(hobbies_val)}</p>'
        )
    body = _join_visible(
        [
            _sec_summary(d, h2_class="tpl-h2 tpl-h2--hc"),
            _resume_job_sections(d, h2_class="tpl-h2 tpl-h2--hc"),
            _sec_education(d, h2_class="tpl-h2 tpl-h2--hc"),
            _sec_certifications(d, h2_class="tpl-h2 tpl-h2--hc"),
        ],
        "",
    )
    return (
        f'<div class="tpl tpl-high-contrast"><header class="tpl-hc-top">'
        f'<h1 class="tpl-hc-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-hc-title", d)}'
        f"{_contact_hc_row_html(d)}</header>"
        f'<div class="tpl-hc-body">'
        f'<aside class="tpl-hc-side">{"".join(p for p in side_parts if p)}</aside>'
        f'<div class="tpl-hc-main">{body}</div>'
        f"</div></div>"
    )


def _tpl_aurora(d: dict) -> str:
    contact_html = _contact_au_row_html(d)
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    row_parts: list[str] = []
    if edu_html.strip():
        row_parts.append(
            f'<section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Education</h2>'
            f'{edu_html}</section>'
        )
    if skills_html.strip():
        row_parts.append(
            f'<section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Skills</h2>'
            f'<ul class="tpl-bullets">{skills_html}</ul></section>'
        )
    row_html = f'<div class="tpl-au-row">{"".join(row_parts)}</div>' if row_parts else ""
    certs = _certifications_html(d)
    langs = _languages_html(d)
    cert_row_parts: list[str] = []
    if certs.strip():
        cert_row_parts.append(
            f'<section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Certifications</h2>'
            f"{certs}</section>"
        )
    if langs.strip():
        cert_row_parts.append(
            f'<section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Languages</h2>'
            f'<ul class="tpl-bullets">{langs}</ul></section>'
        )
    cert_row_html = (
        f'<div class="tpl-au-row">{"".join(cert_row_parts)}</div>' if cert_row_parts else ""
    )
    body = (
        _sec_summary(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")
        + _resume_job_sections(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")
        + row_html
        + cert_row_html
        + _sec_hobbies(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")
    )
    return (
        f'<div class="tpl tpl-aurora"><div class="tpl-au-hero">{_photo_html(d, "tpl-au-photo")}'
        f'<div class="tpl-au-hero-text"><h1 class="tpl-au-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-au-tagline", d)}'
        f'{contact_html}</div></div><div class="tpl-au-body">{body}</div></div>'
    )


def _mz_sec_block(title: str, inner: str) -> str:
    if not (inner or "").strip():
        return ""
    return f'<h2 class="tpl-mz-h2">{_esc(title)}</h2>{inner}'


def _mz_resume_job_sections(d: dict, class_job: str = "tpl-job tpl-job--mz") -> str:
    return (
        _mz_sec_block(PROJECTS_TITLE, _job_blocks_html(_projects_from_data(d), class_job))
        + _mz_sec_block(
            ACHIEVEMENTS_ACTIVITIES_TITLE,
            _job_blocks_html(_achievements_from_data(d), class_job),
        )
        + _mz_sec_block(
            WORK_EXPERIENCE_TITLE,
            _job_blocks_html(_work_experience_from_data(d), class_job),
        )
    )


def _tpl_magazine(d: dict) -> str:
    contact_html = _contact_mz_row_html(d)
    main_col = _join_visible(
        [
            (
                f'<h2 class="tpl-mz-h2">{CAREER_OBJECTIVE_TITLE}</h2>'
                f'<p class="tpl-mz-lead">{_esc(d.get("summary"))}</p>'
                if _has_display_text(d.get("summary"))
                else ""
            ),
            _mz_resume_job_sections(d),
        ]
    )
    aside_parts: list[str] = [_photo_html(d, "tpl-mz-photo")]
    pills = _skills_pills_html(d)
    if pills.strip():
        aside_parts.append(f'<h3 class="tpl-mz-h3">Skills</h3><div class="tpl-mz-pills">{pills}</div>')
    edu_html = _education_html(d)
    if edu_html.strip():
        aside_parts.append(f'<h3 class="tpl-mz-h3">Education</h3>{edu_html}')
    langs = _languages_html(d)
    if langs.strip():
        aside_parts.append(
            f'<h3 class="tpl-mz-h3">Languages</h3>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{langs}</ul>'
        )
    certs = _certifications_html(d)
    if certs.strip():
        aside_parts.append(f'<h3 class="tpl-mz-h3">Certifications</h3>{certs}')
    hob = _hobbies_text(d)
    if hob.strip():
        aside_parts.append(f'<h3 class="tpl-mz-h3">Hobbies</h3><p class="tpl-p">{_esc(hob)}</p>')
    return (
        f'<div class="tpl tpl-magazine"><header class="tpl-mz-header"><div class="tpl-mz-accent"></div>'
        f'<div class="tpl-mz-intro"><p class="tpl-mz-kicker">Professional profile</p>'
        f'<h1 class="tpl-mz-name">{_esc(d.get("fullName"))}</h1>'
        f'{_tpl_headline("tpl-mz-title", d)}'
        f'{contact_html}</div></header><div class="tpl-mz-grid">'
        f'<section class="tpl-mz-col">{main_col}</section>'
        f'<aside class="tpl-mz-aside">{"".join(aside_parts)}</aside></div></div>'
    )


def _timeline_track_section(title: str, items: list[dict]) -> str:
    inner = _experience_timeline_html(items)
    if not inner.strip():
        return ""
    return (
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">{title}</h2>'
        f'<div class="tpl-tl-track">{inner}</div></section>'
    )


def _tpl_timeline(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    timeline_secs = _join_visible(
        [
            _timeline_track_section("Projects", _projects_from_data(d)),
            _timeline_track_section(ACHIEVEMENTS_ACTIVITIES_TITLE, _achievements_from_data(d)),
            _timeline_track_section("Work Experience", _work_experience_from_data(d)),
        ]
    )
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    two_col_parts: list[str] = []
    if edu_html.strip():
        two_col_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Education</h2>{edu_html}</section>'
        )
    if skills_html.strip():
        two_col_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Skills</h2>'
            f'<ul class="tpl-bullets tpl-tl-skills-list">{skills_html}</ul></section>'
        )
    two_col = f'<div class="tpl-tl-two">{"".join(two_col_parts)}</div>' if two_col_parts else ""
    return (
        f'<div class="tpl tpl-timeline"><header class="tpl-tl-head">'
        f'<h1 class="tpl-tl-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-tl-sub">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-tl-contact">{cj}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-tl-section-title")}'
        f"{timeline_secs}{two_col}"
        f'{_sec_certifications(d, h2_class="tpl-tl-section-title")}'
        f'{_sec_languages(d, h2_class="tpl-tl-section-title")}'
        f'{_sec_hobbies(d, h2_class="tpl-tl-section-title")}'
        f'{_sec_interests(d, h2_class="tpl-tl-section-title")}'
        f"</div>"
    )


def _tpl_executive(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
    side_parts: list[str] = [_photo_html(d, "tpl-ex-photo")]
    if citems:
        side_parts.append(f'<h2 class="tpl-ex-h2">Contact</h2><ul class="tpl-ex-list">{citems}</ul>')
    skills = _skills_list_html(d)
    if skills.strip():
        side_parts.append(
            f'<h2 class="tpl-ex-h2">Core skills</h2>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{skills}</ul>'
        )
    langs = _languages_html(d)
    if langs.strip():
        side_parts.append(
            f'<h2 class="tpl-ex-h2">Languages</h2>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{langs}</ul>'
        )
    return (
        f'<div class="tpl tpl-executive"><aside class="tpl-ex-side">{"".join(side_parts)}</aside>'
        f'<div class="tpl-ex-main"><header class="tpl-ex-top">'
        f'<h1 class="tpl-ex-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ex-title">{_esc(d.get("headline"))}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-ex-h2-main")}'
        f'{_sec_experience(d, h2_class="tpl-ex-h2-main")}'
        f'{_sec_education(d, h2_class="tpl-ex-h2-main")}'
        f'{_sec_certifications(d, h2_class="tpl-ex-h2-main")}'
        f'{_sec_interests(d, h2_class="tpl-ex-h2-main")}'
        f'{_sec_hobbies(d, h2_class="tpl-ex-h2-main")}'
        f"</div></div>"
    )


def _tpl_studio(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    pills = _skills_pills_html(d)
    pills_html = f'<div class="tpl-st-skills">{pills}</div>' if pills.strip() else ""
    langs = _languages_html(d)
    lang_sec = (
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">Languages</h2>'
        f'<ul class="tpl-bullets">{langs}</ul></section>'
        if langs.strip()
        else ""
    )
    split_parts = [_sec_education(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2"), lang_sec]
    split_html = (
        f'<div class="tpl-st-split">{"".join(p for p in split_parts if p)}</div>'
        if any(split_parts)
        else ""
    )
    return (
        f'<div class="tpl tpl-studio"><header class="tpl-st-hero"><div class="tpl-st-hero-inner">'
        f'{_photo_html(d, "tpl-st-photo")}<div><h1 class="tpl-st-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-st-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-st-contact">{cj}</p></div></div>'
        f'{pills_html}</header><div class="tpl-st-body">'
        f'{_sec_summary(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2")}'
        f'{_sec_experience(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2", class_job="tpl-job tpl-job--st")}'
        f'{split_html}'
        f'{_sec_certifications(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2")}'
        f'{_sec_interests(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2")}'
        f'{_sec_hobbies(d, wrap_class="tpl-st-card", h2_class="tpl-st-h2")}'
        f"</div></div>"
    )


def _tpl_nova(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    edu_html = _education_html(d)
    pills = _skills_pills_html(d)
    split_parts: list[str] = []
    if edu_html.strip():
        split_parts.append(
            f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Education</h2>{edu_html}</section>'
        )
    if pills.strip():
        split_parts.append(
            f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Skills</h2>'
            f'<div class="tpl-nv-pills">{pills}</div></section>'
        )
    split_html = f'<div class="tpl-nv-split">{"".join(split_parts)}</div>' if split_parts else ""
    return (
        f'<div class="tpl tpl-nova"><div class="tpl-nv-hero"><div class="tpl-nv-blob" aria-hidden="true"></div>'
        f'<div class="tpl-nv-card">{_photo_html(d, "tpl-nv-photo")}<div class="tpl-nv-intro">'
        f'<h1 class="tpl-nv-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-nv-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-nv-contact">{cj}</p></div></div></div><div class="tpl-nv-body">'
        f'{_sec_summary(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}'
        f'{_sec_experience(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}'
        f'{split_html}{_sec_certifications(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}{_sec_languages(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}'
        f'{_sec_hobbies(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}'
        f'{_sec_interests(d, wrap_class="tpl-nv-panel", h2_class="tpl-nv-h2")}'
        f"</div></div>"
    )


def _tpl_ledger(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))

    def _lg_block(title: str, inner: str) -> str:
        if not inner.strip():
            return ""
        return (
            f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2">'
            f'<span class="tpl-lg-hash">#</span> {title}</h2>{inner}</section>'
        )

    summary_inner = (
        f'<p class="tpl-lg-p">{_esc(d.get("summary"))}</p>'
        if _has_display_text(d.get("summary"))
        else ""
    )
    skills_list = _skills_list_html(d)
    skills_inner = f'<ul class="tpl-lg-list">{skills_list}</ul>' if skills_list.strip() else ""
    langs = _languages_html(d)
    langs_inner = f'<ul class="tpl-lg-list">{langs}</ul>' if langs.strip() else ""
    hobbies_inner = (
        f'<p class="tpl-lg-p">{_esc(d.get("hobbies"))}</p>'
        if _has_display_text(d.get("hobbies"))
        else ""
    )
    interests_inner = (
        f'<p class="tpl-lg-p">{_esc(d.get("interests"))}</p>'
        if _has_display_text(d.get("interests"))
        else ""
    )
    return (
        f'<div class="tpl tpl-ledger"><header class="tpl-lg-head">'
        f'<h1 class="tpl-lg-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-lg-meta"><span class="tpl-lg-label">ROLE</span> {_esc(d.get("headline"))}</p>'
        f'<p class="tpl-lg-meta"><span class="tpl-lg-label">CONTACT</span> {cj}</p></header>'
        f'{_lg_block(CAREER_OBJECTIVE_TITLE, summary_inner)}'
        f'{_lg_block(ACHIEVEMENTS_ACTIVITIES_TITLE, _experience_html(d, "tpl-job tpl-job--lg"))}'
        f'{_lg_block("Education", _education_html(d))}'
        f'{_lg_block("Skills", skills_inner)}'
        f'{_lg_block("Certifications", _certifications_html(d))}'
        f'{_lg_block("Languages", langs_inner)}'
        f'{_lg_block("Hobbies", hobbies_inner)}'
        f'{_lg_block("Interests", interests_inner)}'
        f"</div>"
    )


def _tpl_horizon(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    sm = f'<p class="tpl-p">{_esc(d.get("summary"))}</p>' if _has_display_text(d.get("summary")) else ""
    edu_html = _education_html(d)
    pills = _skills_pills_html(d)
    split_parts: list[str] = []
    if edu_html.strip():
        split_parts.append(
            f'<section class="tpl-hz-panel"><div class="tpl-hz-bar"></div>'
            f'<h2 class="tpl-hz-h2">Education</h2>{edu_html}</section>'
        )
    if pills.strip():
        split_parts.append(
            f'<section class="tpl-hz-panel"><div class="tpl-hz-bar"></div>'
            f'<h2 class="tpl-hz-h2">Skills</h2><div class="tpl-hz-pills">{pills}</div></section>'
        )
    split_html = f'<div class="tpl-hz-split">{"".join(split_parts)}</div>' if split_parts else ""
    ln = _languages_html(d)
    ln_html = f'<ul class="tpl-bullets">{ln}</ul>' if ln.strip() else ""
    hob = f'<p class="tpl-p">{_esc(d.get("hobbies"))}</p>' if _has_display_text(d.get("hobbies")) else ""
    intr = f'<p class="tpl-p">{_esc(d.get("interests"))}</p>' if _has_display_text(d.get("interests")) else ""
    return (
        f'<div class="tpl tpl-horizon"><header class="tpl-hz-head">'
        f'<h1 class="tpl-hz-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-hz-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-hz-contact">{cj}</p></header>'
        f'{_hz_sec(CAREER_OBJECTIVE_TITLE, sm)}'
        f'{_hz_sec(ACHIEVEMENTS_ACTIVITIES_TITLE, _experience_html(d))}'
        f'{_hz_sec("Projects", _job_blocks_html(_projects_from_data(d)))}'
        f'{_hz_sec("Work Experience", _job_blocks_html(_work_experience_from_data(d)))}'
        f"{split_html}"
        f'{_hz_sec("Certifications", _certifications_html(d))}'
        f'{_hz_sec("Languages", ln_html)}'
        f'{_hz_sec("Hobbies", hob)}'
        f'{_hz_sec("Interests", intr)}'
        f"</div>"
    )


def _tpl_folio(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    counter = 0

    def _fo_num() -> str:
        nonlocal counter
        counter += 1
        return str(counter).zfill(2)

    def _fo_sec(title: str, inner: str) -> str:
        if not inner.strip():
            return ""
        return (
            f'<section class="tpl-fo-sec"><span class="tpl-fo-num">{_fo_num()}</span>'
            f'<div class="tpl-fo-content"><h2 class="tpl-fo-h2">{title}</h2>{inner}</div></section>'
        )

    summary_inner = (
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p>'
        if _has_display_text(d.get("summary"))
        else ""
    )
    skills_text = _skills_join_text(d)
    skills_inner = f'<p class="tpl-fo-skills">{skills_text}</p>' if skills_text.strip() else ""
    sections = _join_visible(
        [
            _fo_sec(CAREER_OBJECTIVE_TITLE, summary_inner),
            _fo_sec("Projects", _job_blocks_html(_projects_from_data(d), "tpl-job tpl-job--fo")),
            _fo_sec(
                ACHIEVEMENTS_ACTIVITIES_TITLE,
                _job_blocks_html(_achievements_from_data(d), "tpl-job tpl-job--fo"),
            ),
            _fo_sec(
                "Work Experience",
                _job_blocks_html(_work_experience_from_data(d), "tpl-job tpl-job--fo"),
            ),
            _fo_sec("Education", _education_html(d)),
            _fo_sec("Skills", skills_inner),
            _fo_sec("Certifications", _certifications_html(d)),
            _fo_sec("Languages", f'<ul class="tpl-bullets">{_languages_html(d)}</ul>'),
            _fo_sec(
                "Hobbies",
                f'<p class="tpl-p">{_esc(d.get("hobbies"))}</p>'
                if _has_display_text(d.get("hobbies"))
                else "",
            ),
            _fo_sec(
                "Interests",
                f'<p class="tpl-p">{_esc(d.get("interests"))}</p>'
                if _has_display_text(d.get("interests"))
                else "",
            ),
        ]
    )
    return (
        f'<div class="tpl tpl-folio"><header class="tpl-fo-head">{_photo_html(d, "tpl-fo-photo")}<div>'
        f'<h1 class="tpl-fo-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-fo-line">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-fo-contact">{cj}</p></div></header>'
        f"{sections}"
        f"</div>"
    )


def _tpl_vertex(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    grid_parts: list[str] = []
    if edu_html.strip():
        grid_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Education</h2>{edu_html}</section>'
        )
    if skills_html.strip():
        grid_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Skills</h2>'
            f'<ul class="tpl-bullets">{skills_html}</ul></section>'
        )
    grid_html = f'<div class="tpl-vx-grid">{"".join(grid_parts)}</div>' if grid_parts else ""
    return (
        f'<div class="tpl tpl-vertex"><header class="tpl-vx-banner"><div class="tpl-vx-banner-inner">'
        f'<h1 class="tpl-vx-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-vx-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-vx-contact">{cj}</p></div></header><div class="tpl-vx-body">'
        f'{_sec_summary(d, h2_class="tpl-vx-h2")}'
        f'{_sec_experience(d, h2_class="tpl-vx-h2")}'
        f'{grid_html}'
        f'{_sec_certifications(d, h2_class="tpl-vx-h2")}'
        f'{_sec_languages(d, h2_class="tpl-vx-h2")}'
        f'{_sec_hobbies(d, h2_class="tpl-vx-h2")}'
        f'{_sec_interests(d, h2_class="tpl-vx-h2")}'
        f"</div></div>"
    )


def _tpl_atlantic_pro(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    headline = (
        f'<p class="tpl-ap-title">{_esc(d.get("headline"))}</p>'
        if _has_display_text(d.get("headline"))
        else ""
    )
    skills = _skills_list_html(d)
    langs = _languages_html(d)
    side_parts: list[str] = []
    if skills.strip():
        side_parts.append(
            f'<h3 class="tpl-ap-h3">Skills</h3>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{skills}</ul>'
        )
    if langs.strip():
        side_parts.append(
            f'<h3 class="tpl-ap-h3">Languages</h3>'
            f'<ul class="tpl-bullets tpl-bullets--tight">{langs}</ul>'
        )
    certs = _certifications_html(d)
    if certs.strip():
        side_parts.append(f'<h3 class="tpl-ap-h3">Certifications</h3>{certs}')
    return (
        f'<div class="tpl tpl-atlantic-pro"><header class="tpl-ap-head">'
        f'<h1 class="tpl-ap-name">{_esc(d.get("fullName"))}</h1>'
        f"{headline}"
        f'<p class="tpl-ap-contact">{cj}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-ap-h2")}'
        f'<div class="tpl-ap-grid">'
        f'{_sec_experience(d, h2_class="tpl-ap-h2")}'
        f'<aside class="tpl-ap-side">{"".join(side_parts)}</aside></div>'
        f'{_sec_education(d, h2_class="tpl-ap-h2")}'
        f'{_sec_interests(d, h2_class="tpl-ap-h2")}'
        f"</div>"
    )


def _tpl_zen_column(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    headline = (
        f'<p class="tpl-zc-title">{_esc(d.get("headline"))}</p>'
        if _has_display_text(d.get("headline"))
        else ""
    )
    pills = _skills_pills_html(d)
    pills_html = f'<div class="tpl-zc-pills">{pills}</div>' if pills.strip() else ""
    certs_langs = _join_visible(
        [
            _certifications_html(d),
            f'<ul class="tpl-bullets">{_languages_html(d)}</ul>' if _languages_html(d).strip() else "",
        ]
    )
    return (
        f'<div class="tpl tpl-zen-column"><header class="tpl-zc-head">'
        f'<h1 class="tpl-zc-name">{_esc(d.get("fullName"))}</h1>'
        f"{headline}"
        f'<p class="tpl-zc-contact">{cj}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-zc-h2")}'
        f'{_sec_experience(d, h2_class="tpl-zc-h2", class_job="tpl-job tpl-job--zc")}'
        f'{_sec_education(d, h2_class="tpl-zc-h2")}'
        f'{_sec_block("Skills", pills_html, h2_class="tpl-zc-h2")}'
        f'{_sec_block("Certifications & Languages", certs_langs, h2_class="tpl-zc-h2")}'
        f'{_sec_interests(d, h2_class="tpl-zc-h2")}'
        f"</div>"
    )


def _tpl_global_grid(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    headline = (
        f'<p class="tpl-gg-title">{_esc(d.get("headline"))}</p>'
        if _has_display_text(d.get("headline"))
        else ""
    )
    return (
        f'<div class="tpl tpl-global-grid"><header class="tpl-gg-head"><div>'
        f'<h1 class="tpl-gg-name">{_esc(d.get("fullName"))}</h1>'
        f"{headline}"
        f"</div>{_photo_html(d, 'tpl-gg-photo')}</header>"
        f'<p class="tpl-gg-contact">{cj}</p><div class="tpl-gg-layout">'
        f'{_sec_summary(d, wrap_class="tpl-sec tpl-gg-main", h2_class="tpl-gg-h2")}'
        f'{_sec_experience(d, wrap_class="tpl-sec tpl-gg-main", h2_class="tpl-gg-h2")}'
        f'{_sec_education(d, wrap_class="tpl-sec tpl-gg-half", h2_class="tpl-gg-h2")}'
        f'{_sec_skills_list(d, wrap_class="tpl-sec tpl-gg-half", h2_class="tpl-gg-h2")}'
        f'{_sec_languages(d, wrap_class="tpl-sec tpl-gg-half", h2_class="tpl-gg-h2")}'
        f'{_sec_certifications(d, wrap_class="tpl-sec tpl-gg-half", h2_class="tpl-gg-h2")}'
        f'{_sec_interests(d, wrap_class="tpl-sec tpl-gg-main", h2_class="tpl-gg-h2")}'
        f"</div></div>"
    )


STUDIO_TEMPLATE_ALIASES: dict[str, str] = {
    "global-elegance": "magazine",
    "euro-corporate": "executive",
    "tokyo-minimal": "minimalist",
    "nordic-clean": "horizon",
}


SIDEBAR_PDF_TEMPLATE_ROOTS = frozenset(
    {
        "tpl-classic-sidebar",
        "tpl-professional-border",
        "tpl-tech-focus",
        "tpl-high-contrast",
        "tpl-executive",
        "tpl-magazine",
    }
)

TPL_RENDERERS: dict[str, Callable[[dict], str]] = {
    "minimalist": _tpl_minimalist,
    "classic-sidebar": _tpl_classic_sidebar,
    "colored-header": _tpl_colored_header,
    "modern-split": _tpl_modern_split,
    "professional-border": _tpl_professional_border,
    "bold-header": _tpl_bold_header,
    "tech-focus": _tpl_tech_focus,
    "elegant-serif": _tpl_elegant_serif,
    "geometric": _tpl_geometric,
    "high-contrast": _tpl_high_contrast,
    "aurora": _tpl_aurora,
    "magazine": _tpl_magazine,
    "timeline": _tpl_timeline,
    "executive": _tpl_executive,
    "studio": _tpl_studio,
    "nova": _tpl_nova,
    "ledger": _tpl_ledger,
    "horizon": _tpl_horizon,
    "folio": _tpl_folio,
    "vertex": _tpl_vertex,
    "atlantic-pro": _tpl_atlantic_pro,
    "zen-column": _tpl_zen_column,
    "global-grid": _tpl_global_grid,
}


def resolve_studio_template_id(template_id: str) -> str:
    tid = (template_id or "classic-sidebar").strip().lower()
    tid = STUDIO_TEMPLATE_ALIASES.get(tid, tid)
    if tid not in TPL_RENDERERS:
        return "classic-sidebar"
    return tid


def all_studio_template_ids() -> list[str]:
    """Every template id accepted by the studio (including aliases)."""
    ids = sorted(TPL_RENDERERS.keys())
    for alias in STUDIO_TEMPLATE_ALIASES:
        if alias not in ids:
            ids.append(alias)
    return sorted(set(ids))


def _hex_to_rgb_triplet(hex_s: str) -> tuple[int, int, int]:
    h = (hex_s or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        v = int(h, 16)
    except ValueError:
        return (27, 158, 122)
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def studio_proto_pack_from_resume(resume) -> dict | None:
    wiz = _wizard_draft_dict(resume)
    if not wiz:
        return None
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    if not isinstance(sp, dict) or not isinstance(sp.get("resume"), dict):
        return None
    return sp


def studio_pack_font_stack(pack: dict) -> str:
    from users.resume_payload import (
        DEFAULT_STUDIO_EMBED_FONT,
        _STUDIO_FONT_IDS,
        studio_font_stack_from_id,
    )

    raw = (pack.get("font") or "").strip()[:240] or DEFAULT_STUDIO_EMBED_FONT
    if raw.lower() in _STUDIO_FONT_IDS:
        return studio_font_stack_from_id(raw)
    if not re.match(r'^[\w\s\-",.()+]+$', raw):
        return DEFAULT_STUDIO_EMBED_FONT
    return raw


def studio_pack_accent_hex(pack: dict) -> str:
    cid = (pack.get("color") or "teal").strip().lower()
    return _STUDIO_COLOR_HEX.get(cid, _STUDIO_COLOR_HEX["teal"])


def studio_pack_font_size_vars(pack: dict) -> tuple[str, float]:
    from users.resume_payload import _STUDIO_FONT_SIZES

    fid = (pack.get("fontSize") or "standard").strip().lower()
    body_size, font_scale = _STUDIO_FONT_SIZES.get(fid, _STUDIO_FONT_SIZES["standard"])
    return body_size, font_scale


def studio_pack_effective_body_size(pack: dict) -> str:
    """Body font size with font-scale baked in (wkhtmltopdf ignores CSS zoom)."""
    body_size, font_scale = studio_pack_font_size_vars(pack)
    m = re.match(r"([\d.]+)\s*pt", body_size.strip(), re.I)
    pt = float(m.group(1)) if m else 11.5
    return f"{pt * font_scale:.2f}pt"


_FONT_GOOGLE_FAMILY_PARAMS: dict[str, str] = {
    "Inter": "Inter:wght@400;600;700",
    "Source Sans 3": "Source+Sans+3:wght@400;600;700",
    "DM Sans": "DM+Sans:wght@400;600;700",
    "Open Sans": "Open+Sans:wght@400;600;700",
    "IBM Plex Sans": "IBM+Plex+Sans:wght@400;600;700",
    "Lora": "Lora:wght@400;600;700",
    "Merriweather": "Merriweather:wght@400;700",
    "Crimson Pro": "Crimson+Pro:wght@400;600;700",
    "Playfair Display": "Playfair+Display:wght@400;600;700",
    "Outfit": "Outfit:wght@400;600;700",
}


@lru_cache(maxsize=64)
def _fetch_google_fonts_css_text(href: str, _cache_v: int = _FONTS_FETCH_CACHE_VERSION) -> str:
    """Fetch Google Fonts CSS (request TTF for wkhtmltopdf — it cannot load woff2)."""
    del _cache_v
    try:
        req = urllib.request.Request(href, headers={"User-Agent": _GOOGLE_FONTS_UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        logger.warning("Google Fonts CSS fetch failed for %s: %s", href, exc)
        return ""


@lru_cache(maxsize=256)
def _fetch_font_binary(url: str, _cache_v: int = _FONTS_FETCH_CACHE_VERSION) -> bytes:
    del _cache_v
    req = urllib.request.Request(url, headers={"User-Agent": _GOOGLE_FONTS_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _embed_gstatic_urls_as_data_uris(css: str) -> str:
    """Rewrite gstatic font URLs as data URIs so wkhtmltopdf needs no network for fonts."""

    def _repl(match: re.Match[str]) -> str:
        url = match.group(1)
        if not url.startswith("https://fonts.gstatic.com/"):
            return match.group(0)
        try:
            raw = _fetch_font_binary(url)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.warning("Font file fetch failed %s: %s", url, exc)
            return match.group(0)
        lower = url.lower()
        if lower.endswith(".woff2") or "woff2" in lower:
            return match.group(0)
        if lower.endswith(".woff"):
            fmt = "font/woff"
        else:
            fmt = "font/ttf"
        b64 = base64.b64encode(raw).decode("ascii")
        return f"url(data:{fmt};base64,{b64})"

    return re.sub(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", _repl, css)


def studio_pdf_embedded_fonts_css(pack: dict) -> str:
    """@font-face CSS with embedded binaries — matches live preview fonts in wkhtmltopdf."""
    href = studio_pdf_google_fonts_href(pack)
    css = _fetch_google_fonts_css_text(href)
    if not css.strip():
        return ""
    return _embed_gstatic_urls_as_data_uris(css)


def studio_pdf_google_fonts_href(pack: dict) -> str:
    """Google Fonts URL for fonts used by this resume (faster load in wkhtmltopdf)."""
    stack = studio_pack_font_stack(pack)
    families = re.findall(r'"([^"]+)"', stack)
    params: list[str] = []
    for fam in families:
        spec = _FONT_GOOGLE_FAMILY_PARAMS.get(fam)
        if spec:
            params.append(f"family={spec}")
    if not params:
        params.append(f"family={_FONT_GOOGLE_FAMILY_PARAMS['Inter']}")
    return "https://fonts.googleapis.com/css2?" + "&".join(params) + "&display=swap"


STUDIO_GOOGLE_FONTS_HREF = (
    "https://fonts.googleapis.com/css2?"
    "family=Crimson+Pro:ital,wght@0,400;0,600;0,700;1,400&"
    "family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&"
    "family=IBM+Plex+Sans:wght@400;500;600;700&"
    "family=Inter:wght@400;500;600;700&"
    "family=Lora:ital,wght@0,400;0,600;0,700;1,400&"
    "family=Merriweather:ital,wght@0,400;0,700;1,400&"
    "family=Open+Sans:wght@400;600;700&"
    "family=Outfit:wght@400;500;600;700&"
    "family=Playfair+Display:wght@400;600;700&"
    "family=Source+Sans+3:wght@400;600;700&"
    "display=swap"
)

PDF_CONTENT_MIN_HEIGHT = "285mm"

STUDIO_PDF_PAGE_CSS = f"""
@page {{ size: A4 portrait; margin: 6mm; }}
html.tt-pdf-export {{
  margin: 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  background: #fff;
  --pdf-page-min-height: {PDF_CONTENT_MIN_HEIGHT};
  font-size: calc(16px * var(--font-scale, 1));
  font-family: var(--font-stack, "Inter", system-ui, sans-serif);
}}
body.tt-pdf-export {{
  margin: 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  background: #fff;
  overflow-x: hidden !important;
  overflow-y: visible !important;
  font-family: var(--font-stack, "Inter", system-ui, sans-serif);
}}
body.tt-pdf-export .pdf-wrap,
body.tt-pdf-export .preview-wrap,
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume .resume__mount {{
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0;
  box-sizing: border-box;
  overflow: visible !important;
}}
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume .resume__mount,
body.tt-pdf-export .resume.pdf-exporting .tpl,
body.tt-pdf-export article#resume.resume .tpl {{
  min-height: auto !important;
}}
/* Sidebar / two-column templates — stretch accent column to full page */
body.tt-pdf-export .tpl-classic-sidebar,
body.tt-pdf-export .tpl-executive {{
  min-height: var(--pdf-page-min-height) !important;
}}
body.tt-pdf-export .tpl-tech-focus {{
  min-height: auto !important;
  align-items: stretch !important;
}}
body.tt-pdf-export .tpl-professional-border {{
  min-height: auto !important;
  align-items: stretch !important;
}}
body.tt-pdf-export article#resume.resume {{
  box-shadow: none !important;
  border-radius: 0 !important;
  font-size: var(--pdf-body-size, var(--body-size, 11.5pt)) !important;
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}}
body.tt-pdf-export article#resume.resume .resume__mount {{
  zoom: 1 !important;
  transform: none !important;
}}
body.tt-pdf-export .resume.pdf-exporting .resume__mount {{
  zoom: 1 !important;
}}
/* Sidebar accent columns — full printable page height */
body.tt-pdf-export .tpl-cs-side,
body.tt-pdf-export .tpl-ex-side {{
  min-height: var(--pdf-page-min-height) !important;
}}
body.tt-pdf-export .tpl-tf-side {{
  min-height: auto !important;
  align-self: stretch !important;
}}
body.tt-pdf-export .tpl-pb-side {{
  min-height: auto !important;
  align-self: stretch !important;
}}
body.tt-pdf-export .tpl-high-contrast {{
  min-height: var(--pdf-page-min-height) !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 4px !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-hc-top {{
  background: #111111 !important;
  color: #ffffff !important;
  padding: 1.35rem 1.75rem !important;
  text-align: center !important;
}}
body.tt-pdf-export .tpl-hc-name,
body.tt-pdf-export .tpl-hc-title {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  justify-content: center !important;
  align-items: center !important;
  gap: 0 0.1rem !important;
  margin: 0 !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  align-items: center !important;
  flex: 0 0 auto !important;
  gap: 0.3rem !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row .tpl-contact-icon,
body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row .tpl-contact-fallback {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row .tpl-contact-text {{
  color: #ffffff !important;
  white-space: nowrap !important;
}}
body.tt-pdf-export .tpl-hc-body {{
  flex: 1 1 auto !important;
  min-height: calc(var(--pdf-page-min-height) - 5rem - 4px) !important;
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
}}
body.tt-pdf-export .tpl-hc-side,
body.tt-pdf-export .tpl-hc-main {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  margin: 0 !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-hc-side {{
  width: 26% !important;
  min-height: 100% !important;
  background: #111111 !important;
  color: #ffffff !important;
  padding: 1.25rem 1rem 2rem !important;
}}
body.tt-pdf-export .tpl-hc-main {{
  width: 74% !important;
  padding: 1.5rem 1.5rem 2rem !important;
}}
body.tt-pdf-export .tpl-hc-side .tpl-bullets,
body.tt-pdf-export .tpl-hc-side .tpl-hc-small,
body.tt-pdf-export .tpl-hc-side .tpl-hc-h3 {{
  color: #e5e7eb !important;
  visibility: visible !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-h2--hc {{
  color: #111111 !important;
  border-bottom-color: #111111 !important;
}}
body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-p,
body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-job,
body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-edu-block,
body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-cert,
body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-bullets {{
  display: block !important;
  visibility: visible !important;
  color: #111111 !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-hc-body {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-hc-side,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-hc-main {{
  display: table-cell !important;
  float: none !important;
  margin: 0 !important;
  vertical-align: top !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-hc-side {{
  width: 26% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-hc-main {{
  width: 74% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-hc-body {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-hc-side,
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-hc-main {{
  display: table-cell !important;
  float: none !important;
  margin: 0 !important;
  vertical-align: top !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-hc-side {{
  width: 26% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-hc-main {{
  width: 74% !important;
}}
body.tt-pdf-export .tpl-magazine {{
  min-height: auto !important;
  display: block !important;
  width: 100% !important;
  break-inside: avoid !important;
  page-break-inside: avoid !important;
}}
body.tt-pdf-export .tpl-mz-header {{
  display: grid !important;
  grid-template-columns: 10px 1fr !important;
  width: 100% !important;
  min-height: auto !important;
  break-inside: avoid !important;
  page-break-inside: avoid !important;
  break-after: avoid !important;
  page-break-after: avoid !important;
}}
body.tt-pdf-export .tpl-mz-intro {{
  padding: 1rem 1.35rem 0.85rem !important;
}}
body.tt-pdf-export .tpl-mz-name {{
  font-size: 1.55rem !important;
  line-height: 1.15 !important;
}}
body.tt-pdf-export .tpl-mz-title {{
  font-size: 0.92rem !important;
  margin-top: 0.35rem !important;
}}
body.tt-pdf-export .tpl-mz-accent {{
  background: var(--resume-accent) !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  gap: 0 0.1rem !important;
  margin: 0.45rem 0 0 !important;
  font-size: 0.78rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  align-items: center !important;
  flex: 0 0 auto !important;
  gap: 0.25rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
}}
body.tt-pdf-export .tpl-mz-grid {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
  min-height: auto !important;
  flex: none !important;
  break-inside: auto !important;
  page-break-inside: auto !important;
}}
body.tt-pdf-export .tpl-mz-col,
body.tt-pdf-export .tpl-mz-aside {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  overflow: visible !important;
  min-height: auto !important;
}}
body.tt-pdf-export .tpl-mz-col {{
  width: 58% !important;
  padding: 0.85rem 1rem 1rem !important;
}}
body.tt-pdf-export .tpl-mz-aside {{
  width: 42% !important;
  padding: 0.85rem 0.85rem 1rem !important;
  background: #f8fafc !important;
  border-left: 1px solid #e5e7eb !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-h2 {{
  margin: 0 0 0.35rem !important;
  font-size: 0.82rem !important;
  padding-left: 0.5rem !important;
  border-left-width: 3px !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-h2 + .tpl-mz-h2,
body.tt-pdf-export .tpl-magazine .tpl-mz-lead + .tpl-mz-h2,
body.tt-pdf-export .tpl-magazine .tpl-job + .tpl-mz-h2 {{
  margin-top: 0.65rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-h3 {{
  margin: 0.65rem 0 0.25rem !important;
  font-size: 0.66rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-h3:first-of-type {{
  margin-top: 0 !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-lead {{
  margin: 0 0 0.65rem !important;
  font-size: 0.82rem !important;
  line-height: 1.45 !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-p,
body.tt-pdf-export .tpl-magazine .tpl-job,
body.tt-pdf-export .tpl-magazine .tpl-edu-block,
body.tt-pdf-export .tpl-magazine .tpl-cert,
body.tt-pdf-export .tpl-magazine .tpl-bullets,
body.tt-pdf-export .tpl-magazine .tpl-mz-pills {{
  display: block !important;
  visibility: visible !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-job {{
  margin-bottom: 0.45rem !important;
  break-inside: auto !important;
  page-break-inside: auto !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-job-head {{
  font-size: 0.8rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-bullets {{
  margin: 0.15rem 0 0 !important;
  padding-left: 1rem !important;
  font-size: 0.78rem !important;
  line-height: 1.35 !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-bullets li {{
  margin-bottom: 0.12rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-pills {{
  margin-bottom: 0.15rem !important;
}}
body.tt-pdf-export .tpl-magazine .tpl-mz-pills .tpl-pill {{
  display: inline-block !important;
  font-size: 0.68rem !important;
  padding: 0.12rem 0.45rem !important;
  margin: 0 0.18rem 0.18rem 0 !important;
}}
body.tt-pdf-export .tpl-mz-photo {{
  width: 100% !important;
  max-width: 120px !important;
  height: auto !important;
  aspect-ratio: auto !important;
  margin: 0 auto 0.65rem !important;
  display: block !important;
  border-radius: 4px !important;
  object-fit: cover !important;
  border-width: 2px !important;
}}
body.tt-pdf-export .tpl-aurora {{
  min-height: var(--pdf-page-min-height) !important;
  display: flex !important;
  flex-direction: column !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-au-hero {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 1.5rem !important;
  padding: 2rem 1.75rem !important;
  background: var(--resume-accent) !important;
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-au-name,
body.tt-pdf-export .tpl-au-tagline {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  gap: 0 0.1rem !important;
  margin: 0.5rem 0 0 !important;
  font-size: 0.85rem !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  align-items: center !important;
  flex: 0 0 auto !important;
  gap: 0.3rem !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row .tpl-contact-icon,
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row .tpl-contact-fallback,
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row .tpl-contact-text {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-au-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
}}
body.tt-pdf-export .tpl-au-photo {{
  width: 100px !important;
  height: 100px !important;
  flex-shrink: 0 !important;
  border-radius: 20px !important;
  border: 3px solid rgba(255, 255, 255, 0.5) !important;
  object-fit: cover !important;
}}
body.tt-pdf-export .tpl-au-body {{
  padding: 1.5rem 1.5rem 2rem !important;
  display: block !important;
}}
body.tt-pdf-export .tpl-au-card {{
  display: block !important;
  visibility: visible !important;
  break-inside: avoid !important;
  page-break-inside: avoid !important;
  margin-bottom: 1rem !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-au-h2 {{
  color: var(--resume-accent) !important;
}}
body.tt-pdf-export .tpl-aurora .tpl-p,
body.tt-pdf-export .tpl-aurora .tpl-job,
body.tt-pdf-export .tpl-aurora .tpl-edu-block,
body.tt-pdf-export .tpl-aurora .tpl-cert,
body.tt-pdf-export .tpl-aurora .tpl-bullets {{
  display: block !important;
  visibility: visible !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-au-row {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  border-collapse: separate !important;
  border-spacing: 1rem 0 !important;
  margin-bottom: 1rem !important;
}}
body.tt-pdf-export .tpl-au-row .tpl-au-card--half {{
  display: table-cell !important;
  width: 50% !important;
  vertical-align: top !important;
}}
/* Undo responsive breakpoints — PDF page is narrower than 1100px */
body.tt-pdf-export article#resume.resume .tpl-colored-header {{
  min-height: auto !important;
}}
body.tt-pdf-export .tpl-ch-row {{
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
  margin-bottom: 0.35rem !important;
}}
body.tt-pdf-export .tpl-ch-row::after {{
  content: "" !important;
  display: table !important;
  clear: both !important;
}}
body.tt-pdf-export .tpl-ch-row > .tpl-sec {{
  display: block !important;
  float: left !important;
  width: 49% !important;
  min-width: 0 !important;
  max-width: 49% !important;
  box-sizing: border-box !important;
  padding-right: 0.65rem !important;
  vertical-align: top !important;
}}
body.tt-pdf-export .tpl-ch-row > .tpl-sec:last-child {{
  float: right !important;
  padding-right: 0 !important;
  padding-left: 0.65rem !important;
}}
body.tt-pdf-export .tpl-ch-row > .tpl-sec:only-child {{
  float: none !important;
  width: 100% !important;
  max-width: 100% !important;
  padding: 0 !important;
}}
body.tt-pdf-export .tpl-colored-header {{
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  min-height: auto !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-bar,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body {{
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  min-height: auto !important;
  height: auto !important;
  max-height: none !important;
  box-sizing: border-box !important;
  overflow: visible !important;
  position: static !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-bar {{
  flex: 0 0 auto !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-body {{
  color: var(--text, #1a1a2e) !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-body > .tpl-sec {{
  display: block !important;
  visibility: visible !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-row > .tpl-sec {{
  display: block !important;
  visibility: visible !important;
  width: 49% !important;
  max-width: 49% !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-h2,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-p,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-job,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-edu-block,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-cert,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-bullets,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-ch-subsec,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-ch-stack,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-ch-lang-list {{
  display: block !important;
  visibility: visible !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-ch-subsec,
body.tt-pdf-export .tpl-colored-header .tpl-ch-body .tpl-ch-stack {{
  width: 100% !important;
  max-width: 100% !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-h2 {{
  color: var(--resume-accent) !important;
  border-bottom: 2px solid var(--resume-accent) !important;
  padding-bottom: 0.3rem !important;
  margin: 0 0 0.45rem !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-job-head {{
  display: flex !important;
  flex-direction: row !important;
  justify-content: space-between !important;
  align-items: baseline !important;
  gap: 0.5rem !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-job-dates {{
  white-space: nowrap !important;
  flex-shrink: 0 !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-lang-chip {{
  background: rgba(var(--accent-rgb), 0.1) !important;
  border: 1px solid rgba(var(--accent-rgb), 0.28) !important;
  border-radius: 999px !important;
  padding: 0.28rem 0.72rem !important;
  font-size: 0.82rem !important;
  line-height: 1.35 !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-lang-name {{
  font-weight: 600 !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-lang-level {{
  opacity: 0.78 !important;
  font-size: 0.78rem !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-sec--full {{
  display: block !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-ch-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  justify-content: center !important;
  align-items: center !important;
  gap: 0 1rem !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  flex: 0 0 auto !important;
  align-items: center !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-contact-row .tpl-contact-icon {{
  color: var(--resume-accent-text, #ffffff) !important;
}}
body.tt-pdf-export .tpl-colored-header .tpl-ch-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-ch-row--bottom {{
  width: 100% !important;
}}
body.tt-pdf-export .tpl-ch-lang-list {{
  display: block !important;
  line-height: 1.7;
}}
body.tt-pdf-export .tpl-ch-lang-chip {{
  display: inline-block !important;
  vertical-align: top;
  margin: 0 0.35rem 0.35rem 0 !important;
}}
body.tt-pdf-export .tpl-ch-stack {{
  display: block !important;
  width: 100% !important;
  min-height: auto !important;
}}
body.tt-pdf-export .tpl-ch-subsec {{
  display: block !important;
}}
body.tt-pdf-export .tpl-ch-subsec {{
  width: 100% !important;
  margin-bottom: 0.85rem !important;
}}
body.tt-pdf-export .tpl-ch-subsec:last-child {{
  margin-bottom: 0 !important;
}}
body.tt-pdf-export .tpl-ms-grid {{
  display: block !important;
  width: 100% !important;
  padding: 1.25rem 1.1rem 1.5rem !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-ms-row {{
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
  margin-bottom: 1rem !important;
}}
body.tt-pdf-export .tpl-ms-row::after {{
  content: "" !important;
  display: table !important;
  clear: both !important;
}}
body.tt-pdf-export .tpl-ms-row > .tpl-sec {{
  display: block !important;
  float: left !important;
  width: 49% !important;
  max-width: 49% !important;
  min-width: auto !important;
  box-sizing: border-box !important;
  padding-right: 0.65rem !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-ms-row > .tpl-sec:last-child {{
  float: right !important;
  padding-right: 0 !important;
  padding-left: 0.65rem !important;
}}
body.tt-pdf-export .tpl-ms-row > .tpl-sec:only-child {{
  float: none !important;
  width: 100% !important;
  max-width: 100% !important;
  padding: 0 !important;
}}
body.tt-pdf-export .tpl-ms-grid > .tpl-sec.tpl-ms-span2,
body.tt-pdf-export .tpl-ms-span2 {{
  display: block !important;
  clear: both !important;
  float: none !important;
  width: 100% !important;
  max-width: 100% !important;
  min-width: auto !important;
  margin-bottom: 1rem !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-modern-split {{
  display: block !important;
  min-height: auto !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-ms-top {{
  display: block !important;
  width: 100% !important;
  background: var(--resume-accent) !important;
  color: var(--resume-accent-text, #ffffff) !important;
  padding: 1.15rem 1.25rem !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-ms-brand {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 1rem !important;
}}
body.tt-pdf-export .tpl-ms-photo {{
  flex-shrink: 0 !important;
  width: 72px !important;
  height: 72px !important;
}}
body.tt-pdf-export .tpl-ms-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  align-items: center !important;
  gap: 0 1rem !important;
  width: 100% !important;
  margin-top: 0.75rem !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-ms-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  flex: 0 0 auto !important;
  align-items: center !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-ms-contact-row .tpl-contact-icon {{
  color: var(--resume-accent-text, #ffffff) !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-ms-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-h2 {{
  color: var(--resume-accent) !important;
  border-bottom: 2px solid var(--resume-accent) !important;
  padding-bottom: 0.3rem !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-p,
body.tt-pdf-export .tpl-modern-split .tpl-bullets,
body.tt-pdf-export .tpl-modern-split .tpl-job,
body.tt-pdf-export .tpl-modern-split .tpl-edu-block,
body.tt-pdf-export .tpl-modern-split .tpl-cert {{
  color: #111111 !important;
  display: block !important;
  visibility: visible !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-ms-grid > .tpl-sec.tpl-ms-span2:last-child .tpl-p {{
  margin-top: 0.35rem !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-job-head {{
  display: flex !important;
  flex-direction: row !important;
  justify-content: space-between !important;
  align-items: baseline !important;
  gap: 0.5rem !important;
}}
body.tt-pdf-export .tpl-modern-split .tpl-ms-grid .tpl-sec {{
  display: block !important;
  visibility: visible !important;
  overflow: visible !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-ap-grid {{
  display: grid !important;
  grid-template-columns: 1fr 230px !important;
  gap: 1rem !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-gg-layout {{
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  gap: 1rem !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-gg-main {{
  grid-column: 1 / -1 !important;
}}
/* WeasyPrint (default): keep CSS grid/flex layouts from prototype */
body.tt-pdf-export .preview-wrap {{
  display: block !important;
  padding: 0 !important;
  width: 100% !important;
  max-width: 100% !important;
}}
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume .resume__mount,
body.tt-pdf-export article#resume.resume .tpl-classic-sidebar {{
  width: 100% !important;
  max-width: 100% !important;
}}
/* Classic sidebar: table layout fills page width reliably in WeasyPrint/wkhtmltopdf */
body.tt-pdf-export .tpl-classic-sidebar {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-side,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  margin: 0 !important;
  min-width: 0 !important;
  max-width: none !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-side {{
  width: 30% !important;
  padding: 1.15rem 0.85rem !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main {{
  width: 70% !important;
  padding: 1.15rem 1.1rem 1.35rem 1.25rem !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-sec,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-h2,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-p,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-job,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-edu-block,
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-cert {{
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}}
/* Tech focus: table layout fills page width reliably in WeasyPrint/wkhtmltopdf */
body.tt-pdf-export .tpl-tech-focus {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
  grid-template-columns: none !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-side,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  margin: 0 !important;
  min-width: 0 !important;
  max-width: none !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-side {{
  width: 28% !important;
  padding: 1rem 0.75rem 1.5rem !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main {{
  width: 72% !important;
  padding: 0 0.75rem 1.5rem 1rem !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-sec,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-h2,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-p,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-job,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-edu-block,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-cert,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-head,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-name,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-title {{
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-classic-sidebar {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-classic-sidebar .tpl-cs-side,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-classic-sidebar .tpl-cs-main {{
  display: table-cell !important;
  float: none !important;
  width: auto !important;
  margin: 0 !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-classic-sidebar .tpl-cs-side {{
  width: 30% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-classic-sidebar .tpl-cs-main {{
  width: 70% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-tech-focus {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-tech-focus .tpl-tf-side,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-tech-focus .tpl-tf-main {{
  display: table-cell !important;
  float: none !important;
  margin: 0 !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  max-width: none !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-tech-focus .tpl-tf-side {{
  width: 28% !important;
  padding: 1rem 0.75rem 1.5rem !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-tech-focus .tpl-tf-main {{
  width: 72% !important;
  padding: 0 0.75rem 1.5rem 1rem !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-professional-border {{
  display: grid !important;
  grid-template-columns: 1fr 28% !important;
  width: 100% !important;
  align-items: stretch !important;
  min-height: auto !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-professional-border > .tpl-pb-main,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-professional-border > .tpl-pb-side {{
  float: none !important;
  width: auto !important;
  margin: 0 !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-executive {{
  display: grid !important;
  grid-template-columns: 28% 1fr !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-executive .tpl-ex-side,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-executive .tpl-ex-main {{
  float: none !important;
  width: auto !important;
  margin: 0 !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  min-height: auto !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid .tpl-mz-col,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid .tpl-mz-aside {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  min-height: auto !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid .tpl-mz-col {{
  width: 58% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid .tpl-mz-aside {{
  width: 42% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-magazine {{
  min-height: auto !important;
  display: block !important;
}}
/* wkhtmltopdf: float columns (grid on div/aside is unreliable) */
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-classic-sidebar {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-classic-sidebar::after {{
  content: none !important;
  display: none !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-classic-sidebar .tpl-cs-side {{
  display: table-cell !important;
  float: none !important;
  width: 30% !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.85rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-classic-sidebar .tpl-cs-main {{
  display: table-cell !important;
  float: none !important;
  width: 70% !important;
  margin-left: 0 !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  max-width: none !important;
  padding: 1.15rem 1.1rem 1.35rem 1.25rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-tech-focus {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-tech-focus::after {{
  content: none !important;
  display: none !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-tech-focus .tpl-tf-side {{
  display: table-cell !important;
  float: none !important;
  width: 28% !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  padding: 1rem 0.75rem 1.5rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-tech-focus .tpl-tf-main {{
  display: table-cell !important;
  float: none !important;
  width: 72% !important;
  margin-left: 0 !important;
  vertical-align: top !important;
  box-sizing: border-box !important;
  max-width: none !important;
  padding: 0 0.75rem 1.5rem 1rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-professional-border {{
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-professional-border::after {{
  content: "";
  display: table;
  clear: both;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-professional-border > .tpl-pb-main {{
  margin-right: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-professional-border > .tpl-pb-side {{
  float: right !important;
  width: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-executive {{
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-executive::after {{
  content: "";
  display: table;
  clear: both;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-executive .tpl-ex-side {{
  float: left !important;
  width: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.9rem 1.5rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-executive .tpl-ex-main {{
  margin-left: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 0 1rem 1.5rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-mz-grid {{
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-mz-grid::after {{
  content: "";
  display: table;
  clear: both;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-mz-grid .tpl-mz-col {{
  float: left !important;
  width: 58% !important;
  box-sizing: border-box !important;
  padding: 1.15rem 1rem 1.5rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-mz-grid .tpl-mz-aside {{
  float: right !important;
  width: 42% !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.9rem 1.5rem !important;
}}
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume * {{
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
  font-synthesis: none;
}}
body.tt-pdf-export .tpl-bullets,
body.tt-pdf-export .tpl-bullets li,
body.tt-pdf-export .tpl-job,
body.tt-pdf-export .tpl-job strong,
body.tt-pdf-export .tpl-p,
body.tt-pdf-export .tpl-h2,
body.tt-pdf-export .tpl-cs-name,
body.tt-pdf-export .tpl-cs-contact,
body.tt-pdf-export .tpl-cs-h3 {{
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}}
body.tt-pdf-export .resume[data-template="elegant-serif"],
body.tt-pdf-export .resume[data-template="ledger"] {{
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}}
body.tt-pdf-export .tpl-geo-split {{
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-geometric {{
  min-height: auto !important;
  width: 100% !important;
  max-width: 100% !important;
  padding-bottom: 1.5rem !important;
}}
body.tt-pdf-export .tpl-geo-head {{
  display: flex !important;
  align-items: center !important;
  gap: 1.25rem !important;
  padding: 1.5rem 1.75rem !important;
  border-left: 6px solid var(--resume-accent) !important;
  background: rgba(var(--accent-rgb), 0.15) !important;
  box-sizing: border-box !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-geo-text {{
  flex: 1 1 auto !important;
  min-width: 0 !important;
}}
body.tt-pdf-export .tpl-geo-title {{
  margin: 0.25rem 0 0 !important;
  font-weight: 600 !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  gap: 0 0.1rem !important;
  margin: 0.5rem 0 0 !important;
  font-size: 0.85rem !important;
  color: #6b7280 !important;
  width: 100% !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-head + .tpl-sec {{
  margin-top: 1.25rem !important;
}}
body.tt-pdf-export .tpl-geo-photo {{
  width: 88px !important;
  height: 88px !important;
  flex-shrink: 0 !important;
  border-radius: 8px !important;
  border: 3px solid var(--resume-accent) !important;
  object-fit: cover !important;
}}
body.tt-pdf-export .tpl-geo-name {{
  color: var(--resume-accent) !important;
}}
body.tt-pdf-export .tpl-geo-h2 {{
  display: inline-block !important;
  background: var(--resume-accent) !important;
  color: var(--resume-accent-text, #ffffff) !important;
  padding: 0.25rem 0.85rem !important;
  font-weight: 800 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
}}
body.tt-pdf-export .tpl-geo-layout {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  max-width: 100% !important;
  padding: 0 1.75rem !important;
  box-sizing: border-box !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
  page-break-inside: auto !important;
  break-inside: auto !important;
}}
body.tt-pdf-export .tpl-geo-main,
body.tt-pdf-export .tpl-geo-aside {{
  display: table-cell !important;
  float: none !important;
  vertical-align: top !important;
  margin: 0 !important;
  min-width: 0 !important;
  max-width: none !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-geo-main {{
  width: 66% !important;
  padding-right: 1rem !important;
}}
body.tt-pdf-export .tpl-geo-aside {{
  width: 34% !important;
  background: rgba(var(--accent-rgb), 0.07) !important;
  border-left: 4px solid var(--resume-accent) !important;
  padding: 1rem 1rem 1.25rem !important;
  text-align: left !important;
  page-break-inside: avoid !important;
  break-inside: avoid !important;
}}
body.tt-pdf-export .tpl-geo-aside .tpl-geo-h2 {{
  display: inline-block !important;
  text-align: left !important;
}}
body.tt-pdf-export .tpl-geo-pills {{
  display: flex !important;
  flex-wrap: wrap !important;
  justify-content: flex-start !important;
  align-items: center !important;
  gap: 0.35rem !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-geo-pills .tpl-pill {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  visibility: visible !important;
  margin: 0 !important;
  min-height: 1.65rem !important;
  padding: 0.28rem 0.75rem !important;
  line-height: 1.2 !important;
  text-align: center !important;
  box-sizing: border-box !important;
  vertical-align: middle !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-sec {{
  padding: 0 1.75rem !important;
  display: block !important;
  visibility: visible !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-main .tpl-sec {{
  padding: 0 !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  align-items: center !important;
  gap: 0.3rem !important;
  flex: 0 0 auto !important;
  vertical-align: middle !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact-row .tpl-contact-icon {{
  color: #6b7280 !important;
  flex-shrink: 0 !important;
  margin-top: 0 !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact .tpl-contact-item {{
  display: inline-flex !important;
  align-items: center !important;
  gap: 0.3rem !important;
  vertical-align: middle !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-contact .tpl-contact-icon {{
  color: #6b7280 !important;
  flex-shrink: 0 !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-p,
body.tt-pdf-export .tpl-geometric .tpl-job,
body.tt-pdf-export .tpl-geometric .tpl-edu-block,
body.tt-pdf-export .tpl-geometric .tpl-cert,
body.tt-pdf-export .tpl-geometric .tpl-bullets {{
  display: block !important;
  visibility: visible !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-geometric .tpl-geo-main .tpl-sec {{
  page-break-inside: avoid !important;
  break-inside: avoid !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-geo-layout {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-geo-main,
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-geo-aside {{
  display: table-cell !important;
  float: none !important;
  margin: 0 !important;
  vertical-align: top !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-geo-main {{
  width: 66% !important;
}}
body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-geo-aside {{
  width: 34% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-geo-layout {{
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-geo-main,
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-geo-aside {{
  display: table-cell !important;
  float: none !important;
  margin: 0 !important;
  vertical-align: top !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-geo-main {{
  width: 66% !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-geo-aside {{
  width: 34% !important;
}}
body.tt-pdf-export .tpl-sec--half,
body.tt-pdf-export .tpl-ch-body,
body.tt-pdf-export .tpl-ch-row > *,
body.tt-pdf-export .tpl-pb-main,
body.tt-pdf-export .tpl-pb-side,
body.tt-pdf-export .tpl-cs-side,
body.tt-pdf-export .tpl-cs-main {{
  min-width: 0 !important;
  overflow: visible !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main {{
  max-width: none !important;
}}
body.tt-pdf-export .tpl-ch-body {{
  padding: 1.25rem 1.1rem 1.5rem !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-main {{
  min-width: auto !important;
  max-width: none !important;
  overflow: visible !important;
  padding-bottom: 1.5rem !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-side {{
  min-width: auto !important;
  min-height: auto !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-main .tpl-sec:last-child {{
  margin-bottom: 0 !important;
  page-break-inside: avoid !important;
}}
body.tt-pdf-export .tpl-pb-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  gap: 0 1rem !important;
  width: 100% !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  flex: 0 0 auto !important;
  align-items: center !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-contact-row .tpl-contact-icon {{
  color: var(--resume-accent) !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-h2,
body.tt-pdf-export .tpl-professional-border .tpl-p,
body.tt-pdf-export .tpl-professional-border .tpl-job,
body.tt-pdf-export .tpl-professional-border .tpl-edu-block,
body.tt-pdf-export .tpl-professional-border .tpl-cert,
body.tt-pdf-export .tpl-professional-border .tpl-bullets,
body.tt-pdf-export .tpl-professional-border .tpl-pb-h3 {{
  color: #111111 !important;
  display: block !important;
  visibility: visible !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}}
body.tt-pdf-export .tpl-professional-border .tpl-pb-main {{
  overflow: visible !important;
  padding-bottom: 2rem !important;
}}
body.tt-pdf-export[data-pdf-engine="wkhtmltopdf"] .tpl-professional-border {{
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-h2 {{
  color: var(--resume-accent) !important;
  border-bottom: 2px solid var(--resume-accent) !important;
  padding-bottom: 0.3rem !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-p,
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-bullets,
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-job,
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-edu-block,
body.tt-pdf-export .tpl-bold-header .tpl-bh-body .tpl-cert {{
  color: #111111 !important;
  display: block !important;
  visibility: visible !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-bar {{
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-name,
body.tt-pdf-export .tpl-bold-header .tpl-bh-title,
body.tt-pdf-export .tpl-bold-header .tpl-bh-contact {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-h2,
body.tt-pdf-export .tpl-p,
body.tt-pdf-export .tpl-bullets,
body.tt-pdf-export .tpl-job {{
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}}
body.tt-pdf-export .tpl-min-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  align-items: center !important;
  gap: 0 1.1rem !important;
  width: 100% !important;
  line-height: 1.45;
}}
body.tt-pdf-export .tpl-min-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
  align-items: center !important;
  max-width: none !important;
  min-width: 0 !important;
  margin: 0 !important;
}}
body.tt-pdf-export .tpl-min-contact-row .tpl-contact-icon {{
  margin-top: 0 !important;
}}
body.tt-pdf-export .tpl-min-contact-row .tpl-contact-text {{
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export .tpl-min-tags {{
  display: block !important;
  line-height: 1.6;
}}
body.tt-pdf-export .tpl-min-tags .tpl-pill {{
  display: inline-block !important;
  vertical-align: top;
  margin: 0 0.35rem 0.35rem 0 !important;
}}
body.tt-pdf-export .tpl-cs-contact .tpl-contact-item {{
  display: flex !important;
  align-items: flex-start !important;
  gap: 0.35rem !important;
  max-width: 100% !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-contact .tpl-contact-icon {{
  color: var(--resume-accent-text, #ffffff) !important;
  flex-shrink: 0 !important;
  margin-top: 1px !important;
}}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-contact .tpl-contact-icon svg {{
  fill: currentColor !important;
}}
/* PDF engines: inline SVG contact icons often fail — show text fallbacks instead */
body.tt-pdf-export .tpl-contact-icon svg {{
  display: none !important;
}}
body.tt-pdf-export .tpl-contact-icon .tpl-contact-fallback {{
  display: inline-flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 0.75rem !important;
  font-weight: 700 !important;
  line-height: 1 !important;
  font-family: Arial, Helvetica, sans-serif !important;
  width: 0.9rem !important;
  height: 0.9rem !important;
  min-width: 0.9rem !important;
  min-height: 0.9rem !important;
  flex: 0 0 auto !important;
}}
body.tt-pdf-export .tpl-contact-fallback {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  line-height: 1 !important;
  font-family: Arial, Helvetica, sans-serif !important;
  width: 0.85rem !important;
  height: 0.85rem !important;
  flex: 0 0 auto !important;
}}
body.tt-pdf-export .tpl-contact-icon-img {{
  display: inline-block !important;
  width: 0.85rem !important;
  height: 0.85rem !important;
  flex: 0 0 auto !important;
}}
body.tt-pdf-export .tpl-bh-contact-row {{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  justify-content: center !important;
  align-items: center !important;
  gap: 0 1rem !important;
  width: 100% !important;
  margin-top: 0.5rem !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-contact-row .tpl-contact-item {{
  display: inline-flex !important;
  flex: 0 0 auto !important;
  align-items: center !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-contact-row .tpl-contact-icon,
body.tt-pdf-export .tpl-bold-header .tpl-bh-contact-row .tpl-contact-fallback {{
  color: #ffffff !important;
}}
body.tt-pdf-export .tpl-bold-header .tpl-bh-contact-row .tpl-contact-text {{
  color: #ffffff !important;
  white-space: nowrap !important;
}}
body.tt-pdf-export article#resume.resume {{
  max-width: none !important;
  overflow-wrap: normal !important;
  word-break: normal !important;
}}
body.tt-pdf-export article#resume.resume .tpl-tech-focus {{
  width: 100% !important;
  max-width: 100% !important;
}}
body.tt-pdf-export article#resume.resume.pdf-exporting .tpl-tech-focus .tpl-tf-main {{
  display: table-cell !important;
  float: none !important;
  width: 72% !important;
  margin-left: 0 !important;
  max-width: none !important;
}}
body.tt-pdf-export article#resume.resume.pdf-exporting .tpl-tech-focus .tpl-tf-side {{
  display: table-cell !important;
  float: none !important;
  width: 28% !important;
  margin-left: 0 !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-side {{
  background: #e5e7eb !important;
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main {{
  overflow: visible !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-contact .tpl-contact-item {{
  display: flex !important;
  align-items: flex-start !important;
  gap: 0.35rem !important;
  max-width: 100% !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-contact .tpl-contact-icon {{
  color: var(--resume-accent) !important;
  flex-shrink: 0 !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-skill-bar {{
  display: block !important;
  height: 6px !important;
  background: #d1d5db !important;
  border-radius: 999px !important;
  overflow: hidden !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-skill-bar span {{
  display: block !important;
  height: 100% !important;
  background: var(--resume-accent) !important;
  border-radius: 999px !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-h2 {{
  color: var(--resume-accent) !important;
  border-bottom: 2px solid var(--resume-accent) !important;
  padding-bottom: 0.3rem !important;
}}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-p,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-bullets,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-job,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-edu-block,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-cert,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-name,
body.tt-pdf-export .tpl-tech-focus .tpl-tf-title {{
  color: #111111 !important;
  display: block !important;
  visibility: visible !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}}
body.tt-pdf-export .tpl-edu-block strong sup {{
  font-size: 0.62em !important;
  vertical-align: super !important;
  line-height: 0 !important;
  font-weight: 700 !important;
}}
body.tt-pdf-export img[class*="tpl-"],
body.tt-pdf-export .tpl-photo,
body.tt-pdf-export .tpl-photo--placeholder,
body.tt-pdf-export .tpl-photo-initial {{
  display: block !important;
  visibility: visible !important;
}}
body.tt-pdf-export .tpl-pb-avatar,
body.tt-pdf-export .tpl-ms-photo,
body.tt-pdf-export .tpl-avatar,
body.tt-pdf-export .tpl-cs-side img,
body.tt-pdf-export .tpl-pb-side img,
body.tt-pdf-export .tpl-geo-photo,
body.tt-pdf-export .tpl-au-photo,
body.tt-pdf-export .tpl-mz-photo,
body.tt-pdf-export .tpl-ex-photo,
body.tt-pdf-export .tpl-st-photo,
body.tt-pdf-export .tpl-nv-photo,
body.tt-pdf-export .tpl-fo-photo,
body.tt-pdf-export .tpl-gg-photo {{
  display: block !important;
  visibility: visible !important;
  object-fit: cover !important;
  max-width: none !important;
}}
body.tt-pdf-export .tpl-pb-avatar,
body.tt-pdf-export img.tpl-pb-avatar {{
  width: 100px !important;
  height: 100px !important;
  border-radius: 50% !important;
}}
body.tt-pdf-export .tpl-ms-photo,
body.tt-pdf-export img.tpl-ms-photo {{
  width: 72px !important;
  height: 72px !important;
  border-radius: 12px !important;
}}
body.tt-pdf-export .tpl-avatar,
body.tt-pdf-export img.tpl-avatar {{
  width: 88px !important;
  height: 88px !important;
  border-radius: 50% !important;
}}
body.tt-pdf-export .tpl-photo--placeholder {{
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}}
body.tt-pdf-export .tpl-photo-initial {{
  display: block !important;
  visibility: visible !important;
  font-size: 1.35rem !important;
  font-weight: 700 !important;
  line-height: 1 !important;
  color: var(--resume-accent) !important;
}}
"""


def studio_resume_pdf_stylesheet_text() -> str:
    """Load prototype CSS for inline PDF/preview HTML (WeasyPrint ignores file:// links)."""
    from django.contrib.staticfiles import finders

    css_path = finders.find("resume-builder-prototype/styles.css")
    if not css_path:
        return ""
    try:
        return Path(css_path).read_text(encoding="utf-8")
    except OSError:
        return ""


def studio_pdf_template_context(
    mount_html: str,
    template_id: str,
    pack: dict,
) -> dict:
    """Shared context for studio PDF shell template (matches live preview theme)."""
    from django.conf import settings

    engine = (getattr(settings, "RESUME_PDF_ENGINE", "weasyprint") or "weasyprint").strip().lower()
    return {
        "studio_google_fonts_href": studio_pdf_google_fonts_href(pack),
        "studio_embedded_fonts_css": studio_pdf_embedded_fonts_css(pack),
        "studio_resume_css_inline": studio_resume_pdf_stylesheet_text(),
        "studio_root_style": studio_pack_root_css_block(pack),
        "studio_pdf_page_css": STUDIO_PDF_PAGE_CSS,
        "studio_mount_html": mount_html,
        "studio_template_id": template_id,
        "studio_pdf_engine": engine,
    }


def studio_pack_root_css_block(pack: dict) -> str:
    accent = studio_pack_accent_hex(pack)
    r, g, b = _hex_to_rgb_triplet(accent)
    font = studio_pack_font_stack(pack)
    align = (pack.get("textAlign") or "start").strip().lower()
    if align not in ("start", "center", "end", "justify"):
        align = "start"
    body_size, font_scale = studio_pack_font_size_vars(pack)
    pdf_body_size = studio_pack_effective_body_size(pack)
    return (
        f":root{{--accent:{accent};--accent-contrast:#ffffff;--accent-rgb:{r}, {g}, {b};"
        f"--font-stack:{font};--resume-text-align:{align};"
        f"--body-size:{body_size};--pdf-body-size:{pdf_body_size};--font-scale:{font_scale};}}"
    )


def studio_proto_pack_to_mount_html(pack: dict) -> tuple[str, str]:
    rd = pack.get("resume") if isinstance(pack.get("resume"), dict) else {}
    requested = (pack.get("template") or "classic-sidebar").strip().lower()
    tid = resolve_studio_template_id(requested)
    return TPL_RENDERERS[tid](rd), requested


def build_studio_render_pack(resume, request=None, *, template_override: str | None = None) -> dict:
    """Fresh resumeData + layout prefs for preview/PDF (always current DB state)."""
    from users.resume_payload import (
        DEFAULT_STUDIO_EMBED_FONT,
        resume_studio_prototype_payload,
        studio_prefs_from_resume_record,
    )

    payload = resume_studio_prototype_payload(
        resume, request, ignore_studio_proto_merge=True
    )
    hobbies = str(payload.get("hobbies") or "").strip()
    if not hobbies:
        interests = str(payload.get("interests") or "").strip()
        if interests:
            payload = dict(payload)
            payload["hobbies"] = interests
    if request is not None:
        from users.resume_pdf_service import embed_resume_photo_data_uri

        user = getattr(resume, "user", None)
        payload = embed_resume_photo_data_uri(payload, resume, user, request=request)
    prefs = studio_prefs_from_resume_record(resume)
    tid = (template_override or prefs.get("template") or "classic-sidebar").strip().lower()
    align = (prefs.get("textAlign") or "start").strip().lower()
    if align not in ("start", "center", "end", "justify"):
        align = "start"
    return {
        "resume": payload,
        "template": tid,
        "color": (prefs.get("color") or "teal").strip().lower(),
        "font": (prefs.get("font") or DEFAULT_STUDIO_EMBED_FONT).strip(),
        "textAlign": align,
        "fontSize": (prefs.get("fontSize") or "standard").strip().lower(),
    }


def studio_render_html_for_resume(
    resume, request=None, *, template_override: str | None = None
) -> tuple[str, str, dict]:
    pack = build_studio_render_pack(resume, request, template_override=template_override)
    mount_html, template_id = studio_proto_pack_to_mount_html(pack)
    return mount_html, template_id, pack


def studio_resume_uses_proto_layout(resume) -> bool:
    return studio_proto_pack_from_resume(resume) is not None
