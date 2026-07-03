from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from course_mindmap.admin_mixins import CompleteMindmapDeleteMixin
from course_mindmap.constants import (
    DEBUG_COMMANDS,
    GENERATION_STATUS_GENERATED,
    GENERATION_STATUS_VERIFIED,
    GRADE_MODE_NONE,
    IMPLEMENTATION_STEPS,
)
from course_mindmap.forms import MindmapGenerateForm
from course_mindmap.models import CourseMindmapConfig, CourseMindmapData, CourseMindmapGeneration
from course_mindmap.registry import get_adapter
from course_mindmap.service import generate_mindmaps, verify_generation


def _help_panel_html() -> str:
    steps = "".join(f"<li>{s}</li>" for s in IMPLEMENTATION_STEPS)
    cmds = "".join(
        f'<li><strong>{c["title"]}</strong><pre class="cmm-debug-cmd">{c["command"]}</pre></li>'
        for c in DEBUG_COMMANDS
    )
    return mark_safe(
        f"""
      <button type="button" class="cmm-info-btn" id="cmm-info-toggle"
              title="Show implementation steps and debug commands" aria-expanded="false"
              aria-controls="cmm-help-panel">ℹ</button>
      <div id="cmm-help-panel" class="cmm-help-panel" hidden>
        <h3>Implementation steps</h3>
        <ol>{steps}</ol>
        <h3>Debugging terminal commands</h3>
        <ul class="cmm-debug-list">{cmds}</ul>
        <p class="help">Mindmaps are stored in the database (<code>CourseMindmapData</code>) for fast reads — no static JSON files.</p>
      </div>
      """
    )


@admin.register(CourseMindmapGeneration)
class CourseMindmapGenerationAdmin(CompleteMindmapDeleteMixin, admin.ModelAdmin):
    change_list_template = "admin/course_mindmap/generation_changelist.html"
    list_display = [
        "id",
        "course_display",
        "course_type_key",
        "status_badge",
        "dry_run",
        "scope_summary",
        "created",
        "preview_link",
    ]
    list_filter = ["status", "dry_run", "course_type_key"]
    search_fields = ["object_id", "course_type_key"]
    readonly_fields = [
        "course_type_key",
        "content_type",
        "object_id",
        "status",
        "dry_run",
        "map_type",
        "scope_count",
        "report_display",
        "error_message",
        "generated_by",
        "created",
        "modified",
    ]
    ordering = ("-created",)
    actions = ["delete_dry_run_generations", "delete_complete_course_mindmap"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        """Generations are audit logs — view via Preview only, not editable."""
        return False

    @admin.action(description="Delete selected dry-run entries (audit log only)")
    def delete_dry_run_generations(self, request, queryset):
        dry = queryset.filter(dry_run=True)
        count = dry.count()
        for obj in dry:
            obj.delete(hard_delete=True)
        self.message_user(
            request,
            f"Deleted {count} dry-run generation log(s). Live mindmap data (Run) was not affected.",
            messages.SUCCESS,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_view),
                name="course_mindmap_generate",
            ),
            path(
                "courses-by-type/",
                self.admin_site.admin_view(self.courses_by_type_ajax),
                name="course_mindmap_courses_by_type",
            ),
            path(
                "<int:generation_id>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="course_mindmap_preview",
            ),
            path(
                "<int:generation_id>/verify/",
                self.admin_site.admin_view(self.verify_view),
                name="course_mindmap_verify",
            ),
            path(
                "data/<int:data_id>/json/",
                self.admin_site.admin_view(self.data_json_proxy),
                name="course_mindmap_data_json",
            ),
            path(
                "<int:generation_id>/scope-json/",
                self.admin_site.admin_view(self.generation_scope_json_proxy),
                name="course_mindmap_generation_scope_json",
            ),
            path(
                "<int:generation_id>/scope-frame/",
                self.admin_site.admin_view(self.scope_frame_proxy),
                name="course_mindmap_scope_frame",
            ),
        ]
        return custom + urls

    def scope_frame_proxy(self, request, generation_id):
        from course_mindmap.views import scope_preview_frame_view

        return scope_preview_frame_view(request, generation_id)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["help_panel"] = _help_panel_html()
        return super().changelist_view(request, extra_context=extra_context)

    def data_json_proxy(self, request, data_id):
        from course_mindmap.views import mindmap_data_json_view

        return mindmap_data_json_view(request, data_id)

    def generation_scope_json_proxy(self, request, generation_id):
        from course_mindmap.views import generation_scope_json_view

        return generation_scope_json_view(request, generation_id)

    def courses_by_type_ajax(self, request):
        key = request.GET.get("course_type_key", "")
        if not key:
            return JsonResponse({"courses": []})
        try:
            adapter = get_adapter(key)
            courses = [
                {"id": c.pk, "name": adapter.get_course_display_name(c)}
                for c in adapter.get_course_queryset()[:500]
            ]
            return JsonResponse({"courses": courses})
        except Exception as exc:
            return JsonResponse({"courses": [], "error": str(exc)}, status=400)

    def generate_view(self, request):
        initial_type = request.GET.get("course_type_key") or request.POST.get("course_type_key")
        form = MindmapGenerateForm(
            request.POST or None,
            initial_course_type_key=initial_type,
        )
        if request.method == "GET" and not request.POST:
            course_id = request.GET.get("course_id")
            if course_id and initial_type:
                form.fields["course_id"].initial = course_id
        if request.method == "POST" and form.is_valid():
            course_type_key = form.cleaned_data["course_type_key"]
            course_id = int(form.cleaned_data["course_id"])
            map_type = form.cleaned_data.get("map_type") or ""
            action = request.POST.get("action", "dry_run")
            dry_run = action != "run"
            gen = generate_mindmaps(
                course_type_key=course_type_key,
                course_id=course_id,
                dry_run=dry_run,
                map_type=map_type,
                user=request.user,
            )
            if gen.status == "failed":
                messages.error(request, gen.error_message or "Generation failed.")
            elif dry_run:
                messages.success(
                    request,
                    f"Dry run complete — {gen.scope_count} scope(s). Review the preview before Run.",
                )
            else:
                messages.success(
                    request,
                    f"Saved {gen.scope_count} mindmap row(s) to the database.",
                )
            return redirect(
                reverse("admin:course_mindmap_preview", args=[gen.pk])
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Generate course mindmap",
            "form": form,
            "help_panel": _help_panel_html(),
            "opts": self.model._meta,
        }
        return render(request, "admin/course_mindmap/generate.html", context)

    def preview_view(self, request, generation_id):
        gen = get_object_or_404(CourseMindmapGeneration, pk=generation_id)
        report = gen.report or {}
        scopes = report.get("scopes") or []
        config = CourseMindmapConfig.objects.filter(
            content_type=gen.content_type,
            object_id=gen.object_id,
        ).first()

        preview_items = []
        db_rows = {
            (r.scope, r.scope_id): r
            for r in CourseMindmapData.objects.filter(
                content_type=gen.content_type,
                object_id=gen.object_id,
                is_valid=True,
            )
        }
        for item in scopes:
            scope = item.get("scope")
            scope_id = item.get("scope_id")
            if scope_id is None:
                scope_id = 0
            db_row = db_rows.get((scope, scope_id))
            if not db_row and scope == "course":
                db_row = db_rows.get((scope, 0))
            if db_row:
                json_url = reverse("admin:course_mindmap_data_json", args=[db_row.pk])
            else:
                q = f"scope={scope}"
                if scope_id is not None:
                    q += f"&scope_id={scope_id}"
                json_url = (
                    reverse("admin:course_mindmap_generation_scope_json", args=[gen.pk])
                    + "?"
                    + q
                )
            preview_items.append(
                {
                    "scope": scope,
                    "scope_id": scope_id,
                    "label": item.get("label") or scope,
                    "is_valid": item.get("is_valid", False),
                    "error": item.get("error", ""),
                    "json_url": json_url,
                    "widget_id": f"{scope}-{scope_id or 'root'}",
                }
            )

        can_verify = (
            not gen.dry_run
            and gen.status == GENERATION_STATUS_GENERATED
            and report.get("valid_total", 0) > 0
        )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Mindmap preview — {report.get('course_name', gen.object_id)}",
            "generation": gen,
            "report": report,
            "preview_items": preview_items,
            "config": config,
            "can_verify": can_verify,
            "help_panel": _help_panel_html(),
            "opts": self.model._meta,
            "map_type": gen.map_type,
        }
        return render(request, "admin/course_mindmap/preview.html", context)

    def verify_view(self, request, generation_id):
        gen = get_object_or_404(CourseMindmapGeneration, pk=generation_id)
        if gen.dry_run:
            messages.error(request, "Cannot verify a dry run. Use Run first.")
            return redirect(reverse("admin:course_mindmap_preview", args=[gen.pk]))
        verify_generation(gen, user=request.user)
        messages.success(request, "Mindmap verified. Configuration is now unlocked.")
        config = CourseMindmapConfig.objects.filter(
            content_type=gen.content_type,
            object_id=gen.object_id,
        ).first()
        if config:
            return redirect(
                reverse("admin:course_mindmap_coursemindmapconfig_change", args=[config.pk])
            )
        return redirect(reverse("admin:course_mindmap_coursemindmapgeneration_changelist"))

    @admin.display(description="Course")
    def course_display(self, obj):
        try:
            adapter = get_adapter(obj.course_type_key)
            course = adapter.get_course_by_id(obj.object_id)
            if course:
                return adapter.get_course_display_name(course)
        except Exception:
            pass
        return f"#{obj.object_id}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "dry_run": "#6c757d",
            "generated": "#0d6efd",
            "verified": "#198754",
            "failed": "#dc3545",
        }
        c = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            c,
            obj.get_status_display(),
        )

    @admin.display(description="Scopes")
    def scope_summary(self, obj):
        counts = (obj.report or {}).get("counts") or {}
        if not counts:
            return obj.scope_count or "—"
        return format_html(
            "C:{} · Ch:{} · S:{}",
            counts.get("course", 0),
            counts.get("chapter", 0),
            counts.get("section", 0),
        )

    @admin.display(description="Preview")
    def preview_link(self, obj):
        url = reverse("admin:course_mindmap_preview", args=[obj.pk])
        return format_html('<a href="{}">Preview</a>', url)

    @admin.display(description="Report")
    def report_display(self, obj):
        import json

        return format_html(
            "<pre style='max-height:400px;overflow:auto'>{}</pre>",
            json.dumps(obj.report, indent=2)[:8000],
        )


class CourseMindmapConfigAdminForm(forms.ModelForm):
    class Meta:
        model = CourseMindmapConfig
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.instance.is_verified:
            for field in (
                "enable_title_mindmap",
                "enable_sidebar_mindmap",
                "enable_content_area_mindmap",
            ):
                if cleaned.get(field):
                    raise ValidationError(
                        "Enable placement toggles only after mindmap is verified. "
                        "Open the generation preview and click Mark as verified."
                    )
        any_enabled = any(
            cleaned.get(f)
            for f in (
                "enable_title_mindmap",
                "enable_sidebar_mindmap",
                "enable_content_area_mindmap",
            )
        )
        if any_enabled and cleaned.get("grade_mode") == GRADE_MODE_NONE:
            raise ValidationError(
                "Set grade mode to All or Selected classes when enabling mindmap placements."
            )
        return cleaned


@admin.register(CourseMindmapConfig)
class CourseMindmapConfigAdmin(CompleteMindmapDeleteMixin, admin.ModelAdmin):
    form = CourseMindmapConfigAdminForm
    change_form_template = "admin/course_mindmap/config_change_form.html"
    list_display = [
        "id",
        "course_display",
        "course_type_key",
        "verified_badge",
        "placements_summary",
        "grade_mode",
        "modified",
    ]
    list_filter = ["is_verified", "course_type_key", "grade_mode"]
    filter_horizontal = ["grades"]
    actions = ["delete_complete_course_mindmap"]
    readonly_fields = [
        "course_type_key",
        "content_type",
        "object_id",
        "is_verified",
        "verified_at",
        "verified_by",
        "last_generation",
        "created",
        "modified",
        "manage_generation_link",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "course_type_key",
                    "content_type",
                    "object_id",
                    "manage_generation_link",
                    "is_verified",
                    "verified_at",
                    "verified_by",
                    "last_generation",
                )
            },
        ),
        (
            "Mindmap placements (unlocked after verify)",
            {
                "fields": (
                    "enable_title_mindmap",
                    "enable_sidebar_mindmap",
                    "enable_content_area_mindmap",
                    "map_type",
                ),
            },
        ),
        (
            "Class visibility",
            {
                "fields": ("grade_mode", "grades"),
                "description": "Reuse SkillLab course grades (Class 6th–12th). Default: none — hidden for all.",
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and not obj.is_verified:
            ro.extend(
                [
                    "enable_title_mindmap",
                    "enable_sidebar_mindmap",
                    "enable_content_area_mindmap",
                    "grade_mode",
                    "grades",
                    "map_type",
                ]
            )
        return ro

    @admin.display(description="Course")
    def course_display(self, obj):
        try:
            adapter = get_adapter(obj.course_type_key)
            course = adapter.get_course_by_id(obj.object_id)
            if course:
                return adapter.get_course_display_name(course)
        except Exception:
            pass
        return f"#{obj.object_id}"

    @admin.display(description="Verified")
    def verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color:#198754;">✓ Verified</span>')
        return format_html('<span style="color:#6c757d;">Locked</span>')

    @admin.display(description="Placements")
    def placements_summary(self, obj):
        parts = []
        if obj.enable_title_mindmap:
            parts.append("Title")
        if obj.enable_sidebar_mindmap:
            parts.append("Sidebar")
        if obj.enable_content_area_mindmap:
            parts.append("Content")
        return ", ".join(parts) if parts else "—"

    @admin.display(description="Generate / preview")
    def manage_generation_link(self, obj):
        if not obj.pk:
            return "—"
        url = (
            reverse("admin:course_mindmap_generate")
            + f"?course_type_key={obj.course_type_key}&course_id={obj.object_id}"
        )
        return format_html('<a href="{}">Open mindmap generator</a>', url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["help_panel"] = _help_panel_html()
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(CourseMindmapData)
class CourseMindmapDataAdmin(CompleteMindmapDeleteMixin, admin.ModelAdmin):
    list_display = ["id", "course_type_key", "object_id", "scope", "scope_id", "label", "is_valid", "modified"]
    list_filter = ["course_type_key", "scope", "is_valid"]
    search_fields = ["label", "object_id"]
    readonly_fields = ["payload_preview", "generation", "created", "modified"]
    actions = ["delete_complete_course_mindmap"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Payload")
    def payload_preview(self, obj):
        import json

        return format_html(
            "<pre style='max-height:300px;overflow:auto'>{}</pre>",
            json.dumps(obj.payload, indent=2)[:6000],
        )
