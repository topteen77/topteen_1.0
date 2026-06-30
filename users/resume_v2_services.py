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
    "personal": "Personal Info",
    "education": "Education",
    "skills": "Skills",
    "projects": "Projects",
    "certificates": "Certificates",
    "languages": "Languages",
    "hobbies": "Hobbies",
    "achievements": "Achievements",
    "summary": "Summary",
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
    for a in UserResumeActivity.objects.filter(resume=resume).order_by("id"):
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
            missing.append("Summary")

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
                "text": "Improve Summary for student profile",
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
        """Counts from DB — source of truth for V2 studio (not stale wizard JSON)."""
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
            "skills": UserResumeSkill.objects.filter(resume=resume).count(),
            "projects": projects,
            "certificates": UserResumeCertificate.objects.filter(resume=resume).count(),
            "activities": projects + achievements,
            "achievements": achievements,
            "internships": UserResumeInternship.objects.filter(resume=resume).count(),
        }

    @staticmethod
    def section_completion(resume, sections: list | None = None) -> dict:
        sections = sections or STUDENT_SECTIONS
        if not resume:
            result = {
                sec: {"percent": 0, "status": "missing", "label": SECTION_LABELS.get(sec, sec.title())}
                for sec in sections
            }
            return {"sections": result, "overall": 0}
        payload = resume_studio_prototype_payload(resume)
        result = {}

        for sec in sections:
            pct, status = ResumeV2Metrics._section_status(sec, resume, payload)
            result[sec] = {"percent": pct, "status": status, "label": SECTION_LABELS.get(sec, sec.title())}

        values = [v["percent"] for v in result.values()]
        overall = round(sum(values) / len(values)) if values else 0
        return {"sections": result, "overall": overall}

    @staticmethod
    def _section_status(section: str, resume, payload: dict) -> tuple:
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
            if n >= 2:
                return (100, "complete")
            if n >= 1:
                return (70, "partial")
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
        sections = ResumeV2Metrics.section_completion(resume)
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
    """Generate or improve summary text (prototype: template-based; real AI via resume_guided_ai)."""

    @staticmethod
    def generate(user, resume, career_goal: str = "") -> str:
        profile = UserProfile.objects.filter(user=user).first()
        name = (user.name or "Student").strip()
        grade = (getattr(profile, "grade", None) or "student").strip()
        school = (getattr(profile, "schoolname", None) or "").strip()
        skills = [s.title for s in UserResumeSkill.objects.filter(resume=resume)[:5] if s.title]
        skill_text = ", ".join(skills[:3]) if skills else "technology and problem solving"

        goal = career_goal or "future career opportunities"
        parts = [
            f"Motivated {grade} student",
        ]
        if school:
            parts[0] += f" at {school}"
        parts.append(f"with strong interests in {skill_text}")
        parts.append(f"Seeking {goal.replace('_', ' ')}.")
        return " ".join(parts) + f" {name} is eager to apply analytical skills and a growth mindset to meaningful projects."

    @staticmethod
    def improve(text: str, mode: str = "professional") -> str:
        t = (text or "").strip()
        if not t:
            return t
        if mode == "ats":
            return t + " Demonstrated leadership, teamwork, and results-driven problem solving."
        if mode == "shorten":
            sentences = re.split(r"(?<=[.!?])\s+", t)
            return " ".join(sentences[:2]).strip()
        if mode == "expand":
            return t + " Committed to continuous learning and delivering measurable impact in collaborative environments."
        return t[0].upper() + t[1:] if t else t


class ProjectDescriptionGenerator:
    """Generate ATS-friendly bullet points for a project."""

    @staticmethod
    def generate(title: str, technologies: str = "") -> list:
        title = (title or "Project").strip()
        tech = (technologies or "relevant tools").strip()
        return [
            f"Designed and implemented {title} using {tech} to solve a real-world problem.",
            f"Collaborated with peers to plan, build, and iterate on {title} within project deadlines.",
            f"Applied problem-solving and analytical skills to optimize outcomes in {title}.",
            f"Documented process and results, demonstrating clear communication and technical proficiency.",
        ]


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


def v2_templates_catalog() -> list[dict]:
    """All studio HTML templates (DB catalog or static fallback) for V2 picker."""
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
        level = (lg.get("level") or "").strip()[:200]
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


# Curated skill/keyword bank for autocomplete (Google-suggest style UX)
STUDENT_KEYWORDS = [
    "Teamwork", "Leadership", "Communication", "Problem Solving", "Public Speaking",
    "Time Management", "Creativity", "Research", "Writing", "Presentation",
    "Mathematics", "Science", "English", "Hindi", "Computer Science",
    "Python", "JavaScript", "HTML", "CSS", "Microsoft Office", "Excel",
    "Volunteering", "Community Service", "Debate", "Sports", "Music", "Art",
    "Robotics", "Science Fair", "Coding", "Web Design", "Canva",
    "Critical Thinking", "Adaptability", "Organization", "Collaboration",
]

# Merge with technical keywords for suggestions
COMMON_KEYWORDS = STUDENT_KEYWORDS + [
    "Python", "JavaScript", "Java", "C++", "C#", "SQL", "HTML", "CSS", "React", "Node.js",
    "Django", "Flask", "Git", "GitHub", "Linux", "AWS", "Azure", "Docker", "Kubernetes",
    "Machine Learning", "Data Analysis", "Excel", "PowerPoint", "Public Speaking",
    "Leadership", "Teamwork", "Communication", "Problem Solving", "Critical Thinking",
    "Time Management", "Project Management", "Research", "Writing", "Presentation",
    "Mathematics", "Physics", "Chemistry", "Biology", "Economics", "Statistics",
    "Digital Marketing", "Graphic Design", "UI/UX Design", "Figma", "Photoshop",
    "Volunteering", "Community Service", "Debate", "Model UN", "Robotics",
    "Hackathon", "Olympiad", "Science Fair", "Coding", "Web Development",
    "Mobile Development", "Android", "iOS", "Swift", "Kotlin", "TypeScript",
    "MongoDB", "PostgreSQL", "MySQL", "Redis", "REST API", "Agile", "Scrum",
    "Customer Service", "Sales", "Marketing", "Finance", "Accounting",
    "Creative Thinking", "Adaptability", "Collaboration", "Analytical Skills",
    "Attention to Detail", "Organizational Skills", "Interpersonal Skills",
    "Conflict Resolution", "Decision Making", "Strategic Planning",
    "TensorFlow", "PyTorch", "Pandas", "NumPy", "Tableau", "Power BI",
    "Canva", "Microsoft Office", "Google Workspace", "Scratch", "Arduino",
]


class KeywordSuggestionService:
    """Filter keyword suggestions as the user types (Google-suggest style)."""

    @staticmethod
    def _profile_keywords(user) -> list[str]:
        out = []
        profile = UserProfile.objects.filter(user=user).first()
        if not profile:
            return out
        for subj in profile.subject.all()[:20]:
            name = getattr(subj, "name", None) or str(subj)
            if name.strip():
                out.append(name.strip())
        for hobby in profile.hobbies.all()[:20]:
            name = getattr(hobby, "name", None) or str(hobby)
            if name.strip():
                out.append(name.strip())
        return out

    @classmethod
    def _existing_skill_keys(cls, resume) -> set:
        if not resume:
            return set()
        return {
            (s.title or "").strip().lower()
            for s in UserResumeSkill.objects.filter(resume=resume)
        }

    @classmethod
    def _keyword_pool(cls, user, resume) -> list[str]:
        pool = list(COMMON_KEYWORDS)
        pool.extend(cls._profile_keywords(user))
        if resume:
            payload = resume_studio_prototype_payload(resume)
            ats = ATSScoringService.score(payload)
            pool.extend(ats.get("missing_keywords") or [])
        return pool

    @classmethod
    def suggest(cls, user, resume, query: str, limit: int = 8) -> list[dict]:
        q = (query or "").strip().lower()
        existing = cls._existing_skill_keys(resume)
        pool = cls._keyword_pool(user, resume)

        seen = set()
        results = []
        for kw in pool:
            label = kw.strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            if q and q not in key:
                continue
            results.append({
                "label": label,
                "already_added": key in existing,
                "source": "suggest",
            })
            if len(results) >= limit:
                break

        if q:
            results.sort(
                key=lambda x: (0 if x["label"].lower().startswith(q) else 1, x["label"].lower())
            )
        return results[:limit]
