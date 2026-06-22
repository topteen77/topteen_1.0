"""Shared resume editor JSON for classic builder modals (template20) and API responses."""

import html
import json
import re

from core import choices

from .models import (
    UserProfile,
    UserResume,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
)

# Studio iframe “Save as new copy” — wizard JSON + server PDF generated_html
STUDIO_PROTO_V1_KEY = "studio_proto_v1"
# Wizard root flag: keep using AI `generated_html` for PDF while studio_proto_v1 drives the template library.
WIZARD_PREFER_GENERATED_PDF_KEY = "prefer_generated_pdf"
DEFAULT_STUDIO_EMBED_FONT = '"Inter", system-ui, sans-serif'

_STUDIO_COLOR_HEX = {
    "teal": "#1b9e7a",
    "blue": "#2563eb",
    "sky": "#0ea5e9",
    "indigo": "#4f46e5",
    "green": "#16a34a",
    "purple": "#7c3aed",
    "orange": "#ea580c",
    "rose": "#e11d48",
    "slate": "#334155",
    "black": "#171717",
}


def _wizard_is_studio_only(wiz: dict) -> bool:
    if not isinstance(wiz, dict) or STUDIO_PROTO_V1_KEY not in wiz:
        return False
    keys = {k for k in wiz.keys() if k not in (WIZARD_PREFER_GENERATED_PDF_KEY,)}
    return keys == {STUDIO_PROTO_V1_KEY}


def wizard_prefers_generated_pdf(resume) -> bool:
    wiz = _wizard_draft_dict(resume)
    return bool(wiz and wiz.get(WIZARD_PREFER_GENERATED_PDF_KEY))


def ensure_studio_proto_v1_defaults_saved(resume, request=None) -> bool:
    """
    If wizard JSON has no usable studio_proto_v1.resume, persist one built from the
    guided/AI wizard + DB rows so the template library iframe starts with that content
    (default layout: classic-sidebar).
    """
    wiz = _wizard_draft_dict(resume)
    if wiz is None:
        wiz = {}
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    has_meaningful = False
    if isinstance(sp, dict):
        rd = sp.get("resume")
        if isinstance(rd, dict):
            if (str(rd.get("fullName") or "").strip() or str(rd.get("headline") or "").strip()):
                has_meaningful = True
            ex = rd.get("experience")
            sk = rd.get("skills")
            if isinstance(ex, list) and len(ex) > 0:
                has_meaningful = True
            if isinstance(sk, list) and len(sk) > 0:
                has_meaningful = True
    if has_meaningful:
        return False
    base = resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
    pack = {
        "resume": base,
        "template": "classic-sidebar",
        "color": "teal",
        "font": DEFAULT_STUDIO_EMBED_FONT,
        "textAlign": "start",
    }
    new_wiz = dict(wiz)
    new_wiz[STUDIO_PROTO_V1_KEY] = pack
    if (str(getattr(resume, "generated_html", None) or "").strip()):
        # Keep server PDF on AI HTML until the user works from a studio-first copy without this flag.
        new_wiz.setdefault(WIZARD_PREFER_GENERATED_PDF_KEY, True)
    resume.wizard_draft_json = json.dumps(new_wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])
    return True


def _merge_studio_proto_resume_into_payload(payload: dict, proto_resume: dict) -> dict:
    if not isinstance(proto_resume, dict):
        return payload
    keys = (
        "fullName",
        "headline",
        "email",
        "phone",
        "address",
        "linkedin",
        "website",
        "summary",
        "photo",
        "skills",
        "experience",
        "education",
        "certifications",
        "languages",
        "interests",
    )
    out = dict(payload)
    for k in keys:
        if k not in proto_resume:
            continue
        v = proto_resume[k]
        if k in ("skills", "experience", "education", "certifications", "languages"):
            if isinstance(v, list):
                out[k] = v
        elif k == "interests":
            out[k] = str(v or "")
        else:
            out[k] = v
    return out


def studio_prefs_from_resume_record(resume) -> dict:
    if resume is None:
        return {}
    wiz = _wizard_draft_dict(resume)
    if not wiz:
        return {}
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    if not isinstance(sp, dict):
        return {}
    out = {}
    for k in ("template", "color", "font", "textAlign"):
        v = sp.get(k)
        if v is not None and str(v).strip():
            out[k] = v
    return out


def _studio_level_to_proficiency(level) -> int:
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return choices.UserResumeProficiency.BEGINNER
    if lv <= 2:
        return choices.UserResumeProficiency.BEGINNER
    if lv <= 3:
        return choices.UserResumeProficiency.INTERMEDIATE
    return choices.UserResumeProficiency.EXPERT


def apply_studio_resume_to_userresume_children(resume, rd: dict) -> None:
    """Replace child rows from prototype resumeData (skills, experience, certifications, …)."""
    UserResumeSkill.objects.filter(resume=resume).delete()
    UserResumeCertificate.objects.filter(resume=resume).delete()
    UserResumeInternship.objects.filter(resume=resume).delete()
    UserResumeActivity.objects.filter(resume=resume).delete()
    UserResumeVolunteerInvolvement.objects.filter(resume=resume).delete()

    for sk in rd.get("skills") or []:
        name = (sk.get("name") or "").strip()
        if not name:
            continue
        UserResumeSkill.objects.create(
            resume=resume,
            title=name[:250],
            description="",
            profficiency=_studio_level_to_proficiency(sk.get("level")),
        )

    for ex in rd.get("experience") or []:
        title = (ex.get("title") or "").strip() or "Experience"
        company = (ex.get("company") or "").strip() or "—"
        bullets = ex.get("bullets") or []
        loc = (ex.get("location") or "").strip()
        bullet_lines = [str(b).strip() for b in bullets if str(b).strip()]
        if loc:
            desc = "\n".join([f"Location: {loc}"] + bullet_lines)[:4000]
        else:
            desc = "\n".join(bullet_lines)[:4000]
        UserResumeInternship.objects.create(
            resume=resume,
            role=title[:250],
            provider=company[:250],
            description=desc,
            start_date=None,
            end_date=None,
        )

    for c in rd.get("certifications") or []:
        nm = (c.get("name") or "").strip()
        if not nm:
            continue
        issuer = (c.get("issuer") or "").strip()
        UserResumeCertificate.objects.create(
            resume=resume,
            title=nm[:250],
            description=issuer[:2000],
            issue_date=None,
        )

    for ed in rd.get("education") or []:
        school = (ed.get("school") or "").strip()
        degree = (ed.get("degree") or "").strip()
        if not school and not degree:
            continue
        title = (degree or "Education")[:250]
        detail = " ".join(x for x in [school, (ed.get("dates") or "").strip(), (ed.get("detail") or "").strip()] if x)[:2000]
        UserResumeActivity.objects.create(
            resume=resume,
            title=title,
            description=detail,
            issue_date=None,
        )

    for lang in rd.get("languages") or []:
        nm = (lang.get("name") or "").strip()
        if not nm:
            continue
        lv = (lang.get("level") or "").strip()
        UserResumeActivity.objects.create(
            resume=resume,
            title=f"Language: {nm}"[:250],
            description=lv[:500],
            issue_date=None,
        )

    interests = (rd.get("interests") or "").strip()
    if interests:
        UserResumeActivity.objects.create(
            resume=resume,
            title="Interests",
            description=interests[:2000],
            issue_date=None,
        )


def studio_v1_pack_to_generated_html(pack: dict) -> str:
    """Self-contained HTML fragment for userresumepdf_generated.html (pdfkit)."""
    rd = pack.get("resume") if isinstance(pack.get("resume"), dict) else {}
    color_id = (pack.get("color") or "teal").strip().lower()
    accent = _STUDIO_COLOR_HEX.get(color_id, _STUDIO_COLOR_HEX["teal"])
    font_raw = (pack.get("font") or '"Inter", system-ui, sans-serif').strip()[:240] or '"Inter", system-ui, sans-serif'
    if not re.match(r'^[\w\s\-",.()+]+$', font_raw):
        font_raw = '"Inter", system-ui, sans-serif'
    align = (pack.get("textAlign") or "start").strip().lower()
    if align not in ("start", "center", "end", "justify"):
        align = "start"
    ta = {"start": "left", "center": "center", "end": "right", "justify": "justify"}.get(align, "left")

    def esc(x):
        return html.escape(str(x or ""), quote=True)

    contact_bits = [
        esc(p)
        for p in [
            rd.get("email"),
            rd.get("phone"),
            rd.get("address"),
            rd.get("linkedin"),
            rd.get("website"),
        ]
        if (p or "").strip()
    ]
    contact_html = " · ".join(contact_bits) if contact_bits else ""

    lines = [
        f'<div class="studio-pdf-root" style="font-family:{font_raw};color:#1a1a2e;text-align:{ta};max-width:820px;margin:0 auto;">',
        f'<div style="border-bottom:3px solid {esc(accent)};padding-bottom:10px;margin-bottom:14px;">',
        f'<div style="font-size:26px;font-weight:700;">{esc(rd.get("fullName"))}</div>',
        f'<div style="font-size:13px;color:#4a5a6e;margin-top:4px;">{esc(rd.get("headline"))}</div>',
        f'<div style="font-size:11px;color:#5a6a80;margin-top:8px;line-height:1.5;">{contact_html}</div>',
        "</div>",
    ]
    sm = (rd.get("summary") or "").strip()
    if sm:
        lines.append(
            f'<div style="margin:14px 0;padding:10px 12px;background:#f4f6fc;border-left:3px solid {esc(accent)};font-size:13px;line-height:1.6;">{esc(sm)}</div>'
        )
    skills = rd.get("skills") or []
    if skills:
        lines.append('<div style="margin-top:16px;"><div style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Skills</div><div style="margin-top:6px;line-height:1.6;font-size:12px;">')
        lines.append(", ".join(esc((s.get("name") or "").strip()) for s in skills if (s.get("name") or "").strip()))
        lines.append("</div></div>")
    for ex in rd.get("experience") or []:
        title = (ex.get("title") or "").strip()
        if not title:
            continue
        co = (ex.get("company") or "").strip()
        dates = (ex.get("dates") or "").strip()
        lines.append('<div style="margin-top:12px;">')
        lines.append(
            f'<div style="display:flex;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;"><span>{esc(title)}</span><span style="font-size:11px;color:#888;white-space:nowrap;">{esc(dates)}</span></div>'
        )
        loc = (ex.get("location") or "").strip()
        sub = " · ".join(x for x in [co, loc] if x)
        if sub:
            lines.append(f'<div style="font-size:12px;color:#5a6a80;font-style:italic;">{esc(sub)}</div>')
        for b in ex.get("bullets") or []:
            bt = str(b).strip()
            if bt:
                lines.append(f'<div style="font-size:12px;margin:3px 0 3px 12px;">▸ {esc(bt)}</div>')
        lines.append("</div>")
    for ed in rd.get("education") or []:
        deg = (ed.get("degree") or "").strip()
        sch = (ed.get("school") or "").strip()
        if not deg and not sch:
            continue
        lines.append(
            f'<div style="margin-top:10px;font-size:12px;"><strong>{esc(deg)}</strong> — {esc(sch)} <span style="color:#888;">{esc(ed.get("dates") or "")}</span></div>'
        )
    for c in rd.get("certifications") or []:
        nm = (c.get("name") or "").strip()
        if not nm:
            continue
        lines.append(
            f'<div style="margin-top:6px;font-size:12px;"><strong>{esc(nm)}</strong> — {esc(c.get("issuer") or "")} <span style="color:#888;">{esc(c.get("date") or "")}</span></div>'
        )
    lines.append("</div>")
    return "\n".join(lines)


def resume_editor_payload(resume):
    """JSON-serializable rows for classic resume modals (edit from DB in the browser)."""

    def dstr(d):
        if not d:
            return ""
        return d.isoformat()

    skills = []
    for s in UserResumeSkill.objects.filter(resume=resume).order_by("id"):
        skills.append(
            {
                "id": s.pk,
                "title": s.title or "",
                "description": s.description or "",
                "profficiency": int(s.profficiency),
            }
        )
    certificates = []
    for c in UserResumeCertificate.objects.filter(resume=resume).order_by("id"):
        certificates.append(
            {
                "id": c.pk,
                "title": c.title or "",
                "description": c.description or "",
                "issue_date": dstr(c.issue_date),
            }
        )
    internships = []
    for it in UserResumeInternship.objects.filter(resume=resume).order_by("id"):
        internships.append(
            {
                "id": it.pk,
                "provider": it.provider or "",
                "role": it.role or "",
                "description": it.description or "",
                "start_date": dstr(it.start_date),
                "end_date": dstr(it.end_date),
            }
        )
    activities = []
    for a in UserResumeActivity.objects.filter(resume=resume).order_by("id"):
        activities.append(
            {
                "id": a.pk,
                "title": a.title or "",
                "description": a.description or "",
                "issue_date": dstr(a.issue_date),
            }
        )
    volunteers = []
    for v in UserResumeVolunteerInvolvement.objects.filter(resume=resume).order_by("id"):
        volunteers.append(
            {
                "id": v.pk,
                "title": v.title or "",
                "role": v.role or "",
                "description": v.description or "",
                "start_date": dstr(v.start_date),
                "end_date": dstr(v.end_date),
            }
        )
    return {
        "skills": skills,
        "certificates": certificates,
        "internships": internships,
        "activities": activities,
        "volunteers": volunteers,
    }


def _iso_range(start, end):
    a = start.isoformat() if start else ""
    b = end.isoformat() if end else ""
    if a and b:
        return f"{a} — {b}"
    if a:
        return a
    if b:
        return b
    return ""


def _desc_bullets(text):
    if not text or not str(text).strip():
        return []
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()][:14]


def _proficiency_level(raw):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 3
    if v == choices.UserResumeProficiency.BEGINNER:
        return 2
    if v == choices.UserResumeProficiency.INTERMEDIATE:
        return 4
    if v == choices.UserResumeProficiency.EXPERT:
        return 5
    return 3


def _absolute_media_url(request, file_field):
    if not file_field:
        return ""
    try:
        url = file_field.url
    except ValueError:
        return ""
    if request is None:
        return url
    return request.build_absolute_uri(url)


def _wizard_draft_dict(resume):
    raw = getattr(resume, "wizard_draft_json", None) or ""
    if not str(raw).strip():
        return None
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return o if isinstance(o, dict) else None


GUIDED_WIZARD_FIELD_KEYS = frozenset(
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
        "board_state",
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
    }
)


def _wizard_guided_slice(wiz: dict | None) -> dict:
    if not isinstance(wiz, dict):
        return {}
    out = {k: wiz[k] for k in GUIDED_WIZARD_FIELD_KEYS if k in wiz}
    for meta in ("generated_once", "proofread"):
        if meta in wiz:
            out[meta] = wiz[meta]
    return out


def _wizard_has_guided_content(wiz: dict | None) -> bool:
    guided = _wizard_guided_slice(wiz)
    for k, v in guided.items():
        if k in ("generated_once", "proofread"):
            continue
        if isinstance(v, str) and v.strip():
            return True
    return False


def _merge_wizard_drafts(primary: dict | None, fallback: dict | None) -> dict:
    """Keep non-empty values in primary; fill gaps from fallback."""
    out = dict(primary or {})
    for k, v in (fallback or {}).items():
        if k in (STUDIO_PROTO_V1_KEY, WIZARD_PREFER_GENERATED_PDF_KEY):
            continue
        if k == "generated_once":
            if not out.get(k) and v:
                out[k] = v
            continue
        if k == "proofread":
            if k not in out and isinstance(v, bool):
                out[k] = v
            continue
        cur = out.get(k)
        if cur is None or (isinstance(cur, str) and not str(cur).strip()):
            if v is None:
                continue
            if isinstance(v, str) and not str(v).strip():
                continue
            out[k] = v
    return out


def _join_drow(*parts) -> str:
    return " | ".join(str(p).strip() for p in parts if p is not None and str(p).strip())


def _map_grade_to_education_level(grade: str) -> str:
    g = (grade or "").strip().lower()
    if not g:
        return ""
    if any(x in g for x in ("o-level", "o level", "gcse")) or re.search(r"\b10\b", g):
        return "Class 10 / O-Levels / GCSE"
    if any(
        x in g
        for x in (
            "11",
            "12",
            "a-level",
            "a level",
            "ib",
            "cbse",
            "icse",
            "+2",
            "plus 2",
            "plus2",
            "hsc",
            "senior",
        )
    ):
        return "Class 11–12 / A-Levels / IB / CBSE / ICSE"
    if "undergraduate" in g or "under grad" in g:
        if "final" in g:
            return "Undergraduate — Final Year"
        return "Undergraduate — Year 1 or 2"
    if any(x in g for x in ("master", "masters", "graduate student", "postgrad")):
        return "Graduate / Masters Student"
    if any(x in g for x in ("mba", "phd", "working professional")):
        return "Working Professional (MBA / PhD applicant)"
    if "gap year" in g or "deferred" in g:
        return "Gap Year / Deferred Entry"
    if "transfer" in g:
        return "Transfer Student"
    return (grade or "").strip()[:120]


def _guess_country_from_user(user) -> str:
    mobile = str(getattr(user, "mobile", None) or "").strip()
    if mobile.startswith("+91") or (len(mobile) == 10 and mobile[0] in "6789"):
        return "India"
    return ""


def _profile_to_wizard_seed(user, profile) -> dict:
    if user is None:
        return {}
    out: dict = {
        "name": (user.name or "").strip()[:200],
        "email": (user.email or "").strip()[:200],
        "phone": str(user.mobile or "").strip()[:80],
    }
    country = _guess_country_from_user(user)
    if country:
        out["country"] = country
    if not profile:
        return out
    school = (profile.schoolname or "").strip()
    if school:
        out["school"] = school[:300]
    level = _map_grade_to_education_level(profile.grade or "")
    if level:
        out["level"] = level[:120]
    subjects = [s.name.strip() for s in profile.subject.all() if getattr(s, "name", None)]
    if subjects:
        out["subjects"] = ", ".join(subjects)[:500]
    streams = [f.name.strip() for f in profile.figure_out.all() if getattr(f, "name", None)]
    if streams:
        out["course"] = ", ".join(streams)[:200]
    hobbies = [h.name.strip() for h in profile.hobbies.all() if getattr(h, "name", None)]
    if hobbies:
        out["hobbies"] = ", ".join(hobbies)[:500]
    return out


def _resume_children_to_wizard_seed(resume) -> dict:
    if resume is None:
        return {}
    out: dict = {}

    about = (resume.about or "").strip()
    if about:
        out["personal"] = about[:4000]

    intern_rows = []
    for it in UserResumeInternship.objects.filter(resume=resume).order_by("id"):
        desc = " ".join(_desc_bullets(it.description))[:800]
        intern_rows.append(
            _join_drow(it.role, it.provider, _iso_range(it.start_date, it.end_date), desc)
        )
    if intern_rows:
        out["intern"] = "\n".join(intern_rows)

    community_rows = []
    for v in UserResumeVolunteerInvolvement.objects.filter(resume=resume).order_by("id"):
        desc = " ".join(_desc_bullets(v.description))[:800]
        community_rows.append(_join_drow(v.title, v.role, _iso_range(v.start_date, v.end_date), desc))
    if community_rows:
        out["community"] = "\n".join(community_rows)

    extra_rows = []
    lang_parts = []
    for a in UserResumeActivity.objects.filter(resume=resume).order_by("id"):
        title = (a.title or "").strip()
        desc = (a.description or "").strip()
        if title.lower().startswith("language:"):
            nm = title.split(":", 1)[-1].strip()
            lang_parts.append(f"{nm} ({desc})" if desc else nm)
            continue
        row = _join_drow(title, desc)
        if row:
            extra_rows.append(row)
    if extra_rows:
        out["extra"] = "\n".join(extra_rows)
    if lang_parts:
        out["langs"] = ", ".join(lang_parts)

    cert_lines = []
    for c in UserResumeCertificate.objects.filter(resume=resume).order_by("id"):
        title = (c.title or "").strip()
        if not title:
            continue
        issuer = (c.description or "").strip()
        date = c.issue_date.isoformat() if c.issue_date else ""
        cert_lines.append(" — ".join(x for x in [title, issuer, date] if x))
    if cert_lines:
        out["certs"] = "\n".join(cert_lines)

    tech_skills = []
    soft_skills = []
    for s in UserResumeSkill.objects.filter(resume=resume).order_by("id"):
        title = (s.title or "").strip()
        if not title:
            continue
        if s.profficiency == choices.UserResumeProficiency.EXPERT:
            tech_skills.append(title)
        elif s.profficiency == choices.UserResumeProficiency.INTERMEDIATE:
            tech_skills.append(title)
        else:
            soft_skills.append(title)
    if tech_skills:
        out["tech"] = ", ".join(tech_skills)[:800]
    if soft_skills:
        out["soft"] = ", ".join(soft_skills)[:800]

    return out


def _studio_payload_to_wizard_seed(rd: dict | None) -> dict:
    if not isinstance(rd, dict):
        return {}
    out: dict = {}
    out["name"] = (rd.get("fullName") or "").strip()[:200]
    out["email"] = (rd.get("email") or "").strip()[:200]
    out["phone"] = (rd.get("phone") or "").strip()[:80]
    out["linkedin"] = (rd.get("linkedin") or "").strip()[:500]
    out["portfolio"] = (rd.get("website") or "").strip()[:500]
    addr = (rd.get("address") or "").strip()
    if addr:
        out["country"] = addr.split(",")[0].strip()[:120]
    headline = (rd.get("headline") or "").strip()
    summary = (rd.get("summary") or "").strip()
    if headline:
        out["course"] = headline[:200]
    if summary:
        out["career"] = summary[:1200]
        if not out.get("personal"):
            out["personal"] = summary[:4000]

    edu = rd.get("education") or []
    if edu and isinstance(edu[0], dict):
        e = edu[0]
        school = (e.get("school") or "").strip()
        degree = (e.get("degree") or "").strip()
        detail = (e.get("detail") or "").strip()
        if school:
            out["school"] = school[:300]
        if degree:
            mapped = _map_grade_to_education_level(degree)
            out["level"] = (mapped or degree)[:120]
            if not out.get("course"):
                out["course"] = degree[:200]
        if detail:
            out["subjects"] = detail[:500]
            if not out.get("gpa"):
                out["gpa"] = detail[:200]

    tech = []
    soft = []
    for sk in rd.get("skills") or []:
        if not isinstance(sk, dict):
            continue
        name = (sk.get("name") or "").strip()
        if not name:
            continue
        try:
            lv = int(sk.get("level"))
        except (TypeError, ValueError):
            lv = 3
        if lv >= 4:
            tech.append(name)
        else:
            soft.append(name)
    if tech:
        out["tech"] = ", ".join(tech)[:800]
    if soft:
        out["soft"] = ", ".join(soft)[:800]

    langs = []
    for lg in rd.get("languages") or []:
        if not isinstance(lg, dict):
            continue
        nm = (lg.get("name") or "").strip()
        lv = (lg.get("level") or "").strip()
        if nm:
            langs.append(f"{nm} ({lv})" if lv else nm)
    if langs:
        out["langs"] = ", ".join(langs)[:500]

    cert_lines = []
    for c in rd.get("certifications") or []:
        if not isinstance(c, dict):
            continue
        nm = (c.get("name") or "").strip()
        if not nm:
            continue
        issuer = (c.get("issuer") or "").strip()
        date = (c.get("date") or "").strip()
        cert_lines.append(" — ".join(x for x in [nm, issuer, date] if x))
    if cert_lines:
        out["certs"] = "\n".join(cert_lines)

    intern_rows = []
    extra_rows = []
    community_rows = []
    for ex in rd.get("experience") or []:
        if not isinstance(ex, dict):
            continue
        title = (ex.get("title") or "").strip()
        company = (ex.get("company") or "").strip()
        dates = (ex.get("dates") or "").strip()
        bullets = ex.get("bullets") or []
        desc = " ".join(str(b).strip() for b in bullets if str(b).strip())[:800]
        row = _join_drow(title, company, dates, desc)
        if not row:
            continue
        company_l = company.lower()
        title_l = title.lower()
        if "volunteer" in company_l or "community" in title_l:
            community_rows.append(row)
        elif company_l == "activity" or title_l.startswith("language:"):
            extra_rows.append(row)
        elif "intern" in title_l:
            intern_rows.append(row)
        else:
            intern_rows.append(row)
    if intern_rows:
        out["intern"] = "\n".join(intern_rows)
    if extra_rows:
        out["extra"] = "\n".join(extra_rows)
    if community_rows:
        out["community"] = "\n".join(community_rows)

    interests = (rd.get("interests") or "").strip()
    if interests:
        out["hobbies"] = interests[:500]
    return out


def _best_sibling_wizard_seed(user, exclude_resume_id) -> dict:
    if user is None:
        return {}
    for sibling in UserResume.objects.filter(user=user).exclude(pk=exclude_resume_id).order_by("-modified"):
        wiz = _wizard_draft_dict(sibling)
        if wiz and _wizard_has_guided_content(wiz):
            return _wizard_guided_slice(wiz)
        child_seed = _resume_children_to_wizard_seed(sibling)
        if _wizard_has_guided_content(child_seed):
            return child_seed
    return {}


def prepare_admitcv_wizard_restore(resume, request=None) -> dict:
    """
    Build wizard JSON for the AdmitCV studio: saved draft wins, then profile,
    resume sections, studio payload, and other resumes for the same user fill gaps.
    """
    existing = _wizard_draft_dict(resume) or {}
    existing_guided = _wizard_guided_slice(existing)
    user = getattr(resume, "user", None)
    profile = UserProfile.objects.filter(user=user).first() if user else None

    inferred: dict = {}
    for layer in (
        _profile_to_wizard_seed(user, profile),
        _resume_children_to_wizard_seed(resume),
        _studio_payload_to_wizard_seed(
            resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=False)
        ),
        _best_sibling_wizard_seed(user, resume.pk),
    ):
        inferred = _merge_wizard_drafts(inferred, layer)

    wiz = existing
    sp = wiz.get(STUDIO_PROTO_V1_KEY) if isinstance(wiz, dict) else None
    if isinstance(sp, dict) and isinstance(sp.get("resume"), dict):
        inferred = _merge_wizard_drafts(
            inferred, _studio_payload_to_wizard_seed(sp["resume"])
        )

    final = _merge_wizard_drafts(inferred, existing_guided)
    for meta_key in (STUDIO_PROTO_V1_KEY, WIZARD_PREFER_GENERATED_PDF_KEY):
        if meta_key in existing:
            final[meta_key] = existing[meta_key]
    if existing.get("generated_once"):
        final["generated_once"] = True
    elif (getattr(resume, "generated_html", None) or "").strip():
        final["generated_once"] = True
    return final


def _split_skill_tokens(text):
    if not text or not str(text).strip():
        return []
    t = str(text).strip()
    if "\n" in t:
        return [x.strip() for x in t.splitlines() if x.strip()][:30]
    return [x.strip() for x in re.split(r"[,;·|]", t) if x.strip()][:30]


def _skills_from_wizard(d):
    skills = []
    for chunk, base_level in ((d.get("tech"), 4), (d.get("soft"), 3)):
        for name in _split_skill_tokens(chunk or ""):
            if len(name) > 1:
                skills.append({"name": name[:160], "level": base_level})
    return skills


def _dedupe_skills_by_name(rows):
    seen = set()
    out = []
    for s in rows:
        nm = (s.get("name") or "").strip().lower()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append(s)
    return out[:24]


def _parse_langs_text(txt):
    if not txt or not str(txt).strip():
        return []
    t = str(txt).strip()
    out = []
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if len(lines) <= 1 and "," in t and not re.search(r"[—–-]", t):
        lines = [x.strip() for x in t.split(",") if x.strip()]
    for line in lines[:14]:
        m = re.match(r"^(.+?)\s*[—–-]\s*(.+)$", line)
        if m:
            out.append({"name": m.group(1).strip()[:80], "level": m.group(2).strip()[:80]})
        else:
            out.append({"name": line[:80], "level": ""})
    return out


def _wizard_experience_blocks(d):
    pairs = [
        ("Internships", d.get("intern")),
        ("Research", d.get("research")),
        ("Leadership", d.get("lead")),
        ("Activities", d.get("extra")),
        ("Sports", d.get("sport")),
        ("Community service", d.get("community")),
        ("Projects", d.get("projects")),
        ("Academic awards", d.get("awards")),
        ("Competitions", d.get("olymp")),
        ("Standardised tests", d.get("tests")),
    ]
    out = []
    for label, val in pairs:
        body = (val or "").strip()
        if not body:
            continue
        bullets = _desc_bullets(body)
        if not bullets:
            bullets = [body[:700]]
        out.append(
            {
                "title": label,
                "company": "—",
                "location": "",
                "dates": "—",
                "bullets": bullets,
            }
        )
    return out


def _wizard_short_summary(d):
    """Short profile text for the prototype — not the full build_plain_resume_summary dump."""
    parts = []
    career = (d.get("career") or "").strip()
    if career:
        parts.append(career[:1200])
    unis = (d.get("unis") or "").strip()
    if unis:
        parts.append("Study destinations: " + unis[:500])
    if parts:
        return "\n\n".join(parts)
    personal = (d.get("personal") or "").strip()
    if personal:
        return personal[:1200]
    return ""


def _wizard_education_rows(d):
    school = (d.get("school") or "").strip()
    level = (d.get("level") or "").strip()
    course = (d.get("course") or "").strip()
    if not (school or level or course):
        return []
    detail_parts = []
    gpa = (d.get("gpa") or "").strip()
    brd = (d.get("board") or "").strip()
    subj = (d.get("subjects") or "").strip()
    if gpa:
        detail_parts.append(gpa)
    if brd:
        detail_parts.append(brd)
    if subj:
        detail_parts.append("Subjects: " + subj[:220])
    return [
        {
            "degree": course or level or "Student",
            "school": school or "—",
            "dates": "",
            "detail": " · ".join(detail_parts)[:500],
        }
    ]


def _wizard_cert_rows(d):
    txt = (d.get("certs") or "").strip()
    if not txt:
        return []
    blocks = re.split(r"\n\s*\n+", txt)
    out = []
    for blk in blocks[:16]:
        line = blk.strip().replace("\n", " ")
        if not line:
            continue
        out.append({"name": line[:220], "issuer": "", "date": ""})
    return out


def _fallback_summary_from_about(about, max_len=900):
    """When there is no wizard, keep a readable summary instead of an enormous blob."""
    a = (about or "").strip()
    if not a:
        return ""
    if len(a) <= max_len:
        return a
    cut = a[:max_len]
    sp = cut.rfind(". ")
    if sp > max_len // 2:
        return cut[: sp + 1].strip()
    return cut.rstrip() + "…"


def resume_studio_prototype_payload(resume, request=None, *, ignore_studio_proto_merge: bool = False):
    """
    Shape matches static resume-builder prototype (app.js resumeData):
    fullName, headline, email, phone, address, linkedin, website, summary, photo,
    skills[{name, level}], experience[...], education[...], certifications[...],
    languages[{name, level}], interests (string).

    ignore_studio_proto_merge: when True, skip merging studio_proto_v1.resume (used when
    building a fresh studio pack from wizard/DB data).
    """
    user = resume.user
    if user is None:
        return {}

    profile = UserProfile.objects.filter(user=user).first()

    skills_out = []
    for s in UserResumeSkill.objects.filter(resume=resume).order_by("id"):
        title = (s.title or "").strip()
        if not title:
            continue
        skills_out.append({"name": title, "level": _proficiency_level(s.profficiency)})

    experience_out = []
    for it in UserResumeInternship.objects.filter(resume=resume).order_by("id"):
        role = (it.role or "").strip() or "Internship"
        provider = (it.provider or "").strip()
        dates = _iso_range(it.start_date, it.end_date)
        bullets = _desc_bullets(it.description)
        if not bullets and (it.description or "").strip():
            bullets = [(it.description or "").strip()[:500]]
        experience_out.append(
            {
                "title": role,
                "company": provider or "—",
                "location": "",
                "dates": dates or "—",
                "bullets": bullets,
            }
        )

    for a in UserResumeActivity.objects.filter(resume=resume).order_by("id"):
        title = (a.title or "").strip() or "Activity"
        dates = a.issue_date.isoformat() if a.issue_date else ""
        bullets = _desc_bullets(a.description)
        experience_out.append(
            {
                "title": title,
                "company": "Activity",
                "location": "",
                "dates": dates or "—",
                "bullets": bullets,
            }
        )

    for v in UserResumeVolunteerInvolvement.objects.filter(resume=resume).order_by("id"):
        title = (v.title or "").strip() or "Volunteer"
        role = (v.role or "").strip()
        company = "Volunteer" + (f" · {role}" if role else "")
        dates = _iso_range(v.start_date, v.end_date)
        bullets = _desc_bullets(v.description)
        experience_out.append(
            {
                "title": title,
                "company": company,
                "location": "",
                "dates": dates or "—",
                "bullets": bullets,
            }
        )

    education_out = []
    if profile:
        school = (profile.schoolname or "").strip()
        grade = (profile.grade or "").strip()
        if school or grade:
            degree = grade or "Student"
            education_out.append(
                {
                    "degree": degree,
                    "school": school or "—",
                    "dates": "",
                    "detail": "",
                }
            )

    certs_out = []
    for c in UserResumeCertificate.objects.filter(resume=resume).order_by("id"):
        title = (c.title or "").strip()
        if not title:
            continue
        desc = (c.description or "").strip()
        certs_out.append(
            {
                "name": title,
                "issuer": (desc[:120] + "…") if len(desc) > 120 else desc,
                "date": c.issue_date.isoformat() if c.issue_date else "",
            }
        )

    hobby_names = []
    if profile:
        hobby_names = [h.name for h in profile.hobbies.all()[:30] if getattr(h, "name", None)]

    parts_addr = []
    if profile and (profile.schoolname or "").strip():
        parts_addr.append((profile.schoolname or "").strip())
    if profile and (profile.grade or "").strip():
        parts_addr.append((profile.grade or "").strip())

    # Prefer resume-specific photo (used by template picker); fallback to user profile avatar.
    photo = _absolute_media_url(request, getattr(resume, "image", None)) or _absolute_media_url(
        request, getattr(user, "image", None)
    )

    full_name = (user.name or "").strip() or (user.email or "").split("@")[0]
    headline = (resume.title or "").strip() or "Resume"
    email = (user.email or "").strip()
    phone = (user.mobile or "").strip()
    linkedin = ""
    website = ""
    summary = (resume.about or "").strip()
    languages_out = []
    interests = ", ".join(hobby_names)

    wiz = _wizard_draft_dict(resume)
    wiz_guided = None
    if wiz:
        wiz_guided = {
            k: v
            for k, v in wiz.items()
            if k not in (STUDIO_PROTO_V1_KEY, WIZARD_PREFER_GENERATED_PDF_KEY)
        }
        if not wiz_guided:
            wiz_guided = None
    if wiz_guided and not _wizard_is_studio_only(wiz):
        wname = (wiz_guided.get("name") or "").strip()
        if wname and not (user.name or "").strip():
            full_name = wname
        headline = (
            (wiz_guided.get("course") or "").strip()
            or (wiz_guided.get("career") or "").strip()[:120]
            or headline
        )[:200]
        email = (wiz_guided.get("email") or "").strip() or email
        phone = (wiz_guided.get("phone") or "").strip() or phone
        linkedin = (wiz_guided.get("linkedin") or "").strip()
        website = (wiz_guided.get("portfolio") or "").strip()
        country = (wiz_guided.get("country") or "").strip()
        if country:
            parts_addr = [country] + [p for p in parts_addr if p]

        wsum = _wizard_short_summary(wiz_guided)
        summary = wsum if wsum else _fallback_summary_from_about(summary, 700)

        wiz_skills = _skills_from_wizard(wiz_guided)
        skills_out = _dedupe_skills_by_name(skills_out + wiz_skills)

        wiz_exp = _wizard_experience_blocks(wiz_guided)
        experience_out = wiz_exp + experience_out

        wiz_edu = _wizard_education_rows(wiz_guided)
        if wiz_edu:
            education_out = wiz_edu + education_out

        wiz_certs = _wizard_cert_rows(wiz_guided)
        if wiz_certs:
            certs_out = wiz_certs + certs_out

        languages_out = _parse_langs_text(wiz_guided.get("langs") or "")

        wh = (wiz_guided.get("hobbies") or "").strip()
        if wh:
            interests = ", ".join(x for x in [wh, interests] if x)

    elif summary:
        summary = _fallback_summary_from_about(summary, 1000)

    out = {
        "fullName": full_name,
        "headline": headline,
        "email": email,
        "phone": phone,
        "address": ", ".join(parts_addr) if parts_addr else "",
        "linkedin": linkedin,
        "website": website,
        "summary": summary,
        "photo": photo,
        "skills": skills_out,
        "experience": experience_out,
        "education": education_out,
        "certifications": certs_out,
        "languages": languages_out,
        "interests": interests,
    }
    if (
        not ignore_studio_proto_merge
        and wiz
        and isinstance(wiz.get(STUDIO_PROTO_V1_KEY), dict)
    ):
        sp = wiz[STUDIO_PROTO_V1_KEY]
        if isinstance(sp.get("resume"), dict):
            out = _merge_studio_proto_resume_into_payload(out, sp["resume"])
    return out


def guided_wizard_payload_for_studio(resume, request, guided_draft: dict | None) -> dict:
    """
    Merge the latest guided step answers into the in-memory wizard JSON (without saving),
    then build studio resumeData from DB + wizard (same rules as resume_studio_prototype_payload).
    """
    old_json = resume.wizard_draft_json
    try:
        wiz = dict(_wizard_draft_dict(resume) or {})
        if isinstance(guided_draft, dict):
            for k, v in guided_draft.items():
                wiz[k] = v
        resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
        return resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
    finally:
        resume.wizard_draft_json = old_json


def merge_studio_resume_ai_overlay(base: dict, overlay_raw: dict | None) -> dict:
    """
    Combine DB/wizard-derived resumeData with AI RESUME_DATA. AI non-empty fields win;
    AI empty lists do not wipe base lists (so a missing AI experience block still keeps wizard data).
    """
    out = normalize_studio_resume_payload(base)
    if not isinstance(overlay_raw, dict) or not overlay_raw:
        return out
    ov = normalize_studio_resume_payload(overlay_raw)
    for key in ("fullName", "headline", "email", "phone", "address", "linkedin", "website", "summary", "photo"):
        val = ov.get(key)
        if val is not None and str(val).strip():
            out[key] = val
    for key in ("skills", "experience", "education", "certifications", "languages"):
        v = ov.get(key)
        if isinstance(v, list) and len(v) > 0:
            out[key] = v
    inter = ov.get("interests")
    if inter is not None and str(inter).strip():
        out["interests"] = str(inter).strip()
    return out


def _norm_str(v: object, max_len: int = 8000) -> str:
    if v is None:
        return ""
    t = str(v).strip()
    return t[:max_len] if len(t) > max_len else t


def _norm_skill_item(sk: object) -> dict | None:
    if isinstance(sk, str):
        name = sk.strip()
        if not name:
            return None
        return {"name": name[:200], "level": 3}
    if not isinstance(sk, dict):
        return None
    name = _norm_str(sk.get("name") or sk.get("skill") or sk.get("title"), 200)
    if not name:
        return None
    try:
        lev = int(sk.get("level"))
    except (TypeError, ValueError):
        lev = 3
    return {"name": name, "level": max(1, min(5, lev))}


def _norm_experience_item(ex: object) -> dict | None:
    if not isinstance(ex, dict):
        return None
    title = _norm_str(
        ex.get("title") or ex.get("role") or ex.get("position") or ex.get("job_title"),
        300,
    )
    company = _norm_str(
        ex.get("company") or ex.get("employer") or ex.get("organization") or ex.get("org"),
        300,
    )
    if not title and not company:
        return None
    if not title:
        title = "Experience"
    if not company:
        company = "—"
    loc = _norm_str(ex.get("location") or ex.get("city") or ex.get("place"), 300)
    dates = _norm_str(ex.get("dates") or ex.get("duration") or ex.get("period") or ex.get("date_range"), 200)
    bullets_raw = ex.get("bullets") or ex.get("highlights") or ex.get("points") or []
    bl: list[str] = []
    if isinstance(bullets_raw, str):
        for line in bullets_raw.splitlines():
            t = line.strip().lstrip("•*- ").strip()
            if t:
                bl.append(t[:1200])
    elif isinstance(bullets_raw, list):
        for b in bullets_raw:
            t = _norm_str(b, 1200)
            if t:
                bl.append(t)
    return {
        "title": title,
        "company": company,
        "location": loc,
        "dates": dates,
        "bullets": bl[:24],
    }


def _norm_education_item(ed: object) -> dict | None:
    if not isinstance(ed, dict):
        return None
    degree = _norm_str(ed.get("degree") or ed.get("qualification") or ed.get("program"), 400)
    school = _norm_str(ed.get("school") or ed.get("institution") or ed.get("university") or ed.get("college"), 400)
    if not degree and not school:
        return None
    detail = _norm_str(ed.get("detail") or ed.get("gpa") or ed.get("honours"), 2000)
    return {
        "degree": degree or "Education",
        "school": school,
        "dates": _norm_str(ed.get("dates") or ed.get("duration"), 200),
        "detail": detail,
    }


def _norm_cert_item(c: object) -> dict | None:
    if not isinstance(c, dict):
        return None
    name = _norm_str(c.get("name") or c.get("title") or c.get("certificate"), 400)
    if not name:
        return None
    return {
        "name": name,
        "issuer": _norm_str(c.get("issuer") or c.get("organization"), 400),
        "date": _norm_str(c.get("date") or c.get("year"), 120),
    }


def _norm_lang_item(lg: object) -> dict | None:
    if not isinstance(lg, dict):
        return None
    name = _norm_str(lg.get("name") or lg.get("language"), 200)
    if not name:
        return None
    lv = _norm_str(lg.get("level") or lg.get("proficiency"), 200)
    return {"name": name, "level": lv or "—"}


def normalize_studio_resume_payload(raw: dict) -> dict:
    """
    Coerce AI or partial JSON into the resume studio `resumeData` shape used by
    static/resume-builder-prototype/app.js (experience: title, company, location, dates, bullets).
    """
    if not isinstance(raw, dict):
        raw = {}
    skills: list[dict] = []
    for sk in raw.get("skills") or []:
        n = _norm_skill_item(sk)
        if n:
            skills.append(n)
    experience: list[dict] = []
    for ex in raw.get("experience") or []:
        n = _norm_experience_item(ex)
        if n:
            experience.append(n)
    education: list[dict] = []
    for ed in raw.get("education") or []:
        n = _norm_education_item(ed)
        if n:
            education.append(n)
    certs: list[dict] = []
    for c in raw.get("certifications") or []:
        n = _norm_cert_item(c)
        if n:
            certs.append(n)
    langs: list[dict] = []
    for lg in raw.get("languages") or []:
        n = _norm_lang_item(lg)
        if n:
            langs.append(n)
    interests_val = raw.get("interests")
    if isinstance(interests_val, list):
        interests = ", ".join(_norm_str(x, 500) for x in interests_val if _norm_str(x, 500))[:2000]
    else:
        interests = _norm_str(interests_val, 2000)
    photo = _norm_str(raw.get("photo"), 500000)
    if photo and not photo.startswith(("data:", "http://", "https://", "/")):
        photo = ""
    if len(photo) > 500 and not photo.startswith("data:"):
        photo = photo[:500]
    return {
        "fullName": _norm_str(raw.get("fullName") or raw.get("name") or raw.get("full_name"), 300),
        "headline": _norm_str(raw.get("headline") or raw.get("tagline") or raw.get("title_line"), 500),
        "email": _norm_str(raw.get("email"), 320),
        "phone": _norm_str(raw.get("phone") or raw.get("mobile"), 120),
        "address": _norm_str(raw.get("address") or raw.get("location") or raw.get("city"), 500),
        "linkedin": _norm_str(raw.get("linkedin") or raw.get("linkedin_url"), 500),
        "website": _norm_str(raw.get("website") or raw.get("portfolio") or raw.get("url"), 500),
        "summary": _norm_str(raw.get("summary") or raw.get("profile") or raw.get("objective"), 8000),
        "photo": photo,
        "skills": skills[:40],
        "experience": experience[:30],
        "education": education[:20],
        "certifications": certs[:40],
        "languages": langs[:30],
        "interests": interests,
    }


def resume_studio_embed_finish_pdf_urls(request, resume):
    """Absolute URLs for prototype iframe (Finish / server PDF links)."""
    from urllib.parse import urlencode

    from django.urls import reverse

    finish = request.build_absolute_uri(reverse("users:resumebuilder"))
    pdf_base = reverse("users:resumepdf")
    q = urlencode({"resume_id": int(resume.pk)})
    pdf = request.build_absolute_uri(f"{pdf_base}?{q}")
    return finish, pdf
