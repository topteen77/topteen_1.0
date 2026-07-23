"""Resume Builder V2 views — dashboard, creation flow, studio, and API endpoints."""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.utils import timezone

from core.breadcrumbs import get_breadcrumb
from core.utils import build_html_head

from .models import (
    UserProfile,
    UserResume,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
)
from .resume_payload import (
    STUDIO_THEME_COLORS,
    STUDIO_FONT_FAMILIES,
    resume_editor_payload,
    resume_studio_prototype_payload,
    studio_font_id_from_stack,
    studio_prefs_from_resume_record,
)
from .resume_v2_ai import friendly_openai_error
from .resume_v2_services import (
    RESUME_GOALS,
    STUDENT_SECTIONS,
    ProfileAutofillDetector,
    ProjectDescriptionGenerator,
    AchievementDescriptionGenerator,
    ResumeProfileAnalyzer,
    ResumeSuggestionService,
    ResumeSummaryGenerator,
    ResumeFullGenerator,
    ResumeV2Metrics,
    add_skills_to_resume,
    add_resume_education_entry,
    build_resume_sections_snapshot,
    resume_goal_label,
    apply_template_to_resume,
    apply_theme_prefs_to_resume,
    apply_ai_generated_resume,
    build_ai_resume_comparison,
    clear_ai_resume_pending,
    get_ai_resume_pending,
    delete_resume_education_entry,
    is_profile_education_entry,
    update_resume_education_entry,
    validate_education_entry_payload,
    filter_missing_keywords,
    get_v2_meta,
    resume_card_context,
    resume_photo_url,
    resume_has_own_photo,
    user_avatar_initial,
    user_has_profile_photo,
    save_v2_meta,
    save_resume_hobbies,
    save_resume_languages,
    resolve_resume_template,
    studio_ui_state,
    studio_personal_context,
    sync_studio_proto_resume_from_db,
    sync_v2_recommended_sections,
    template_by_id,
    v2_templates_catalog,
)
from .resume_profile_store import (
    apply_profile_autofill,
    bootstrap_user_resume_from_profile,
)
from .resume_profile_sync import (
    apply_profile_sync_offer,
    offer_activity_profile_sync,
    offer_certificate_profile_sync,
    offer_education_profile_sync,
    offer_headline_profile_sync,
    offer_personal_profile_sync,
    offer_skills_profile_sync,
    offer_summary_profile_sync,
)
from .views import (
    RESUME_TITLE_MAX_LEN,
    _hub_nav_counts,
    _validate_new_resume_title,
)


def _v2_breadcrumb(extra=None):
    items = [
        {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
        {"title": "Resume Builder", "text": "Resume Builder", "url": reverse_lazy("users:resume_v2_dashboard")},
    ]
    if extra:
        items.extend(extra)
    return get_breadcrumb(items)


def _base_ctx(request, resume=None):
    UserProfile.objects.get_or_create(user=request.user)
    ctx = {
        "profile_user": request.user,
        "html_head": build_html_head(title="Resume Builder", description="AI-powered resume builder"),
    }
    ctx.update(_hub_nav_counts(request.user))
    if resume:
        ctx["resume"] = resume
    return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2DashboardView(TemplateView):
    template_name = "template20/user/resume_v2_dashboard.html"

    def get_context_data(self, **kwargs):
        request = self.request
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(request))
        ctx["breadcrumb"] = _v2_breadcrumb([{"title": "Dashboard", "text": "Dashboard", "url": ""}])

        user = request.user
        # Prefetch children once — resume_card_context / metrics otherwise N+1 per section.
        resumes = list(
            UserResume.objects.filter(user=user)
            .select_related("user", "user__user_profile")
            .prefetch_related(
                "userresumeskill_set",
                "userresumecertificate_set",
                "userresumeactivity_set",
                "userresumeinternship_set",
                "userresumevolunteerinvolvement_set",
                "user__user_profile__hobbies",
            )
            .order_by("-modified")
        )
        profile_pct = user.get_profile_completion_percentage()
        autofill = ProfileAutofillDetector.detect(user)
        suggestions = ResumeSuggestionService.suggestions(user, resumes[0] if resumes else None)
        analysis = ResumeProfileAnalyzer.analyze(user)

        resume_cards = [resume_card_context(r, request) for r in resumes]

        from core.ai_feature_quota import FEATURE_RESUME_CREATE, feature_status, shop_url

        create_status = feature_status(user, FEATURE_RESUME_CREATE, request=request)
        ctx.update(
            {
                "profile_completion": profile_pct,
                "profile_missing": autofill["missing"],
                "ai_suggestions": suggestions,
                "profile_analysis": analysis,
                "resume_cards": resume_cards,
                "resume_count": len(resumes),
                "latest_resume": resumes[0] if resumes else None,
                "existing_resume_titles": [(r.title or "").strip() for r in resumes if (r.title or "").strip()],
                "resume_create_locked": bool(create_status.get("locked")),
                "resume_create_remaining": create_status.get("remaining"),
                "ai_quota_shop_url": shop_url(),
                "ai_quota_recharge_message": "AI tokens need to recharge — Buy now.",
            }
        )
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2CreateView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        title = (request.POST.get("title") or "").strip()[:RESUME_TITLE_MAX_LEN]
        title_error = _validate_new_resume_title(request.user, title)
        if title_error:
            messages.error(request, title_error)
            return redirect("users:resume_v2_dashboard")
        from core.ai_feature_quota import (
            FEATURE_RESUME_CREATE,
            AIFeatureQuotaExceeded,
            consume_feature,
            ensure_can_use_feature,
            shop_url,
        )

        try:
            ensure_can_use_feature(request.user, FEATURE_RESUME_CREATE, request=request)
        except AIFeatureQuotaExceeded:
            messages.error(
                request,
                "AI tokens need to recharge — Buy now.",
            )
            return redirect(shop_url())
        resume = UserResume.objects.create(user=request.user, title=title)
        try:
            consume_feature(request.user, FEATURE_RESUME_CREATE, request=request)
        except Exception:
            pass
        bootstrap_user_resume_from_profile(request.user, resume)
        messages.success(request, "Resume created. Choose your goal to continue.")
        return redirect("users:resume_v2_goal", resume_id=resume.pk)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2GoalView(TemplateView):
    template_name = "template20/user/resume_v2_goal.html"

    def get_context_data(self, resume_id, **kwargs):
        request = self.request
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(request, resume))
        ctx["breadcrumb"] = _v2_breadcrumb(
            [{"title": resume.title or "Resume", "text": resume.title or "Resume", "url": ""}]
        )
        analysis = ResumeProfileAnalyzer.analyze(request.user, resume)
        meta = get_v2_meta(resume)
        ctx.update(
            {
                "resume_goals": RESUME_GOALS,
                "profile_analysis": analysis,
                "selected_goal": meta.get("goal") or "",
            }
        )
        return ctx

    def post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        goal = (request.POST.get("goal") or "").strip()
        use_recommended = request.POST.get("use_recommended") == "1"
        analysis = ResumeProfileAnalyzer.analyze(request.user, resume)

        patch = {"goal": goal, "profile_type": analysis["type"]}
        if use_recommended:
            patch["recommended_template"] = analysis["recommended_template"]
            patch["recommended_sections"] = analysis["recommended_sections"]
        save_v2_meta(resume, patch)
        return redirect("users:resume_v2_templates", resume_id=resume.pk)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2TemplatesView(TemplateView):
    template_name = "template20/user/resume_v2_templates.html"

    def get_context_data(self, resume_id, **kwargs):
        request = self.request
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(request, resume))
        ctx["breadcrumb"] = _v2_breadcrumb(
            [{"title": "Templates", "text": "Templates", "url": ""}]
        )
        meta = get_v2_meta(resume)
        analysis = ResumeProfileAnalyzer.analyze(request.user, resume)
        catalog = v2_templates_catalog()
        recommended_tpl = template_by_id(
            meta.get("recommended_template") or analysis["recommended_template"]
        ) or template_by_id("minimalist")
        selected_tpl = resolve_resume_template(meta, recommended_tpl["id"])
        ctx.update(
            {
                "templates": catalog,
                "recommended_id": recommended_tpl["id"],
                "selected_template": selected_tpl["id"],
                "goal": meta.get("goal") or "",
            }
        )
        return ctx

    def post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        template_id = (request.POST.get("template_id") or "").strip()
        tpl = template_by_id(template_id)
        if not tpl:
            messages.error(request, "Please select a valid template.")
            return redirect("users:resume_v2_templates", resume_id=resume.pk)
        save_v2_meta(
            resume,
            {
                "template_id": tpl["id"],
                "prototype_key": tpl["prototype_key"],
            },
        )
        return redirect("users:resume_v2_studio", resume_id=resume.pk)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2StudioView(TemplateView):
    template_name = "template20/user/resume_v2_studio.html"

    def get_context_data(self, resume_id, **kwargs):
        request = self.request
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        bootstrap_user_resume_from_profile(request.user, resume, request)
        resume.refresh_from_db()
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(request, resume))
        ctx["breadcrumb"] = _v2_breadcrumb(
            [{"title": "Studio", "text": "Studio", "url": ""}]
        )

        meta = get_v2_meta(resume)
        analysis = ResumeProfileAnalyzer.analyze(request.user, resume)
        sections_list = sync_v2_recommended_sections(resume, request.user)

        metrics = ResumeV2Metrics.section_completion(resume, sections_list)
        strength = ResumeV2Metrics.resume_strength(resume, request)
        autofill = ProfileAutofillDetector.detect(request.user, resume)
        suggestions = ResumeSuggestionService.suggestions(request.user, resume, sections_list)
        missing_keywords = filter_missing_keywords(strength, resume)
        payload = resume_studio_prototype_payload(resume, request)

        tpl = resolve_resume_template(meta, analysis.get("recommended_template") or "classic-sidebar")
        prototype_key = tpl["prototype_key"]
        catalog = v2_templates_catalog()
        studio_prefs = studio_prefs_from_resume_record(resume)
        profile = UserProfile.objects.filter(user=request.user).first()
        profile_hobbies = (
            [h.name for h in profile.hobbies.all() if getattr(h, "name", None)] if profile else []
        )
        studio_hobbies = (payload.get("hobbies") or "").strip()
        if not studio_hobbies:
            studio_hobbies = (payload.get("interests") or "").strip()
        if not studio_hobbies and profile_hobbies:
            studio_hobbies = ", ".join(profile_hobbies[:15])
        goal_id = meta.get("goal") or ""

        ctx.update(
            {
                "sections_list": sections_list,
                "section_metrics": metrics["sections"],
                "overall_completion": metrics["overall"],
                "strength": strength,
                "autofill": autofill,
                "ai_suggestions": suggestions,
                "profile_analysis": analysis,
                "resume_payload_json": json.dumps(payload, ensure_ascii=False, default=str),
                "prototype_payload": payload,
                "v2_meta_json": json.dumps(meta, ensure_ascii=False, default=str),
                "prototype_key": prototype_key,
                "template_id": tpl["id"],
                "goal": goal_id,
                "goal_label": resume_goal_label(goal_id),
                "studio_theme_colors": STUDIO_THEME_COLORS,
                "studio_theme_fonts": STUDIO_FONT_FAMILIES,
                "studio_theme_color": (studio_prefs.get("color") or "teal"),
                "studio_theme_font_size": (studio_prefs.get("fontSize") or "standard"),
                "studio_theme_font_id": studio_font_id_from_stack(studio_prefs.get("font")),
                "preview_embed_url": reverse(
                    "users:resumebuilder_templates_embed", kwargs={"resume_id": resume.pk}
                )
                + "?mode=preview&template="
                + prototype_key,
                "pdf_url": reverse("users:resumepdf") + f"?resume_id={resume.pk}&inline=1",
                "editor_payload": resume_editor_payload(resume),
                "v2_templates": catalog,
                "template_count": len(catalog),
                "selected_template_id": tpl["id"],
                "resume_photo_url": resume_photo_url(request, resume, request.user),
                "resume_has_own_photo": resume_has_own_photo(resume),
                "has_profile_photo": user_has_profile_photo(request.user),
                "avatar_initial": user_avatar_initial(request.user),
                "missing_keywords": missing_keywords,
                "photo_upload_url": reverse(
                    "users:resumebuilder_studio_photo_upload", kwargs={"resume_id": resume.pk}
                ),
                "resume_headline": payload.get("headline") or "",
                "studio_hobbies": studio_hobbies,
                "personal_fields": studio_personal_context(request.user, resume),
                "profile_hobbies": profile_hobbies,
                "has_ai_pending": get_ai_resume_pending(resume) is not None,
            }
        )
        from core.ai_feature_quota import (
            FEATURE_RESUME_AI,
            feature_status,
            quota_applies,
            shop_url,
        )
        from core.llm_quota import get_balance

        ai_status = feature_status(request.user, FEATURE_RESUME_AI, request=request)
        try:
            token_balance = int(get_balance(request.user, request=request) or 0)
        except Exception:
            token_balance = 0
        ctx.update(
            {
                "resume_ai_locked": bool(ai_status.get("locked")),
                "resume_ai_remaining": ai_status.get("remaining"),
                "resume_ai_unlimited": bool(ai_status.get("unlimited")),
                "resume_ai_quota_applies": quota_applies(request.user),
                "ai_token_balance": token_balance,
                "ai_quota_shop_url": shop_url(),
                "ai_quota_status_url": reverse("core:ai_feature_quota_status"),
                "ai_quota_recharge_message": "AI tokens need to recharge — Buy now.",
            }
        )
        return ctx


def _json_studio_response(request, resume, extra=None):
    """Merge mutation result with fresh UI state for the studio."""
    sections_list = sync_v2_recommended_sections(resume, request.user)
    state = studio_ui_state(request.user, resume, request, sections_list)
    out = {"success": True, **state}
    if extra:
        out.update(extra)
    return JsonResponse(out)


def _mutate_studio(request, resume, extra=None):
    sync_studio_proto_resume_from_db(resume, request)
    return _json_studio_response(request, resume, extra)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2AutofillView(View):
    http_method_names = ["post"]

    def post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        result = apply_profile_autofill(request.user, resume)
        return JsonResponse(result)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2AIView(View):
    http_method_names = ["post"]

    def post(self, request, resume_id, *args, **kwargs):
        from core.ai_feature_quota import AIFeatureQuotaExceeded, feature_quota_error_response
        from core.llm_quota import LLMQuotaExceeded, quota_error_response

        try:
            return self._handle_ai_post(request, resume_id, *args, **kwargs)
        except AIFeatureQuotaExceeded as exc:
            return feature_quota_error_response(exc)
        except LLMQuotaExceeded as exc:
            return quota_error_response(exc)

    def _handle_ai_post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        action = (body.get("action") or "").strip()
        if action == "sync_to_profile":
            offer = body.get("offer")
            if not isinstance(offer, dict) or not offer.get("kind"):
                return JsonResponse({"error": "Invalid profile sync request"}, status=400)
            apply_profile_sync_offer(request.user, offer)
            return _mutate_studio(request, resume, {"profile_synced": True})
        if action == "generate_summary":
            text = ResumeSummaryGenerator.generate(
                request.user, resume, career_goal=body.get("career_goal") or get_v2_meta(resume).get("goal", "")
            )
            return JsonResponse({"text": text})
        if action == "improve_summary":
            text = ResumeSummaryGenerator.improve(
                request.user,
                resume,
                body.get("text") or resume.about or "",
                body.get("mode") or "professional",
            )
            return JsonResponse({"text": text})
        if action == "improve_achievement":
            text = AchievementDescriptionGenerator.improve(
                request.user,
                resume,
                body.get("title") or "",
                body.get("text") or "",
                body.get("mode") or "professional",
            )
            return JsonResponse({"text": text})
        if action == "generate_achievement":
            text = AchievementDescriptionGenerator.generate(
                request.user,
                resume,
                body.get("title") or "",
            )
            return JsonResponse({"text": text})
        if action == "generate_project":
            bullets = ProjectDescriptionGenerator.generate(
                request.user,
                resume,
                body.get("title") or "",
                body.get("technologies") or "",
            )
            return JsonResponse({"bullets": bullets})
        if action == "add_certificate":
            title = (body.get("title") or "").strip()[:250]
            if not title:
                return JsonResponse({"error": "Certificate name is required"}, status=400)
            desc = (body.get("description") or "").strip()[:2000]
            if not desc:
                return JsonResponse({"error": "Who gave it is required"}, status=400)
            UserResumeCertificate.objects.create(
                resume=resume,
                title=title,
                description=desc,
                issue_date=body.get("issue_date") or None,
            )
            offer = offer_certificate_profile_sync(request.user, title, desc)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "update_certificate":
            item_id = body.get("item_id")
            title = (body.get("title") or "").strip()[:250]
            desc = (body.get("description") or "").strip()[:2000]
            if not item_id:
                return JsonResponse({"error": "Certificate not found"}, status=400)
            if not title:
                return JsonResponse({"error": "Certificate name is required"}, status=400)
            if not desc:
                return JsonResponse({"error": "Who gave it is required"}, status=400)
            cert = UserResumeCertificate.objects.filter(pk=int(item_id), resume=resume).first()
            if not cert:
                return JsonResponse({"error": "Certificate not found"}, status=404)
            cert.title = title
            cert.description = desc
            cert.issue_date = body.get("issue_date") or None
            cert.save(update_fields=["title", "description", "issue_date", "modified"])
            offer = offer_certificate_profile_sync(request.user, title, desc)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "add_education":
            school = (body.get("school") or "").strip()[:250]
            grade = (body.get("grade") or "").strip()[:100]
            if not school:
                return JsonResponse({"error": "School name is required"}, status=400)
            if not grade:
                return JsonResponse({"error": "Class or grade is required"}, status=400)
            edu_err = validate_education_entry_payload(
                resume,
                request.user,
                school=school,
                grade=grade,
                passing_year=(body.get("passing_year") or "").strip(),
                result_type=(body.get("result_type") or "").strip(),
                result_value=(body.get("result_value") or "").strip(),
            )
            if edu_err:
                return JsonResponse({"error": edu_err}, status=400)
            add_resume_education_entry(
                resume,
                request.user,
                school=school,
                grade=grade,
                dates=(body.get("dates") or "").strip(),
                detail=(body.get("detail") or "").strip(),
                passing_year=(body.get("passing_year") or "").strip(),
                result_type=(body.get("result_type") or "").strip(),
                result_value=(body.get("result_value") or "").strip(),
            )
            return _mutate_studio(request, resume)
        if action == "update_education":
            entry_id = (body.get("entry_id") or body.get("item_id") or "").strip()
            school = (body.get("school") or "").strip()[:250]
            grade = (body.get("grade") or "").strip()[:100]
            if not entry_id:
                return JsonResponse({"error": "Education entry not found"}, status=400)
            if not school:
                return JsonResponse({"error": "School name is required"}, status=400)
            if not grade:
                return JsonResponse({"error": "Class or grade is required"}, status=400)
            edu_err = validate_education_entry_payload(
                resume,
                request.user,
                school=school,
                grade=grade,
                passing_year=(body.get("passing_year") or "").strip(),
                result_type=(body.get("result_type") or "").strip(),
                result_value=(body.get("result_value") or "").strip(),
                entry_id=entry_id,
            )
            if edu_err:
                return JsonResponse({"error": edu_err}, status=400)
            updated = update_resume_education_entry(
                resume,
                request.user,
                entry_id,
                school=school,
                grade=grade,
                dates=(body.get("dates") or "").strip(),
                detail=(body.get("detail") or "").strip(),
                passing_year=(body.get("passing_year") or "").strip(),
                result_type=(body.get("result_type") or "").strip(),
                result_value=(body.get("result_value") or "").strip(),
            )
            if updated is None:
                return JsonResponse({"error": "Education entry not found"}, status=404)
            offer = None
            if is_profile_education_entry(resume, request.user, entry_id):
                offer = offer_education_profile_sync(
                    request.user, school=school, grade=grade
                )
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "save_summary":
            summary = (body.get("text") or "").strip()[:5000]
            resume.about = summary
            resume.save(update_fields=["about", "modified"])
            offer = offer_summary_profile_sync(request.user, summary)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "save_headline":
            headline = (body.get("headline") or "").strip()[:200]
            save_v2_meta(resume, {"headline": headline})
            offer = offer_headline_profile_sync(request.user, headline)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "save_personal":
            personal_ctx = studio_personal_context(request.user, resume)
            headline = (body.get("headline") or "").strip()[:200]
            meta = get_v2_meta(resume)
            personal_patch = dict(meta.get("personal") or {})
            sync_kwargs: dict = {}

            if personal_ctx.get("can_edit_name"):
                sync_kwargs["name"] = (body.get("name") or "").strip()[:250]
            if personal_ctx.get("can_edit_phone"):
                sync_kwargs["phone"] = (body.get("phone") or "").strip()[:25]
            if personal_ctx.get("can_edit_school"):
                sync_kwargs["school"] = (body.get("school") or "").strip()[:250]
            if personal_ctx.get("can_edit_grade"):
                sync_kwargs["grade"] = (body.get("grade") or "").strip()[:100]

            if sync_kwargs:
                for key, val in sync_kwargs.items():
                    if val:
                        personal_patch[key] = val

            offer = offer_personal_profile_sync(request.user, resume, body)
            save_v2_meta(
                resume,
                {
                    "headline": headline,
                    "personal": personal_patch,
                },
            )
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "add_skill":
            title = (body.get("title") or "").strip()
            add_skills_to_resume(resume, title)
            offer = offer_skills_profile_sync(request.user, title)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "add_activity":
            title = (body.get("title") or "").strip()[:250]
            desc = (body.get("description") or "").strip()[:2000]
            if not title:
                return JsonResponse({"error": "Title is required"}, status=400)
            if not desc:
                return JsonResponse({"error": "Description is required"}, status=400)
            UserResumeActivity.objects.create(resume=resume, title=title, description=desc)
            offer = offer_activity_profile_sync(request.user, title, desc)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "update_activity":
            item_id = body.get("item_id")
            title = (body.get("title") or "").strip()[:250]
            desc = (body.get("description") or "").strip()[:2000]
            if not item_id:
                return JsonResponse({"error": "Project not found"}, status=400)
            if not title:
                return JsonResponse({"error": "Title is required"}, status=400)
            if not desc:
                return JsonResponse({"error": "Description is required"}, status=400)
            updated = UserResumeActivity.objects.filter(
                pk=int(item_id), resume=resume
            ).update(title=title, description=desc)
            if not updated:
                return JsonResponse({"error": "Project not found"}, status=404)
            offer = offer_activity_profile_sync(request.user, title, desc)
            return _mutate_studio(
                request, resume, {"profile_sync_offer": offer} if offer else None
            )
        if action == "add_internship":
            role = (body.get("role") or "").strip()[:250]
            provider = (body.get("provider") or "").strip()[:250]
            description = (body.get("description") or "").strip()[:2000]
            start_date = body.get("start_date") or None
            end_date = body.get("end_date") or None
            if not role:
                return JsonResponse({"error": "Role is required"}, status=400)
            if not provider:
                return JsonResponse({"error": "Company or place is required"}, status=400)
            if not description:
                return JsonResponse({"error": "Description is required"}, status=400)
            if not start_date:
                return JsonResponse({"error": "Start date is required"}, status=400)
            if start_date and end_date and str(end_date) < str(start_date):
                return JsonResponse({"error": "End date must be after start date"}, status=400)
            UserResumeInternship.objects.create(
                resume=resume,
                role=role,
                provider=provider,
                description=description,
                start_date=start_date,
                end_date=end_date,
            )
            return _mutate_studio(request, resume)
        if action == "delete_item":
            item_type = (body.get("item_type") or "").strip()
            item_id = body.get("item_id")
            if item_type == "education" and item_id:
                _, err = delete_resume_education_entry(
                    resume, request.user, str(item_id)
                )
                if err:
                    return JsonResponse({"error": err}, status=400)
                return _mutate_studio(request, resume)
            model_map = {
                "skill": UserResumeSkill,
                "certificate": UserResumeCertificate,
                "activity": UserResumeActivity,
                "internship": UserResumeInternship,
            }
            model = model_map.get(item_type)
            if model and item_id:
                model.objects.filter(pk=int(item_id), resume=resume).delete()
            return _mutate_studio(request, resume)
        if action == "generate_resume":
            goal = (body.get("career_goal") or get_v2_meta(resume).get("goal") or "").strip()
            client_sections = body.get("sections") if isinstance(body.get("sections"), dict) else {}
            snapshot = build_resume_sections_snapshot(resume, request.user, client_sections)
            applied, generated, comparison, used_ai, err = ResumeFullGenerator.generate(
                request.user, resume, snapshot, career_goal=goal, apply=False
            )
            if err:
                return JsonResponse(
                    {"error": friendly_openai_error(err)},
                    status=400 if used_ai is False else 502,
                )
            review_url = reverse("users:resume_v2_ai_review", kwargs={"resume_id": resume.pk})
            return JsonResponse(
                {
                    "success": True,
                    "ai_generated": used_ai,
                    "generated": generated,
                    "original": snapshot,
                    "comparison": comparison,
                    "review_url": review_url,
                    "message": "AI draft ready — review changes in the comparison window.",
                }
            )
        if action == "apply_ai_resume":
            pending = get_ai_resume_pending(resume)
            if not pending:
                return JsonResponse({"error": "No AI draft to apply. Generate again first."}, status=400)
            generated = pending.get("generated")
            if not isinstance(generated, dict):
                return JsonResponse({"error": "Invalid AI draft data."}, status=400)
            sections_raw = body.get("sections")
            sections = None
            if isinstance(sections_raw, list) and sections_raw:
                sections = [str(s).strip() for s in sections_raw if str(s).strip()]
            apply_all = bool(body.get("apply_all"))
            if apply_all:
                sections = None
            elif not sections:
                return JsonResponse({"error": "Select at least one section to apply."}, status=400)
            applied = apply_ai_generated_resume(resume, request.user, generated, sections=sections)
            clear_ai_resume_pending(resume)
            sync_offers = []
            if applied.get("headline"):
                offer = offer_headline_profile_sync(request.user, applied["headline"])
                if offer:
                    sync_offers.append(offer)
            if applied.get("summary"):
                offer = offer_summary_profile_sync(request.user, applied["summary"])
                if offer:
                    sync_offers.append(offer)
            extra = {"applied_fields": applied, "ai_applied": True}
            if sync_offers:
                extra["profile_sync_offers"] = sync_offers
            return _mutate_studio(request, resume, extra)
        if action == "discard_ai_resume":
            clear_ai_resume_pending(resume)
            return JsonResponse({"success": True, "discarded": True})
        if action == "get_ai_pending_review":
            pending = get_ai_resume_pending(resume)
            if not pending:
                return JsonResponse({"has_pending": False})
            original = pending.get("original") or {}
            generated = pending.get("generated") or {}
            comparison = build_ai_resume_comparison(original, generated)
            goal_id = (pending.get("goal") or get_v2_meta(resume).get("goal") or "").strip()
            return JsonResponse(
                {
                    "has_pending": True,
                    "comparison": comparison,
                    "original": original,
                    "generated": generated,
                    "goal_label": resume_goal_label(goal_id),
                }
            )
        if action == "save_languages":
            langs_raw = body.get("languages")
            if not isinstance(langs_raw, list):
                return JsonResponse({"error": "languages must be a list"}, status=400)
            save_resume_languages(resume, langs_raw)
            return _mutate_studio(request, resume)
        if action == "save_hobbies":
            save_resume_hobbies(resume, (body.get("text") or body.get("hobbies") or ""))
            return _mutate_studio(request, resume)
        if action == "select_template":
            template_id = (body.get("template_id") or "").strip()
            if not apply_template_to_resume(resume, template_id, request):
                return JsonResponse({"error": "Invalid template"}, status=400)
            resume.refresh_from_db()
            tpl = template_by_id(template_id)
            return _json_studio_response(
                request,
                resume,
                {
                    "template_id": template_id,
                    "prototype_key": tpl["prototype_key"] if tpl else "",
                },
            )
        if action == "save_theme":
            if not apply_theme_prefs_to_resume(
                resume,
                request,
                color=body.get("color"),
                font_size=body.get("font_size"),
                font_id=body.get("font_id") or body.get("font_family"),
            ):
                return JsonResponse({"error": "Invalid theme options"}, status=400)
            prefs = studio_prefs_from_resume_record(resume)
            return _json_studio_response(
                request,
                resume,
                {
                    "theme_color": prefs.get("color") or "teal",
                    "theme_font_size": prefs.get("fontSize") or "standard",
                    "theme_font_id": studio_font_id_from_stack(prefs.get("font")),
                },
            )
        return JsonResponse({"error": "Unknown action"}, status=400)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2AIReviewView(View):
    """Popup page: section-wise old vs new AI resume comparison before applying."""

    http_method_names = ["get"]
    template_name = "template20/user/resume_v2_ai_review.html"

    def get(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        pending = get_ai_resume_pending(resume)
        if not pending:
            messages.info(request, "No AI draft found. Generate a resume from the studio first.")
            return redirect("users:resume_v2_studio", resume_id=resume.pk)
        original = pending.get("original") or {}
        generated = pending.get("generated") or {}
        comparison = build_ai_resume_comparison(original, generated)
        goal_id = (pending.get("goal") or get_v2_meta(resume).get("goal") or "").strip()
        ctx = {
            "resume": resume,
            "goal_label": resume_goal_label(goal_id),
            "comparison": comparison,
            "original": original,
            "generated": generated,
            "ai_url": reverse("users:resume_v2_ai", kwargs={"resume_id": resume.pk}),
            "studio_url": reverse("users:resume_v2_studio", kwargs={"resume_id": resume.pk}),
        }
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2DeleteView(View):
    """POST: permanently remove one resume and return to the V2 dashboard."""

    http_method_names = ["post"]

    def post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        resume.delete(hard_delete=True)
        messages.success(request, "That resume was deleted.")
        return redirect("users:resume_v2_dashboard")


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeV2AnalyticsPartialView(View):
    """HTMX partial: resume health metrics card."""

    http_method_names = ["get"]

    def get(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        strength = ResumeV2Metrics.resume_strength(resume, request)
        return render(
            request,
            "template20/user/includes/resume_v2_analytics_partial.html",
            {"strength": strength},
        )
