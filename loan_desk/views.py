"""Loan Desk views — dedicated shell for Manager / Executive (+ PWA)."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from core import choices
from loan_desk.decorators import (
    is_loan_desk_user,
    is_loan_manager,
    loan_desk_user_only,
    loan_manager_only,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
VALID_QUEUES = (
    "all",
    "not_started",
    "new",  # alias → not_started
    "not_followed_up",
    "today",
    "missed_yesterday",
    "pending",
    "qualified",
    "not_qualified",
    "unassigned",
)


def _base_ctx(request, **extra):
    return {
        "is_manager": is_loan_manager(request.user),
        "loan_user": request.user,
        "search_q": (request.GET.get("q") or "").strip(),
        **extra,
    }


class LoanDeskLoginView(View):
    template_name = "template20/loan_desk/login.html"

    def get(self, request):
        if is_loan_desk_user(request.user):
            return redirect("loan_desk:dashboard")
        ctx = {"next": request.GET.get("next") or ""}
        if request.user.is_authenticated and not is_loan_desk_user(request.user):
            ctx["error"] = (
                "Sign in with a Loan Desk manager or executive account to continue."
            )
        return render(request, self.template_name, ctx)

    def post(self, request):
        from loan_desk.validation import validate_login

        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        next_url = (request.POST.get("next") or "").strip() or reverse("loan_desk:dashboard")

        ok, field_errors = validate_login(email, password)
        if not ok:
            return render(
                request,
                self.template_name,
                {
                    "error": "Please fix the highlighted fields.",
                    "field_errors": field_errors,
                    "email": email,
                    "next": next_url,
                },
                status=400,
            )

        user = authenticate(request, username=email, password=password)
        if user is None:
            from users.models import User

            u = User.objects.filter(email__iexact=email).first()
            if u and u.check_password(password):
                user = u
        if user is None or not is_loan_desk_user(user):
            return render(
                request,
                self.template_name,
                {
                    "error": "Invalid credentials or account not enabled for Loan Desk.",
                    "field_errors": {
                        "email": "Check email and password.",
                        "password": "Check email and password.",
                    },
                    "email": email,
                    "next": next_url,
                },
                status=400,
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if not next_url.startswith("/"):
            next_url = reverse("loan_desk:dashboard")
        return redirect(next_url)


class LoanDeskLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("loan_desk:login")

    def post(self, request):
        return self.get(request)


@method_decorator(loan_desk_user_only, name="dispatch")
class LoanDeskDashboardView(TemplateView):
    template_name = "template20/loan_desk/dashboard.html"

    def get_context_data(self, **kwargs):
        from loan_desk.services import desk_dashboard_context

        ctx = super().get_context_data(**kwargs)
        request = self.request
        dash = desk_dashboard_context(request.user)
        ctx.update(
            _base_ctx(
                request,
                active_nav="dashboard",
                page_title="Dashboard",
                **dash,
            )
        )
        return ctx


@method_decorator(loan_desk_user_only, name="dispatch")
class LoanDeskHomeView(TemplateView):
    template_name = "template20/loan_desk/home.html"

    def get_context_data(self, **kwargs):
        from loan_desk.services import (
            attach_list_call_context,
            desk_base_queryset,
            desk_queue_counts,
            desk_queue_filter,
            desk_search_clients,
            unique_leads_latest,
        )

        ctx = super().get_context_data(**kwargs)
        request = self.request
        search_q = (request.GET.get("q") or "").strip()
        queue = (request.GET.get("queue") or "not_started").strip().lower()
        if queue not in VALID_QUEUES:
            queue = "not_started"
        if queue == "new":
            queue = "not_started"
        status = (request.GET.get("status") or "").strip()

        base = desk_base_queryset(request.user)
        # Client search looks across all queues in the user's scope
        if search_q:
            qs = desk_search_clients(base, search_q)
            queue = "all"
        else:
            qs = desk_queue_filter(base, queue)
            if queue == "all" and status.isdigit():
                qs = qs.filter(status=int(status))

        # One card per person (mobile/email); latest enquiry wins; mark re-enquiries.
        unique_apps = unique_leads_latest(qs)
        paginator = Paginator(unique_apps, PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page") or 1)
        applications = attach_list_call_context(
            list(page_obj.object_list),
            remark_limit=3,
        )
        counts = desk_queue_counts(request.user)
        from urllib.parse import urlencode

        return_params = {"queue": queue}
        if search_q:
            return_params["q"] = search_q
        if status and not search_q:
            return_params["status"] = status
        if page_obj.number > 1:
            return_params["page"] = page_obj.number
        return_q = "?" + urlencode(return_params)

        ctx.update(
            _base_ctx(
                request,
                applications=applications,
                page_obj=page_obj,
                queue=queue,
                search_q=search_q,
                queue_counts=counts,
                status_choices=choices.EducationLoanApplicationStatus.CHOICES,
                filter_status=status,
                bank_email_sent=choices.EducationLoanBankEmailStatus.SENT,
                bank_email_error=choices.EducationLoanBankEmailStatus.ERROR,
                crm_success=choices.EducationLoanCRMSyncStatus.SUCCESS,
                crm_error=choices.EducationLoanCRMSyncStatus.ERROR,
                active_nav="enquiries",
                page_title="Search clients" if search_q else "Enquiries",
                queue_return_url=reverse("loan_desk:home") + return_q,
                open_statuses=choices.EducationLoanApplicationStatus.OPEN_STATUSES,
            )
        )
        return ctx


def models_Q_assigned_or_unassigned(user):
    from django.db.models import Q

    return Q(assigned_to=user) | Q(assigned_to__isnull=True)


def _desk_safe_next(request, pk: int, *, default_tab: str = ""):
    """Prefer posted next path under /loan-desk/, else detail (?tab=)."""
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/loan-desk/") and "://" not in next_url:
        return redirect(next_url)
    tab = (request.POST.get("tab") or default_tab or "").strip()
    url = reverse("loan_desk:detail", kwargs={"pk": pk})
    if tab:
        url = f"{url}?tab={tab}"
    return redirect(url)


def _can_access_application(request, app) -> bool:
    if is_loan_manager(request.user) or request.user.is_superuser:
        return True
    if app.assigned_to_id and app.assigned_to_id != request.user.id:
        return False
    return True


@method_decorator(loan_desk_user_only, name="dispatch")
class LoanDeskDetailView(View):
    template_name = "template20/loan_desk/detail.html"

    def get(self, request, pk):
        from users.models import EducationLoanApplication

        app = get_object_or_404(
            EducationLoanApplication.objects.select_related(
                "assigned_to", "parent", "qualification_decided_by"
            ),
            pk=pk,
        )
        if app.status == choices.EducationLoanApplicationStatus.DRAFT:
            raise Http404()
        if not _can_access_application(request, app):
            return HttpResponse(status=403)
        from loan_desk.validation import parse_call_outcome_from_remark

        remarks_raw = list(app.remarks.select_related("author").all()[:50])
        remarks = []
        for remark in remarks_raw:
            outcome_key, outcome_label, note = parse_call_outcome_from_remark(
                remark.body or ""
            )
            remark.call_outcome = outcome_key
            remark.call_outcome_label = outcome_label
            remark.display_body = note or (remark.body or "")
            remarks.append(remark)
        team = []
        if is_loan_manager(request.user) or request.user.is_superuser:
            from loan_desk.services import loan_desk_team_users

            team = list(loan_desk_team_users(enabled_only=True))

        from loan_desk.services import (
            desk_queue_counts,
            related_enquiries_for,
            rendered_client_email_templates_for,
            whatsapp_api_url,
        )

        can_decide = is_loan_manager(request.user) or request.user.is_superuser
        is_qualified = app.status == choices.EducationLoanApplicationStatus.QUALIFIED
        pipeline_open = app.status in choices.EducationLoanApplicationStatus.OPEN_STATUSES
        previous_enquiries = related_enquiries_for(app, limit=8)
        is_reenquired = len(previous_enquiries) > 0
        enquiry_count = len(previous_enquiries) + 1
        whatsapp_url = whatsapp_api_url(app.mobile or "")
        import json

        client_email_templates = rendered_client_email_templates_for(
            app, actor=request.user
        )
        client_email_templates_json = json.dumps(client_email_templates)

        # Status dropdown: executives stay in open pipeline + closed; managers see all non-draft
        if can_decide:
            status_choices = [
                c
                for c in choices.EducationLoanApplicationStatus.CHOICES
                if c[0] != choices.EducationLoanApplicationStatus.DRAFT
            ]
        else:
            allowed = set(choices.EducationLoanApplicationStatus.OPEN_STATUSES) | {
                choices.EducationLoanApplicationStatus.CLOSED,
                app.status,
            }
            status_choices = [
                c
                for c in choices.EducationLoanApplicationStatus.CHOICES
                if c[0] in allowed
            ]

        return render(
            request,
            self.template_name,
            _base_ctx(
                request,
                application=app,
                remarks=remarks,
                team=team,
                whatsapp_url=whatsapp_url,
                active_tab=(request.GET.get("tab") or "").strip(),
                client_email_default_subject=(
                    f"Regarding your education loan enquiry #{app.id}"
                ),
                client_email_templates=client_email_templates,
                client_email_templates_json=client_email_templates_json,
                status_choices=status_choices,
                has_schedule_datetime=bool(
                    app.callback_preferred_at or app.next_follow_up_at
                ),
                callback_status_value=choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED,
                follow_up_status_value=choices.EducationLoanApplicationStatus.FOLLOW_UP,
                closed_status_value=choices.EducationLoanApplicationStatus.CLOSED,
                can_decide=can_decide,
                is_qualified=is_qualified,
                pipeline_open=pipeline_open,
                disqualify_reasons=choices.EducationLoanDisqualifyReason.CHOICES,
                bank_email_none=choices.EducationLoanBankEmailStatus.NONE,
                bank_email_sent=choices.EducationLoanBankEmailStatus.SENT,
                bank_email_error=choices.EducationLoanBankEmailStatus.ERROR,
                crm_pending=choices.EducationLoanCRMSyncStatus.PENDING,
                crm_sent=choices.EducationLoanCRMSyncStatus.SENT,
                crm_success=choices.EducationLoanCRMSyncStatus.SUCCESS,
                crm_error=choices.EducationLoanCRMSyncStatus.ERROR,
                queue_counts=desk_queue_counts(request.user),
                queue="",
                previous_enquiries=previous_enquiries,
                is_reenquired=is_reenquired,
                enquiry_count=enquiry_count,
                active_nav="enquiries",
                page_title=f"Enquiry #{app.id}",
            ),
        )

    def post(self, request, pk):
        from loan_desk.services import (
            disqualify_lead,
            push_lead_to_bank_api,
            push_lead_to_bank_email,
            qualify_lead,
            send_client_email,
        )
        from loan_desk.validation import (
            validate_assignee,
            validate_client_email,
            validate_disqualify,
            validate_follow_up,
            validate_qualify_note,
            validate_remark,
            validate_status,
        )
        from users.models import EducationLoanApplication, EducationLoanRemark, User

        app = get_object_or_404(EducationLoanApplication, pk=pk)
        if app.status == choices.EducationLoanApplicationStatus.DRAFT:
            raise Http404()
        if not _can_access_application(request, app):
            return HttpResponse(status=403)

        action = (request.POST.get("action") or "").strip()
        can_decide = is_loan_manager(request.user) or request.user.is_superuser

        if action == "remark":
            from loan_desk.validation import (
                format_remark_with_call_outcome,
                validate_call_outcome,
            )

            ok_c, cerr, outcome = validate_call_outcome(
                request.POST.get("call_outcome") or ""
            )
            if not ok_c:
                messages.error(
                    request, cerr.get("call_outcome") or "Select call status."
                )
                return _desk_safe_next(request, pk)
            ok, errors = validate_remark(request.POST.get("body") or "")
            if not ok:
                messages.error(request, errors.get("body") or "Invalid remark.")
                return _desk_safe_next(request, pk)
            body = format_remark_with_call_outcome(
                request.POST.get("body") or "", outcome or ""
            )
            EducationLoanRemark.objects.create(
                application=app, author=request.user, body=body[:5000]
            )
            app.last_followed_up_at = timezone.now()
            app.save(update_fields=["last_followed_up_at", "modified"])
            messages.success(request, "Remark added.")
        elif action == "client_email":
            ok, errors = validate_client_email(
                request.POST.get("subject") or "",
                request.POST.get("body") or "",
            )
            if not ok:
                messages.error(
                    request,
                    errors.get("subject")
                    or errors.get("body")
                    or "Invalid email.",
                )
                return _desk_safe_next(request, pk, default_tab="activity")
            ok, msg = send_client_email(
                app,
                actor=request.user,
                subject=request.POST.get("subject") or "",
                body=request.POST.get("body") or "",
            )
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        elif action == "log_follow_up":
            # Caller logs this call + optional next schedule (from queue cards)
            from loan_desk.validation import (
                format_remark_with_call_outcome,
                validate_call_outcome,
            )

            ok_c, cerr, outcome = validate_call_outcome(
                request.POST.get("call_outcome") or ""
            )
            if not ok_c:
                messages.error(
                    request, cerr.get("call_outcome") or "Select call status."
                )
                return _desk_safe_next(request, pk)
            ok, errors = validate_remark(request.POST.get("body") or "")
            if not ok:
                messages.error(request, errors.get("body") or "Add call notes to follow up.")
                return _desk_safe_next(request, pk)
            next_raw = (request.POST.get("next_follow_up_at") or "").strip()
            next_dt = None
            if next_raw:
                ok_f, ferr, next_dt = validate_follow_up(next_raw)
                if not ok_f:
                    messages.error(
                        request, ferr.get("next_follow_up_at") or "Invalid follow-up."
                    )
                    return _desk_safe_next(request, pk)
            body = format_remark_with_call_outcome(
                request.POST.get("body") or "", outcome or ""
            )
            EducationLoanRemark.objects.create(
                application=app, author=request.user, body=body[:5000]
            )
            app.last_followed_up_at = timezone.now()
            update_fields = ["last_followed_up_at", "modified"]
            if next_dt is not None:
                app.next_follow_up_at = next_dt
                update_fields.append("next_follow_up_at")
            if app.status in (
                choices.EducationLoanApplicationStatus.ENQUIRY_SENT,
                choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED,
            ):
                app.status = choices.EducationLoanApplicationStatus.FOLLOW_UP
                update_fields.append("status")
            elif (
                next_dt is not None
                and app.status == choices.EducationLoanApplicationStatus.IN_PROGRESS
            ):
                app.status = choices.EducationLoanApplicationStatus.FOLLOW_UP
                update_fields.append("status")
            app.save(update_fields=list(dict.fromkeys(update_fields)))
            messages.success(
                request,
                "Follow-up logged."
                + (" Next call scheduled." if next_dt is not None else ""),
            )
        elif action == "follow_up":
            ok, errors, dt = validate_follow_up(request.POST.get("next_follow_up_at") or "")
            if not ok:
                messages.error(
                    request, errors.get("next_follow_up_at") or "Invalid follow-up."
                )
                return _desk_safe_next(request, pk)
            app.next_follow_up_at = dt
            if app.status == choices.EducationLoanApplicationStatus.ENQUIRY_SENT:
                app.status = choices.EducationLoanApplicationStatus.FOLLOW_UP
            app.save(update_fields=["next_follow_up_at", "status", "modified"])
            messages.success(request, "Follow-up scheduled.")
        elif action == "status":
            has_schedule = bool(app.callback_preferred_at or app.next_follow_up_at)
            ok, errors, st = validate_status(
                request.POST.get("status"),
                has_schedule_datetime=has_schedule,
            )
            if not ok:
                messages.error(request, errors.get("status") or "Invalid status.")
                return _desk_safe_next(request, pk, default_tab="status")
            # Executives cannot set qualify statuses via dropdown
            if not can_decide and st in (
                choices.EducationLoanApplicationStatus.QUALIFIED,
                choices.EducationLoanApplicationStatus.NOT_QUALIFIED,
            ):
                messages.error(request, "Only managers can set qualification status.")
                return _desk_safe_next(request, pk, default_tab="status")
            app.status = st
            app.save(update_fields=["status", "modified"])
            messages.success(request, "Status updated.")
        elif action == "assign":
            if not can_decide:
                messages.error(request, "Only managers can assign lead follow.")
                return _desk_safe_next(request, pk, default_tab="assign")
            from loan_desk.services import loan_desk_team_users

            team_ids = [int(u.id) for u in loan_desk_team_users(enabled_only=True)]
            ok, errors, aid = validate_assignee(
                request.POST.get("assigned_to"), team_ids=team_ids
            )
            if not ok:
                messages.error(request, errors.get("assigned_to") or "Invalid assignee.")
                return _desk_safe_next(request, pk, default_tab="assign")
            prev_assignee_id = app.assigned_to_id
            if aid is None:
                app.assigned_to = None
            else:
                app.assigned_to = User.objects.filter(id=aid).first()
            app.save(update_fields=["assigned_to", "modified"])
            if aid and aid != prev_assignee_id and app.assigned_to_id:
                try:
                    from loan_desk.tasks import send_loan_assignment_notify

                    send_loan_assignment_notify.delay(app.id, request.user.id)
                except Exception:
                    try:
                        from loan_desk.services import notify_lead_assignee

                        notify_lead_assignee(
                            app, request=request, assigned_by=request.user
                        )
                    except Exception:
                        pass
            messages.success(request, "Lead follow updated.")
        elif action == "qualify":
            if not can_decide:
                messages.error(request, "Only managers can qualify leads.")
                return redirect("loan_desk:detail", pk=pk)
            ok, errors = validate_qualify_note(request.POST.get("qualification_note") or "")
            if not ok:
                messages.error(
                    request, errors.get("qualification_note") or "Invalid note."
                )
                return redirect("loan_desk:detail", pk=pk)
            ok, msg = qualify_lead(
                app,
                actor=request.user,
                note=request.POST.get("qualification_note") or "",
            )
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        elif action == "disqualify":
            if not can_decide:
                messages.error(request, "Only managers can mark leads Not Qualified.")
                return redirect("loan_desk:detail", pk=pk)
            ok, errors = validate_disqualify(
                request.POST.get("disqualify_reason") or "",
                request.POST.get("disqualify_reason_text") or "",
            )
            if not ok:
                messages.error(
                    request,
                    errors.get("disqualify_reason")
                    or errors.get("disqualify_reason_text")
                    or "Invalid reason.",
                )
                return redirect("loan_desk:detail", pk=pk)
            ok, msg = disqualify_lead(
                app,
                actor=request.user,
                reason=request.POST.get("disqualify_reason") or "",
                reason_text=request.POST.get("disqualify_reason_text") or "",
            )
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        elif action == "bank_email":
            if not can_decide:
                messages.error(request, "Only managers can push leads to the bank by email.")
                return redirect("loan_desk:detail", pk=pk)
            ok, msg = push_lead_to_bank_email(app, actor=request.user)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        elif action in ("bank_api", "bank_api_resend"):
            if not can_decide:
                messages.error(request, "Only managers can push leads to the Bank API.")
                return redirect("loan_desk:detail", pk=pk)
            ok, msg = push_lead_to_bank_api(app, actor=request.user, force=True)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        else:
            messages.error(request, "Unknown action.")
        return _desk_safe_next(request, pk)


class LoanDeskInstantLoginView(View):
    def get(self, request, token):
        from loan_desk.services import consume_instant_login_token

        user, application = consume_instant_login_token(token)
        if not user or not application:
            messages.error(request, "This login link is invalid or has expired.")
            return redirect("loan_desk:login")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("loan_desk:detail", pk=application.id)


@method_decorator(loan_manager_only, name="dispatch")
class LoanDeskEmailTemplatesView(View):
    """Manager CRUD for client email message templates."""

    template_name = "template20/loan_desk/email_templates.html"

    def get(self, request):
        from loan_desk.services import (
            CLIENT_EMAIL_TEMPLATE_VARIABLES,
            SAMPLE_CLIENT_EMAIL_BODY,
            SAMPLE_CLIENT_EMAIL_SUBJECT,
            desk_queue_counts,
        )
        from users.models import EducationLoanClientEmailTemplate

        edit_id = (request.GET.get("edit") or "").strip()
        edit_tpl = None
        if edit_id.isdigit():
            edit_tpl = EducationLoanClientEmailTemplate.objects.filter(
                pk=int(edit_id)
            ).first()

        templates = list(
            EducationLoanClientEmailTemplate.objects.order_by(
                "sort_order", "name", "id"
            )
        )
        return render(
            request,
            self.template_name,
            _base_ctx(
                request,
                templates=templates,
                edit_template=edit_tpl,
                placeholder_vars=CLIENT_EMAIL_TEMPLATE_VARIABLES,
                sample_email_subject=SAMPLE_CLIENT_EMAIL_SUBJECT,
                sample_email_body=SAMPLE_CLIENT_EMAIL_BODY,
                queue_counts=desk_queue_counts(request.user),
                queue="",
                active_nav="email_templates",
                page_title="Email templates",
            ),
        )

    def post(self, request):
        from loan_desk.validation import validate_email_template
        from users.models import EducationLoanClientEmailTemplate

        action = (request.POST.get("action") or "").strip()

        if action == "delete":
            pk = (request.POST.get("template_id") or "").strip()
            tpl = (
                EducationLoanClientEmailTemplate.objects.filter(pk=int(pk)).first()
                if pk.isdigit()
                else None
            )
            if not tpl:
                messages.error(request, "Template not found.")
            else:
                tpl.delete()
                messages.success(request, f"Template “{tpl.name}” deleted.")
            return redirect("loan_desk:email_templates")

        if action == "toggle":
            pk = (request.POST.get("template_id") or "").strip()
            tpl = (
                EducationLoanClientEmailTemplate.objects.filter(pk=int(pk)).first()
                if pk.isdigit()
                else None
            )
            if not tpl:
                messages.error(request, "Template not found.")
            else:
                tpl.is_active = not tpl.is_active
                tpl.save(update_fields=["is_active", "modified"])
                state = "active" if tpl.is_active else "inactive"
                messages.success(request, f"Template “{tpl.name}” is now {state}.")
            return redirect("loan_desk:email_templates")

        if action in ("create", "update"):
            ok, errors, cleaned = validate_email_template(
                request.POST.get("name") or "",
                request.POST.get("subject") or "",
                request.POST.get("body") or "",
                request.POST.get("sort_order") or "0",
            )
            if not ok:
                messages.error(
                    request,
                    errors.get("name")
                    or errors.get("subject")
                    or errors.get("body")
                    or errors.get("sort_order")
                    or "Invalid template.",
                )
                edit_q = ""
                if action == "update":
                    pk = (request.POST.get("template_id") or "").strip()
                    if pk.isdigit():
                        edit_q = f"?edit={pk}"
                return redirect(reverse("loan_desk:email_templates") + edit_q)

            is_active = (request.POST.get("is_active") or "") == "1"
            if action == "create":
                EducationLoanClientEmailTemplate.objects.create(
                    name=cleaned["name"],
                    subject=cleaned["subject"],
                    body=cleaned["body"],
                    sort_order=cleaned["sort_order"],
                    is_active=is_active,
                    created_by=request.user,
                )
                messages.success(request, "Email template created.")
            else:
                pk = (request.POST.get("template_id") or "").strip()
                tpl = (
                    EducationLoanClientEmailTemplate.objects.filter(pk=int(pk)).first()
                    if pk.isdigit()
                    else None
                )
                if not tpl:
                    messages.error(request, "Template not found.")
                else:
                    tpl.name = cleaned["name"]
                    tpl.subject = cleaned["subject"]
                    tpl.body = cleaned["body"]
                    tpl.sort_order = cleaned["sort_order"]
                    tpl.is_active = is_active
                    tpl.save(
                        update_fields=[
                            "name",
                            "subject",
                            "body",
                            "sort_order",
                            "is_active",
                            "modified",
                        ]
                    )
                    messages.success(request, "Email template updated.")
            return redirect("loan_desk:email_templates")

        messages.error(request, "Unknown action.")
        return redirect("loan_desk:email_templates")


@require_http_methods(["GET"])
def loan_desk_manifest(request):
    from loan_desk.pwa import loan_desk_manifest_response

    return loan_desk_manifest_response(request)


@require_http_methods(["GET"])
def loan_desk_service_worker(request):
    from loan_desk.pwa import loan_desk_service_worker_response

    return loan_desk_service_worker_response(request)
