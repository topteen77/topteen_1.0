"""
Build context dict for the AI Counselling Engine from Django request.user.
Maps UserProfile (grade, schoolname, etc.) to engine context: grade (int 9-12),
board, ses_score, student_name, optional aptitude_score.
"""
import re
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model

User = get_user_model()


def get_counselling_context(user) -> Dict[str, Any]:
    """
    Build context for POST /counsel from the given user (request.user).
    Returns dict with: grade (int 9-12), board (str), ses_score (float 0-1),
    student_name (str), optionally aptitude_score (float 0-1).
    """
    context = {
        "grade": 9,
        "board": "CBSE",
        "ses_score": 0.5,
        "student_name": _get_display_name(user),
        "aptitude_score": 0.7,
    }
    if not user or not user.is_authenticated:
        return context
    try:
        profile = getattr(user, "user_profile", None)
        if profile:
            grade_int = _parse_grade(profile.grade)
            if grade_int is not None:
                context["grade"] = grade_int
            if hasattr(profile, "board") and profile.board:
                context["board"] = str(profile.board).strip() or context["board"]
            if getattr(profile, "socio_economic_score", None) is not None:
                try:
                    ses = float(profile.socio_economic_score)
                    context["ses_score"] = max(0.0, min(1.0, ses))
                except (TypeError, ValueError):
                    pass
        name = _get_display_name(user)
        if name:
            context["student_name"] = name
    except Exception:
        pass
    return context


def _parse_grade(grade_value) -> Optional[int]:
    """Parse UserProfile.grade (CharField) to int 9-12."""
    if grade_value is None:
        return None
    s = str(grade_value).strip()
    if not s:
        return None
    # Try integer first
    try:
        n = int(s)
        if 9 <= n <= 12:
            return n
    except ValueError:
        pass
    # Try "Class 10", "10", "Grade 11", etc.
    match = re.search(r"(?:class|grade)?\s*(\d{1,2})", s, re.IGNORECASE)
    if match:
        try:
            n = int(match.group(1))
            if 9 <= n <= 12:
                return n
        except ValueError:
            pass
    return None


def _get_display_name(user) -> str:
    if not user:
        return ""
    if getattr(user, "get_full_name", None) and user.get_full_name():
        return user.get_full_name().strip()
    if getattr(user, "name", None) and user.name:
        return str(user.name).strip()
    if getattr(user, "email", None) and user.email:
        return str(user.email).strip()
    return ""
