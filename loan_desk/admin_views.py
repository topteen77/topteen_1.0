"""Admin Loan Team CRUD — one list + AJAX add/edit for Manager & Executive."""
from __future__ import annotations

import json
import secrets

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core import choices


def _role_label(user_type: int) -> str:
    if user_type == choices.UserType.LOAN_MANAGER:
        return "Loan Manager"
    if user_type == choices.UserType.LOAN_EXECUTIVE:
        return "Loan Executive"
    return "—"


def _serialize_member(user) -> dict:
    enabled = True
    try:
        enabled = bool(user.get_user_status())
    except Exception:
        enabled = getattr(user, "user_status", None) == choices.UserStatus.UNBLOCK
    return {
        "id": user.id,
        "name": user.name or "",
        "email": user.email or "",
        "mobile": user.mobile or "",
        "user_type": int(user.user_type),
        "role": _role_label(int(user.user_type)),
        "enabled": enabled,
        "role_badge": "manager"
        if int(user.user_type) == choices.UserType.LOAN_MANAGER
        else "executive",
    }


def _loan_team_qs():
    from users.models import User

    return User.objects.filter(
        user_type__in=choices.UserType.LOAN_DESK_TYPES
    ).order_by("user_type", "name", "email")


def _parse_json(request: HttpRequest) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    data = {}
    data.update(request.POST.dict())
    return data


@staff_member_required
def loan_team_list_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        return HttpResponseForbidden()

    members = [_serialize_member(u) for u in _loan_team_qs()]
    context = {
        **admin.site.each_context(request),
        "title": "Loan team",
        "members": members,
        "members_json": json.dumps(members),
        "hub_zone": "education_loan",
        "loan_manager_type": choices.UserType.LOAN_MANAGER,
        "loan_executive_type": choices.UserType.LOAN_EXECUTIVE,
        "has_permission": True,
    }
    return render(request, "admin/hub/loan_team_list.html", context)


@staff_member_required
@require_http_methods(["GET"])
def loan_team_get_api(request: HttpRequest, user_id: int) -> JsonResponse:
    if not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Not allowed"}, status=403)
    from users.models import User

    user = User.objects.filter(
        id=user_id, user_type__in=choices.UserType.LOAN_DESK_TYPES
    ).first()
    if not user:
        return JsonResponse({"success": False, "message": "Team member not found."}, status=404)
    return JsonResponse({"success": True, "member": _serialize_member(user)})


@staff_member_required
@require_http_methods(["POST"])
def loan_team_save_api(request: HttpRequest) -> JsonResponse:
    """Create or update a loan team member (AJAX)."""
    if not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Not allowed"}, status=403)

    from users.models import User

    data = _parse_json(request)
    try:
        user_id = int(data.get("id") or 0)
    except (TypeError, ValueError):
        user_id = 0

    try:
        user_type = int(data.get("user_type") or 0)
    except (TypeError, ValueError):
        user_type = 0

    if user_type not in choices.UserType.LOAN_DESK_TYPES:
        return JsonResponse(
            {"success": False, "message": "Select Loan Manager or Loan Executive."},
            status=400,
        )

    name = (data.get("name") or "").strip() or "Loan Team"
    email = (data.get("email") or "").strip().lower()
    mobile = (data.get("mobile") or "").strip() or None
    password = (data.get("password") or "").strip()
    enabled_raw = data.get("enabled", True)
    if isinstance(enabled_raw, str):
        enabled = enabled_raw.lower() in ("1", "true", "yes", "on")
    else:
        enabled = bool(enabled_raw)

    if not email or "@" not in email:
        return JsonResponse(
            {"success": False, "message": "A valid login email is required."},
            status=400,
        )

    plain_password = None
    if user_id:
        user = User.objects.filter(
            id=user_id, user_type__in=choices.UserType.LOAN_DESK_TYPES
        ).first()
        if not user:
            return JsonResponse(
                {"success": False, "message": "Team member not found."}, status=404
            )
        conflict = (
            User.objects.filter(email__iexact=email).exclude(id=user.id).exists()
        )
        if conflict:
            return JsonResponse(
                {"success": False, "message": "Another user already has this email."},
                status=400,
            )
        user.name = name
        user.email = email
        user.mobile = mobile
        user.user_type = user_type
        user.user_status = (
            choices.UserStatus.UNBLOCK if enabled else choices.UserStatus.BLOCK
        )
        if password:
            user.set_password(password)
            plain_password = password
        user.save()
        msg = f"{_role_label(user_type)} “{user.name or user.email}” updated."
    else:
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse(
                {"success": False, "message": "A user with this email already exists."},
                status=400,
            )
        if not password:
            password = secrets.token_urlsafe(10)
            plain_password = password
        else:
            plain_password = password
        user = User.create_user(
            email=email,
            mobile=mobile,
            name=name,
            user_type=user_type,
        )
        user.set_password(password)
        user.user_type = user_type
        user.user_status = (
            choices.UserStatus.UNBLOCK if enabled else choices.UserStatus.BLOCK
        )
        user.is_active = True
        user.save()
        msg = f"{_role_label(user_type)} “{user.name or user.email}” added."
        if plain_password:
            msg += f" Temporary password: {plain_password}"

    return JsonResponse(
        {
            "success": True,
            "message": msg,
            "member": _serialize_member(user),
            "generated_password": plain_password if not user_id else None,
            "members": [_serialize_member(u) for u in _loan_team_qs()],
        }
    )


@staff_member_required
@require_http_methods(["POST"])
def loan_team_toggle_api(request: HttpRequest, user_id: int) -> JsonResponse:
    if not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Not allowed"}, status=403)
    from users.models import User

    user = User.objects.filter(
        id=user_id, user_type__in=choices.UserType.LOAN_DESK_TYPES
    ).first()
    if not user:
        return JsonResponse({"success": False, "message": "Team member not found."}, status=404)

    enabled_now = True
    try:
        enabled_now = bool(user.get_user_status())
    except Exception:
        enabled_now = user.user_status == choices.UserStatus.UNBLOCK

    user.user_status = (
        choices.UserStatus.BLOCK if enabled_now else choices.UserStatus.UNBLOCK
    )
    user.save(update_fields=["user_status"])
    state = "disabled" if enabled_now else "enabled"
    return JsonResponse(
        {
            "success": True,
            "message": f"{user.name or user.email} {state}.",
            "member": _serialize_member(user),
            "members": [_serialize_member(u) for u in _loan_team_qs()],
        }
    )
