"""Push education loan leads to a configurable Bank API (URL, method, parameters)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.utils import timezone

from core import choices
from users.models import EducationLoanApplication, EducationLoanCRMSettings

logger = logging.getLogger(__name__)

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

# Variables available in api_url and parameters_template
BANK_API_VARIABLES: List[Tuple[str, str]] = [
    ("lead_id", "Enquiry / lead id"),
    ("status", "Status label"),
    ("parent_id", "Parent user id"),
    ("student_id", "Student user id"),
    ("student_name", "Student name"),
    ("parent_name", "Parent name"),
    ("mobile", "Mobile"),
    ("email", "Email"),
    ("institute_name", "Institute / college"),
    ("course_name", "Course"),
    ("country_preference", "Country preference"),
    ("loan_amount", "Loan amount"),
    ("interest_rate", "Interest rate %"),
    ("tenure_years", "Tenure (years)"),
    ("moratorium_months", "Moratorium months"),
    ("estimated_emi", "Estimated EMI"),
    ("total_interest", "Total interest"),
    ("total_payable", "Total payable"),
    ("additional_details", "Additional details"),
    ("submitted_at", "Submitted at (ISO)"),
    ("callback_preferred_at", "Callback preferred at (ISO)"),
    ("callback_note", "Callback note"),
    ("qualification_note", "Qualification note"),
    ("source", "Fixed source tag (topteen_education_loan)"),
]


def build_crm_lead_payload(app: EducationLoanApplication) -> Dict[str, Any]:
    """Default full lead payload when parameters template is blank."""
    return _typed_variables(app)


def _num(value):
    return float(value) if value is not None else None


def _typed_variables(app: EducationLoanApplication) -> Dict[str, Any]:
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
        "callback_preferred_at": (
            app.callback_preferred_at.isoformat() if app.callback_preferred_at else None
        ),
        "callback_note": app.callback_note or "",
        "qualification_note": getattr(app, "qualification_note", None) or "",
    }


def lead_variables_for_template(app: EducationLoanApplication) -> Dict[str, str]:
    """String values for {{variable}} substitution (JSON-safe when dumped)."""
    typed = _typed_variables(app)
    out: Dict[str, str] = {}
    for key, value in typed.items():
        if value is None:
            out[key] = ""
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


def substitute_template(template: str, variables: Dict[str, str]) -> str:
    def repl(match):
        name = match.group(1)
        return variables.get(name, "")

    return _VAR_RE.sub(repl, template or "")


def _coerce_json_scalars(obj: Any) -> Any:
    """Turn numeric/boolean-looking strings into JSON scalars after substitution."""
    if isinstance(obj, dict):
        return {k: _coerce_json_scalars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_json_scalars(v) for v in obj]
    if not isinstance(obj, str):
        return obj
    s = obj.strip()
    if s == "":
        return ""
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.lower() in ("null", "none"):
        return None
    try:
        if re.fullmatch(r"-?\d+", s):
            return int(s)
        if re.fullmatch(r"-?\d+\.\d+", s):
            return float(s)
    except ValueError:
        pass
    return obj


def build_request_parameters(
    app: EducationLoanApplication,
    settings_obj: EducationLoanCRMSettings,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Build parameters dict from template + variables.
    Returns (params, error_message).
    """
    raw = (settings_obj.parameters_template or "").strip()
    if not raw:
        return build_crm_lead_payload(app), None

    variables = lead_variables_for_template(app)
    rendered = substitute_template(raw, variables)
    try:
        data = json.loads(rendered)
    except json.JSONDecodeError as exc:
        return None, f"Bank API parameters JSON is invalid after variable substitution: {exc}"
    if not isinstance(data, dict):
        return None, "Bank API parameters must be a JSON object."
    return _coerce_json_scalars(data), None


def validate_parameters_template(raw: str) -> Tuple[bool, str]:
    """Admin validation: template must be JSON object with {{vars}} replaced by null."""
    text = (raw or "").strip()
    if not text:
        return True, ""
    test = _VAR_RE.sub("null", text)
    try:
        data = json.loads(test)
    except json.JSONDecodeError as exc:
        return False, f"Parameters must be valid JSON (use {{{{variable}}}} placeholders). {exc}"
    if not isinstance(data, dict):
        return False, "Parameters must be a JSON object (key/value map)."
    return True, ""


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


def _bank_api_allowed_statuses():
    return {
        choices.EducationLoanApplicationStatus.ENQUIRY_SENT,
        choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED,
        choices.EducationLoanApplicationStatus.IN_PROGRESS,
        choices.EducationLoanApplicationStatus.FOLLOW_UP,
        choices.EducationLoanApplicationStatus.QUALIFIED,
    }


def sync_education_loan_lead_to_crm(
    app: EducationLoanApplication,
    *,
    force: bool = False,
    require_qualified: bool = False,
) -> Tuple[bool, str]:
    """Push lead to Bank API using configured URL, method, and parameters."""
    if require_qualified:
        if app.status != choices.EducationLoanApplicationStatus.QUALIFIED:
            return False, "Only qualified leads can be pushed to the Bank API."
    elif app.status not in _bank_api_allowed_statuses():
        return False, "This lead status cannot be pushed to the Bank API."

    if not force and app.crm_sync_status == choices.EducationLoanCRMSyncStatus.SUCCESS:
        return True, "Lead already pushed to Bank API successfully."

    settings_obj = EducationLoanCRMSettings.load()
    if not settings_obj.is_enabled:
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.PENDING
        app.crm_sync_response = "Bank API sync disabled in admin settings."
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "modified"])
        return False, "Bank API sync is disabled."

    variables = lead_variables_for_template(app)
    api_url = substitute_template((settings_obj.api_url or "").strip(), variables).strip()
    if not api_url:
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_synced_at = timezone.now()
        app.crm_sync_response = "Bank API URL is not configured."
        app.save(update_fields=["crm_sync_status", "crm_synced_at", "crm_sync_response", "modified"])
        return False, "Bank API URL is not configured."

    params, param_err = build_request_parameters(app, settings_obj)
    if param_err:
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_synced_at = timezone.now()
        app.crm_sync_response = param_err
        app.save(update_fields=["crm_sync_status", "crm_synced_at", "crm_sync_response", "modified"])
        return False, param_err

    method = (getattr(settings_obj, "http_method", None) or "POST").upper().strip()
    if method not in {c[0] for c in choices.EducationLoanBankApiHttpMethod.CHOICES}:
        method = choices.EducationLoanBankApiHttpMethod.POST

    headers = {"Accept": "application/json"}
    auth_name = (settings_obj.auth_header_name or "").strip()
    auth_value = (settings_obj.auth_header_value or "").strip()
    if auth_name and auth_value:
        headers[auth_name] = auth_value

    timeout = max(5, min(int(settings_obj.timeout_seconds or 20), 120))

    app.crm_sync_status = choices.EducationLoanCRMSyncStatus.SENT
    app.crm_synced_at = timezone.now()
    app.crm_sync_response = f"Sending lead to Bank API ({method})..."
    app.save(update_fields=["crm_sync_status", "crm_synced_at", "crm_sync_response", "modified"])

    request_kwargs: Dict[str, Any] = {"headers": headers, "timeout": timeout}
    if method == choices.EducationLoanBankApiHttpMethod.GET:
        request_kwargs["params"] = params
    else:
        headers["Content-Type"] = "application/json"
        request_kwargs["headers"] = headers
        request_kwargs["json"] = params

    try:
        response = requests.request(method, api_url, **request_kwargs)
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
            return True, "Lead pushed to Bank API successfully."

        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_sync_response = _truncate_response(
            f"HTTP {response.status_code}: {response_text or 'Bank API request failed.'}"
        )
        app.crm_synced_at = timezone.now()
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "crm_synced_at", "modified"])
        return False, app.crm_sync_response

    except requests.RequestException as exc:
        logger.warning("Education loan Bank API sync failed for lead %s: %s", app.id, exc)
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.ERROR
        app.crm_sync_response = _truncate_response(str(exc))
        app.crm_synced_at = timezone.now()
        app.save(update_fields=["crm_sync_status", "crm_sync_response", "crm_synced_at", "modified"])
        return False, app.crm_sync_response
