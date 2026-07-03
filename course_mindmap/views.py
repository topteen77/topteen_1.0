from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template import engines
from django.views.decorators.http import require_GET

from course_mindmap.models import CourseMindmapData, CourseMindmapGeneration


@staff_member_required
@require_GET
def mindmap_data_json_view(request, data_id: int):
    """Serve mindmap JSON from DB for admin preview and future frontend."""
    row = get_object_or_404(CourseMindmapData, pk=data_id)
    if not row.is_valid:
        raise Http404("Invalid mindmap data")
    return JsonResponse(row.payload)


@staff_member_required
@require_GET
def generation_scope_json_view(request, generation_id: int):
    """Serve scope JSON from a dry-run generation report (not yet in DB)."""
    gen = get_object_or_404(CourseMindmapGeneration, pk=generation_id)
    scope = request.GET.get("scope", "")
    scope_id_raw = request.GET.get("scope_id", "")
    if scope == "course" and not scope_id_raw:
        scope_id = 0
    elif scope_id_raw.isdigit():
        scope_id = int(scope_id_raw)
    else:
        scope_id = None

    report = gen.report or {}
    for item in report.get("scopes") or []:
        item_sid = item.get("scope_id")
        if item_sid is None and item.get("scope") == "course":
            item_sid = 0
        if item.get("scope") == scope and item_sid == scope_id:
            payload = item.get("payload")
            if payload:
                return JsonResponse(payload)
    raise Http404("Scope not found in generation report")


def _resolve_json_url(request, generation_id: int, scope: str, scope_id) -> str:
    from django.urls import reverse

    gen = get_object_or_404(CourseMindmapGeneration, pk=generation_id)
    db_qs = CourseMindmapData.objects.filter(
        content_type=gen.content_type,
        object_id=gen.object_id,
        scope=scope,
        is_valid=True,
    )
    if scope_id is None or scope_id == "" or scope_id == 0:
        db_row = db_qs.filter(scope_id=0).first()
    else:
        db_row = db_qs.filter(scope_id=int(scope_id)).first()
    if db_row:
        return request.build_absolute_uri(
            reverse("admin:course_mindmap_data_json", args=[db_row.pk])
        )
    q = f"scope={scope}"
    if scope_id is not None and scope_id != "":
        q += f"&scope_id={scope_id}"
    return request.build_absolute_uri(
        reverse("admin:course_mindmap_generation_scope_json", args=[generation_id]) + "?" + q
    )


@staff_member_required
@require_GET
def scope_preview_frame_view(request, generation_id: int):
    """Render Jinja2 mindmap widget in an iframe-friendly page (admin preview)."""
    scope = request.GET.get("scope", "course")
    scope_id_raw = request.GET.get("scope_id", "")
    scope_id = scope_id_raw if scope_id_raw != "" else None
    gen = get_object_or_404(CourseMindmapGeneration, pk=generation_id)

    json_url = _resolve_json_url(request, generation_id, scope, scope_id)
    widget_id = f"adm-{scope}-{scope_id or 'root'}"
    map_type = gen.map_type or "9"

    try:
        from counselor.mindmap_config import get_counselor_mindmap_map_type

        counselor_map_type = get_counselor_mindmap_map_type()
    except Exception:
        counselor_map_type = "classic_vertical"

    jinja2 = engines["jinja2"]
    template = jinja2.get_template("course_mindmap/preview_scope_frame.html")
    html = template.render(
        {
            "mindmap_json_url": json_url,
            "widget_id": widget_id,
            "mindmap_map_type": map_type or counselor_map_type,
            "counselor_mindmap_map_type": counselor_map_type,
            "scope_label": request.GET.get("label", scope),
        },
        request=request,
    )
    from django.http import HttpResponse

    return HttpResponse(html)
