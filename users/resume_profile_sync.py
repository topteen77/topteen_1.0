"""Profile sync offers — prompt student before copying resume edits to TopTeen profile."""

from __future__ import annotations

from .models import UserProfile
from .resume_profile_store import (
    _get_profile,
    _load_doc,
    sync_activity_to_user_profile,
    sync_certificate_to_user_profile,
    sync_headline_to_user_profile,
    sync_personal_fields_to_user_profile,
    sync_profile_education_to_user_profile,
    sync_skill_to_user_profile,
    sync_summary_to_user_profile,
)
from .resume_v2_services import studio_personal_context

PROFILE_FIELD_LABELS = {
    "name": "Name",
    "phone": "Phone number",
    "school": "School",
    "grade": "Class / grade",
    "headline": "Headline",
    "summary": "Career objective",
    "skill": "Skill",
    "activity": "Activity",
    "project": "Project",
    "certificate": "Certificate",
}


def _profile_doc(user) -> dict:
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return {}
    return _load_doc(profile.resume_profile_json)


def build_profile_sync_offer(kind: str, payload: dict, labels: list[str] | None = None) -> dict:
    label_list = labels or []
    if not label_list and payload:
        for key in payload:
            if key in ("text", "titles", "description", "is_project"):
                continue
            label_list.append(PROFILE_FIELD_LABELS.get(key, key.replace("_", " ").title()))
    return {
        "kind": kind,
        "payload": payload,
        "labels": label_list,
    }


def offer_personal_profile_sync(user, resume, body: dict) -> dict | None:
    ctx = studio_personal_context(user, resume)
    payload: dict = {}
    labels: list[str] = []

    if ctx.get("can_edit_name"):
        name = (body.get("name") or "").strip()[:250]
        if name and name != (ctx.get("name") or "").strip():
            payload["name"] = name
            labels.append(PROFILE_FIELD_LABELS["name"])
    if ctx.get("can_edit_phone"):
        phone = (body.get("phone") or "").strip()[:25]
        if phone and phone != (ctx.get("phone") or "").strip():
            payload["phone"] = phone
            labels.append(PROFILE_FIELD_LABELS["phone"])
    if ctx.get("can_edit_school"):
        school = (body.get("school") or "").strip()[:250]
        if school and school != (ctx.get("school") or "").strip():
            payload["school"] = school
            labels.append(PROFILE_FIELD_LABELS["school"])
    if ctx.get("can_edit_grade"):
        grade = (body.get("grade") or "").strip()[:100]
        if grade and grade != (ctx.get("grade") or "").strip():
            payload["grade"] = grade
            labels.append(PROFILE_FIELD_LABELS["grade"])

    headline = (body.get("headline") or "").strip()[:200]
    if headline:
        doc = _profile_doc(user)
        current = (doc.get("personal") or {}).get("headline") or ""
        if headline != (current or "").strip():
            payload["headline"] = headline
            labels.append(PROFILE_FIELD_LABELS["headline"])

    if not payload:
        return None
    return build_profile_sync_offer("personal", payload, labels)


def offer_education_profile_sync(user, *, school: str, grade: str) -> dict | None:
    school = (school or "").strip()[:250]
    grade = (grade or "").strip()[:100]
    if not school and not grade:
        return None
    profile = UserProfile.objects.filter(user=user).first()
    profile_school = (getattr(profile, "schoolname", None) or "").strip() if profile else ""
    profile_grade = (getattr(profile, "grade", None) or "").strip() if profile else ""
    if school == profile_school and grade == profile_grade:
        return None
    payload = {"school": school, "grade": grade}
    return build_profile_sync_offer(
        "education",
        payload,
        [PROFILE_FIELD_LABELS["school"], PROFILE_FIELD_LABELS["grade"]],
    )


def offer_summary_profile_sync(user, summary: str) -> dict | None:
    summary = (summary or "").strip()[:5000]
    if not summary:
        return None
    doc = _profile_doc(user)
    if summary == (doc.get("summary") or "").strip():
        return None
    return build_profile_sync_offer(
        "summary",
        {"text": summary},
        [PROFILE_FIELD_LABELS["summary"]],
    )


def offer_headline_profile_sync(user, headline: str) -> dict | None:
    headline = (headline or "").strip()[:200]
    if not headline:
        return None
    doc = _profile_doc(user)
    current = (doc.get("personal") or {}).get("headline") or ""
    if headline == (current or "").strip():
        return None
    return build_profile_sync_offer(
        "headline",
        {"headline": headline},
        [PROFILE_FIELD_LABELS["headline"]],
    )


def offer_skills_profile_sync(user, raw_title: str) -> dict | None:
    titles: list[str] = []
    for chunk in (raw_title or "").replace(";", ",").split(","):
        part = chunk.strip()
        if part:
            titles.append(part[:250])
    if not titles:
        return None
    doc = _profile_doc(user)
    existing = {
        (x or "").strip().lower()
        for x in (doc.get("skills") or [])
        if isinstance(x, str) or x is not None
    }
    new_titles = [t for t in titles if t.lower() not in existing]
    if not new_titles:
        return None
    if len(new_titles) == 1:
        labels = [PROFILE_FIELD_LABELS["skill"] + f" ({new_titles[0]})"]
    else:
        labels = [PROFILE_FIELD_LABELS["skill"]]
    return build_profile_sync_offer("skills", {"titles": new_titles}, labels)


def offer_activity_profile_sync(user, title: str, description: str) -> dict | None:
    title = (title or "").strip()[:250]
    if not title:
        return None
    desc = (description or "").strip()[:2000]
    is_project = desc.startswith("Technologies: ")
    label = PROFILE_FIELD_LABELS["project"] if is_project else PROFILE_FIELD_LABELS["activity"]
    return build_profile_sync_offer(
        "activity",
        {"title": title, "description": desc, "is_project": is_project},
        [label],
    )


def offer_certificate_profile_sync(user, title: str, description: str = "") -> dict | None:
    title = (title or "").strip()[:250]
    if not title:
        return None
    doc = _profile_doc(user)
    bucket = doc.get("certificates") or []
    keys = {
        (x.get("title") or x.get("name") or "").strip().lower()
        for x in bucket
        if isinstance(x, dict)
    }
    if title.lower() in keys:
        return None
    return build_profile_sync_offer(
        "certificate",
        {"title": title, "description": (description or "").strip()[:2000]},
        [PROFILE_FIELD_LABELS["certificate"]],
    )


def apply_profile_sync_offer(user, offer: dict) -> None:
    kind = (offer.get("kind") or "").strip()
    payload = offer.get("payload") or {}
    if kind == "personal":
        sync_kwargs = {}
        headline = payload.pop("headline", None)
        for key in ("name", "phone", "school", "grade"):
            if key in payload:
                sync_kwargs[key] = payload[key]
        if sync_kwargs:
            sync_personal_fields_to_user_profile(user, **sync_kwargs)
        if headline:
            sync_headline_to_user_profile(user, headline)
    elif kind == "education":
        sync_profile_education_to_user_profile(
            user,
            school=payload.get("school") or "",
            grade=payload.get("grade") or "",
        )
    elif kind == "summary":
        sync_summary_to_user_profile(user, payload.get("text") or "")
    elif kind == "headline":
        sync_headline_to_user_profile(user, payload.get("headline") or "")
    elif kind == "skills":
        for title in payload.get("titles") or []:
            sync_skill_to_user_profile(user, title)
    elif kind == "activity":
        sync_activity_to_user_profile(
            user,
            payload.get("title") or "",
            payload.get("description") or "",
        )
    elif kind == "certificate":
        sync_certificate_to_user_profile(
            user,
            payload.get("title") or "",
            payload.get("description") or "",
        )
