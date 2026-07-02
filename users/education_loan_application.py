"""Persist parent education loan calculator drafts and enquiry submissions."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from core import choices
from users.models import EducationLoanApplication, ParentStudentLink, User


def _to_decimal(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value, max_len: int = 300) -> str:
    return str(value or "").strip()[:max_len]


def serialize_education_loan_application(app: EducationLoanApplication) -> Dict[str, Any]:
    def _num(field):
        val = getattr(app, field, None)
        return float(val) if val is not None else None

    return {
        "id": app.id,
        "status": app.status,
        "status_label": app.get_status_display(),
        "student_id": app.student_id,
        "calculator": {
            "loan_amount": _num("loan_amount"),
            "interest_rate": _num("interest_rate"),
            "tenure_years": _num("tenure_years"),
            "moratorium_months": app.moratorium_months,
            "country_preference": app.country_preference or "",
            "estimated_emi": _num("estimated_emi"),
            "total_interest": _num("total_interest"),
            "total_payable": _num("total_payable"),
        },
        "application": {
            "student_name": app.student_name or "",
            "parent_name": app.parent_name or "",
            "mobile": app.mobile or "",
            "email": app.email or "",
            "institute_name": app.institute_name or "",
            "course_name": app.course_name or "",
            "additional_details": app.additional_details or "",
        },
        "modified": app.modified.isoformat() if app.modified else None,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "created": app.created.isoformat() if app.created else None,
    }


def _format_inr(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"INR {float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def serialize_education_loan_application_for_parent_list(app: EducationLoanApplication) -> Dict[str, Any]:
    data = serialize_education_loan_application(app)
    calc = data.get("calculator") or {}
    application = data.get("application") or {}
    student_name = (application.get("student_name") or "").strip() or "Student not set"

    def _display_dt(value):
        if not value:
            return "—"
        try:
            return timezone.localtime(value).strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(value)

    data["display_modified"] = _display_dt(app.modified)
    data["display_submitted"] = _display_dt(app.submitted_at)
    data["display_loan_amount"] = _format_inr(calc.get("loan_amount"))
    data["display_emi"] = _format_inr(calc.get("estimated_emi"))
    data["display_total_payable"] = _format_inr(calc.get("total_payable"))
    data["student_initial"] = student_name[0].upper() if student_name else "?"
    data["has_calculator"] = bool(calc.get("loan_amount"))
    data["tenure_label"] = (
        f"{calc.get('tenure_years')} yrs" if calc.get("tenure_years") is not None else "—"
    )
    data["country_label"] = calc.get("country_preference") or "—"
    data["interest_label"] = (
        f"{calc.get('interest_rate')}%" if calc.get("interest_rate") is not None else "—"
    )
    return data


def build_parent_loan_applications_summary(applications: List[Dict[str, Any]]) -> Dict[str, Any]:
    draft_count = 0
    enquiry_count = 0
    total_amount = 0.0
    for item in applications:
        if item.get("status") == choices.EducationLoanApplicationStatus.DRAFT:
            draft_count += 1
        elif item.get("status") == choices.EducationLoanApplicationStatus.ENQUIRY_SENT:
            enquiry_count += 1
        amount = (item.get("calculator") or {}).get("loan_amount")
        if amount:
            total_amount += float(amount)
    return {
        "total": len(applications),
        "draft_count": draft_count,
        "enquiry_count": enquiry_count,
        "total_amount_display": _format_inr(total_amount) if total_amount else "INR 0",
    }


def get_parent_education_loan_applications(parent: User):
    return (
        EducationLoanApplication.objects.filter(parent=parent)
        .select_related("student")
        .order_by("-modified", "-id")
    )


def get_parent_education_loan_draft(parent: User) -> Optional[EducationLoanApplication]:
    return (
        EducationLoanApplication.objects.filter(
            parent=parent,
            status=choices.EducationLoanApplicationStatus.DRAFT,
        )
        .order_by("-modified")
        .first()
    )


def get_parent_latest_enquiry(parent: User) -> Optional[EducationLoanApplication]:
    return (
        EducationLoanApplication.objects.filter(
            parent=parent,
            status=choices.EducationLoanApplicationStatus.ENQUIRY_SENT,
        )
        .order_by("-submitted_at", "-id")
        .first()
    )


def _resolve_linked_student(parent: User, student_id) -> Optional[User]:
    if not student_id:
        return None
    try:
        student_id = int(student_id)
    except (TypeError, ValueError):
        return None
    link = ParentStudentLink.objects.filter(parent=parent, student_id=student_id).select_related("student").first()
    return link.student if link else None


def validate_education_loan_submission(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    application = payload.get("application") or {}
    calculator = payload.get("calculator") or {}
    errors: List[str] = []

    if not _clean_text(application.get("student_name"), 200):
        errors.append("Student name is required.")
    email = _clean_text(application.get("email"), 254)
    if not email or "@" not in email:
        errors.append("A valid email address is required.")
    if not _clean_text(application.get("institute_name"), 300):
        errors.append("Institute / college name is required.")
    if not _clean_text(application.get("course_name"), 300):
        errors.append("Course name is required.")

    mobile = _clean_text(application.get("mobile"), 20)
    digits = "".join(ch for ch in mobile if ch.isdigit())
    if mobile and len(digits) != 10:
        errors.append("Enter a valid 10-digit mobile number.")

    amount = _to_decimal(calculator.get("loan_amount"))
    rate = _to_decimal(calculator.get("interest_rate"))
    tenure = _to_decimal(calculator.get("tenure_years"))
    moratorium = _to_int(calculator.get("moratorium_months"))
    country = _clean_text(calculator.get("country_preference"), 100)

    if amount is None or not (Decimal("10000") <= amount <= Decimal("50000000")):
        errors.append("Enter a loan amount between INR 10,000 and 5,00,00,000.")
    if rate is None or not (Decimal("0.1") <= rate <= Decimal("30")):
        errors.append("Enter an annual interest rate between 0.1% and 30%.")
    if tenure is None or not (Decimal("1") <= tenure <= Decimal("20")):
        errors.append("Enter a loan tenure between 1 and 20 years.")
    if moratorium is None or moratorium < 0 or moratorium > 48:
        errors.append("Enter moratorium between 0 and 48 months.")
    if not country:
        errors.append("Please select a country preference.")

    return (len(errors) == 0, errors)


def save_education_loan_application(
    parent: User,
    payload: Dict[str, Any],
    *,
    as_draft: bool,
) -> Tuple[EducationLoanApplication, Optional[List[str]]]:
    if not as_draft:
        ok, errors = validate_education_loan_submission(payload)
        if not ok:
            return None, errors

    application = payload.get("application") or {}
    calculator = payload.get("calculator") or {}
    application_id = payload.get("application_id")

    app = None
    if application_id:
        app = EducationLoanApplication.objects.filter(
            parent=parent,
            id=application_id,
        ).first()

    if app is None and as_draft:
        app = get_parent_education_loan_draft(parent)

    if app is None:
        app = EducationLoanApplication(parent=parent)

    student = _resolve_linked_student(parent, payload.get("student_id"))
    app.student = student
    app.loan_amount = _to_decimal(calculator.get("loan_amount"))
    app.interest_rate = _to_decimal(calculator.get("interest_rate"))
    app.tenure_years = _to_decimal(calculator.get("tenure_years"))
    app.moratorium_months = _to_int(calculator.get("moratorium_months"))
    app.country_preference = _clean_text(calculator.get("country_preference"), 100)
    app.estimated_emi = _to_decimal(calculator.get("estimated_emi"))
    app.total_interest = _to_decimal(calculator.get("total_interest"))
    app.total_payable = _to_decimal(calculator.get("total_payable"))
    app.student_name = _clean_text(application.get("student_name"), 200)
    app.parent_name = _clean_text(application.get("parent_name") or parent.name, 200)
    app.mobile = _clean_text(application.get("mobile") or parent.mobile, 20)
    app.email = _clean_text(application.get("email") or parent.email, 254)
    app.institute_name = _clean_text(application.get("institute_name"), 300)
    app.course_name = _clean_text(application.get("course_name"), 300)
    app.additional_details = _clean_text(application.get("additional_details"), 5000)

    if as_draft:
        app.status = choices.EducationLoanApplicationStatus.DRAFT
        app.submitted_at = None
    else:
        app.status = choices.EducationLoanApplicationStatus.ENQUIRY_SENT
        app.submitted_at = timezone.now()
        app.crm_sync_status = choices.EducationLoanCRMSyncStatus.PENDING
        app.crm_synced_at = None
        app.crm_external_id = ""
        app.crm_sync_response = ""

    app.save()

    if not as_draft:
        from users.education_loan_crm import sync_education_loan_lead_to_crm

        sync_education_loan_lead_to_crm(app)

    return app, None
