"""Per-user resume profile JSON — single source synced with account data and resume edits."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from core.models import Hobbies, Subject

from .models import (
    UserProfile,
    UserResume,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeSkill,
)

USER_RESUME_PROFILE_VERSION = 1


def _empty_doc() -> dict:
    return {
        "version": USER_RESUME_PROFILE_VERSION,
        "updated_at": "",
        "personal": {"name": "", "email": "", "phone": "", "headline": ""},
        "education": {"school": "", "grade": ""},
        "summary": "",
        "skills": [],
        "projects": [],
        "certificates": [],
        "achievements": [],
        "activities": [],
        "interests": [],
    }


def _load_doc(raw: str | None) -> dict:
    if not raw:
        return _empty_doc()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return _empty_doc()
    if not isinstance(data, dict):
        return _empty_doc()
    base = _empty_doc()
    for key in base:
        if key in data:
            base[key] = data[key]
    return base


def _save_doc(profile: UserProfile, doc: dict) -> None:
    doc = dict(doc)
    doc["version"] = USER_RESUME_PROFILE_VERSION
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    profile.resume_profile_json = json.dumps(doc, ensure_ascii=False, default=str)
    profile.save(update_fields=["resume_profile_json", "modified"])


def _append_unique_str(items: list, value: str) -> bool:
    title = (value or "").strip()
    if not title:
        return False
    key = title.lower()
    existing = {(str(x) if not isinstance(x, dict) else (x.get("title") or x.get("name") or "")).strip().lower() for x in items}
    if key in existing:
        return False
    items.append(title)
    return True


def _merge_account_into_doc(user, doc: dict) -> dict:
    profile = UserProfile.objects.filter(user=user).first()
    personal = doc.setdefault("personal", {})
    personal["name"] = (user.name or "").strip()
    personal["email"] = (user.email or "").strip()
    personal["phone"] = str(user.mobile or "").strip()

    education = doc.setdefault("education", {})
    if profile:
        if (profile.schoolname or "").strip():
            education["school"] = (profile.schoolname or "").strip()
        if (profile.grade or "").strip():
            education["grade"] = (profile.grade or "").strip()
        for subj in profile.subject.all():
            name = getattr(subj, "name", None) or str(subj)
            _append_unique_str(doc.setdefault("skills", []), name)
        for hobby in profile.hobbies.all():
            name = getattr(hobby, "name", None) or str(hobby)
            _append_unique_str(doc.setdefault("interests", []), name)
    return doc


def ensure_user_resume_profile_json(user, *, merge_account: bool = True) -> dict:
    """Load or create the per-user resume JSON; optionally refresh from account data."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    doc = _load_doc(profile.resume_profile_json)
    if merge_account:
        doc = _merge_account_into_doc(user, doc)
        _save_doc(profile, doc)
    return doc


def apply_user_resume_profile_to_resume(user, resume, doc: dict | None = None) -> dict:
    """Populate empty resume sections from the user's profile JSON."""
    doc = doc or ensure_user_resume_profile_json(user)
    imported: list[str] = []

    if not (resume.about or "").strip():
        summary = (doc.get("summary") or "").strip()
        if not summary:
            from .resume_v2_services import ResumeSummaryGenerator

            summary = ResumeSummaryGenerator.generate(user, resume)
        resume.about = summary[:2000]
        resume.save(update_fields=["about", "modified"])
        imported.append("summary")

    existing_skills = {
        (s.title or "").strip().lower()
        for s in UserResumeSkill.objects.filter(resume=resume)
    }
    for skill in doc.get("skills") or []:
        title = skill if isinstance(skill, str) else (skill.get("title") or skill.get("name") or "")
        title = str(title).strip()[:250]
        if title and title.lower() not in existing_skills:
            UserResumeSkill.objects.create(resume=resume, title=title)
            existing_skills.add(title.lower())
            imported.append("skills")

    if not UserResumeActivity.objects.filter(resume=resume).exists():
        for proj in doc.get("projects") or []:
            if isinstance(proj, dict):
                title = (proj.get("title") or "").strip()[:250]
                desc = (proj.get("description") or "").strip()[:2000]
                tech = (proj.get("technologies") or "").strip()
            else:
                title = str(proj).strip()[:250]
                desc = "Project from profile."
                tech = ""
            if not title:
                continue
            full_desc = f"Technologies: {tech}\n{desc}" if tech else desc
            UserResumeActivity.objects.create(resume=resume, title=title, description=full_desc[:2000])
            imported.append("projects")

        for act in doc.get("activities") or doc.get("achievements") or []:
            if isinstance(act, dict):
                title = (act.get("title") or "").strip()[:250]
                desc = (act.get("description") or "Activity from profile.").strip()[:2000]
            else:
                title = str(act).strip()[:250]
                desc = "Activity from profile."
            if title:
                UserResumeActivity.objects.create(resume=resume, title=title, description=desc)
                imported.append("activities")

        for interest in doc.get("interests") or []:
            name = str(interest).strip()[:250]
            if name:
                UserResumeActivity.objects.create(
                    resume=resume,
                    title=name,
                    description="Extracurricular interest from profile.",
                )
                imported.append("activities")

    if not UserResumeCertificate.objects.filter(resume=resume).exists():
        for cert in doc.get("certificates") or []:
            if isinstance(cert, dict):
                title = (cert.get("title") or cert.get("name") or "").strip()[:250]
                desc = (cert.get("description") or cert.get("issuer") or "").strip()[:2000]
            else:
                title = str(cert).strip()[:250]
                desc = ""
            if title:
                UserResumeCertificate.objects.create(resume=resume, title=title, description=desc)
                imported.append("certificates")

    if doc.get("education", {}).get("school") or doc.get("education", {}).get("grade"):
        imported.append("education")
    if doc.get("personal", {}).get("name") or doc.get("personal", {}).get("email"):
        imported.append("personal")

    return {"imported": list(dict.fromkeys(imported)), "success": True}


def bootstrap_user_resume_from_profile(user, resume, request=None) -> dict:
    """Refresh user JSON from account, then apply to resume (automatic fill)."""
    doc = ensure_user_resume_profile_json(user, merge_account=True)
    result = apply_user_resume_profile_to_resume(user, resume, doc)
    if request is not None:
        from .resume_v2_services import sync_studio_proto_resume_from_db

        sync_studio_proto_resume_from_db(resume, request)
    return result


def apply_profile_autofill(user, resume) -> dict:
    """Back-compat alias used by autofill endpoint — now automatic."""
    return bootstrap_user_resume_from_profile(user, resume)


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def sync_skill_to_user_profile(user, title: str) -> None:
    title = (title or "").strip()
    if not title:
        return
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    if _append_unique_str(doc.setdefault("skills", []), title):
        _save_doc(profile, doc)
    subj = Subject.objects.filter(name__iexact=title).first()
    if subj:
        profile.subject.add(subj)


def sync_activity_to_user_profile(user, title: str, description: str) -> None:
    title = (title or "").strip()
    if not title:
        return
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    entry = {"title": title, "description": (description or "").strip()[:2000]}
    if (description or "").startswith("Technologies: "):
        bucket = doc.setdefault("projects", [])
    else:
        bucket = doc.setdefault("achievements", [])
    keys = {(x.get("title") or "").strip().lower() for x in bucket if isinstance(x, dict)}
    if title.lower() not in keys:
        bucket.append(entry)
        _save_doc(profile, doc)
    hobby = Hobbies.objects.filter(name__iexact=title).first()
    if hobby:
        profile.hobbies.add(hobby)


def sync_certificate_to_user_profile(user, title: str, description: str = "") -> None:
    title = (title or "").strip()
    if not title:
        return
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    bucket = doc.setdefault("certificates", [])
    keys = {(x.get("title") or x.get("name") or "").strip().lower() for x in bucket if isinstance(x, dict)}
    if title.lower() not in keys:
        bucket.append({"title": title, "description": (description or "").strip()[:2000]})
        _save_doc(profile, doc)


def sync_summary_to_user_profile(user, summary: str) -> None:
    summary = (summary or "").strip()
    if not summary:
        return
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    doc["summary"] = summary[:5000]
    _save_doc(profile, doc)


def sync_headline_to_user_profile(user, headline: str) -> None:
    headline = (headline or "").strip()
    if not headline:
        return
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    doc.setdefault("personal", {})["headline"] = headline[:200]
    _save_doc(profile, doc)


def sync_personal_fields_to_user_profile(
    user,
    *,
    name: str | None = None,
    phone: str | None = None,
    school: str | None = None,
    grade: str | None = None,
) -> None:
    """Persist studio personal edits to account + per-user resume JSON."""
    profile = _get_profile(user)
    doc = _load_doc(profile.resume_profile_json)
    personal = doc.setdefault("personal", {})
    user_updates: list[str] = []
    profile_updates: list[str] = []

    if name is not None:
        clean = (name or "").strip()[:250]
        if clean:
            personal["name"] = clean
            existing = (user.name or "").strip()
            if not existing or existing == "Student" or existing.lower() == (user.email or "").strip().lower():
                user.name = clean
                user_updates.append("name")

    if phone is not None:
        clean = (phone or "").strip()[:25]
        if clean:
            personal["phone"] = clean
            if not str(user.mobile or "").strip():
                user.mobile = clean
                user_updates.append("mobile")

    if school is not None:
        clean = (school or "").strip()[:250]
        if clean:
            personal["school"] = clean
            if not (profile.schoolname or "").strip():
                profile.schoolname = clean
                profile_updates.append("schoolname")

    if grade is not None:
        clean = (grade or "").strip()[:100]
        if clean:
            personal["grade"] = clean
            if not (profile.grade or "").strip():
                profile.grade = clean
                profile_updates.append("grade")

    if user_updates:
        user.save(update_fields=user_updates + ["modified"])
    if profile_updates:
        profile.save(update_fields=profile_updates + ["modified"])
    _save_doc(profile, doc)
