"""Push education loan enquiry leads to an external CRM API."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from django.utils import timezone

from core import choices
from users.models import EducationLoanApplication, EducationLoanCRMSettings

logger = logging.getLogger(__name__)


def build_crm_lead_payload(app: EducationLoanApplication) -> Dict[str, Any]:
    def _num(value):
        return float(value) if value is not None else None

    return {
        "lead_id": app.id,
        "source": "topteen_education_loan",
        "status": app.get_status_display(),
        "parent_id": app.parent_id,
        "student_id": app.student_id,
        "student_name": app.student_name or "",
        "parent_name": app.parent_name or "",
        "mobile": app.mobile or "",
        "email": app.email or "",
        "institute_name": app.institute_name or "",
        "course_name": app.course_name or "",
        "country_preference": app.country_preference or "",
        "loan_amount": _num(app.loan_amount),
        "interest_rate": _num(app.interest_rate),
        "tenure_years": _num(app.tenure_years),
        "moratorium_months": app.moratorium_months,
        "estimated_emi": _num(app.estimated_emi),
        "total_interest": _num(app.total_interest),
        "total_payable": _num(app.total_payable),
        "additional_details": app.additional_details or "",
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
    }


def _extract_external_id(response_data: Any) -> str:
    if not isinstance(response_data, dict):
        return ""
    for key in ("id", "lead_id", "external_id", "record_id"):
        value = response_data.get(key)
        if value not in (None, ""):
            return str(value)[:120]
    data = response_data.get("data")
    if isinstance(data, dict):
        for key in ("id", "lead_id", "external_id", "record_id"):
            value = data.get(key)
            if value not in (None, ""):
                return str(value)[:120]
    return ""


def _truncate_response(text: str, limit: int = 4000) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def sync_education_loan_lead_to_crm(
    app: EducationLoanApplication,
    *,
    force: bool = False,
) -> Tuple[bool, str]:
    """Send enquiry lead to CRM. Returns (success, message)."""
    if app.status != choices.EducationLoanApplicationStatus.ENQUIRY_SENT:
        return False, "Only submitted enquiries are synced to CRM."

    if not force and app.crm_sync_status == choices.EducationLoanCRMSyncStatus.SUCCESS:
        return True, "Lead already synced successfully."

    settings_obj = EducationLoanCRMSettings.load()
    if not settings_obj.is_enabled:
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.PENDING
        app.crm_sync_response = "CRM sync disabled in admin settings."
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "modified"])
        return False, "CRM sync is disabled."

    api_url = (settings_obj.api_url or "").strip()
    if not api_url:
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_synced_at = timezone.now()
        app.crm_sync_response = "CRM API URL is not configured."
        app.save(update_fields=["crm_sync_status", "crm_synced_at", "crm_sync_response", "modified"])
        return False, "CRM API URL is not configured."

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth_name = (settings_obj.auth_header_name or "").strip()
    auth_value = (settings_obj.auth_header_value or "").strip()
    if auth_name and auth_value:
        headers[auth_name] = auth_value

    payload = build_crm_lead_payload(app)
    timeout = max(5, min(int(settings_obj.timeout_seconds or 20), 120))

    app.crm_sync_status = choices.EducationLoanCRMSyncStatus.SENT
    app.crm_synced_at = timezone.now()
    app.crm_sync_response = "Sending lead to CRM..."
    app.save(update_fields=["crm_sync_status", "crm_synced_at", "crm_sync_response", "modified"])

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        response_text = _truncate_response(response.text or "")
        if 200 <= response.status_code < 300:
            external_id = ""
            try:
                response_data = response.json()
                external_id = _extract_external_id(response_data)
            except ValueError:
                response_data = None
            app.crm_sync_status = choices.EducationLoanCRMSyncStatus.SUCCESS
            app.crm_external_id = external_id
            app.crm_sync_response = response_text or f"HTTP {response.status_code}"
            app.crm_synced_at = timezone.now()
            app.save(
                update_fields=[
                    "crm_sync_status",
                    "crm_external_id",
                    "crm_sync_response",
                    "crm_synced_at",
                    "modified",
                ]
            )
            return True, "Lead synced to CRM successfully."

        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_sync_response = _truncate_response(
            f"HTTP {response.status_code}: {response_text or 'CRM request failed.'}"
        )
        app.crm_synced_at = timezone.now()
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "crm_synced_at", "modified"])
        return False, app.crm_sync_response

    except requests.RequestException as exc:
        logger.warning("Education loan CRM sync failed for lead %s: %s", app.id, exc)
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_sync_response = _truncate_response(str(exc))
        app.crm_synced_at = timezone.now()
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "crm_synced_at", "modified"])
        return False, app.crm_sync_response
