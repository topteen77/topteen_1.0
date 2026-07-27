"""HTTP APIs for student/parent AI feature quotas."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views import View

from core.ajax_auth import ajax_session_expired_response
from core.ai_feature_quota import (
    ALL_FEATURES,
    AIFeatureQuotaExceeded,
    consume_feature,
    feature_quota_error_response,
    status_for_user,
)


class _AIFeatureQuotaAPIMixin:
    """JSON APIs must not use @login_required redirects (would set ?next= to this URL)."""

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, "is_authenticated", False):
            return ajax_session_expired_response(request)
        return super().dispatch(request, *args, **kwargs)


class AIFeatureQuotaStatusAPI(_AIFeatureQuotaAPIMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse(status_for_user(request.user, request=request))


class AIFeatureQuotaConsumeAPI(_AIFeatureQuotaAPIMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}
        feature = (body.get("feature") or request.POST.get("feature") or "").strip()
        if feature not in ALL_FEATURES:
            return JsonResponse(
                {"error": "Invalid feature", "features": list(ALL_FEATURES)},
                status=400,
            )
        try:
            amount = int(body.get("amount") or 1)
        except (TypeError, ValueError):
            amount = 1
        try:
            status = consume_feature(
                request.user,
                feature,
                amount=amount,
                request=request,
            )
        except AIFeatureQuotaExceeded as exc:
            return feature_quota_error_response(exc)
        return JsonResponse({"success": True, **status})
