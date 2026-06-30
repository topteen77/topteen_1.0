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


_PLACEHOLDER_DASHES = frozenset({"—", "-", "–"})


def _has_display_text(value: Any) -> bool:
    s = str(value or "").strip()
    return bool(s) and s not in _PLACEHOLDER_DASHES


def _join_display(parts: list[Any], sep: str = " · ") -> str:
    bits = [_esc(p) for p in parts if _has_display_text(p)]
    return sep.join(bits)


def _photo_html(d: dict, class_name: str) -> str:
    ph = (d.get("photo") or "").strip()
    if ph:
        return f'<img class="{class_name}" src="{_esc(ph)}" alt="" />'
    return f'<div class="{class_name} tpl-photo tpl-photo--placeholder" aria-hidden="true"></div>'


def _contact_parts(d: dict) -> list[str]:
    out: list[str] = []
    for k in ("phone", "email", "address", "linkedin", "website"):
        v = (d.get(k) or "").strip()
        if v:
            out.append(_esc(v))
    return out


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
    parts: list[str] = []
    for exp in d.get("experience") or []:
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
        deg = _esc(ed.get("degree") or "")
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


def _experience_timeline_html(d: dict) -> str:
    parts: list[str] = []
    for exp in d.get("experience") or []:
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


def _join_visible(parts: list[str], separator: str = "") -> str:
    return separator.join(p for p in parts if (p or "").strip())


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
    title_html = (
        f'<span class="tpl-ico">{icon}</span> {CAREER_OBJECTIVE_TITLE}' if icon else None
    )
    return _sec_text(CAREER_OBJECTIVE_TITLE, d.get("summary"), title_html=title_html, **kwargs)


def _sec_experience(d: dict, class_job: str = "tpl-job", **kwargs: Any) -> str:
    return _sec_block("Experience", _experience_html(d, class_job), **kwargs)


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
    return _sec_text("Interests", d.get("interests"), **kwargs)


def _sec_hobbies(d: dict, **kwargs: Any) -> str:
    return _sec_text("Hobbies", d.get("hobbies"), **kwargs)


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
    contact = " · ".join(_contact_parts(d))
    sections = _join_visible(
        [
            _sec_summary(d, h2_class="tpl-h2 tpl-h2--center"),
            _sec_experience(d, h2_class="tpl-h2 tpl-h2--center", class_job="tpl-job tpl-job--min"),
            _sec_education(d, h2_class="tpl-h2 tpl-h2--center"),
            _sec_skills_list(
                d, h2_class="tpl-h2 tpl-h2--center", ul_class="tpl-bullets tpl-bullets--center"
            ),
            _sec_certifications(d, h2_class="tpl-h2 tpl-h2--center"),
            _sec_languages(
                d, h2_class="tpl-h2 tpl-h2--center", ul_class="tpl-bullets tpl-bullets--center"
            ),
            _sec_hobbies(d, h2_class="tpl-h2 tpl-h2--center"),
            _sec_interests(d, h2_class="tpl-h2 tpl-h2--center"),
        ],
        '<hr class="tpl-min-rule" />',
    )
    header_rule = '<hr class="tpl-min-rule" />' if sections else ""
    return (
        f'<div class="tpl tpl-minimalist"><header class="tpl-min-head">'
        f'<h1 class="tpl-min-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-min-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-min-contact">{contact}</p></header>{header_rule}{sections}</div>'
    )


def _tpl_classic_sidebar(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
    return (
        f'<div class="tpl tpl-classic-sidebar"><aside class="tpl-cs-side">{_photo_html(d, "tpl-avatar")}'
        f'<h1 class="tpl-cs-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-cs-title">{_esc(d.get("headline"))}</p>'
        f'<ul class="tpl-cs-contact">{citems}</ul>'
        f'{_aside_skills(d)}{_aside_languages(d)}'
        f'</aside><div class="tpl-cs-main">'
        f'{_sec_summary(d)}{_sec_experience(d)}{_sec_education(d)}'
        f'{_sec_certifications(d)}{_sec_hobbies(d)}{_sec_interests(d)}'
        f"</div></div>"
    )


def _tpl_colored_header(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    exp_sec = _sec_experience(d, wrap_class="tpl-sec tpl-sec--half")
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    edu_skills_parts: list[str] = []
    if edu_html.strip():
        edu_skills_parts.append(f'<h2 class="tpl-h2">Education</h2>{edu_html}')
    if skills_html.strip():
        spaced = " tpl-h2--spaced" if edu_html.strip() else ""
        edu_skills_parts.append(
            f'<h2 class="tpl-h2{spaced}">Skills</h2><ul class="tpl-bullets">{skills_html}</ul>'
        )
    edu_skills_sec = (
        f'<section class="tpl-sec tpl-sec--half">{"".join(edu_skills_parts)}</section>'
        if edu_skills_parts
        else ""
    )
    row = _join_visible([exp_sec, edu_skills_sec])
    row_html = f'<div class="tpl-ch-row">{row}</div>' if row else ""
    return (
        f'<div class="tpl tpl-colored-header"><header class="tpl-ch-bar">'
        f'<h1 class="tpl-ch-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ch-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-ch-contact">{contact}</p></header><div class="tpl-ch-body">'
        f'{_sec_summary(d)}{row_html}{_sec_certifications(d)}{_sec_languages(d)}{_sec_hobbies(d)}{_sec_interests(d)}'
        f"</div></div>"
    )


def _tpl_modern_split(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    ico_edu = '<span class="tpl-ico">🎓</span> Education'
    ico_exp = '<span class="tpl-ico">💼</span> Experience'
    ico_skills = '<span class="tpl-ico">⚡</span> Skills'
    ico_langs = '<span class="tpl-ico">🌐</span> Languages'
    ico_certs = '<span class="tpl-ico">🏅</span> Certifications'
    return (
        f'<div class="tpl tpl-modern-split"><header class="tpl-ms-top"><div class="tpl-ms-brand">'
        f'{_photo_html(d, "tpl-ms-photo")}<div><h1 class="tpl-ms-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ms-title">{_esc(d.get("headline"))}</p></div></div>'
        f'<p class="tpl-ms-contact">{contact}</p></header><div class="tpl-ms-grid">'
        f'{_sec_summary(d, icon="📋")}'
        f'{_sec_education(d, title_html=ico_edu)}'
        f'{_sec_experience(d, wrap_class="tpl-sec tpl-ms-span2", title_html=ico_exp)}'
        f'{_sec_skills_list(d, title_html=ico_skills)}'
        f'{_sec_languages(d, title_html=ico_langs)}'
        f'{_sec_certifications(d, wrap_class="tpl-sec tpl-ms-span2", title_html=ico_certs)}'
        f'{_sec_hobbies(d, wrap_class="tpl-sec tpl-ms-span2")}'
        f'{_sec_interests(d, wrap_class="tpl-sec tpl-ms-span2")}'
        f"</div></div>"
    )


def _tpl_professional_border(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-professional-border"><div class="tpl-pb-main">'
        f'<header class="tpl-pb-header"><h1 class="tpl-pb-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-pb-title">{_esc(d.get("headline"))}</p><p class="tpl-pb-contact">{cj}</p></header>'
        f'{_sec_summary(d)}{_sec_experience(d)}{_sec_education(d)}'
        f'{_sec_certifications(d)}{_sec_hobbies(d)}{_sec_interests(d)}'
        f'</div><aside class="tpl-pb-side">{_photo_html(d, "tpl-pb-avatar")}'
        f'{_aside_skills(d, h_class="tpl-pb-h3")}{_aside_languages(d, h_class="tpl-pb-h3")}'
        f"</aside></div>"
    )


def _tpl_bold_header(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-bold-header"><header class="tpl-bh-bar">'
        f'<h1 class="tpl-bh-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-bh-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-bh-contact">{cj}</p></header><div class="tpl-bh-body">'
        f'{_sec_summary(d)}{_sec_experience(d)}{_sec_education(d)}'
        f'{_sec_skills_list(d)}{_sec_certifications(d)}{_sec_languages(d)}{_sec_hobbies(d)}{_sec_interests(d)}'
        f"</div></div>"
    )


def _tpl_tech_focus(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
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
            f'<ul class="tpl-bullets tpl-bullets--tight">{citems}</ul>'
        )
    return (
        f'<div class="tpl tpl-tech-focus"><aside class="tpl-tf-side">{"".join(side_parts)}</aside>'
        f'<div class="tpl-tf-main"><header class="tpl-tf-head"><h1 class="tpl-tf-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-tf-title">{_esc(d.get("headline"))}</p></header>'
        f'{_sec_summary(d)}{_sec_experience(d)}{_sec_education(d)}'
        f'{_sec_certifications(d)}{_sec_hobbies(d)}{_sec_interests(d)}'
        f"</div></div>"
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
    cj = " · ".join(_contact_parts(d))
    edu_html = _education_html(d)
    skills_html = _skills_list_html(d)
    split_parts: list[str] = []
    if edu_html.strip():
        split_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Education</h2>{edu_html}</section>'
        )
    if skills_html.strip():
        split_parts.append(
            f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Skills</h2>'
            f'<ul class="tpl-bullets">{skills_html}</ul></section>'
        )
    split_html = f'<div class="tpl-geo-split">{"".join(split_parts)}</div>' if split_parts else ""
    return (
        f'<div class="tpl tpl-geometric"><header class="tpl-geo-head">{_photo_html(d, "tpl-geo-photo")}'
        f'<div class="tpl-geo-text"><h1 class="tpl-geo-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-geo-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-geo-contact">{cj}</p></div></header>'
        f'{_sec_summary(d, h2_class="tpl-geo-h2")}'
        f'{_sec_experience(d, h2_class="tpl-geo-h2")}'
        f'{split_html}{_sec_certifications(d, h2_class="tpl-geo-h2")}{_sec_languages(d, h2_class="tpl-geo-h2")}'
        f'{_sec_hobbies(d, h2_class="tpl-geo-h2")}'
        f'{_sec_interests(d, h2_class="tpl-geo-h2")}'
        f"</div>"
    )


def _tpl_high_contrast(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    side_parts = [
        _aside_skills(d, h_class="tpl-hc-h3"),
        _aside_languages(d, h_class="tpl-hc-h3"),
    ]
    if _has_display_text(d.get("hobbies")):
        side_parts.append(
            f'<h3 class="tpl-hc-h3">Hobbies</h3>'
            f'<p class="tpl-hc-small">{_esc(d.get("hobbies"))}</p>'
        )
    if _has_display_text(d.get("interests")):
        side_parts.append(
            f'<h3 class="tpl-hc-h3">Interests</h3>'
            f'<p class="tpl-hc-small">{_esc(d.get("interests"))}</p>'
        )
    return (
        f'<div class="tpl tpl-high-contrast"><header class="tpl-hc-top">'
        f'<h1 class="tpl-hc-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-hc-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-hc-contact">{cj}</p></header><div class="tpl-hc-body">'
        f'<aside class="tpl-hc-side">{"".join(p for p in side_parts if p)}</aside>'
        f'<div class="tpl-hc-main">'
        f'{_sec_summary(d, h2_class="tpl-h2 tpl-h2--hc")}'
        f'{_sec_experience(d, h2_class="tpl-h2 tpl-h2--hc")}'
        f'{_sec_education(d, h2_class="tpl-h2 tpl-h2--hc")}'
        f'{_sec_certifications(d, h2_class="tpl-h2 tpl-h2--hc")}'
        f"</div></div></div>"
    )


def _tpl_aurora(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
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
    return (
        f'<div class="tpl tpl-aurora"><div class="tpl-au-hero">{_photo_html(d, "tpl-au-photo")}'
        f'<div class="tpl-au-hero-text"><h1 class="tpl-au-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-au-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-au-contact">{cj}</p></div></div><div class="tpl-au-body">'
        f'{_sec_summary(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}'
        f'{_sec_experience(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}'
        f'{row_html}{_sec_certifications(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}{_sec_languages(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}'
        f'{_sec_hobbies(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}'
        f'{_sec_interests(d, wrap_class="tpl-au-card", h2_class="tpl-au-h2")}'
        f"</div></div>"
    )


def _tpl_magazine(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    main_col = _join_visible(
        [
            _sec_summary(d, h2_class="tpl-mz-h2", p_class="tpl-mz-lead"),
            _sec_block(
                "Experience",
                _experience_html(d, "tpl-job tpl-job--mz"),
                h2_class="tpl-mz-h2",
                wrap_class="",
            ),
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
    if _has_display_text(d.get("hobbies")):
        aside_parts.append(
            f'<h3 class="tpl-mz-h3">Hobbies</h3><p class="tpl-p">{_esc(d.get("hobbies"))}</p>'
        )
    if _has_display_text(d.get("interests")):
        aside_parts.append(
            f'<h3 class="tpl-mz-h3">Interests</h3><p class="tpl-p">{_esc(d.get("interests"))}</p>'
        )
    return (
        f'<div class="tpl tpl-magazine"><header class="tpl-mz-header"><div class="tpl-mz-accent"></div>'
        f'<div class="tpl-mz-intro"><p class="tpl-mz-kicker">Professional profile</p>'
        f'<h1 class="tpl-mz-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-mz-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-mz-contact">{cj}</p></div></header><div class="tpl-mz-grid">'
        f'<section class="tpl-mz-col">{main_col}</section>'
        f'<aside class="tpl-mz-aside">{"".join(aside_parts)}</aside></div></div>'
    )


def _tpl_timeline(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    exp_timeline = _experience_timeline_html(d)
    exp_sec = (
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Experience</h2>'
        f'<div class="tpl-tl-track">{exp_timeline}</div></section>'
        if exp_timeline.strip()
        else ""
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
            f'<ul class="tpl-bullets">{skills_html}</ul></section>'
        )
    two_col = f'<div class="tpl-tl-two">{"".join(two_col_parts)}</div>' if two_col_parts else ""
    return (
        f'<div class="tpl tpl-timeline"><header class="tpl-tl-head">'
        f'<h1 class="tpl-tl-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-tl-sub">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-tl-contact">{cj}</p></header>'
        f'{_sec_summary(d, h2_class="tpl-tl-section-title")}'
        f'{exp_sec}{two_col}'
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
        f'{_lg_block("Experience", _experience_html(d, "tpl-job tpl-job--lg"))}'
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
    sk = _skills_list_html(d)
    sk_html = f'<ul class="tpl-bullets">{sk}</ul>' if sk.strip() else ""
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
        f'{_hz_sec("Experience", _experience_html(d))}'
        f'{_hz_sec("Education", _education_html(d))}'
        f'{_hz_sec("Skills", sk_html)}'
        f'{_hz_sec("Certifications", _certifications_html(d))}'
        f'{_hz_sec("Languages", ln_html)}'
        f'{_hz_sec("Hobbies", hob)}'
        f'{_hz_sec("Interests", intr)}'
        f"</div>"
    )


def _tpl_folio(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))

    def _fo_sec(num: str, title: str, inner: str) -> str:
        if not inner.strip():
            return ""
        return (
            f'<section class="tpl-fo-sec"><span class="tpl-fo-num">{num}</span>'
            f'<div class="tpl-fo-content"><h2 class="tpl-fo-h2">{title}</h2>{inner}</div></section>'
        )

    more_parts: list[str] = []
    certs = _certifications_html(d)
    if certs.strip():
        more_parts.append(certs)
    langs = _languages_html(d)
    if langs.strip():
        more_parts.append(f'<ul class="tpl-bullets">{langs}</ul>')
    if _has_display_text(d.get("hobbies")):
        more_parts.append(f'<p class="tpl-p">{_esc(d.get("hobbies"))}</p>')
    if _has_display_text(d.get("interests")):
        more_parts.append(f'<p class="tpl-p">{_esc(d.get("interests"))}</p>')
    skills_text = _skills_join_text(d)
    summary_inner = (
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p>'
        if _has_display_text(d.get("summary"))
        else ""
    )
    skills_inner = f'<p class="tpl-p">{skills_text}</p>' if skills_text.strip() else ""
    return (
        f'<div class="tpl tpl-folio"><header class="tpl-fo-head">{_photo_html(d, "tpl-fo-photo")}<div>'
        f'<h1 class="tpl-fo-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-fo-line">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-fo-contact">{cj}</p></div></header>'
        f'{_fo_sec("01", CAREER_OBJECTIVE_TITLE, summary_inner)}'
        f'{_fo_sec("02", "Experience", _experience_html(d, "tpl-job tpl-job--fo"))}'
        f'{_fo_sec("03", "Education", _education_html(d))}'
        f'{_fo_sec("04", "Skills", skills_inner)}'
        f'{_fo_sec("05", "More", "".join(more_parts))}'
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
}


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

STUDIO_PDF_PAGE_CSS = """
@page { size: A4 portrait; margin: 6mm; }
html.tt-pdf-export {
  margin: 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  background: #fff;
  /* Scale rem-based headings (preview uses zoom on .resume__mount). */
  font-size: calc(16px * var(--font-scale, 1));
  font-family: var(--font-stack, "Inter", system-ui, sans-serif);
}
body.tt-pdf-export {
  margin: 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  background: #fff;
  overflow-x: hidden !important;
  overflow-y: visible !important;
  font-family: var(--font-stack, "Inter", system-ui, sans-serif);
}
body.tt-pdf-export .pdf-wrap,
body.tt-pdf-export .preview-wrap,
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume .resume__mount,
body.tt-pdf-export article#resume.resume .tpl {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0;
  box-sizing: border-box;
  overflow: visible !important;
  min-height: auto !important;
}
body.tt-pdf-export article#resume.resume {
  box-shadow: none !important;
  border-radius: 0 !important;
  min-height: auto !important;
  font-size: var(--pdf-body-size, var(--body-size, 11.5pt)) !important;
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}
body.tt-pdf-export article#resume.resume .resume__mount {
  min-height: auto !important;
  zoom: 1 !important;
  transform: none !important;
}
/* Override prototype pdf-exporting rule that resets zoom (font scale is baked above). */
body.tt-pdf-export .resume.pdf-exporting .resume__mount {
  zoom: 1 !important;
}
/* Undo responsive breakpoints — PDF page is narrower than 1100px */
body.tt-pdf-export .tpl-ch-row {
  display: flex !important;
  flex-direction: row !important;
  align-items: flex-start !important;
  gap: 1rem !important;
  width: 100% !important;
}
body.tt-pdf-export .tpl-ch-row > .tpl-sec {
  flex: 1 1 0 !important;
  min-width: 0 !important;
}
body.tt-pdf-export .tpl-ms-grid {
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  gap: 1rem !important;
  width: 100% !important;
}
/* wkhtmltopdf: float columns (grid/table on div/aside is unreliable) */
body.tt-pdf-export .tpl-classic-sidebar {
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}
body.tt-pdf-export .tpl-classic-sidebar::after {
  content: "";
  display: table;
  clear: both;
}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-side {
  float: left !important;
  width: 29% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.85rem !important;
}
body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main {
  margin-left: 29% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 1.15rem 1rem 1.35rem !important;
}
body.tt-pdf-export .tpl-professional-border {
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}
body.tt-pdf-export .tpl-professional-border::after {
  content: "";
  display: table;
  clear: both;
}
body.tt-pdf-export .tpl-professional-border > .tpl-pb-main {
  margin-right: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
}
body.tt-pdf-export .tpl-professional-border > .tpl-pb-side {
  float: right !important;
  width: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
}
body.tt-pdf-export article#resume.resume,
body.tt-pdf-export article#resume.resume * {
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
  font-synthesis: none;
}
body.tt-pdf-export .tpl-bullets,
body.tt-pdf-export .tpl-bullets li,
body.tt-pdf-export .tpl-job,
body.tt-pdf-export .tpl-job strong,
body.tt-pdf-export .tpl-p,
body.tt-pdf-export .tpl-h2,
body.tt-pdf-export .tpl-cs-name,
body.tt-pdf-export .tpl-cs-contact,
body.tt-pdf-export .tpl-cs-h3 {
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}
body.tt-pdf-export .resume[data-template="elegant-serif"],
body.tt-pdf-export .resume[data-template="ledger"] {
  font-family: var(--font-stack, "Inter", system-ui, sans-serif) !important;
}
body.tt-pdf-export .tpl-hc-body,
body.tt-pdf-export .tpl-geo-split {
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  width: 100% !important;
}
body.tt-pdf-export .tpl-tech-focus {
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
}
body.tt-pdf-export .tpl-tech-focus::after {
  content: "";
  display: table;
  clear: both;
}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-side {
  float: left !important;
  width: 26% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 1rem 0.75rem 1.5rem !important;
}
body.tt-pdf-export .tpl-tech-focus .tpl-tf-main {
  margin-left: 26% !important;
  display: block !important;
  box-sizing: border-box !important;
}
body.tt-pdf-export .tpl-executive {
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
  min-height: auto !important;
}
body.tt-pdf-export .tpl-executive::after {
  content: "";
  display: table;
  clear: both;
}
body.tt-pdf-export .tpl-executive .tpl-ex-side {
  float: left !important;
  width: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.9rem 1.5rem !important;
}
body.tt-pdf-export .tpl-executive .tpl-ex-main {
  margin-left: 28% !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 0 1rem 1.5rem !important;
}
body.tt-pdf-export .tpl-mz-grid {
  display: block !important;
  width: 100% !important;
  overflow: hidden !important;
  min-height: auto !important;
}
body.tt-pdf-export .tpl-mz-grid::after {
  content: "";
  display: table;
  clear: both;
}
body.tt-pdf-export .tpl-mz-grid .tpl-mz-col {
  float: left !important;
  width: 58% !important;
  box-sizing: border-box !important;
  padding: 1.15rem 1rem 1.5rem !important;
}
body.tt-pdf-export .tpl-mz-grid .tpl-mz-aside {
  float: right !important;
  width: 42% !important;
  box-sizing: border-box !important;
  padding: 1.15rem 0.9rem 1.5rem !important;
}
body.tt-pdf-export .tpl-sec--half,
body.tt-pdf-export .tpl-ch-body,
body.tt-pdf-export .tpl-ch-row > *,
body.tt-pdf-export .tpl-ms-grid > *,
body.tt-pdf-export .tpl-pb-main,
body.tt-pdf-export .tpl-pb-side,
body.tt-pdf-export .tpl-cs-side,
body.tt-pdf-export .tpl-cs-main {
  min-width: 0 !important;
  max-width: 100% !important;
  overflow: visible !important;
  box-sizing: border-box !important;
}
body.tt-pdf-export .tpl-ch-body {
  padding: 1.25rem 1.1rem 1.5rem !important;
}
body.tt-pdf-export .tpl-h2,
body.tt-pdf-export .tpl-p,
body.tt-pdf-export .tpl-bullets,
body.tt-pdf-export .tpl-job {
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
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
    return {
        "studio_google_fonts_href": studio_pdf_google_fonts_href(pack),
        "studio_embedded_fonts_css": studio_pdf_embedded_fonts_css(pack),
        "studio_resume_css_inline": studio_resume_pdf_stylesheet_text(),
        "studio_root_style": studio_pack_root_css_block(pack),
        "studio_pdf_page_css": STUDIO_PDF_PAGE_CSS,
        "studio_mount_html": mount_html,
        "studio_template_id": template_id,
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
    font_esc = html.escape(font, quote=True)
    return (
        f":root{{--accent:{accent};--accent-contrast:#ffffff;--accent-rgb:{r}, {g}, {b};"
        f'--font-stack:{font_esc};--resume-text-align:{align};'
        f"--body-size:{body_size};--pdf-body-size:{pdf_body_size};--font-scale:{font_scale};}}"
    )


def studio_proto_pack_to_mount_html(pack: dict) -> tuple[str, str]:
    rd = pack.get("resume") if isinstance(pack.get("resume"), dict) else {}
    tid = (pack.get("template") or "classic-sidebar").strip().lower()
    if tid not in TPL_RENDERERS:
        tid = "classic-sidebar"
    return TPL_RENDERERS[tid](rd), tid


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
