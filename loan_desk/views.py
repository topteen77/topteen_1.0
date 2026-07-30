"""Loan Desk views — dedicated shell for Manager / Executive (+ PWA)."""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from core import choices
from loan_desk.decorators import is_loan_desk_user, is_loan_manager, loan_desk_user_only

logger = logging.getLogger(__name__)


def _base_ctx(request, **extra):
    return {
        "is_manager": is_loan_manager(request.user),
        "loan_user": request.user,
        **extra,
    }


class LoanDeskLoginView(View):
    template_name = "template20/loan_desk/login.html"

    def get(self, request):
        if is_loan_desk_user(request.user):
            return redirect("loan_desk:home")
        return render(request, self.template_name, {"next": request.GET.get("next") or ""})

    def post(self, request):
        from loan_desk.validation import validate_login

        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        next_url = (request.POST.get("next") or "").strip() or reverse("loan_desk:home")

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
            next_url = reverse("loan_desk:home")
        return redirect(next_url)


class LoanDeskLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("loan_desk:login")

    def post(self, request):
        return self.get(request)


@method_decorator(loan_desk_user_only, name="dispatch")
class LoanDeskHomeView(TemplateView):
    template_name = "template20/loan_desk/home.html"

    def get_context_data(self, **kwargs):
        from users.models import EducationLoanApplication

        ctx = super().get_context_data(**kwargs)
        request = self.request
        status = (request.GET.get("status") or "").strip()
        qs = (
            EducationLoanApplication.objects.exclude(
                status=choices.EducationLoanApplicationStatus.DRAFT
            )
            .select_related("assigned_to", "parent")
            .order_by("-submitted_at", "-id")
        )
        if not is_loan_manager(request.user) and not request.user.is_superuser:
            qs = qs.filter(
                models_Q_assigned_or_unassigned(request.user)
            )
        if status.isdigit():
            qs = qs.filter(status=int(status))
        overdue = (request.GET.get("overdue") or "").strip() == "1"
        if overdue:
            from datetime import timedelta

            from loan_desk.services import _reminder_filter_q
            from users.models import EducationLoanOpsSettings

            ops = EducationLoanOpsSettings.load()
            now = timezone.now()
            hours = max(1, int(ops.reminder_unfollowed_after_hours or 24))
            threshold = now - timedelta(hours=hours)
            qs = qs.filter(
                status__in=choices.EducationLoanApplicationStatus.OPEN_STATUSES,
            ).filter(_reminder_filter_q(now=now, threshold=threshold))
        apps = list(qs[:100])
        ctx.update(
            _base_ctx(
                request,
                applications=apps,
                status_choices=choices.EducationLoanApplicationStatus.CHOICES,
                filter_status=status,
                filter_overdue=overdue,
                page_title="Loan enquiries",
            )
        )
        return ctx


def models_Q_assigned_or_unassigned(user):
    from django.db.models import Q

    return Q(assigned_to=user) | Q(assigned_to__isnull=True)


@method_decorator(loan_desk_user_only, name="dispatch")
class LoanDeskDetailView(View):
    template_name = "template20/loan_desk/detail.html"

    def get(self, request, pk):
        from users.models import EducationLoanApplication

        app = get_object_or_404(
            EducationLoanApplication.objects.select_related("assigned_to", "parent"),
            pk=pk,
        )
        if app.status == choices.EducationLoanApplicationStatus.DRAFT:
            raise Http404()
        if (
            not is_loan_manager(request.user)
            and not request.user.is_superuser
            and app.assigned_to_id
            and app.assigned_to_id != request.user.id
        ):
            return HttpResponse(status=403)
        remarks = app.remarks.select_related("author").all()[:50]
        team = []
        if is_loan_manager(request.user) or request.user.is_superuser:
            from loan_desk.services import loan_desk_team_users

            team = list(loan_desk_team_users(enabled_only=True))
        return render(
            request,
            self.template_name,
            _base_ctx(
                request,
                application=app,
                remarks=remarks,
                team=team,
                status_choices=[
                    c
                    for c in choices.EducationLoanApplicationStatus.CHOICES
                    if c[0] != choices.EducationLoanApplicationStatus.DRAFT
                ],
                has_schedule_datetime=bool(
                    app.callback_preferred_at or app.next_follow_up_at
                ),
                callback_status_value=choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED,
                follow_up_status_value=choices.EducationLoanApplicationStatus.FOLLOW_UP,
                page_title=f"Enquiry #{app.id}",
            ),
        )

    def post(self, request, pk):
        from loan_desk.validation import (
            validate_assignee,
            validate_follow_up,
            validate_remark,
            validate_status,
        )
        from users.models import EducationLoanApplication, EducationLoanRemark, User

        app = get_object_or_404(EducationLoanApplication, pk=pk)
        if app.status == choices.EducationLoanApplicationStatus.DRAFT:
            raise Http404()
        if (
            not is_loan_manager(request.user)
            and not request.user.is_superuser
            and app.assigned_to_id
            and app.assigned_to_id != request.user.id
        ):
            return HttpResponse(status=403)

        action = (request.POST.get("action") or "").strip()
        if action == "remark":
            ok, errors = validate_remark(request.POST.get("body") or "")
            if not ok:
                messages.error(request, errors.get("body") or "Invalid remark.")
                return redirect("loan_desk:detail", pk=pk)
            body = (request.POST.get("body") or "").strip()
            EducationLoanRemark.objects.create(
                application=app, author=request.user, body=body[:5000]
            )
            app.last_followed_up_at = timezone.now()
            app.save(update_fields=["last_followed_up_at", "modified"])
            messages.success(request, "Remark added.")
        elif action == "follow_up":
            ok, errors, dt = validate_follow_up(request.POST.get("next_follow_up_at") or "")
            if not ok:
                messages.error(
                    request, errors.get("next_follow_up_at") or "Invalid follow-up."
                )
                return redirect("loan_desk:detail", pk=pk)
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
                return redirect("loan_desk:detail", pk=pk)
            app.status = st
            app.save(update_fields=["status", "modified"])
            messages.success(request, "Status updated.")
        elif action == "assign":
            if not (is_loan_manager(request.user) or request.user.is_superuser):
                messages.error(request, "Only managers can assign lead follow.")
                return redirect("loan_desk:detail", pk=pk)
            from loan_desk.services import loan_desk_team_users

            team_ids = [int(u.id) for u in loan_desk_team_users(enabled_only=True)]
            ok, errors, aid = validate_assignee(
                request.POST.get("assigned_to"), team_ids=team_ids
            )
            if not ok:
                messages.error(request, errors.get("assigned_to") or "Invalid assignee.")
                return redirect("loan_desk:detail", pk=pk)
            if aid is None:
                app.assigned_to = None
            else:
                app.assigned_to = User.objects.filter(id=aid).first()
            app.save(update_fields=["assigned_to", "modified"])
            messages.success(request, "Lead follow updated.")
        else:
            messages.error(request, "Unknown action.")
        return redirect("loan_desk:detail", pk=pk)


class LoanDeskInstantLoginView(View):
    def get(self, request, token):
        from loan_desk.services import consume_instant_login_token

        user, application = consume_instant_login_token(token)
        if not user or not application:
            messages.error(request, "This login link is invalid or has expired.")
            return redirect("loan_desk:login")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("loan_desk:detail", pk=application.id)


@require_http_methods(["GET"])
def loan_desk_manifest(request):
    from loan_desk.pwa import loan_desk_manifest_response

    return loan_desk_manifest_response(request)


@require_http_methods(["GET"])
def loan_desk_service_worker(request):
    from loan_desk.pwa import loan_desk_service_worker_response

    return loan_desk_service_worker_response(request)
