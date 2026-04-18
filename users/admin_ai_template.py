"""Admin-only AI resume PDF shell generator (ResumePdfTemplate)."""
from django.contrib import messages
from django.contrib.admin.sites import site
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from users.resume_template_ai import generate_and_create_resumepdf_template_from_post


def ai_resume_template_generator(request: HttpRequest) -> HttpResponse:
    """Wrapped with admin_site.admin_view in ModelAdmin.get_urls (staff-only)."""
    if request.method == "POST":
        tpl, err = generate_and_create_resumepdf_template_from_post(
            request,
            created_by=None,
            is_active=(request.POST.get("activate") or "").strip() == "1",
            sort_order=430,
            description="AI-generated shell from admin generator.",
            slug_prefix="admin",
        )
        if err:
            messages.error(request, err)
            return redirect(request.path)
        messages.success(
            request,
            'Created template "%s" (id=%s). %s'
            % (
                tpl.name,
                tpl.pk,
                "It is active in the library." if tpl.is_active else "Set Active in admin when ready.",
            ),
        )
        return redirect(reverse("admin:users_resumepdftemplate_change", args=(tpl.pk,)))

    ctx = dict(site.each_context(request))
    ctx["title"] = "AI template generator"
    ctx["ai_generator_api_url"] = reverse("admin:users_resumepdftemplate_ai_generator_api")
    return render(request, "admin/users/resumepdftemplate/ai_generator.html", ctx)


def ai_resume_template_generator_api(request: HttpRequest) -> JsonResponse:
    """Staff JSON API: same as form POST; returns preview path for iframe."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    tpl, err = generate_and_create_resumepdf_template_from_post(
        request,
        created_by=None,
        is_active=(request.POST.get("activate") or "").strip() == "1",
        sort_order=430,
        description="AI-generated shell from admin generator.",
        slug_prefix="admin",
    )
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)
    preview_path = reverse("users:admin_resume_pdf_template_preview", kwargs={"template_pk": tpl.pk})
    return JsonResponse(
        {
            "ok": True,
            "template_id": tpl.pk,
            "name": tpl.name,
            "preview_path": preview_path,
            "change_url": reverse("admin:users_resumepdftemplate_change", args=(tpl.pk,)),
        }
    )
