"""
Server-side prompt + OpenAI call for the guided resume wizard (steps 5–6).
Uses settings.OPENAI_API_KEY — never client-supplied keys.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

STYLE_D = {
    "ivy_league": (
        "Ivy League (Harvard, Yale, Princeton, Columbia, Penn, Brown, Dartmouth, Cornell) — "
        "achievement-driven with quantified impact, leadership narrative, intellectual vitality and curiosity, "
        "initiative, depth of commitment, transformational thinking"
    ),
    "oxford_cambridge": (
        "Oxford / Cambridge — academic rigour above all, genuine deep subject passion, "
        "super-curricular activities beyond the curriculum, reading lists and independent intellectual exploration, "
        "research-oriented mindset, critical analytical engagement, intellectual independence"
    ),
    "russell_group": (
        "Russell Group UK (UCL, LSE, Imperial, Warwick, Edinburgh, KCL, Manchester) — "
        "analytical sharpness, interdisciplinary thinking, professional ambition, policy awareness, "
        "global perspective, independence of thought, employability orientation"
    ),
    "scholarship": (
        "Scholarship Applications (Chevening, Rhodes, Gates Cambridge, Aga Khan, Commonwealth, Fulbright) — "
        "leadership in context of adversity, transformative community impact, future potential, "
        "moral character, resilience, global citizenship, clear development mission"
    ),
    "research_cv": (
        "Research CV / PhD — publications and presentations, rigorous research methodology, "
        "intellectual contributions, identification of gaps in literature, supervisor and faculty fit, "
        "academic lineage, theoretical frameworks, research independence"
    ),
    "mba": (
        "MBA / Business School (Wharton, HBS, INSEAD, LBS, Booth, Sloan, Kellogg) — "
        "quantified P&L and business impact with exact figures, team leadership at scale, "
        "career progression arc, entrepreneurial initiatives, strategic thinking, global exposure"
    ),
}

STYLE_LBL = {
    "ivy_league": "Ivy League",
    "oxford_cambridge": "Oxford / Cambridge",
    "russell_group": "Russell Group UK",
    "scholarship": "Scholarship",
    "research_cv": "Research CV",
    "mba": "MBA / Leadership",
}

_ALLOWED_KEYS = frozenset(
    {
        "name",
        "email",
        "phone",
        "country",
        "linkedin",
        "portfolio",
        "level",
        "school",
        "course",
        "career",
        "unis",
        "gpa",
        "board",
        "subjects",
        "tests",
        "awards",
        "olymp",
        "lead",
        "extra",
        "sport",
        "intern",
        "research",
        "community",
        "projects",
        "tech",
        "soft",
        "langs",
        "certs",
        "personal",
        "hobbies",
        "style",
        "format",
        "tag",
        "instr",
        "ts",
    }
)
_MAX_FIELD = 12000


def _clip(s: object, n: int = _MAX_FIELD) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t[:n] if len(t) > n else t


def sanitize_draft(raw: dict) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("draft must be an object")
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k not in _ALLOWED_KEYS:
            continue
        out[k] = _clip(v)
    style = out.get("style") or "ivy_league"
    if style not in STYLE_D:
        style = "ivy_league"
    out["style"] = style
    if not (out.get("name") or "").strip():
        raise ValueError("name is required")
    return out


def strip_markdown_fences(html: str) -> str:
    """Remove ```html / ``` wrappers some models add around HTML (safe for already-clean HTML)."""
    if not html or not isinstance(html, str):
        return ""
    t = html.strip()
    if not t:
        return ""
    # Opening: ``` or ```html (optional language word), then newline
    t = re.sub(r"^```\s*[\w-]*\s*\r?\n", "", t, count=1, flags=re.IGNORECASE)
    t = t.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1 :].lstrip()
        else:
            t = re.sub(r"^```\s*", "", t)
    t = t.strip()
    # Closing fence at end of document
    t = re.sub(r"\r?\n```\s*$", "", t)
    t = re.sub(r"```\s*$", "", t)
    return t.strip()


def split_generated_html(raw: str) -> str:
    """Strip trailing SCORES:{...} and markdown code fences; return HTML only."""
    if not raw:
        return ""
    m = re.search(r"\nSCORES:\s*\{", raw)
    out = raw[: m.start()].strip() if m else raw.strip()
    return strip_markdown_fences(out)


def build_plain_resume_summary_py(d: dict[str, str]) -> str:
    """Plain-text summary for UserResume.about (mirrors admitcv-resume-flow.js buildPlainResumeSummary)."""
    lines: list[str] = []
    head = (d.get("name") or "Student").strip()
    if d.get("course"):
        head += " — " + str(d["course"]).strip()
    if d.get("country"):
        head += " (" + str(d["country"]).strip() + ")"
    lines.append(head)
    if (d.get("unis") or "").strip():
        lines.append("Target universities: " + str(d["unis"]).strip())
    lvl = (d.get("level") or "").strip()
    sch = (d.get("school") or "").strip()
    if lvl or sch:
        lines.append("Education: " + " · ".join(x for x in [lvl, sch] if x))
    gpa = (d.get("gpa") or "").strip()
    brd = (d.get("board") or "").strip()
    subj = (d.get("subjects") or "").strip()
    if gpa or brd or subj:
        ac = " · ".join(x for x in [gpa, brd] if x)
        if subj:
            ac += " | Subjects: " + subj
        lines.append("Academic: " + ac)
    if (d.get("tests") or "").strip():
        lines.append("Tests: " + str(d["tests"]).strip())
    if (d.get("career") or "").strip():
        lines.append("Career goal: " + str(d["career"]).strip())
    for label, key in (
        ("Awards", "awards"),
        ("Competitions", "olymp"),
        ("Leadership", "lead"),
        ("Activities", "extra"),
        ("Sports", "sport"),
        ("Internships", "intern"),
        ("Research", "research"),
        ("Community", "community"),
        ("Projects", "projects"),
    ):
        val = (d.get(key) or "").strip()
        if val:
            lines.append(f"{label}:\n{val}")
    tech = (d.get("tech") or "").strip()
    soft = (d.get("soft") or "").strip()
    if tech or soft:
        sparts = []
        if tech:
            sparts.append("Technical: " + tech)
        if soft:
            sparts.append("Soft skills: " + soft)
        lines.append("Skills: " + " | ".join(sparts))
    if (d.get("langs") or "").strip():
        lines.append("Languages: " + str(d["langs"]).strip())
    if (d.get("certs") or "").strip():
        lines.append("Certifications:\n" + str(d["certs"]).strip())
    if (d.get("personal") or "").strip():
        lines.append("Achievements & notes:\n" + str(d["personal"]).strip())
    if (d.get("hobbies") or "").strip():
        lines.append("Interests: " + str(d["hobbies"]).strip())
    lines.append("")
    st = d.get("style") or "ivy_league"
    lines.append("Admissions style: " + STYLE_LBL.get(st, st))
    fmt = str(d.get("format") or "").replace("_", " ")
    if fmt:
        lines.append("Format: " + fmt)
    if (d.get("instr") or "").strip():
        lines.append("Special instructions: " + str(d["instr"]).strip())
    return "\n\n".join(lines)


def sync_user_fields_from_wizard(user, draft: dict[str, str]) -> None:
    """Fill empty profile / name fields from the wizard (non-destructive)."""
    from users.models import UserProfile

    name = (draft.get("name") or "").strip()
    if name and not (getattr(user, "name", None) or "").strip():
        user.name = name[:200]
        user.save(update_fields=["name"])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    upd: list[str] = []
    school = (draft.get("school") or "").strip()
    if school and not (profile.schoolname or "").strip():
        profile.schoolname = school[:300]
        upd.append("schoolname")
    level = (draft.get("level") or "").strip()
    if level and not (profile.grade or "").strip():
        profile.grade = level[:120]
        upd.append("grade")
    if upd:
        profile.save(update_fields=upd)


def _nz(v: str, default: str = "N/A") -> str:
    t = (v or "").strip()
    return t if t else default


def build_resume_prompt(d: dict[str, str]) -> str:
    style_key = d.get("style") or "ivy_league"
    style_line = STYLE_D.get(style_key, style_key)
    rewrite = (d.get("_rewrite") or "").strip()

    return (
        "You are a world-class university admissions consultant and professional CV writer with 20+ years "
        "experience. Generate a complete, strategically optimised admissions resume in clean HTML.\n\n"
        "COMPLETE STUDENT PROFILE:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"NAME: {_nz(d.get('name'))}\nCOUNTRY: {_nz(d.get('country'))}\nEMAIL: {_nz(d.get('email'))}\n"
        f"PHONE: {_nz(d.get('phone'))}\nLINKEDIN: {_nz(d.get('linkedin'))}\nPORTFOLIO: {_nz(d.get('portfolio'))}\n"
        f"EDUCATION LEVEL: {_nz(d.get('level'))}\nSCHOOL: {_nz(d.get('school'))}\n"
        f"INTENDED COURSE: {_nz(d.get('course'))}\nCAREER GOAL: {_nz(d.get('career'))}\n"
        f"TARGET UNIVERSITIES: {_nz(d.get('unis'), 'Top global universities')}\n\n"
        "ACADEMIC RECORD:\n"
        f"GPA / GRADE: {_nz(d.get('gpa'))}\nGRADING BOARD: {_nz(d.get('board'))}\n"
        f"KEY SUBJECTS: {_nz(d.get('subjects'))}\nTEST SCORES: {_nz(d.get('tests'), 'None provided')}\n"
        f"ACADEMIC AWARDS:\n{_nz(d.get('awards'), 'None listed')}\nOLYMPIADS & COMPETITIONS:\n{_nz(d.get('olymp'), 'None listed')}\n\n"
        f"LEADERSHIP & ACTIVITIES:\n{_nz(d.get('lead'), 'None listed')}\n\nEXTRACURRICULAR ACTIVITIES:\n{_nz(d.get('extra'), 'None listed')}\n\n"
        f"SPORTS:\n{_nz(d.get('sport'), 'None listed')}\n\n"
        f"PROFESSIONAL EXPERIENCE:\nINTERNSHIPS:\n{_nz(d.get('intern'), 'None listed')}\n\nRESEARCH & PUBLICATIONS:\n{_nz(d.get('research'), 'None listed')}\n\n"
        f"COMMUNITY SERVICE:\n{_nz(d.get('community'), 'None listed')}\n\nPROJECTS & ENTREPRENEURSHIP:\n{_nz(d.get('projects'), 'None listed')}\n\n"
        "SKILLS & CREDENTIALS:\n"
        f"TECHNICAL SKILLS: {_nz(d.get('tech'), 'None listed')}\nSOFT SKILLS: {_nz(d.get('soft'), 'None listed')}\n"
        f"LANGUAGES: {_nz(d.get('langs'), 'None listed')}\nCERTIFICATIONS:\n{_nz(d.get('certs'), 'None listed')}\n"
        f"PERSONAL ACHIEVEMENTS:\n{_nz(d.get('personal'), 'None listed')}\nHOBBIES & INTERESTS: {_nz(d.get('hobbies'), 'None listed')}\n\n"
        "RESUME CONFIGURATION:\n"
        f"STYLE: {style_line}\nFORMAT: {_nz(d.get('format'), 'one_page')}\nTAGLINE: {_nz(d.get('tag'), '')}\n"
        f"SPECIAL INSTRUCTIONS: {_nz(d.get('instr'), 'None')}\n"
        + (f"REWRITE MODE: {rewrite}\n" if rewrite else "")
        + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "LANGUAGE TRANSFORMATION RULES — APPLY TO EVERY BULLET:\n"
        '• NEVER use: "I participated", "helped with", "was responsible for", "was part of", "assisted"\n'
        "• ALWAYS use elite action verbs: Spearheaded, Pioneered, Orchestrated, Catalysed, Architected, "
        "Championed, Synthesised, Directed, Mobilised, Instituted, Steered, Elevated, Engineered, Galvanised, Forged\n"
        "• Quantify everything: team sizes, percentages, currency amounts, rankings, people impacted, timeframes\n"
        "• Transform weak statements into powerful achievement narratives.\n"
        "• Every bullet must prove IMPACT, SCALE, DEPTH, or RECOGNITION\n\n"
        "HTML OUTPUT — USE ONLY THESE CSS CLASSES:\n"
        "rv-name, rv-tag, rv-con, rv-sec, rv-sh, rv-it, rv-ith, rv-itn, rv-itd, rv-ito, rv-bul (ul), rv-bul li, "
        "rv-sum, rv-skw (div), rv-sk (span)\n\n"
        "REQUIRED SECTIONS — include all that have data:\n"
        "1. Header: rv-name (full name), rv-tag (course + universities tagline), rv-con (contact row — "
        "wrap linkedin/portfolio in <a href=\"...\"> tags)\n"
        "2. Profile Summary: rv-sum — 3-4 powerful sentences\n"
        "3. Education — school, board, grades, subjects\n"
        "4. Standardised Test Scores (if any)\n"
        "5. Academic Honours & Awards (if any)\n"
        "6. Leadership & Positions of Responsibility\n"
        "7. Research & Intellectual Pursuits (if any)\n"
        "8. Professional Experience & Internships (if any)\n"
        "9. Community Impact & Social Initiatives (if any)\n"
        "10. Extracurricular Activities & Sports\n"
        "11. Projects & Entrepreneurship (if any)\n"
        "12. Skills, Languages & Certifications\n\n"
        "CRITICAL OUTPUT RULES:\n"
        "• Output ONLY the resume HTML — no preamble, no markdown fences, no explanation\n"
        "• Immediately after the HTML, on a NEW LINE, output exactly: SCORES:{...json...}\n"
        "• SCORES JSON must contain: academic, leadership, research, extracurricular, community, global, ats, "
        "overall, fit (all integers 0-100), tier (\"Competitive\"|\"Strong\"|\"Outstanding\"|\"Elite\"), "
        "suggestions (array of 4 actionable strings), booster (string or empty \"\")\n"
        "• The entire response = [HTML][newline]SCORES:{json} — nothing else."
    )


def generate_resume_raw(d: dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Call OpenAI with server OPENAI_API_KEY.
    Returns (full_raw_text_including_optional_SCORES_line, error_message).
    """
    from django.conf import settings

    api_key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not configured on the server."

    model = (getattr(settings, "OPENAI_MODEL", None) or getattr(settings, "AI_MODEL", None) or "gpt-4o-mini").strip()

    prompt = build_resume_prompt(d)

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45,
            max_tokens=6000,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        return None, str(exc)[:800]

    if not raw:
        return None, "Empty response from AI."

    if len(raw) > 120000:
        return None, "AI response too large."

    return raw, None


