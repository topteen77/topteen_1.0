"""HTTP APIs for student/parent AI feature quotas."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

from core.ai_feature_quota import (
    ALL_FEATURES,
    AIFeatureQuotaExceeded,
    consume_feature,
    feature_quota_error_response,
    status_for_user,
)


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class AIFeatureQuotaStatusAPI(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse(status_for_user(request.user, request=request))


@method_decorator(login_required(login_url="/user/login/"), name="dispatch")
class AIFeatureQuotaConsumeAPI(View):
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
