"""
Server-side HTML for studio resumes (PDF + HTML preview).

Mirrors static/resume-builder-prototype/app.js RENDERERS + helpers so PDFs match
the template chosen in the studio (same tpl-* markup + styles.css).
"""

from __future__ import annotations

import html
import re
from typing import Any, Callable

from users.resume_payload import STUDIO_PROTO_V1_KEY, _STUDIO_COLOR_HEX, _wizard_draft_dict


def _esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=True)


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
        loc = exp.get("location") or ""
        loc_bit = f" · {_esc(loc)}" if str(loc).strip() else ""
        sub = _esc(exp.get("company") or "") + loc_bit
        bul_html = f'<ul class="tpl-bullets">{bullets}</ul>' if bullets else ""
        parts.append(
            f'<div class="{class_job}"><div class="tpl-job-head"><strong>{title}</strong>'
            f'<span class="tpl-job-dates">{_esc(exp.get("dates") or "")}</span></div>'
            f'<div class="tpl-job-sub">{sub}</div>{bul_html}</div>'
        )
    return "".join(parts)


def _education_html(d: dict) -> str:
    parts: list[str] = []
    for ed in d.get("education") or []:
        if not isinstance(ed, dict):
            continue
        deg = _esc(ed.get("degree") or "")
        sch = _esc(ed.get("school") or "")
        if not deg and not sch:
            continue
        det = ed.get("detail") or ""
        det_bit = f" — {_esc(det)}" if str(det).strip() else ""
        parts.append(
            f'<div class="tpl-edu-block"><div class="tpl-job-head"><strong>{deg}</strong>'
            f'<span class="tpl-job-dates">{_esc(ed.get("dates") or "")}</span></div>'
            f'<div class="tpl-job-sub">{sch}{det_bit}</div></div>'
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
        issuer = _esc(c.get("issuer") or "")
        date = _esc(c.get("date") or "")
        meta = issuer + (f" · {date}" if date else "")
        parts.append(
            f'<div class="tpl-cert"><strong>{nm}</strong><span class="tpl-cert-meta">{meta}</span></div>'
        )
    return "".join(parts)


def _languages_html(d: dict) -> str:
    parts: list[str] = []
    for ln in d.get("languages") or []:
        if not isinstance(ln, dict):
            continue
        parts.append(
            "<li><span class=\"tpl-lang-name\">"
            f'{_esc(ln.get("name") or "")}</span> — {_esc(ln.get("level") or "")}</li>'
        )
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
        loc = exp.get("location") or ""
        loc_bit = f" · {_esc(loc)}" if str(loc).strip() else ""
        sub = _esc(exp.get("company") or "") + loc_bit
        bul_html = f'<ul class="tpl-bullets">{bullets}</ul>' if bullets else ""
        parts.append(
            f'<div class="tpl-tl-item"><span class="tpl-tl-dot"></span><div class="tpl-tl-inner">'
            f'<div class="tpl-job-head"><strong>{title}</strong>'
            f'<span class="tpl-job-dates">{_esc(exp.get("dates") or "")}</span></div>'
            f'<div class="tpl-job-sub">{sub}</div>{bul_html}</div></div>'
        )
    return "".join(parts)


def _skills_join_text(d: dict) -> str:
    names = []
    for s in d.get("skills") or []:
        if isinstance(s, dict) and (s.get("name") or "").strip():
            names.append(_esc(s["name"].strip()))
    return " · ".join(names)


def _tpl_minimalist(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-minimalist"><header class="tpl-min-head">'
        f'<h1 class="tpl-min-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-min-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-min-contact">{contact}</p></header><hr class="tpl-min-rule" />'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Summary</h2>'
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p></section><hr class="tpl-min-rule" />'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Experience</h2>'
        f'{_experience_html(d, "tpl-job tpl-job--min")}</section><hr class="tpl-min-rule" />'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Education</h2>{_education_html(d)}</section>'
        f'<hr class="tpl-min-rule" />'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Skills</h2>'
        f'<ul class="tpl-bullets tpl-bullets--center">{_skills_list_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Languages</h2>'
        f'<ul class="tpl-bullets tpl-bullets--center">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Interests</h2>'
        f'<p class="tpl-p">{_esc(d.get("interests"))}</p></section></div>'
    )


def _tpl_classic_sidebar(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
    return (
        f'<div class="tpl tpl-classic-sidebar"><aside class="tpl-cs-side">{_photo_html(d, "tpl-avatar")}'
        f'<h1 class="tpl-cs-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-cs-title">{_esc(d.get("headline"))}</p>'
        f'<ul class="tpl-cs-contact">{citems}</ul><h3 class="tpl-cs-h3">Skills</h3>'
        f'<ul class="tpl-bullets tpl-bullets--tight">{_skills_list_html(d)}</ul>'
        f'<h3 class="tpl-cs-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">{_languages_html(d)}</ul>'
        f'</aside><div class="tpl-cs-main">'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_colored_header(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-colored-header"><header class="tpl-ch-bar">'
        f'<h1 class="tpl-ch-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ch-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-ch-contact">{contact}</p></header><div class="tpl-ch-body">'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Profile</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<div class="tpl-ch-row"><section class="tpl-sec tpl-sec--half"><h2 class="tpl-h2">Experience</h2>'
        f'{_experience_html(d)}</section><section class="tpl-sec tpl-sec--half"><h2 class="tpl-h2">Education</h2>'
        f'{_education_html(d)}<h2 class="tpl-h2 tpl-h2--spaced">Skills</h2>'
        f'<ul class="tpl-bullets">{_skills_list_html(d)}</ul></section></div>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Certifications &amp; languages</h2>'
        f'<div class="tpl-two-col">{_certifications_html(d)}</div>'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_modern_split(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-modern-split"><header class="tpl-ms-top"><div class="tpl-ms-brand">'
        f'{_photo_html(d, "tpl-ms-photo")}<div><h1 class="tpl-ms-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ms-title">{_esc(d.get("headline"))}</p></div></div>'
        f'<p class="tpl-ms-contact">{contact}</p></header><div class="tpl-ms-grid">'
        f'<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">📋</span> Summary</h2>'
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🎓</span> Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">💼</span> Experience</h2>'
        f'{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">⚡</span> Skills</h2>'
        f'<ul class="tpl-bullets">{_skills_list_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🌐</span> Languages</h2>'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">🏅</span> Certifications</h2>'
        f'{_certifications_html(d)}</section>'
        f'<section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2">Interests</h2>'
        f'<p class="tpl-p">{_esc(d.get("interests"))}</p></section></div></div>'
    )


def _tpl_professional_border(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-professional-border"><div class="tpl-pb-main">'
        f'<header class="tpl-pb-header"><h1 class="tpl-pb-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-pb-title">{_esc(d.get("headline"))}</p><p class="tpl-pb-contact">{cj}</p></header>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f'</div><aside class="tpl-pb-side">{_photo_html(d, "tpl-pb-avatar")}'
        f'<h3 class="tpl-pb-h3">Skills</h3><ul class="tpl-bullets tpl-bullets--tight">{_skills_list_html(d)}</ul>'
        f'<h3 class="tpl-pb-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">{_languages_html(d)}</ul>'
        f"</aside></div>"
    )


def _tpl_bold_header(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-bold-header"><header class="tpl-bh-bar">'
        f'<h1 class="tpl-bh-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-bh-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-bh-contact">{cj}</p></header><div class="tpl-bh-body">'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Skills</h2><ul class="tpl-bullets">{_skills_list_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Certifications &amp; languages</h2>{_certifications_html(d)}'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_tech_focus(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
    return (
        f'<div class="tpl tpl-tech-focus"><aside class="tpl-tf-side"><h2 class="tpl-tf-h2">Skills</h2>'
        f'{_skill_bars_html(d)}<h2 class="tpl-tf-h2">Languages</h2>'
        f'<ul class="tpl-bullets tpl-bullets--tight">{_languages_html(d)}</ul>'
        f'<h2 class="tpl-tf-h2">Contact</h2><ul class="tpl-bullets tpl-bullets--tight">{citems}</ul></aside>'
        f'<div class="tpl-tf-main"><header class="tpl-tf-head"><h1 class="tpl-tf-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-tf-title">{_esc(d.get("headline"))}</p></header>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_elegant_serif(d: dict) -> str:
    contact = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-elegant-serif"><header class="tpl-el-head">'
        f'<h1 class="tpl-el-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-el-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-el-contact">{contact}</p></header>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Summary</h2><p class="tpl-el-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Experience</h2>'
        f'{_experience_html(d, "tpl-job tpl-job--elegant")}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Skills</h2><p class="tpl-el-p">{_skills_join_text(d)}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Languages</h2><ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-el-h2">Interests</h2><p class="tpl-el-p">{_esc(d.get("interests"))}</p></section>'
        f"</div>"
    )


def _tpl_geometric(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-geometric"><header class="tpl-geo-head">{_photo_html(d, "tpl-geo-photo")}'
        f'<div class="tpl-geo-text"><h1 class="tpl-geo-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-geo-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-geo-contact">{cj}</p></div></header>'
        f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<div class="tpl-geo-split"><section class="tpl-sec"><h2 class="tpl-geo-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Skills</h2><ul class="tpl-bullets">{_skills_list_html(d)}</ul></section></div>'
        f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Certifications &amp; languages</h2>{_certifications_html(d)}'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-geo-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div>"
    )


def _tpl_high_contrast(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-high-contrast"><header class="tpl-hc-top">'
        f'<h1 class="tpl-hc-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-hc-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-hc-contact">{cj}</p></header><div class="tpl-hc-body">'
        f'<aside class="tpl-hc-side"><h3 class="tpl-hc-h3">Skills</h3><ul class="tpl-bullets">{_skills_list_html(d)}</ul>'
        f'<h3 class="tpl-hc-h3">Languages</h3><ul class="tpl-bullets">{_languages_html(d)}</ul>'
        f'<h3 class="tpl-hc-h3">Interests</h3><p class="tpl-hc-small">{_esc(d.get("interests"))}</p></aside>'
        f'<div class="tpl-hc-main">'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Certifications</h2>{_certifications_html(d)}</section>'
        f"</div></div></div>"
    )


def _tpl_aurora(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-aurora"><div class="tpl-au-hero">{_photo_html(d, "tpl-au-photo")}'
        f'<div class="tpl-au-hero-text"><h1 class="tpl-au-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-au-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-au-contact">{cj}</p></div></div><div class="tpl-au-body">'
        f'<section class="tpl-au-card"><h2 class="tpl-au-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-au-card"><h2 class="tpl-au-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<div class="tpl-au-row"><section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Education</h2>'
        f'{_education_html(d)}</section><section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Skills</h2>'
        f'<ul class="tpl-bullets">{_skills_list_html(d)}</ul></section></div>'
        f'<section class="tpl-au-card"><h2 class="tpl-au-h2">Certifications &amp; languages</h2>{_certifications_html(d)}'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-au-card"><h2 class="tpl-au-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_magazine(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-magazine"><header class="tpl-mz-header"><div class="tpl-mz-accent"></div>'
        f'<div class="tpl-mz-intro"><p class="tpl-mz-kicker">Professional profile</p>'
        f'<h1 class="tpl-mz-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-mz-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-mz-contact">{cj}</p></div></header><div class="tpl-mz-grid">'
        f'<section class="tpl-mz-col"><h2 class="tpl-mz-h2">Summary</h2><p class="tpl-mz-lead">{_esc(d.get("summary"))}</p>'
        f'<h2 class="tpl-mz-h2">Experience</h2>{_experience_html(d, "tpl-job tpl-job--mz")}</section>'
        f'<aside class="tpl-mz-aside">{_photo_html(d, "tpl-mz-photo")}'
        f'<h3 class="tpl-mz-h3">Skills</h3><div class="tpl-mz-pills">{_skills_pills_html(d)}</div>'
        f'<h3 class="tpl-mz-h3">Education</h3>{_education_html(d)}'
        f'<h3 class="tpl-mz-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">{_languages_html(d)}</ul>'
        f'<h3 class="tpl-mz-h3">Certifications</h3>{_certifications_html(d)}'
        f'<h3 class="tpl-mz-h3">Interests</h3><p class="tpl-p">{_esc(d.get("interests"))}</p></aside></div></div>'
    )


def _tpl_timeline(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-timeline"><header class="tpl-tl-head">'
        f'<h1 class="tpl-tl-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-tl-sub">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-tl-contact">{cj}</p></header>'
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Summary</h2>'
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Experience</h2>'
        f'<div class="tpl-tl-track">{_experience_timeline_html(d)}</div></section>'
        f'<div class="tpl-tl-two"><section class="tpl-sec"><h2 class="tpl-tl-section-title">Education</h2>'
        f'{_education_html(d)}</section><section class="tpl-sec"><h2 class="tpl-tl-section-title">Skills</h2>'
        f'<ul class="tpl-bullets">{_skills_list_html(d)}</ul></section></div>'
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Languages</h2><ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-tl-section-title">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div>"
    )


def _tpl_executive(d: dict) -> str:
    citems = "".join(f"<li>{x}</li>" for x in _contact_parts(d))
    return (
        f'<div class="tpl tpl-executive"><aside class="tpl-ex-side">{_photo_html(d, "tpl-ex-photo")}'
        f'<h2 class="tpl-ex-h2">Contact</h2><ul class="tpl-ex-list">{citems}</ul>'
        f'<h2 class="tpl-ex-h2">Core skills</h2><ul class="tpl-bullets tpl-bullets--tight">{_skills_list_html(d)}</ul>'
        f'<h2 class="tpl-ex-h2">Languages</h2><ul class="tpl-bullets tpl-bullets--tight">{_languages_html(d)}</ul>'
        f'</aside><div class="tpl-ex-main"><header class="tpl-ex-top">'
        f'<h1 class="tpl-ex-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-ex-title">{_esc(d.get("headline"))}</p></header>'
        f'<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Executive summary</h2>'
        f'<p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Experience</h2>{_experience_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_studio(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-studio"><header class="tpl-st-hero"><div class="tpl-st-hero-inner">'
        f'{_photo_html(d, "tpl-st-photo")}<div><h1 class="tpl-st-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-st-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-st-contact">{cj}</p></div></div>'
        f'<div class="tpl-st-skills">{_skills_pills_html(d)}</div></header><div class="tpl-st-body">'
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">About</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">Experience</h2>'
        f'{_experience_html(d, "tpl-job tpl-job--st")}</section>'
        f'<div class="tpl-st-split"><section class="tpl-st-card"><h2 class="tpl-st-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">Languages</h2><ul class="tpl-bullets">{_languages_html(d)}</ul></section></div>'
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-st-card"><h2 class="tpl-st-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_nova(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-nova"><div class="tpl-nv-hero"><div class="tpl-nv-blob" aria-hidden="true"></div>'
        f'<div class="tpl-nv-card">{_photo_html(d, "tpl-nv-photo")}<div class="tpl-nv-intro">'
        f'<h1 class="tpl-nv-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-nv-tagline">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-nv-contact">{cj}</p></div></div></div><div class="tpl-nv-body">'
        f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<div class="tpl-nv-split"><section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Skills</h2><div class="tpl-nv-pills">{_skills_pills_html(d)}</div></section></div>'
        f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Certifications &amp; languages</h2>{_certifications_html(d)}'
        f'<ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
        f"</div></div>"
    )


def _tpl_ledger(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-ledger"><header class="tpl-lg-head">'
        f'<h1 class="tpl-lg-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-lg-meta"><span class="tpl-lg-label">ROLE</span> {_esc(d.get("headline"))}</p>'
        f'<p class="tpl-lg-meta"><span class="tpl-lg-label">CONTACT</span> {cj}</p></header>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Summary</h2>'
        f'<p class="tpl-lg-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Experience</h2>'
        f'{_experience_html(d, "tpl-job tpl-job--lg")}</section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Skills</h2>'
        f'<ul class="tpl-lg-list">{_skills_list_html(d)}</ul></section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Languages</h2>'
        f'<ul class="tpl-lg-list">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Interests</h2>'
        f'<p class="tpl-lg-p">{_esc(d.get("interests"))}</p></section></div>'
    )


def _tpl_horizon(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    sm = f'<p class="tpl-p">{_esc(d.get("summary"))}</p>'
    sk = f'<ul class="tpl-bullets">{_skills_list_html(d)}</ul>'
    ln = f'<ul class="tpl-bullets">{_languages_html(d)}</ul>'
    intr = f'<p class="tpl-p">{_esc(d.get("interests"))}</p>'

    def _hz_sec(title: str, inner: str) -> str:
        return (
            f'<section class="tpl-hz-sec"><div class="tpl-hz-bar"></div>'
            f'<h2 class="tpl-hz-h2">{title}</h2>{inner}</section>'
        )

    return (
        f'<div class="tpl tpl-horizon"><header class="tpl-hz-head">'
        f'<h1 class="tpl-hz-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-hz-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-hz-contact">{cj}</p></header>'
        f'{_hz_sec("Summary", sm)}'
        f'{_hz_sec("Experience", _experience_html(d))}'
        f'{_hz_sec("Education", _education_html(d))}'
        f'{_hz_sec("Skills", sk)}'
        f'{_hz_sec("Certifications", _certifications_html(d))}'
        f'{_hz_sec("Languages", ln)}'
        f'{_hz_sec("Interests", intr)}'
        f"</div>"
    )


def _tpl_folio(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-folio"><header class="tpl-fo-head">{_photo_html(d, "tpl-fo-photo")}<div>'
        f'<h1 class="tpl-fo-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-fo-line">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-fo-contact">{cj}</p></div></header>'
        f'<section class="tpl-fo-sec"><span class="tpl-fo-num">01</span><div class="tpl-fo-content">'
        f'<h2 class="tpl-fo-h2">Profile</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></div></section>'
        f'<section class="tpl-fo-sec"><span class="tpl-fo-num">02</span><div class="tpl-fo-content">'
        f'<h2 class="tpl-fo-h2">Experience</h2>{_experience_html(d, "tpl-job tpl-job--fo")}</div></section>'
        f'<section class="tpl-fo-sec"><span class="tpl-fo-num">03</span><div class="tpl-fo-content">'
        f'<h2 class="tpl-fo-h2">Education</h2>{_education_html(d)}</div></section>'
        f'<section class="tpl-fo-sec"><span class="tpl-fo-num">04</span><div class="tpl-fo-content">'
        f'<h2 class="tpl-fo-h2">Skills</h2><p class="tpl-p">{_skills_join_text(d)}</p></div></section>'
        f'<section class="tpl-fo-sec"><span class="tpl-fo-num">05</span><div class="tpl-fo-content">'
        f'<h2 class="tpl-fo-h2">More</h2>{_certifications_html(d)}<ul class="tpl-bullets">{_languages_html(d)}</ul>'
        f'<p class="tpl-p">{_esc(d.get("interests"))}</p></div></section></div>'
    )


def _tpl_vertex(d: dict) -> str:
    cj = " · ".join(_contact_parts(d))
    return (
        f'<div class="tpl tpl-vertex"><header class="tpl-vx-banner"><div class="tpl-vx-banner-inner">'
        f'<h1 class="tpl-vx-name">{_esc(d.get("fullName"))}</h1>'
        f'<p class="tpl-vx-title">{_esc(d.get("headline"))}</p>'
        f'<p class="tpl-vx-contact">{cj}</p></div></header><div class="tpl-vx-body">'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Summary</h2><p class="tpl-p">{_esc(d.get("summary"))}</p></section>'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Experience</h2>{_experience_html(d)}</section>'
        f'<div class="tpl-vx-grid"><section class="tpl-sec"><h2 class="tpl-vx-h2">Education</h2>{_education_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Skills</h2><ul class="tpl-bullets">{_skills_list_html(d)}</ul></section></div>'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Certifications</h2>{_certifications_html(d)}</section>'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Languages</h2><ul class="tpl-bullets">{_languages_html(d)}</ul></section>'
        f'<section class="tpl-sec"><h2 class="tpl-vx-h2">Interests</h2><p class="tpl-p">{_esc(d.get("interests"))}</p></section>'
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
    raw = (pack.get("font") or "").strip()[:240] or '"Inter", system-ui, sans-serif'
    if not re.match(r'^[\w\s\-",.()+]+$', raw):
        raw = '"Inter", system-ui, sans-serif'
    return raw


def studio_pack_accent_hex(pack: dict) -> str:
    cid = (pack.get("color") or "teal").strip().lower()
    return _STUDIO_COLOR_HEX.get(cid, _STUDIO_COLOR_HEX["teal"])


def studio_pack_root_css_block(pack: dict) -> str:
    accent = studio_pack_accent_hex(pack)
    r, g, b = _hex_to_rgb_triplet(accent)
    font = studio_pack_font_stack(pack)
    align = (pack.get("textAlign") or "start").strip().lower()
    if align not in ("start", "center", "end", "justify"):
        align = "start"
    font_esc = html.escape(font, quote=True)
    return (
        f":root{{--accent:{accent};--accent-contrast:#ffffff;--accent-rgb:{r}, {g}, {b};"
        f'--font-stack:{font_esc};--resume-text-align:{align};}}'
    )


def studio_proto_pack_to_mount_html(pack: dict) -> tuple[str, str]:
    rd = pack.get("resume") if isinstance(pack.get("resume"), dict) else {}
    tid = (pack.get("template") or "classic-sidebar").strip().lower()
    if tid not in TPL_RENDERERS:
        tid = "classic-sidebar"
    return TPL_RENDERERS[tid](rd), tid


def studio_resume_uses_proto_layout(resume) -> bool:
    return studio_proto_pack_from_resume(resume) is not None
