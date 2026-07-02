"""Parent pay-on-behalf helpers for courses and assessments."""
from __future__ import annotations

from typing import Optional, Tuple

from core import choices


SESSION_CHECKOUT_STUDENT_KEY = "parent_checkout_student_id"


def set_parent_checkout_student(request, student_id: int) -> None:
    request.session[SESSION_CHECKOUT_STUDENT_KEY] = int(student_id)


def clear_parent_checkout_student(request) -> None:
    request.session.pop(SESSION_CHECKOUT_STUDENT_KEY, None)


def get_parent_checkout_student(request, *, student_id: Optional[int] = None):
    """Return a linked student when parent is checking out on their behalf."""
    from users.models import ParentStudentLink

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "user_type", None) != choices.UserType.PARENT:
        return None

    sid = student_id
    if sid is None:
        sid = request.session.get(SESSION_CHECKOUT_STUDENT_KEY)
    try:
        sid = int(sid)
    except (TypeError, ValueError):
        return None
    if not sid:
        return None

    link = (
        ParentStudentLink.objects.filter(parent=user, student_id=sid)
        .select_related("student")
        .first()
    )
    return link.student if link and link.student else None


def resolve_payment_users(request, *, student_id: Optional[int] = None) -> Tuple:
    """
    Return (payer, beneficiary).
    - Student self-checkout: payer == beneficiary == student
    - Parent checkout: payer == parent, beneficiary == linked student
    """
    user = request.user
    if getattr(user, "user_type", None) == choices.UserType.PARENT:
        student = get_parent_checkout_student(request, student_id=student_id)
        if student:
            return user, student
    return user, user
