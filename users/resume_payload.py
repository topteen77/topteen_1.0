"""Shared resume editor JSON for classic builder modals (template20) and API responses."""

import html
import json
import re

from core import choices

from .models import (
    UserProfile,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
)

# Studio iframe “Save as new copy” — wizard JSON + server PDF generated_html
STUDIO_PROTO_V1_KEY = "studio_proto_v1"

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
    return set(wiz.keys()) == {STUDIO_PROTO_V1_KEY}


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
        desc = "\n".join(str(b).strip() for b in bullets if str(b).strip())[:4000]
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
        if co:
            lines.append(f'<div style="font-size:12px;color:#5a6a80;font-style:italic;">{esc(co)}</div>')
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
        parts.append("Target universities: " + unis[:500])
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


def resume_studio_prototype_payload(resume, request=None):
    """
    Shape matches static resume-builder prototype (app.js resumeData):
    fullName, headline, email, phone, address, linkedin, website, summary, photo,
    skills[{name, level}], experience[...], education[...], certifications[...],
    languages[{name, level}], interests (string).
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

    photo = _absolute_media_url(request, getattr(user, "image", None))

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
    if wiz and not _wizard_is_studio_only(wiz):
        wname = (wiz.get("name") or "").strip()
        if wname and not (user.name or "").strip():
            full_name = wname
        headline = (
            (wiz.get("course") or "").strip()
            or (wiz.get("career") or "").strip()[:120]
            or headline
        )[:200]
        email = (wiz.get("email") or "").strip() or email
        phone = (wiz.get("phone") or "").strip() or phone
        linkedin = (wiz.get("linkedin") or "").strip()
        website = (wiz.get("portfolio") or "").strip()
        country = (wiz.get("country") or "").strip()
        if country:
            parts_addr = [country] + [p for p in parts_addr if p]

        wsum = _wizard_short_summary(wiz)
        summary = wsum if wsum else _fallback_summary_from_about(summary, 700)

        wiz_skills = _skills_from_wizard(wiz)
        skills_out = _dedupe_skills_by_name(skills_out + wiz_skills)

        wiz_exp = _wizard_experience_blocks(wiz)
        experience_out = wiz_exp + experience_out

        wiz_edu = _wizard_education_rows(wiz)
        if wiz_edu:
            education_out = wiz_edu + education_out

        wiz_certs = _wizard_cert_rows(wiz)
        if wiz_certs:
            certs_out = wiz_certs + certs_out

        languages_out = _parse_langs_text(wiz.get("langs") or "")

        wh = (wiz.get("hobbies") or "").strip()
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
    if wiz and isinstance(wiz.get(STUDIO_PROTO_V1_KEY), dict):
        sp = wiz[STUDIO_PROTO_V1_KEY]
        if isinstance(sp.get("resume"), dict):
            out = _merge_studio_proto_resume_into_payload(out, sp["resume"])
    return out


def resume_studio_embed_finish_pdf_urls(request, resume):
    """Absolute URLs for prototype iframe (Finish / server PDF links)."""
    from urllib.parse import urlencode

    from django.urls import reverse

    finish = request.build_absolute_uri(reverse("users:resumebuilder"))
    pdf_base = reverse("users:resumepdf")
    q = urlencode({"resume_id": int(resume.pk)})
    pdf = request.build_absolute_uri(f"{pdf_base}?{q}")
    return finish, pdf
