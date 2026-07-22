"""OpenAI helpers for Resume Builder V2 studio (summary, project copy, full resume)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple

from .models import UserProfile, UserResume, UserResumeSkill, ResumeV2AISettings


def _resolve_openai_model() -> str:
    from django.conf import settings

    try:
        admin_model = (ResumeV2AISettings.load().openai_model or "").strip()
    except Exception:
        admin_model = ""
    if admin_model:
        return admin_model
    return (
        getattr(settings, "OPENAI_MODEL", None) or getattr(settings, "AI_MODEL", None) or "gpt-4o-mini"
    ).strip()


def _openai_chat(
    prompt: str,
    *,
    max_tokens: int = 600,
    temperature: float = 0.45,
    system: str = "",
    user=None,
    request=None,
) -> Tuple[Optional[str], Optional[str]]:
    from django.conf import settings

    api_key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if not api_key:
        return None, None

    try:
        from core.llm_quota import LLMQuotaExceeded, ensure_can_use_llm

        ensure_can_use_llm(user, feature="resume_v2", request=request)
    except LLMQuotaExceeded as exc:
        return None, f"QUOTA:{exc.payload.get('message') or 'AI token limit reached'}"

    model = _resolve_openai_model()
    messages: list[dict[str, str]] = []
    if (system or "").strip():
        messages.append({"role": "system", "content": system.strip()})
    messages.append({"role": "user", "content": prompt})
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            from core.llm_billing import log_openai_response
            log_openai_response(
                feature="resume_v2",
                response=response,
                model=model,
                call_type="chat",
                user=user,
                consume=True,
                request=request,
                metadata={"source": "users.resume_v2_ai"},
            )
        except Exception:
            pass
        text = (response.choices[0].message.content or "").strip()
        return text or None, None
    except Exception as exc:
        return None, str(exc)[:400]


def friendly_openai_error(err: str | None) -> str:
    """User-facing message for OpenAI/API failures."""
    if not err:
        return "AI request failed. Please try again."
    if err.startswith("QUOTA:"):
        return err[6:].strip() or "You've used your free AI tokens. Recharge to continue."
    low = err.lower()
    if "insufficient_quota" in low or "exceeded your current quota" in low:
        return (
            "OpenAI quota exceeded. Check billing on your OpenAI account, "
            "or ask an admin to update the API key."
        )
    if "invalid_api_key" in low or "incorrect api key" in low:
        return "OpenAI API key is invalid. Ask an admin to check OPENAI_API_KEY in settings."
    if "rate_limit" in low or "429" in err:
        return "AI rate limit reached. Please wait a moment and try again."
    return err[:300]


def _student_context(user, resume: UserResume) -> dict:
    profile = UserProfile.objects.filter(user=user).first()
    skills = [s.title for s in UserResumeSkill.objects.filter(resume=resume)[:8] if s.title]
    return {
        "name": (getattr(user, "name", None) or "Student").strip(),
        "grade": (getattr(profile, "grade", None) or "student").strip(),
        "school": (getattr(profile, "schoolname", None) or "").strip(),
        "skills": skills,
    }


def _template_summary(user, resume: UserResume, career_goal: str = "") -> str:
    ctx = _student_context(user, resume)
    skill_text = ", ".join(ctx["skills"][:3]) if ctx["skills"] else "technology and problem solving"
    goal = (career_goal or "future career opportunities").replace("_", " ")
    parts = [f"Motivated {ctx['grade']} student"]
    if ctx["school"]:
        parts[0] += f" at {ctx['school']}"
    parts.append(f"with strong interests in {skill_text}")
    parts.append(f"Seeking {goal}.")
    return (
        " ".join(parts)
        + f" {ctx['name']} is eager to apply analytical skills and a growth mindset to meaningful projects."
    )


def _template_improve(text: str, mode: str = "professional") -> str:
    t = (text or "").strip()
    if not t:
        return t
    if mode == "ats":
        return t + " Demonstrated leadership, teamwork, and results-driven problem solving."
    if mode == "shorten":
        sentences = re.split(r"(?<=[.!?])\s+", t)
        return " ".join(sentences[:2]).strip()
    if mode == "expand":
        return (
            t
            + " Committed to continuous learning and delivering measurable impact in collaborative environments."
        )
    return t[0].upper() + t[1:] if t else t


def _template_project_bullets(title: str, technologies: str = "") -> list[str]:
    title = (title or "Project").strip()
    tech = (technologies or "relevant tools").strip()
    return [
        f"Designed and implemented {title} using {tech} to solve a real-world problem.",
        f"Collaborated with peers to plan, build, and iterate on {title} within project deadlines.",
        f"Applied problem-solving and analytical skills to optimize outcomes in {title}.",
        f"Documented process and results, demonstrating clear communication and technical proficiency.",
    ]


def _parse_bullet_list(raw: str) -> list[str]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()
    try:
        bullets = json.loads(cleaned)
        if isinstance(bullets, list):
            return [str(b).strip() for b in bullets if str(b).strip()]
    except json.JSONDecodeError:
        pass
    lines = [ln.strip().lstrip("-•* ") for ln in cleaned.splitlines() if ln.strip()]
    return [ln for ln in lines if len(ln) > 10]


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                pass
    return None


def ai_generate_full_resume(
    user,
    resume: UserResume,
    sections_snapshot: dict,
    *,
    career_goal: str = "",
    goal_label: str = "",
) -> Tuple[dict[str, Any] | None, bool, str | None]:
    """Return (parsed resume JSON, used_ai, error_message)."""
    goal_id = (career_goal or "").strip() or "general"
    goal_display = (goal_label or goal_id).replace("_", " ").strip()
    settings_row = ResumeV2AISettings.load()
    template = (settings_row.generate_resume_prompt or "").strip()
    if not template:
        from .models import DEFAULT_RESUME_V2_AI_PROMPT

        template = DEFAULT_RESUME_V2_AI_PROMPT
    sections_json = json.dumps(sections_snapshot, ensure_ascii=False, indent=2, default=str)
    try:
        prompt = template.format(
            goal_label=goal_display,
            goal_id=goal_id,
            sections_json=sections_json,
        )
    except (KeyError, ValueError):
        prompt = (
            f"Goal: {goal_display} ({goal_id})\n\nResume JSON:\n{sections_json}\n\n"
            "Return improved resume as JSON with keys: headline, summary, skills, education, "
            "projects, certificates, achievements, experience, languages, hobbies."
        )
    raw, err = _openai_chat(prompt, max_tokens=2500, temperature=0.5, user=user)
    if err and str(err).startswith("QUOTA:"):
        from core.llm_quota import LLMQuotaExceeded, build_paywall, get_balance, resolve_role_key

        role_key = resolve_role_key(user)
        raise LLMQuotaExceeded(
            build_paywall(
                role_key=role_key,
                balance=get_balance(user),
                estimated_cost=4000,
                feature="resume_v2",
            )
        )
    if not raw:
        return None, False, friendly_openai_error(err) if err else "AI is not configured (missing OPENAI_API_KEY)."
    parsed = _parse_json_object(raw)
    if not parsed:
        return None, False, "AI returned an invalid response. Try again."
    return parsed, True, None


def _raise_if_quota(err, user, feature="resume_v2"):
    if err and str(err).startswith("QUOTA:"):
        from core.llm_quota import LLMQuotaExceeded, build_paywall, get_balance, resolve_role_key

        role_key = resolve_role_key(user)
        raise LLMQuotaExceeded(
            build_paywall(
                role_key=role_key,
                balance=get_balance(user),
                estimated_cost=2500,
                feature=feature,
            )
        )


def ai_generate_summary(user, resume: UserResume, career_goal: str = "") -> Tuple[str, bool]:
    """Return (summary text, used_ai)."""
    ctx = _student_context(user, resume)
    goal = (career_goal or "future opportunities").replace("_", " ")
    prompt = (
        "Write a concise professional resume summary (2-3 sentences, max 80 words) for a student.\n"
        f"Name: {ctx['name']}\nGrade/level: {ctx['grade']}\nSchool: {ctx['school'] or 'N/A'}\n"
        f"Skills: {', '.join(ctx['skills'][:5]) or 'general academic skills'}\n"
        f"Career goal: {goal}\n"
        "Use third person. Be specific, positive, and ATS-friendly. "
        "Return ONLY the summary text, no headings or quotes."
    )
    text, err = _openai_chat(prompt, max_tokens=200, user=user)
    _raise_if_quota(err, user)
    if text:
        return text.strip()[:2000], True
    return _template_summary(user, resume, career_goal), False


def ai_improve_summary(
    user, resume: UserResume, text: str, mode: str = "professional"
) -> Tuple[str, bool]:
    t = (text or "").strip()
    if not t:
        return ai_generate_summary(user, resume)
    mode_instr = {
        "professional": "Make it more polished and professional while keeping the same meaning.",
        "ats": "Optimize for ATS with strong action words; keep concise.",
        "shorten": "Shorten to 2 sentences max while keeping key points.",
        "expand": "Expand slightly with one specific skill or strength (max 100 words).",
    }.get(mode, "Improve clarity and impact.")
    prompt = (
        f"Improve this student resume summary. {mode_instr}\n\n"
        f"Original:\n{t}\n\nReturn ONLY the improved summary, no headings."
    )
    improved, err = _openai_chat(prompt, max_tokens=250, user=user)
    _raise_if_quota(err, user)
    if improved:
        return improved.strip()[:2000], True
    return _template_improve(t, mode=mode), False


def ai_generate_achievement_description(
    user, resume: UserResume, title: str
) -> Tuple[str, bool]:
    ctx = _student_context(user, resume)
    title = (title or "Achievement").strip()
    prompt = (
        "Write a short resume achievement description (2-4 sentences) for a student.\n"
        f"Achievement: {title}\n"
        f"Student: {ctx['name']}, {ctx['grade']} at {ctx['school'] or 'school'}\n"
        "Highlight impact, role, and skills shown. Return ONLY the description text."
    )
    text, err = _openai_chat(prompt, max_tokens=300, user=user)
    _raise_if_quota(err, user)
    if text:
        return text.strip()[:2000], True
    return (
        f"Recognized for {title.lower()} with a strong commitment to excellence and teamwork.",
        False,
    )


def ai_improve_achievement_description(
    user, resume: UserResume, title: str, text: str, mode: str = "professional"
) -> Tuple[str, bool]:
    t = (text or "").strip()
    if not t:
        return "", False
    ctx = _student_context(user, resume)
    title = (title or "Achievement").strip()
    mode_instr = (
        "Make it concise, ATS-friendly, and achievement-focused with strong verbs."
        if mode == "ats"
        else "Make it clearer and more professional while keeping the student's voice."
    )
    prompt = (
        f"Improve this student resume achievement description. {mode_instr}\n"
        f"Achievement title: {title}\n"
        f"Student: {ctx['name']}, {ctx['grade']} at {ctx['school'] or 'school'}\n\n"
        f"Original:\n{t}\n\nReturn ONLY the improved description, no headings."
    )
    improved, err = _openai_chat(prompt, max_tokens=300, user=user)
    _raise_if_quota(err, user)
    if improved:
        return improved.strip()[:2000], True
    return _template_improve(t, mode=mode), False


def ai_generate_project_bullets(
    user, resume: UserResume, title: str, technologies: str = ""
) -> Tuple[list[str], bool]:
    ctx = _student_context(user, resume)
    title = (title or "Project").strip()
    tech = (technologies or "").strip()
    prompt = (
        "Write 4 ATS-friendly resume bullet points for a student project.\n"
        f"Project: {title}\nTools/technologies: {tech or 'not specified'}\n"
        f"Student: {ctx['name']}, {ctx['grade']} at {ctx['school'] or 'school'}\n"
        "Each bullet should start with a strong verb and show skills learned. "
        "Return ONLY a JSON array of 4 strings, no markdown."
    )
    raw, err = _openai_chat(prompt, max_tokens=400, user=user)
    _raise_if_quota(err, user)
    if raw:
        bullets = _parse_bullet_list(raw)[:6]
        if bullets:
            return bullets, True
    return _template_project_bullets(title, tech), False
