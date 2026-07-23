"""Resume Builder V2 — profile analyzer, ATS scoring, suggestions, and AI helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from .models import (
    UserProfile,
    UserResume,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
)
from .resume_payload import resume_editor_payload, resume_studio_prototype_payload

STUDIO_PROTO_V2_KEY = "studio_proto_v2"

AI_RESUME_REVIEW_KEY = "ai_resume_review"

# Studio section ids → keys in the AI draft JSON payload.
AI_DRAFT_SECTION_KEYS = {
    "personal": ("headline",),
    "summary": ("summary",),
    "skills": ("skills",),
    "education": ("education",),
    "projects": ("projects",),
    "certificates": ("certificates",),
    "achievements": ("achievements",),
    "experience": ("experience",),
    "languages": ("languages",),
    "hobbies": ("hobbies",),
}

RESUME_GOALS = [
    {"id": "internship", "label": "Internship", "icon": "briefcase"},
    {"id": "scholarship", "label": "Scholarship", "icon": "award"},
    {"id": "college_admission", "label": "College Admission", "icon": "graduation", "solid": True},
    {"id": "part_time", "label": "Part-Time Job", "icon": "time-five"},
    {"id": "full_time", "label": "Full-Time Job", "icon": "building"},
    {"id": "volunteer", "label": "Volunteer Program", "icon": "heart"},
    {"id": "competition", "label": "Competition", "icon": "trophy"},
]

# Legacy V2 picker ids → prototype renderer keys (studio_proto_v1.template).
LEGACY_V2_TEMPLATE_IDS = {
    "student_modern": "minimalist",
    "student_professional": "classic-sidebar",
    "ats_basic": "tech-focus",
    "ats_advanced": "professional-border",
    "modern": "modern-split",
    "corporate": "executive",
    "elegant": "elegant-serif",
}

# Badges / scores for highlighted layouts (optional marketing labels).
V2_TEMPLATE_META: dict[str, dict] = {
    "minimalist": {"badges": ["Recommended", "Popular"], "ats_score": 92, "popularity": 95},
    "classic-sidebar": {"badges": ["Recommended", "ATS Friendly"], "ats_score": 94, "popularity": 88},
    "tech-focus": {"badges": ["ATS Friendly"], "ats_score": 96, "popularity": 82},
    "professional-border": {"badges": ["ATS Friendly"], "ats_score": 97, "popularity": 76},
    "modern-split": {"badges": ["Popular"], "ats_score": 85, "popularity": 90},
    "executive": {"badges": [], "ats_score": 88, "popularity": 72},
    "elegant-serif": {"badges": [], "ats_score": 80, "popularity": 65},
    "colored-header": {"badges": ["Popular"], "ats_score": 84, "popularity": 78},
    "bold-header": {"badges": [], "ats_score": 78, "popularity": 68},
    "geometric": {"badges": ["Creative"], "ats_score": 75, "popularity": 70},
    "magazine": {"badges": ["Creative"], "ats_score": 76, "popularity": 72},
    "timeline": {"badges": [], "ats_score": 83, "popularity": 74},
    "studio": {"badges": ["Modern"], "ats_score": 86, "popularity": 80},
}

# Back-compat alias — full list comes from v2_templates_catalog().
V2_TEMPLATES: list[dict] = []

STUDENT_SECTIONS = [
    "personal",
    "education",
    "skills",
    "projects",
    "certificates",
    "languages",
    "hobbies",
    "achievements",
    "summary",
]

EXPERIENCED_SECTIONS = [
    "personal",
    "summary",
    "experience",
    "projects",
    "skills",
    "certificates",
    "languages",
    "hobbies",
]

SECTION_LABELS = {
    "personal": "About you",
    "education": "Education",
    "skills": "Skills",
    "projects": "Projects",
    "certificates": "Certificates",
    "languages": "Languages",
    "hobbies": "Hobbies",
    "achievements": "Achievements & Activities",
    "summary": "Career Objective",
    "experience": "Work Experience",
}

LANGUAGE_LEVEL_OPTIONS = [
    "Native",
    "Fluent",
    "Advanced",
    "Intermediate",
    "Basic",
    "Beginner",
]

_LANGUAGE_LEVEL_ALIASES = {
    "native / mother tongue": "Native",
    "mother tongue": "Native",
    "native speaker": "Native",
    "professional working proficiency": "Fluent",
    "full professional proficiency": "Advanced",
    "conversational": "Intermediate",
    "intermediate (b1)": "Intermediate",
    "intermediate (b2)": "Intermediate",
    "elementary": "Basic",
    "basic (a2)": "Basic",
    "beginner (a1)": "Beginner",
}


def _normalize_language_level(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s in LANGUAGE_LEVEL_OPTIONS:
        return s
    lower = s.lower()
    for opt in LANGUAGE_LEVEL_OPTIONS:
        if opt.lower() == lower:
            return opt
    return _LANGUAGE_LEVEL_ALIASES.get(lower, s)


def studio_sections_for_user(user, resume=None) -> list[str]:
    """Canonical studio section order — always current (not stale v2 meta)."""
    analysis = ResumeProfileAnalyzer.analyze(user, resume)
    if analysis["type"] == "student":
        return list(STUDENT_SECTIONS)
    return list(EXPERIENCED_SECTIONS)


def sync_v2_recommended_sections(resume, user) -> list[str]:
    """Keep wizard v2 meta aligned with current section list."""
    sections = studio_sections_for_user(user, resume)
    meta = get_v2_meta(resume)
    if meta.get("recommended_sections") != sections:
        save_v2_meta(resume, {"recommended_sections": sections})
    return sections


def _studio_activity_counts(resume) -> tuple[int, int]:
    """Projects vs achievements, excluding Language/Hobbies/Interests meta rows."""
    from users.resume_payload import _is_resume_meta_activity_title

    projects = 0
    achievements = 0
    # Prefer prefetched relation when present (dashboard cards).
    activities = list(resume.userresumeactivity_set.all())
    activities.sort(key=lambda a: a.id or 0)
    for a in activities:
        title = (a.title or "").strip()
        if _is_resume_meta_activity_title(title):
            continue
        if (a.description or "").strip().startswith("Technologies:"):
            projects += 1
        else:
            achievements += 1
    return projects, achievements


def _wizard_v2_dict(resume) -> dict:
    raw = getattr(resume, "wizard_draft_json", None) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_v2_meta(resume) -> dict:
    wiz = _wizard_v2_dict(resume)
    meta = wiz.get(STUDIO_PROTO_V2_KEY)
    return meta if isinstance(meta, dict) else {}


def save_v2_meta(resume, patch: dict) -> None:
    wiz = _wizard_v2_dict(resume)
    current = get_v2_meta(resume)
    current.update(patch)
    wiz[STUDIO_PROTO_V2_KEY] = current
    resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])


class ResumeProfileAnalyzer:
    """Detect student vs experienced profile and recommend setup."""

    @staticmethod
    def analyze(user, resume=None) -> dict:
        profile = UserProfile.objects.filter(user=user).first()
        grade = (getattr(profile, "grade", None) or "").strip()
        has_experience = False
        if resume:
            has_experience = UserResumeInternship.objects.filter(resume=resume).exists()
        profile_type = "student"
        if has_experience:
            profile_type = "experienced"
        elif grade and any(g in grade.lower() for g in ("graduate", "bachelor", "master", "phd", "working")):
            profile_type = "experienced"

        if profile_type == "student":
            recommended_template = "minimalist"
            recommended_sections = list(STUDENT_SECTIONS)
        else:
            recommended_template = "modern-split"
            recommended_sections = list(EXPERIENCED_SECTIONS)

        return {
            "type": profile_type,
            "recommended_template": recommended_template,
            "recommended_sections": recommended_sections,
            "grade": grade,
            "school": (getattr(profile, "schoolname", None) or "").strip(),
            "has_experience": has_experience,
        }


class ProfileAutofillDetector:
    """Detect importable profile data for one-click autofill."""

    @staticmethod
    def detect(user, resume=None) -> dict:
        profile = UserProfile.objects.filter(user=user).first()
        found = []
        counts = {}

        if (user.name or "").strip() and (user.name or "").strip() != "Student":
            found.append("Personal Details")
        if user.email:
            found.append("Email")
        if user.mobile:
            found.append("Phone")
        if profile and (profile.schoolname or "").strip():
            found.append("Education")
        if profile and (profile.grade or "").strip():
            found.append("Grade")

        hobby_count = profile.hobbies.count() if profile else 0
        if hobby_count:
            found.append("Interests")
            counts["interests"] = hobby_count

        skill_count = 0
        cert_count = 0
        activity_count = 0
        project_count = 0
        if resume:
            skill_count = UserResumeSkill.objects.filter(resume=resume).count()
            cert_count = UserResumeCertificate.objects.filter(resume=resume).count()
            activity_count = UserResumeActivity.objects.filter(resume=resume).count()
            project_count = activity_count  # activities map to projects/achievements in prototype

        if skill_count:
            found.append("Skills")
            counts["skills"] = skill_count
        if cert_count:
            found.append("Certificates")
            counts["certificates"] = cert_count
        if activity_count:
            found.append("Activities")
            counts["activities"] = activity_count

        missing = []
        if not profile or not (profile.schoolname or "").strip():
            missing.append("Education")
        if skill_count == 0:
            missing.append("Skills")
        if project_count == 0:
            missing.append("Projects")
        if cert_count == 0:
            missing.append("Certifications")
        if activity_count == 0:
            missing.append("Activities")
        if resume and not (resume.about or "").strip():
            missing.append("Career Objective")

        return {
            "found": found,
            "counts": counts,
            "missing": missing,
            "can_autofill": len(found) >= 2,
        }


class ATSScoringService:
    """Rule-based ATS score for prototype (no external API)."""

    _KEYWORDS = (
        "python", "javascript", "java", "sql", "leadership", "teamwork",
        "communication", "problem solving", "project", "internship",
        "certification", "achievement", "volunteer", "research",
    )

    @classmethod
    def score(cls, resume_data: dict) -> dict:
        text_parts = [
            resume_data.get("fullName") or "",
            resume_data.get("headline") or "",
            resume_data.get("summary") or "",
        ]
        for sk in resume_data.get("skills") or []:
            if isinstance(sk, dict):
                text_parts.append(sk.get("name") or "")
        for ex in resume_data.get("experience") or []:
            if isinstance(ex, dict):
                text_parts.extend(ex.get("bullets") or [])
                text_parts.append(ex.get("title") or "")
        blob = " ".join(text_parts).lower()

        found_kw = [kw for kw in cls._KEYWORDS if kw in blob]
        missing_kw = [kw.title() for kw in cls._KEYWORDS if kw not in blob][:5]

        base = 55
        base += min(15, len(resume_data.get("skills") or []) * 3)
        base += min(10, len(resume_data.get("experience") or []) * 4)
        base += min(10, len(found_kw) * 2)
        if (resume_data.get("summary") or "").strip():
            base += 8
        if (resume_data.get("email") or "").strip():
            base += 2

        return {
            "ats_score": min(100, base),
            "readability": min(100, 70 + len(blob.split()) // 10),
            "completeness": cls._completeness(resume_data),
            "keyword_match": min(100, len(found_kw) * 8),
            "professionalism": min(100, 65 + (8 if resume_data.get("summary") else 0)),
            "missing_keywords": missing_kw,
        }

    @staticmethod
    def _completeness(resume_data: dict) -> int:
        checks = [
            bool((resume_data.get("fullName") or "").strip()),
            bool((resume_data.get("email") or "").strip()),
            bool((resume_data.get("summary") or "").strip()),
            bool(resume_data.get("skills")),
            bool(resume_data.get("education")),
            bool(resume_data.get("experience") or resume_data.get("certifications")),
            bool(resume_data.get("languages")),
            bool((resume_data.get("hobbies") or "").strip()),
        ]
        return round(100 * sum(checks) / len(checks))


class ResumeSuggestionService:
    """AI coach suggestions — thresholds match tip text (e.g. 3 skills, 2 projects)."""

    @staticmethod
    def _counts(resume) -> dict:
        if not resume:
            return {
                "skills": 0,
                "projects": 0,
                "certificates": 0,
                "activities": 0,
                "has_summary": False,
            }
        counts = ResumeV2Metrics._item_counts(resume)
        payload = resume_studio_prototype_payload(resume)
        return {
            "skills": counts["skills"],
            "projects": counts["projects"],
            "certificates": counts["certificates"],
            "activities": counts["achievements"],
            "has_summary": bool(
                (payload.get("summary") or "").strip() or (resume.about or "").strip()
            ),
            "has_languages": bool(payload.get("languages")),
            "has_hobbies": bool((payload.get("hobbies") or "").strip()),
        }

    @staticmethod
    def _profile_counts(user) -> dict:
        """Counts from user account + profile (before any resume exists)."""
        profile = UserProfile.objects.filter(user=user).first()
        subjects = list(profile.subject.all()[:20]) if profile else []
        hobbies = list(profile.hobbies.all()[:20]) if profile else []
        return {
            "subjects": len(subjects),
            "subject_names": [getattr(s, "name", str(s)).strip() for s in subjects if getattr(s, "name", str(s)).strip()],
            "hobbies": len(hobbies),
            "hobby_names": [getattr(h, "name", str(h)).strip() for h in hobbies if getattr(h, "name", str(h)).strip()],
            "has_school": bool(profile and (profile.schoolname or "").strip()),
            "has_grade": bool(profile and (profile.grade or "").strip()),
            "has_phone": bool(str(user.mobile or "").strip()),
            "has_photo": user_has_profile_photo(user),
            "has_name": bool((user.name or "").strip() and (user.name or "").strip() != "Student"),
            "profile_completion": user.get_profile_completion_percentage(),
        }

    @staticmethod
    def profile_suggestions(user) -> list:
        """Personalized coach tips from profile data when no resume exists yet."""
        analysis = ResumeProfileAnalyzer.analyze(user)
        pc = ResumeSuggestionService._profile_counts(user)
        items = []
        grade = analysis.get("grade") or ""
        school = analysis.get("school") or ""

        if not pc["has_school"]:
            items.append({
                "text": "Add your school name in My Profile — we'll fill the Education section automatically",
                "action": "complete_profile",
                "section": "education",
                "coach_action": "",
                "priority": "high",
                "link_url": "users:viewprofile",
            })
        if not pc["has_grade"]:
            items.append({
                "text": "Add your grade or class for a stronger resume headline",
                "action": "complete_profile",
                "section": "personal",
                "coach_action": "",
                "priority": "high",
                "link_url": "users:viewprofile",
            })
        if pc["subjects"] == 0:
            items.append({
                "text": "Add favourite subjects in your profile — they'll become skills on your resume",
                "action": "complete_profile",
                "section": "skills",
                "coach_action": "",
                "priority": "high",
                "link_url": "users:viewprofile",
            })
        elif pc["subject_names"]:
            sample = ", ".join(pc["subject_names"][:3])
            extra = f" +{pc['subjects'] - 3} more" if pc["subjects"] > 3 else ""
            items.append({
                "text": f"We'll import skills from your profile: {sample}{extra}",
                "action": "create_resume",
                "section": "skills",
                "coach_action": "",
                "priority": "medium",
            })
        if pc["hobbies"] == 0:
            items.append({
                "text": "Add hobbies or clubs in your profile to showcase extracurricular activities",
                "action": "complete_profile",
                "section": "achievements",
                "coach_action": "",
                "priority": "medium",
                "link_url": "users:viewprofile",
            })
        elif pc["hobby_names"]:
            sample = ", ".join(pc["hobby_names"][:2])
            items.append({
                "text": f"Highlight interests from your profile: {sample}",
                "action": "create_resume",
                "section": "achievements",
                "coach_action": "",
                "priority": "low",
            })
        if not pc["has_phone"]:
            items.append({
                "text": "Add your phone number so employers can contact you",
                "action": "complete_profile",
                "section": "personal",
                "coach_action": "",
                "priority": "medium",
                "link_url": "users:viewprofile",
            })
        if not pc["has_photo"]:
            items.append({
                "text": "Upload a profile photo — it shows on templates that support a picture",
                "action": "complete_profile",
                "section": "personal",
                "coach_action": "",
                "priority": "low",
                "link_url": "users:viewprofile",
            })
        if analysis["type"] == "student" and grade:
            items.append({
                "text": f"Grade {grade} tip: add 2 school projects and any certificates when you build your resume",
                "action": "create_resume",
                "section": "projects",
                "coach_action": "",
                "priority": "medium",
            })
        elif analysis["type"] == "student":
            items.append({
                "text": "Student tip: include school projects, certificates, and a short career objective",
                "action": "create_resume",
                "section": "projects",
                "coach_action": "",
                "priority": "medium",
            })
        if school and pc["has_school"]:
            items.append({
                "text": f"Education ready: {school}" + (f" · Grade {grade}" if grade else ""),
                "action": "profile_ready",
                "section": "education",
                "coach_action": "",
                "priority": "low",
            })
        if pc["profile_completion"] < 70:
            items.append({
                "text": f"Profile {pc['profile_completion']}% complete — fill missing details for a richer auto-filled resume",
                "action": "complete_profile",
                "section": "personal",
                "coach_action": "",
                "priority": "high",
                "link_url": "users:viewprofile",
            })

        if not items:
            items.append({
                "text": "Create your first resume — we'll pull your profile details automatically",
                "action": "create_resume",
                "section": "personal",
                "coach_action": "",
                "priority": "high",
            })

        # De-dupe by text, keep priority order (high first)
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda x: priority_rank.get(x.get("priority"), 9))
        seen = set()
        unique = []
        for item in items:
            key = item["text"]
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique[:5]

    @staticmethod
    def suggestions(user, resume, sections_list=None) -> list:
        if not resume:
            return ResumeSuggestionService.profile_suggestions(user)
        analysis = ResumeProfileAnalyzer.analyze(user, resume)
        counts = ResumeSuggestionService._counts(resume)
        items = []

        if counts["projects"] < 2:
            items.append({
                "text": "Add 2 Projects",
                "action": "add_projects",
                "section": "projects",
                "coach_action": "focus_project",
                "priority": "high",
            })
        if not counts["has_summary"]:
            items.append({
                "text": "Add Career Objective",
                "action": "add_summary",
                "section": "summary",
                "coach_action": "generate_summary",
                "priority": "high",
            })
        if counts["skills"] < 3:
            items.append({
                "text": "Add 3 Skills",
                "action": "add_skills",
                "section": "skills",
                "coach_action": "focus_skill",
                "priority": "medium",
            })
        if counts["certificates"] < 1:
            items.append({
                "text": "Import Certificates",
                "action": "import_certs",
                "section": "certificates",
                "coach_action": "focus_certificate",
                "priority": "medium",
            })
        if not counts.get("has_languages"):
            items.append({
                "text": "Add Languages you speak",
                "action": "add_languages",
                "section": "languages",
                "coach_action": "focus_languages",
                "priority": "medium",
            })
        if not counts.get("has_hobbies"):
            items.append({
                "text": "Add Hobbies to show your interests outside class",
                "action": "add_hobbies",
                "section": "hobbies",
                "coach_action": "focus_hobbies",
                "priority": "low",
            })
        if counts["activities"] < 1:
            items.append({
                "text": "Add Volunteer Activity",
                "action": "add_activity",
                "section": "achievements",
                "coach_action": "focus_achievement",
                "priority": "low",
            })

        if (
            analysis["type"] == "student"
            and counts["has_summary"]
            and len((resume.about or "").strip()) < 80
            and not any(i["action"] == "add_summary" for i in items)
        ):
            items.append({
                "text": "Improve Career Objective for student profile",
                "action": "improve_summary",
                "section": "summary",
                "coach_action": "generate_summary",
                "priority": "medium",
            })

        return items[:5]


class ResumeV2Metrics:
    """Dashboard and card metrics for a resume."""

    @staticmethod
    def _item_counts(resume) -> dict:
        """Counts from DB — source of truth for V2 studio (not stale wizard JSON).

        Uses prefetched child relations when available (``.count()`` would bypass prefetch).
        """
        if not resume:
            return {
                "skills": 0,
                "projects": 0,
                "certificates": 0,
                "activities": 0,
                "achievements": 0,
                "internships": 0,
            }
        projects, achievements = _studio_activity_counts(resume)
        return {
            "skills": len(resume.userresumeskill_set.all()),
            "projects": projects,
            "certificates": len(resume.userresumecertificate_set.all()),
            "activities": projects + achievements,
            "achievements": achievements,
            "internships": len(resume.userresumeinternship_set.all()),
        }

    @staticmethod
    def section_completion(
        resume,
        sections: list | None = None,
        *,
        payload: dict | None = None,
        counts: dict | None = None,
    ) -> dict:
        sections = sections or STUDENT_SECTIONS
        if not resume:
            result = {
                sec: {"percent": 0, "status": "missing", "label": SECTION_LABELS.get(sec, sec.title())}
                for sec in sections
            }
            return {"sections": result, "overall": 0}
        if payload is None:
            payload = resume_studio_prototype_payload(resume)
        if counts is None:
            counts = ResumeV2Metrics._item_counts(resume)
        result = {}

        for sec in sections:
            pct, status = ResumeV2Metrics._section_status(sec, resume, payload, counts)
            result[sec] = {"percent": pct, "status": status, "label": SECTION_LABELS.get(sec, sec.title())}

        values = [v["percent"] for v in result.values()]
        overall = round(sum(values) / len(values)) if values else 0
        return {"sections": result, "overall": overall}

    @staticmethod
    def _section_status(section: str, resume, payload: dict, counts: dict | None = None) -> tuple:
        if counts is None:
            counts = ResumeV2Metrics._item_counts(resume)
        if section == "personal":
            has_name = bool((payload.get("fullName") or "").strip())
            has_email = bool((payload.get("email") or "").strip())
            has_phone = bool((payload.get("phone") or "").strip())
            if has_name and has_email and has_phone:
                return (100, "complete")
            if has_name and has_email:
                return (70, "partial")
            return (40, "partial")
        if section == "education":
            ok = bool(payload.get("education"))
            return (100 if ok else 0, "complete" if ok else "missing")
        if section == "skills":
            n = counts["skills"]
            if n >= 3:
                return (100, "complete")
            if n >= 1:
                return (min(90, 40 + n * 15), "partial")
            return (0, "missing")
        if section == "projects":
            n = counts["projects"]
            if n >= 2:
                return (100, "complete")
            if n >= 1:
                return (60, "partial")
            return (0, "missing")
        if section == "certificates":
            n = counts["certificates"]
            if n >= 1:
                return (100, "complete")
            return (0, "missing")
        if section == "languages":
            n = len(payload.get("languages") or [])
            if n >= 1:
                return (100, "complete")
            return (0, "missing")
        if section == "hobbies":
            ok = bool((payload.get("hobbies") or "").strip())
            return (100 if ok else 0, "complete" if ok else "missing")
        if section == "achievements":
            n = counts["achievements"]
            if n >= 1:
                return (100, "complete")
            return (0, "missing")
        if section == "summary":
            ok = bool((payload.get("summary") or "").strip() or (resume.about or "").strip())
            return (100 if ok else 0, "complete" if ok else "missing")
        if section == "experience":
            n = counts["internships"]
            return (100 if n >= 1 else 0, "complete" if n else "missing")
        return (0, "missing")

    @staticmethod
    def resume_strength(resume, request=None) -> dict:
        if not resume:
            return {
                "score": 0,
                "level": "Beginner",
                "ats": ATSScoringService.score({}),
                "completion": 0,
            }
        payload = resume_studio_prototype_payload(resume, request)
        ats = ATSScoringService.score(payload)
        counts = ResumeV2Metrics._item_counts(resume)
        sections = ResumeV2Metrics.section_completion(
            resume, payload=payload, counts=counts
        )
        score = round((ats["ats_score"] + sections["overall"] + ats["completeness"]) / 3)
        level = "Beginner"
        if score >= 91:
            level = "Outstanding"
        elif score >= 71:
            level = "Strong"
        elif score >= 41:
            level = "Good"
        return {"score": score, "level": level, "ats": ats, "completion": sections["overall"]}


class ResumeSummaryGenerator:
    """Generate or improve summary text via OpenAI (template fallback when unavailable)."""

    @staticmethod
    def generate(user, resume, career_goal: str = "") -> str:
        from .resume_v2_ai import ai_generate_summary

        text, _used_ai = ai_generate_summary(user, resume, career_goal=career_goal)
        return text

    @staticmethod
    def improve(user, resume, text: str, mode: str = "professional") -> str:
        from .resume_v2_ai import ai_improve_summary

        improved, _used_ai = ai_improve_summary(user, resume, text, mode=mode)
        return improved


class ProjectDescriptionGenerator:
    """Generate ATS-friendly bullet points for a project via OpenAI."""

    @staticmethod
    def generate(user, resume, title: str, technologies: str = "") -> list:
        from .resume_v2_ai import ai_generate_project_bullets

        bullets, _used_ai = ai_generate_project_bullets(user, resume, title, technologies)
        return bullets


class AchievementDescriptionGenerator:
    """Generate or improve achievement / activity copy via OpenAI."""

    @staticmethod
    def generate(user, resume, title: str) -> str:
        from .resume_v2_ai import ai_generate_achievement_description

        text, _used_ai = ai_generate_achievement_description(user, resume, title)
        return text

    @staticmethod
    def improve(user, resume, title: str, text: str, mode: str = "professional") -> str:
        from .resume_v2_ai import ai_improve_achievement_description

        improved, _used_ai = ai_improve_achievement_description(user, resume, title, text, mode=mode)
        return improved


def apply_profile_autofill(user, resume) -> dict:
    """Back-compat — delegates to per-user profile JSON bootstrap."""
    from .resume_profile_store import bootstrap_user_resume_from_profile

    return bootstrap_user_resume_from_profile(user, resume)


def v2_template_thumb_class(prototype_key: str) -> str:
    """CSS mock silhouette class for dashboard mini badges (legacy rb2 mocks)."""
    key = (prototype_key or "classic-sidebar").strip().lower()
    return f"rb2-tpl-mock rb2-tpl-mock--{key}"


def v2_template_mock_class(prototype_key: str, catalog_mock: str = "") -> str:
    """Prototype embed mock classes — full set of layout silhouettes for pickers."""
    key = (prototype_key or "classic-sidebar").strip().lower()
    mock = (catalog_mock or f"mock-{key}").strip()
    if not mock.startswith("mock-"):
        mock = f"mock-{key}"
    return f"template-card__mock template-card__{mock}"


def _normalize_template_key(template_id: str) -> str:
    tid = (template_id or "").strip().lower()
    return LEGACY_V2_TEMPLATE_IDS.get(tid, tid)


_V2_TEMPLATES_CATALOG_CACHE: list[dict] | None = None
_V2_TEMPLATES_CATALOG_TS: float = 0.0
_V2_TEMPLATES_CATALOG_TTL = 120.0  # seconds; admin template edits pick up shortly


def invalidate_v2_templates_catalog_cache() -> None:
    global _V2_TEMPLATES_CATALOG_CACHE, _V2_TEMPLATES_CATALOG_TS
    _V2_TEMPLATES_CATALOG_CACHE = None
    _V2_TEMPLATES_CATALOG_TS = 0.0


def v2_templates_catalog() -> list[dict]:
    """All studio HTML templates (DB catalog or static fallback) for V2 picker."""
    import time

    global _V2_TEMPLATES_CATALOG_CACHE, _V2_TEMPLATES_CATALOG_TS
    now = time.time()
    if (
        _V2_TEMPLATES_CATALOG_CACHE is not None
        and (now - _V2_TEMPLATES_CATALOG_TS) < _V2_TEMPLATES_CATALOG_TTL
    ):
        return _V2_TEMPLATES_CATALOG_CACHE

    from users.resume_studio_html import (
        ALLOWED_STUDIO_HTML_TEMPLATE_KEYS,
        studio_html_template_catalog_rows,
    )

    out: list[dict] = []
    seen: set[str] = set()
    for row in studio_html_template_catalog_rows():
        key = _normalize_template_key((row.get("id") or "").strip())
        if not key or key not in ALLOWED_STUDIO_HTML_TEMPLATE_KEYS or key in seen:
            continue
        seen.add(key)
        meta = V2_TEMPLATE_META.get(key, {})
        name = (row.get("name") or key.replace("-", " ").title()).strip()
        catalog_mock = (row.get("mock") or f"mock-{key}").strip()
        out.append(
            {
                "id": key,
                "name": name,
                "category": (row.get("category") or "professional").strip().lower(),
                "prototype_key": key,
                "badges": list(meta.get("badges") or []),
                "ats_score": int(meta.get("ats_score", 85)),
                "popularity": int(meta.get("popularity", 70)),
                "thumb_class": v2_template_thumb_class(key),
                "mock_class": v2_template_mock_class(key, catalog_mock),
            }
        )
    _V2_TEMPLATES_CATALOG_CACHE = out
    _V2_TEMPLATES_CATALOG_TS = now
    return out


def template_by_id(template_id: str) -> dict | None:
    tid = _normalize_template_key(template_id)
    if not tid:
        return None
    for t in v2_templates_catalog():
        if t["id"] == tid or t["prototype_key"] == tid:
            return t
    return None


def resolve_resume_template(meta: dict | None, fallback: str = "classic-sidebar") -> dict:
    """Pick the active template row from saved meta (supports legacy ids)."""
    meta = meta or {}
    for key in (meta.get("template_id"), meta.get("prototype_key"), fallback):
        tpl = template_by_id(str(key or ""))
        if tpl:
            return tpl
    return template_by_id(fallback) or {
        "id": fallback,
        "name": fallback.replace("-", " ").title(),
        "prototype_key": fallback,
        "badges": [],
        "ats_score": 85,
        "popularity": 70,
        "thumb_class": v2_template_thumb_class(fallback),
        "mock_class": v2_template_mock_class(fallback),
        "category": "professional",
    }


def resume_card_context(resume, request) -> dict:
    """Dashboard card: metrics, template label, preview URL."""
    strength = ResumeV2Metrics.resume_strength(resume, request)
    meta = get_v2_meta(resume)
    tpl = resolve_resume_template(meta)
    prototype_key = tpl["prototype_key"]
    from django.urls import reverse

    preview_path = reverse("users:resumebuilder_templates_embed", kwargs={"resume_id": resume.pk})
    return {
        "resume": resume,
        "ats_score": strength["ats"]["ats_score"],
        "completion": strength["completion"],
        "strength": strength["score"],
        "level": strength["level"],
        "template_name": tpl["name"] if tpl else "Student Professional",
        "prototype_key": prototype_key,
        "thumb_class": v2_template_thumb_class(prototype_key),
        "preview_url": preview_path + "?mode=preview",
    }


def save_resume_languages(resume, languages_raw: list | None) -> list[dict]:
    """Persist languages in v2 meta and Language:* activity rows for PDF sync."""
    cleaned: list[dict] = []
    for lg in languages_raw or []:
        if not isinstance(lg, dict):
            continue
        name = (lg.get("name") or "").strip()[:200]
        if not name:
            continue
        level = _normalize_language_level(lg.get("level") or "")[:200]
        if not level:
            continue
        cleaned.append({"name": name, "level": level})
    save_v2_meta(resume, {"languages": cleaned})
    UserResumeActivity.objects.filter(resume=resume, title__startswith="Language:").delete()
    for lg in cleaned:
        UserResumeActivity.objects.create(
            resume=resume,
            title=f"Language: {lg['name']}"[:250],
            description=lg["level"][:500],
        )
    return cleaned


def save_resume_hobbies(resume, text: str) -> str:
    """Persist hobbies in v2 meta and a Hobbies activity row."""
    hobbies = (text or "").strip()[:2000]
    save_v2_meta(resume, {"hobbies": hobbies})
    UserResumeActivity.objects.filter(resume=resume, title="Hobbies").delete()
    if hobbies:
        UserResumeActivity.objects.create(
            resume=resume,
            title="Hobbies",
            description=hobbies[:2000],
        )
    return hobbies


def _parse_class_level(grade: str) -> int | None:
    g = (grade or "").strip().lower()
    if re.search(r"\b12\b|12th|xii|twelfth", g):
        return 12
    if re.search(r"\b10\b|10th|tenth", g):
        return 10
    return None


def _normalize_grade_key(grade: str) -> str:
    level = _parse_class_level(grade)
    if level:
        return f"class-{level}"
    return (grade or "").strip().lower()


def _normalize_percentage_store(result_value: str) -> str:
    s = (result_value or "").strip()
    if not s:
        return ""
    try:
        n = float(s)
    except ValueError:
        return s[:50]
    return f"{round(n, 2):.2f}"


def _validate_percentage_value(result_value: str) -> str | None:
    s = (result_value or "").strip()
    if not s:
        return "Enter your percentage"
    try:
        n = float(s)
    except ValueError:
        return "Enter a valid percentage"
    if n < 0 or n > 100:
        return "Percentage must be between 0 and 100"
    if abs(n - round(n, 2)) > 1e-9:
        return "Percentage can have at most 2 decimal places"
    return None


def _validate_education_duplicates(entries: list[dict]) -> str | None:
    grade_keys: set[str] = set()
    passing_years: set[str] = set()
    for raw in entries:
        grade_key = _normalize_grade_key(raw.get("grade") or "")
        if grade_key:
            if grade_key in grade_keys:
                return "This class or grade is already added"
            grade_keys.add(grade_key)
        py = (raw.get("passing_year") or "").strip()
        if not py:
            py = _infer_passing_year((raw.get("dates") or "").strip())
        if py:
            if py in passing_years:
                if py == "studying":
                    return 'Only one entry can use "Currently studying"'
                return "This passing year is already used for another entry"
            passing_years.add(py)
    return None


def _education_entry_has_marks(raw: dict) -> bool:
    if not isinstance(raw, dict):
        return False
    rt = (raw.get("result_type") or "").strip().lower()
    rv = (raw.get("result_value") or "").strip()
    if rt == "percentage" and rv:
        try:
            n = float(rv)
            return 0 <= n <= 100
        except ValueError:
            return False
    if rt == "grade" and rv:
        return True
    detail = (raw.get("detail") or "").strip()
    if detail.endswith("%"):
        try:
            n = float(detail[:-1].strip())
            return 0 <= n <= 100
        except ValueError:
            return False
    if detail.lower().startswith("grade"):
        return bool(detail.split(":", 1)[-1].strip()) if ":" in detail else len(detail) > 6
    return False


def validate_education_entry_payload(
    resume,
    user,
    *,
    school: str,
    grade: str,
    passing_year: str = "",
    result_type: str = "",
    result_value: str = "",
    entry_id: str | None = None,
) -> str | None:
    """Return user-facing error message, or None if valid."""
    school = (school or "").strip()
    grade = (grade or "").strip()
    passing_year = (passing_year or "").strip()
    result_type = (result_type or "").strip().lower()
    result_value = (result_value or "").strip()

    if passing_year == "studying":
        result_type = ""
        result_value = ""

    if result_type == "percentage":
        pct_err = _validate_percentage_value(result_value)
        if pct_err:
            return pct_err
        result_value = _normalize_percentage_store(result_value)
    elif result_type == "grade" and not result_value:
        return "Select a grade"

    if passing_year == "studying":
        for raw in get_v2_meta(resume).get("education_entries") or []:
            if not isinstance(raw, dict):
                continue
            eid = (raw.get("id") or "").strip()
            if entry_id and eid == entry_id:
                continue
            py = (raw.get("passing_year") or "").strip()
            if not py:
                py = _infer_passing_year((raw.get("dates") or "").strip())
            if py == "studying":
                return 'Only one entry can use "Currently studying"'

    ensure_resume_education_entries(resume, user)
    entries: list[dict] = []
    for raw in get_v2_meta(resume).get("education_entries") or []:
        if not isinstance(raw, dict):
            continue
        eid = (raw.get("id") or "").strip()
        if entry_id and eid == entry_id:
            entries.append(
                {
                    "grade": grade,
                    "passing_year": passing_year,
                    "result_type": result_type,
                    "result_value": result_value,
                    "detail": _education_detail_from_result(result_type, result_value, ""),
                }
            )
        else:
            norm = _norm_education_entry(raw)
            if norm:
                entries.append(norm)

    if not entry_id:
        entries.append(
            {
                "grade": grade,
                "passing_year": passing_year,
                "result_type": result_type,
                "result_value": result_value,
                "detail": _education_detail_from_result(result_type, result_value, ""),
            }
        )

    has_12 = any(_parse_class_level(e.get("grade") or "") == 12 for e in entries)
    if has_12:
        class10 = next((e for e in entries if _parse_class_level(e.get("grade") or "") == 10), None)
        if not class10:
            return "Add a Class 10 entry with your marks when you are in Class 12."
        if not _education_entry_has_marks(class10):
            return "Class 10 percentage or grade is required when you are in Class 12."

    dup_err = _validate_education_duplicates(entries)
    if dup_err:
        return dup_err
    return None


def _infer_passing_year(dates: str) -> str:
    d = (dates or "").strip()
    if not d:
        return ""
    low = d.lower()
    if low in ("present", "currently studying", "studying", "current"):
        return "studying"
    year_match = re.search(r"\b(19|20)\d{2}\b", d)
    if year_match:
        return year_match.group(0)
    if re.fullmatch(r"\d{4}", d):
        return d
    return ""


def _parse_result_from_detail(detail: str) -> tuple[str, str]:
    d = (detail or "").strip()
    if not d:
        return "", ""
    if d.endswith("%"):
        return "percentage", d[:-1].strip()
    if d.lower().startswith("grade:"):
        return "grade", d.split(":", 1)[1].strip()
    if d.lower().startswith("grade "):
        return "grade", d[6:].strip()
    return "", ""


def _education_dates_display(passing_year: str, dates_fallback: str = "") -> str:
    py = (passing_year or "").strip()
    if py == "studying":
        return "Currently studying"
    if py.isdigit() and len(py) == 4:
        return py
    return (dates_fallback or "").strip()[:100]


def _education_detail_from_result(
    result_type: str, result_value: str, detail_fallback: str = ""
) -> str:
    rt = (result_type or "").strip().lower()
    rv = (result_value or "").strip()
    if rt == "percentage" and rv:
        return f"{rv}%" if not rv.endswith("%") else rv[:500]
    if rt == "grade" and rv:
        if rv.lower().startswith("grade"):
            return rv[:500]
        return f"Grade: {rv}"[:500]
    return (detail_fallback or "").strip()[:500]


def _norm_education_entry(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    school = (raw.get("school") or "").strip()[:250]
    grade = (raw.get("grade") or "").strip()[:100]
    if not school and not grade:
        return None
    entry_id = (raw.get("id") or "").strip() or None
    dates_fallback = (raw.get("dates") or "").strip()[:100]
    detail_fallback = (raw.get("detail") or "").strip()[:500]
    passing_year = (raw.get("passing_year") or "").strip()[:20]
    if not passing_year:
        passing_year = _infer_passing_year(dates_fallback)
    result_type = (raw.get("result_type") or "").strip().lower()[:20]
    result_value = (raw.get("result_value") or "").strip()[:50]
    if passing_year == "studying":
        result_type = ""
        result_value = ""
    elif not result_type and not result_value:
        result_type, result_value = _parse_result_from_detail(detail_fallback)
    if result_type == "percentage" and result_value:
        result_value = _normalize_percentage_store(result_value)
    dates = _education_dates_display(passing_year, dates_fallback)
    detail = _education_detail_from_result(result_type, result_value, detail_fallback)
    return {
        "id": entry_id or "",
        "school": school,
        "grade": grade,
        "dates": dates,
        "detail": detail,
        "passing_year": passing_year,
        "result_type": result_type,
        "result_value": result_value,
        "is_profile_school": bool(raw.get("is_profile_school")),
    }


def _tag_profile_education_entries(entries: list[dict], user, resume) -> list[dict]:
    """Ensure the profile-linked school row is flagged (incl. legacy resumes)."""
    if not entries:
        return entries
    meta = get_v2_meta(resume)
    pinned_id = (meta.get("profile_education_entry_id") or "").strip()
    personal = studio_personal_context(user, resume)
    profile_school = (personal.get("school") or "").strip().lower()

    flagged = [e for e in entries if e.get("is_profile_school")]
    if len(flagged) == 1:
        target_id = flagged[0].get("id") or ""
    elif pinned_id and any(e.get("id") == pinned_id for e in entries):
        target_id = pinned_id
    elif profile_school:
        target_id = ""
        for e in entries:
            if (e.get("school") or "").strip().lower() == profile_school:
                target_id = e.get("id") or ""
                break
        if not target_id and len(entries) == 1:
            target_id = entries[0].get("id") or ""
    else:
        target_id = ""

    if not target_id:
        return entries

    changed = False
    for e in entries:
        want = e.get("id") == target_id
        if bool(e.get("is_profile_school")) != want:
            e["is_profile_school"] = want
            changed = True

    if changed or pinned_id != target_id:
        save_v2_meta(resume, {"profile_education_entry_id": target_id})
    return entries


def is_profile_education_entry(resume, user, entry_id: str) -> bool:
    ensure_resume_education_entries(resume, user)
    entry_id = (entry_id or "").strip()
    if not entry_id:
        return False
    for raw in get_v2_meta(resume).get("education_entries") or []:
        if isinstance(raw, dict) and (raw.get("id") or "").strip() == entry_id:
            return bool(raw.get("is_profile_school"))
    return False


def ensure_resume_education_entries(resume, user) -> list[dict]:
    """Load education rows from v2 meta; seed from profile school/grade when empty."""
    import uuid

    meta = get_v2_meta(resume)
    personal = studio_personal_context(user, resume)
    school = (personal.get("school") or "").strip()
    grade = (personal.get("grade") or "").strip()

    def normalize_entries(raw_list) -> list[dict]:
        out: list[dict] = []
        for raw in raw_list or []:
            entry = _norm_education_entry(raw)
            if not entry:
                continue
            if not entry["id"]:
                entry["id"] = f"edu-{uuid.uuid4().hex[:8]}"
            if raw.get("is_profile_school"):
                entry["is_profile_school"] = True
            out.append(entry)
        return _tag_profile_education_entries(out, user, resume)

    if "education_entries" in meta:
        entries = normalize_entries(meta.get("education_entries"))
    else:
        entries = None

    if not entries:
        if school or grade:
            entry_id = f"edu-{uuid.uuid4().hex[:8]}"
            entries = [
                {
                    "id": entry_id,
                    "school": school,
                    "grade": grade,
                    "dates": "Currently studying",
                    "detail": "",
                    "passing_year": "studying",
                    "result_type": "",
                    "result_value": "",
                    "is_profile_school": True,
                }
            ]
            save_v2_meta(
                resume,
                {
                    "education_entries": entries,
                    "profile_education_entry_id": entry_id,
                },
            )
        else:
            entries = []
            if "education_entries" not in meta:
                save_v2_meta(resume, {"education_entries": entries})
        return entries

    if entries != (meta.get("education_entries") or []):
        save_v2_meta(resume, {"education_entries": entries})
    return entries


def add_resume_education_entry(
    resume,
    user,
    *,
    school: str,
    grade: str,
    dates: str = "",
    detail: str = "",
    passing_year: str = "",
    result_type: str = "",
    result_value: str = "",
) -> list[dict]:
    import uuid

    ensure_resume_education_entries(resume, user)
    entries = list(get_v2_meta(resume).get("education_entries") or [])
    raw = {
        "id": f"edu-{uuid.uuid4().hex[:8]}",
        "school": (school or "").strip()[:250],
        "grade": (grade or "").strip()[:100],
        "dates": (dates or "").strip()[:100],
        "detail": (detail or "").strip()[:500],
        "passing_year": (passing_year or "").strip()[:20],
        "result_type": (result_type or "").strip()[:20],
        "result_value": (result_value or "").strip()[:50],
    }
    entry = _norm_education_entry(raw)
    if entry:
        entries.append(entry)
    save_v2_meta(resume, {"education_entries": entries})
    return [_norm_education_entry(e) for e in entries if _norm_education_entry(e)]


def delete_resume_education_entry(resume, user, entry_id: str) -> tuple[list[dict], str | None]:
    ensure_resume_education_entries(resume, user)
    entry_id = (entry_id or "").strip()
    entries_raw = [
        e for e in (get_v2_meta(resume).get("education_entries") or []) if isinstance(e, dict)
    ]
    for raw in entries_raw:
        if (raw.get("id") or "").strip() == entry_id and raw.get("is_profile_school"):
            current = [_norm_education_entry(e) for e in entries_raw if _norm_education_entry(e)]
            return current, "Your current school cannot be removed. Edit it to update your profile."
    entries = [e for e in entries_raw if (e.get("id") or "").strip() != entry_id]
    save_v2_meta(resume, {"education_entries": entries})
    return [_norm_education_entry(e) for e in entries if _norm_education_entry(e)], None


def update_resume_education_entry(
    resume,
    user,
    entry_id: str,
    *,
    school: str,
    grade: str,
    dates: str = "",
    detail: str = "",
    passing_year: str = "",
    result_type: str = "",
    result_value: str = "",
) -> list[dict] | None:
    ensure_resume_education_entries(resume, user)
    entry_id = (entry_id or "").strip()
    if not entry_id:
        return None
    entries: list[dict] = []
    found = False
    for raw in get_v2_meta(resume).get("education_entries") or []:
        if not isinstance(raw, dict):
            continue
        eid = (raw.get("id") or "").strip()
        if eid == entry_id:
            found = True
            normalized = _norm_education_entry(
                {
                    "id": eid,
                    "school": (school or "").strip()[:250],
                    "grade": (grade or "").strip()[:100],
                    "dates": (dates or "").strip()[:100],
                    "detail": (detail or "").strip()[:500],
                    "passing_year": (passing_year or "").strip()[:20],
                    "result_type": (result_type or "").strip()[:20],
                    "result_value": (result_value or "").strip()[:50],
                    "is_profile_school": raw.get("is_profile_school"),
                }
            )
            if normalized:
                entries.append(normalized)
        else:
            entry = _norm_education_entry(raw)
            if entry:
                entries.append(entry)
    if not found:
        return None
    save_v2_meta(resume, {"education_entries": entries})
    return [_norm_education_entry(e) for e in entries if _norm_education_entry(e)]


def sync_studio_proto_resume_from_db(resume, request=None) -> None:
    """Refresh studio_proto_v1.resume from DB so preview picks up photo/skills changes."""
    from .resume_payload import (
        STUDIO_PROTO_V1_KEY,
        ensure_studio_proto_v1_defaults_saved,
        resume_studio_prototype_payload,
    )

    ensure_studio_proto_v1_defaults_saved(resume, request)
    resume.refresh_from_db()
    wiz = _wizard_v2_dict(resume)
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    if not isinstance(sp, dict):
        return
    sp = dict(sp)
    sp["resume"] = resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
    wiz[STUDIO_PROTO_V1_KEY] = sp
    resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])


def user_has_profile_photo(user) -> bool:
    """True when the user has a profile image path set."""
    try:
        img = getattr(user, "image", None)
        return bool(img and getattr(img, "name", None))
    except Exception:
        return False


def user_avatar_initial(user) -> str:
    label = (getattr(user, "name", None) or getattr(user, "email", None) or "?").strip()
    return label[0].upper() if label else "?"


def _meaningful_profile_name(user) -> str:
    name = (getattr(user, "name", None) or "").strip()
    if not name or name == "Student":
        return ""
    email = (getattr(user, "email", None) or "").strip().lower()
    if email and name.lower() == email:
        return ""
    return name


def studio_personal_context(user, resume) -> dict:
    """Personal fields for studio form — empty profile values are editable."""
    profile = UserProfile.objects.filter(user=user).first()
    meta = get_v2_meta(resume)
    personal_meta = meta.get("personal") if isinstance(meta.get("personal"), dict) else {}

    profile_name = _meaningful_profile_name(user)
    profile_phone = str(getattr(user, "mobile", None) or "").strip()
    profile_school = (getattr(profile, "schoolname", None) or "").strip() if profile else ""
    profile_grade = (getattr(profile, "grade", None) or "").strip() if profile else ""

    name = profile_name or (personal_meta.get("name") or "").strip()
    phone = profile_phone or (personal_meta.get("phone") or "").strip()
    school = profile_school or (personal_meta.get("school") or "").strip()
    grade = profile_grade or (personal_meta.get("grade") or "").strip()

    return {
        "name": name,
        "email": (getattr(user, "email", None) or "").strip(),
        "phone": phone,
        "school": school,
        "grade": grade,
        "can_edit_name": not profile_name,
        "can_edit_phone": not profile_phone,
        "can_edit_school": not profile_school,
        "can_edit_grade": not profile_grade,
    }


def _media_url_if_set(request, field) -> str:
    if not field or not getattr(field, "name", None):
        return ""
    from .resume_payload import _absolute_media_url

    return _absolute_media_url(request, field) or ""


def resume_has_own_photo(resume) -> bool:
    img = getattr(resume, "image", None)
    return bool(img and getattr(img, "name", None))


def resume_photo_url(request, resume, user) -> str:
    """Resume-specific upload, then profile photo — for studio display and PDF preview."""
    meta = get_v2_meta(resume)
    if meta.get("hide_resume_photo"):
        return ""
    return (
        _media_url_if_set(request, getattr(resume, "image", None))
        or _media_url_if_set(request, getattr(user, "image", None))
        or ""
    )


def filter_missing_keywords(strength: dict, resume) -> list:
    existing = {
        (s.title or "").strip().lower()
        for s in UserResumeSkill.objects.filter(resume=resume)
    }
    out = []
    for kw in (strength.get("ats") or {}).get("missing_keywords") or []:
        if (kw or "").strip().lower() not in existing:
            out.append(kw)
    return out


def add_skills_to_resume(resume, raw_title: str) -> int:
    parts = []
    for chunk in (raw_title or "").replace(";", ",").split(","):
        t = chunk.strip()
        if t:
            parts.append(t[:250])
    if not parts:
        return 0
    existing = {
        (s.title or "").strip().lower()
        for s in UserResumeSkill.objects.filter(resume=resume)
    }
    added = 0
    for title in parts:
        key = title.lower()
        if key in existing:
            continue
        UserResumeSkill.objects.create(resume=resume, title=title)
        existing.add(key)
        added += 1
    return added


def apply_template_to_resume(resume, template_id: str, request=None) -> bool:
    """Persist template choice into studio_proto_v1 for live preview."""
    tpl = template_by_id(template_id)
    if not tpl:
        return False
    from .resume_payload import (
        DEFAULT_STUDIO_EMBED_FONT,
        STUDIO_PROTO_V1_KEY,
        ensure_studio_proto_v1_defaults_saved,
        resume_studio_prototype_payload,
    )

    ensure_studio_proto_v1_defaults_saved(resume, request)
    resume.refresh_from_db()
    wiz = _wizard_v2_dict(resume)
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    if not isinstance(sp, dict):
        sp = {}
    sp = dict(sp)
    sp["template"] = tpl["prototype_key"]
    sp["resume"] = resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
    sp.setdefault("color", sp.get("color") or "teal")
    sp.setdefault("font", sp.get("font") or DEFAULT_STUDIO_EMBED_FONT)
    sp.setdefault("textAlign", sp.get("textAlign") or "start")
    sp.setdefault("fontSize", sp.get("fontSize") or "standard")
    wiz[STUDIO_PROTO_V1_KEY] = sp
    resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])
    save_v2_meta(
        resume,
        {"template_id": tpl["id"], "prototype_key": tpl["prototype_key"]},
    )
    return True


def apply_theme_prefs_to_resume(
    resume,
    request=None,
    *,
    color: str | None = None,
    font_size: str | None = None,
    font_id: str | None = None,
) -> bool:
    """Persist accent color, font family, and resume font size into studio_proto_v1."""
    from .resume_payload import (
        DEFAULT_STUDIO_EMBED_FONT,
        STUDIO_PROTO_V1_KEY,
        STUDIO_THEME_COLORS,
        _STUDIO_FONT_IDS,
        _STUDIO_FONT_SIZES,
        ensure_studio_proto_v1_defaults_saved,
        resume_studio_prototype_payload,
        studio_font_stack_from_id,
    )

    valid_colors = {row["id"] for row in STUDIO_THEME_COLORS}
    valid_sizes = set(_STUDIO_FONT_SIZES.keys())
    color = (color or "").strip().lower()
    font_size = (font_size or "").strip().lower()
    font_id = (font_id or "").strip().lower()
    if color and color not in valid_colors:
        return False
    if font_size and font_size not in valid_sizes:
        return False
    if font_id and font_id not in _STUDIO_FONT_IDS:
        return False
    if not color and not font_size and not font_id:
        return False

    ensure_studio_proto_v1_defaults_saved(resume, request)
    resume.refresh_from_db()
    wiz = _wizard_v2_dict(resume)
    sp = wiz.get(STUDIO_PROTO_V1_KEY)
    if not isinstance(sp, dict):
        sp = {}
    sp = dict(sp)
    if color:
        sp["color"] = color
    if font_size:
        sp["fontSize"] = font_size
    if font_id:
        sp["font"] = studio_font_stack_from_id(font_id)
    sp["resume"] = resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
    sp.setdefault("template", sp.get("template") or "classic-sidebar")
    sp.setdefault("color", sp.get("color") or "teal")
    sp.setdefault("font", sp.get("font") or DEFAULT_STUDIO_EMBED_FONT)
    sp.setdefault("textAlign", sp.get("textAlign") or "start")
    sp.setdefault("fontSize", sp.get("fontSize") or "standard")
    wiz[STUDIO_PROTO_V1_KEY] = sp
    resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])
    return True


def studio_ui_state(user, resume, request=None, sections_list=None) -> dict:
    """Section metrics + tips for client-side refresh after saves."""
    analysis = ResumeProfileAnalyzer.analyze(user, resume)
    if sections_list is None:
        sections_list = studio_sections_for_user(user, resume)
    metrics = ResumeV2Metrics.section_completion(resume, sections_list)
    strength = ResumeV2Metrics.resume_strength(resume, request)
    return {
        "section_metrics": metrics["sections"],
        "overall_completion": metrics["overall"],
        "suggestions": ResumeSuggestionService.suggestions(user, resume, sections_list),
        "payload": resume_editor_payload(resume),
        "missing_keywords": filter_missing_keywords(strength, resume),
        "resume_photo_url": resume_photo_url(request, resume, user),
        "strength": {
            "score": strength["score"],
            "completion": strength["completion"],
            "level": strength["level"],
            "ats_completeness": strength["ats"]["completeness"],
        },
    }



def resume_goal_label(goal_id: str) -> str:
    gid = (goal_id or "").strip()
    for row in RESUME_GOALS:
        if row["id"] == gid:
            return row["label"]
    return gid.replace("_", " ").title() if gid else "General"


def build_resume_sections_snapshot(resume, user, client_sections: dict | None = None) -> dict:
    """Merge saved resume rows with optional unsaved studio form snapshot from the client."""
    from .resume_payload import _is_resume_meta_activity_title

    personal = studio_personal_context(user, resume)
    payload = resume_editor_payload(resume)
    meta = get_v2_meta(resume)

    projects: list[dict] = []
    achievements: list[dict] = []
    for activity in payload.get("activities") or []:
        title = (activity.get("title") or "").strip()
        desc = (activity.get("description") or "").strip()
        if not title:
            continue
        if desc.startswith("Technologies:"):
            from .resume_payload import _parse_project_activity_description

            tech, body = _parse_project_activity_description(desc)
            projects.append({"title": title, "technologies": tech, "description": body})
        else:
            achievements.append({"title": title, "description": desc})

    snapshot = {
        "personal": {
            "name": personal.get("name") or "",
            "headline": (meta.get("headline") or "").strip(),
            "phone": personal.get("phone") or "",
            "school": personal.get("school") or "",
            "email": personal.get("email") or "",
            "grade": personal.get("grade") or "",
        },
        "summary": (resume.about or "").strip(),
        "skills": [s.get("title") for s in (payload.get("skills") or []) if s.get("title")],
        "education": payload.get("education") or [],
        "projects": projects,
        "certificates": [
            {
                "title": c.get("title") or "",
                "issuer": c.get("description") or "",
                "issue_date": c.get("issue_date") or "",
            }
            for c in (payload.get("certificates") or [])
        ],
        "achievements": achievements,
        "experience": [
            {
                "role": e.get("role") or "",
                "provider": e.get("provider") or "",
                "description": e.get("description") or "",
                "start_date": e.get("start_date") or "",
                "end_date": e.get("end_date") or "",
            }
            for e in (payload.get("internships") or [])
        ],
        "languages": payload.get("languages") or [],
        "hobbies": payload.get("hobbies") or "",
    }

    if isinstance(client_sections, dict):
        for key, val in client_sections.items():
            if isinstance(val, dict) and isinstance(snapshot.get(key), dict):
                snapshot[key] = {**snapshot[key], **val}
            else:
                snapshot[key] = val
    return snapshot


def _parse_optional_date(val) -> object | None:
    from datetime import datetime

    s = (str(val) if val is not None else "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


AI_RESUME_PENDING_KEY = "ai_resume_pending"

AI_COMPARE_SECTIONS: list[tuple[str, str]] = [
    ("headline", "Personal / Headline"),
    ("summary", "Career Objective"),
    ("skills", "Skills"),
    ("education", "Education"),
    ("projects", "Projects"),
    ("certificates", "Certificates"),
    ("achievements", "Achievements"),
    ("experience", "Experience"),
    ("languages", "Languages"),
    ("hobbies", "Hobbies"),
]


def _empty_compare_label() -> str:
    return "(empty)"


def _headline_compare_text(snap: dict, *, generated_shape: bool = False) -> str:
    if generated_shape:
        text = (snap.get("headline") or "").strip()
    else:
        personal = snap.get("personal") if isinstance(snap.get("personal"), dict) else {}
        text = (personal.get("headline") or "").strip()
    return text or _empty_compare_label()


def _summary_compare_text(snap: dict) -> str:
    return (snap.get("summary") or "").strip() or _empty_compare_label()


def _skills_compare_text(snap: dict) -> str:
    raw = snap.get("skills") or []
    if not isinstance(raw, list):
        return _empty_compare_label()
    items = [str(s).strip() for s in raw if str(s).strip()]
    return ", ".join(items) if items else _empty_compare_label()


def _education_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for ed in snap.get("education") or []:
        if not isinstance(ed, dict):
            continue
        parts = [
            (ed.get("school") or "").strip(),
            (ed.get("grade") or "").strip(),
            (ed.get("dates") or "").strip(),
        ]
        head = " — ".join(p for p in parts if p)
        detail = (ed.get("detail") or "").strip()
        if head and detail:
            lines.append(f"{head}\n  {detail}")
        elif head:
            lines.append(head)
        elif detail:
            lines.append(detail)
    return "\n".join(lines) if lines else _empty_compare_label()


def _projects_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for proj in snap.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        title = (proj.get("title") or "").strip()
        if not title:
            continue
        tech = (proj.get("technologies") or "").strip()
        desc = (proj.get("description") or "").strip()
        block = title
        if tech:
            block += f" ({tech})"
        if desc:
            block += f"\n  {desc}"
        lines.append(block)
    return "\n\n".join(lines) if lines else _empty_compare_label()


def _certificates_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for cert in snap.get("certificates") or []:
        if not isinstance(cert, dict):
            continue
        title = (cert.get("title") or "").strip()
        if not title:
            continue
        issuer = (cert.get("issuer") or cert.get("description") or "").strip()
        date = (cert.get("issue_date") or "").strip()
        extra = " — ".join(x for x in [issuer, date] if x)
        lines.append(f"{title}" + (f" ({extra})" if extra else ""))
    return "\n".join(lines) if lines else _empty_compare_label()


def _achievements_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for ach in snap.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        title = (ach.get("title") or "").strip()
        if not title:
            continue
        desc = (ach.get("description") or "").strip()
        lines.append(f"{title}" + (f"\n  {desc}" if desc else ""))
    return "\n\n".join(lines) if lines else _empty_compare_label()


def _experience_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for exp in snap.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        role = (exp.get("role") or "").strip()
        provider = (exp.get("provider") or "").strip()
        if not role and not provider:
            continue
        head = " — ".join(x for x in [role, provider] if x)
        dates = " — ".join(
            x for x in [(exp.get("start_date") or "").strip(), (exp.get("end_date") or "").strip()] if x
        )
        if dates:
            head += f" ({dates})"
        desc = (exp.get("description") or "").strip()
        lines.append(head + (f"\n  {desc}" if desc else ""))
    return "\n\n".join(lines) if lines else _empty_compare_label()


def _languages_compare_text(snap: dict) -> str:
    lines: list[str] = []
    for lg in snap.get("languages") or []:
        if isinstance(lg, dict):
            name = (lg.get("name") or "").strip()
            level = (lg.get("level") or "").strip()
            if name:
                lines.append(f"{name}" + (f" ({level})" if level else ""))
        elif str(lg).strip():
            lines.append(str(lg).strip())
    return ", ".join(lines) if lines else _empty_compare_label()


def _hobbies_compare_text(snap: dict) -> str:
    return (snap.get("hobbies") or "").strip() or _empty_compare_label()


_COMPARE_FORMATTERS = {
    "headline": lambda snap, gen=False: _headline_compare_text(snap, generated_shape=gen),
    "summary": _summary_compare_text,
    "skills": _skills_compare_text,
    "education": _education_compare_text,
    "projects": _projects_compare_text,
    "certificates": _certificates_compare_text,
    "achievements": _achievements_compare_text,
    "experience": _experience_compare_text,
    "languages": _languages_compare_text,
    "hobbies": _hobbies_compare_text,
}


def build_ai_resume_comparison(original: dict, generated: dict) -> list[dict]:
    """Section-wise old vs new text for the AI review popup."""
    rows: list[dict] = []
    for key, label in AI_COMPARE_SECTIONS:
        fmt = _COMPARE_FORMATTERS[key]
        old_text = fmt(original, False) if key == "headline" else fmt(original)
        new_text = fmt(generated, True) if key == "headline" else fmt(generated)
        rows.append(
            {
                "id": key,
                "label": label,
                "old": old_text,
                "new": new_text,
                "changed": old_text != new_text,
            }
        )
    return rows


def save_ai_resume_pending(resume, original: dict, generated: dict, *, career_goal: str = "") -> None:
    from django.utils import timezone

    save_v2_meta(
        resume,
        {
            AI_RESUME_PENDING_KEY: {
                "original": original,
                "generated": generated,
                "created_at": timezone.now().isoformat(),
                "goal": (career_goal or "").strip(),
            }
        },
    )


def get_ai_resume_pending(resume) -> dict | None:
    pending = get_v2_meta(resume).get(AI_RESUME_PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    original = pending.get("original")
    generated = pending.get("generated")
    if not isinstance(original, dict) or not isinstance(generated, dict):
        return None
    return pending


def clear_ai_resume_pending(resume) -> None:
    meta = get_v2_meta(resume)
    if AI_RESUME_PENDING_KEY not in meta:
        return
    meta = dict(meta)
    meta.pop(AI_RESUME_PENDING_KEY, None)
    wiz = _wizard_v2_dict(resume)
    wiz[STUDIO_PROTO_V2_KEY] = meta
    resume.wizard_draft_json = json.dumps(wiz, ensure_ascii=False, default=str)
    resume.save(update_fields=["wizard_draft_json", "modified"])


def _activity_is_project(activity) -> bool:
    return (activity.description or "").strip().startswith("Technologies:")


def _delete_resume_project_activities(resume) -> None:
    from .resume_payload import _is_resume_meta_activity_title

    for activity in UserResumeActivity.objects.filter(resume=resume):
        title = (activity.title or "").strip()
        if _is_resume_meta_activity_title(title):
            continue
        if _activity_is_project(activity):
            activity.delete(hard_delete=True)


def _delete_resume_achievement_activities(resume) -> None:
    from .resume_payload import _is_resume_meta_activity_title

    for activity in UserResumeActivity.objects.filter(resume=resume):
        title = (activity.title or "").strip()
        if _is_resume_meta_activity_title(title):
            continue
        if not _activity_is_project(activity):
            activity.delete(hard_delete=True)


def apply_ai_generated_resume(
    resume, user, data: dict, sections: list[str] | None = None
) -> dict:
    """Persist AI-generated resume JSON to DB and v2 meta. Returns fields applied for the UI."""
    from .resume_payload import _is_resume_meta_activity_title

    apply_all = sections is None
    chosen = {s.strip() for s in (sections or []) if s and str(s).strip()}

    def want(key: str) -> bool:
        return apply_all or key in chosen

    applied: dict = {}

    if want("headline"):
        headline = (data.get("headline") or "").strip()[:200]
        if headline:
            save_v2_meta(resume, {"headline": headline})
            applied["headline"] = headline

    if want("summary"):
        summary = (data.get("summary") or "").strip()[:5000]
        if summary:
            resume.about = summary
            resume.save(update_fields=["about", "modified"])
            applied["summary"] = summary

    if want("skills"):
        skills = data.get("skills") or []
        if isinstance(skills, list):
            UserResumeSkill.objects.filter(resume=resume).delete()
            for raw in skills[:30]:
                title = (str(raw) if raw is not None else "").strip()[:250]
                if title:
                    UserResumeSkill.objects.create(resume=resume, title=title, profficiency=3)

    if want("education"):
        education = data.get("education") or []
        if isinstance(education, list):
            import uuid

            entries = []
            for ed in education[:20]:
                if not isinstance(ed, dict):
                    continue
                school = (ed.get("school") or "").strip()[:250]
                grade = (ed.get("grade") or "").strip()[:100]
                if not school and not grade:
                    continue
                entries.append(
                    {
                        "id": f"edu-{uuid.uuid4().hex[:8]}",
                        "school": school,
                        "grade": grade,
                        "dates": (ed.get("dates") or "").strip()[:100],
                        "detail": (ed.get("detail") or "").strip()[:500],
                    }
                )
            save_v2_meta(resume, {"education_entries": entries})

    if want("certificates"):
        UserResumeCertificate.objects.filter(resume=resume).delete()
        for cert in (data.get("certificates") or [])[:20]:
            if not isinstance(cert, dict):
                continue
            title = (cert.get("title") or "").strip()[:250]
            issuer = (cert.get("issuer") or cert.get("description") or "").strip()[:2000]
            if not title:
                continue
            UserResumeCertificate.objects.create(
                resume=resume,
                title=title,
                description=issuer or "—",
                issue_date=_parse_optional_date(cert.get("issue_date")),
            )

    if want("projects") or want("achievements"):
        if want("projects") and want("achievements"):
            for activity in UserResumeActivity.objects.filter(resume=resume):
                title = (activity.title or "").strip()
                if _is_resume_meta_activity_title(title):
                    continue
                activity.delete(hard_delete=True)
        elif want("projects"):
            _delete_resume_project_activities(resume)
        else:
            _delete_resume_achievement_activities(resume)

    if want("projects"):
        for proj in (data.get("projects") or [])[:20]:
            if not isinstance(proj, dict):
                continue
            title = (proj.get("title") or "").strip()[:250]
            desc = (proj.get("description") or "").strip()[:2000]
            tech = (proj.get("technologies") or "").strip()[:500]
            if not title or not desc:
                continue
            full_desc = f"Technologies: {tech}\n{desc}"[:2000]
            UserResumeActivity.objects.create(resume=resume, title=title, description=full_desc)

    if want("achievements"):
        for ach in (data.get("achievements") or [])[:20]:
            if not isinstance(ach, dict):
                continue
            title = (ach.get("title") or "").strip()[:250]
            desc = (ach.get("description") or "").strip()[:2000]
            if not title:
                continue
            UserResumeActivity.objects.create(resume=resume, title=title, description=desc)

    if want("experience"):
        UserResumeInternship.objects.filter(resume=resume).delete()
        for exp in (data.get("experience") or [])[:20]:
            if not isinstance(exp, dict):
                continue
            role = (exp.get("role") or "").strip()[:250]
            provider = (exp.get("provider") or "").strip()[:250]
            description = (exp.get("description") or "").strip()[:2000]
            if not role and not provider:
                continue
            UserResumeInternship.objects.create(
                resume=resume,
                role=role or "Role",
                provider=provider or "Employer",
                description=description,
                start_date=_parse_optional_date(exp.get("start_date")),
                end_date=_parse_optional_date(exp.get("end_date")),
            )

    if want("languages"):
        languages = data.get("languages") or []
        if isinstance(languages, list):
            save_resume_languages(resume, languages)

    if want("hobbies"):
        hobbies = data.get("hobbies")
        if hobbies is not None:
            applied["hobbies"] = save_resume_hobbies(resume, str(hobbies))

    return applied


class ResumeFullGenerator:
    @staticmethod
    def generate(
        user, resume, sections_snapshot: dict, *, career_goal: str = "", apply: bool = False
    ) -> tuple[dict, dict | None, list[dict], bool, str | None]:
        """
        Return (applied_fields, generated_json, comparison_rows, used_ai, error).
        When apply=False (default), stores pending JSON for review instead of writing to DB.
        """
        from .resume_v2_ai import ai_generate_full_resume

        goal_id = (career_goal or get_v2_meta(resume).get("goal") or "").strip()
        parsed, used_ai, err = ai_generate_full_resume(
            user,
            resume,
            sections_snapshot,
            career_goal=goal_id,
            goal_label=resume_goal_label(goal_id),
        )
        if not parsed:
            return {}, None, [], False, err
        comparison = build_ai_resume_comparison(sections_snapshot, parsed)
        if apply:
            applied = apply_ai_generated_resume(resume, user, parsed)
            clear_ai_resume_pending(resume)
            return applied, parsed, comparison, used_ai, None
        save_ai_resume_pending(resume, sections_snapshot, parsed, career_goal=goal_id)
        return {}, parsed, comparison, used_ai, None
