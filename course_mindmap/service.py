from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from course_mindmap.constants import (
    GENERATION_STATUS_DRY_RUN,
    GENERATION_STATUS_FAILED,
    GENERATION_STATUS_GENERATED,
    GENERATION_STATUS_VERIFIED,
    GRADE_MODE_ALL,
    GRADE_MODE_NONE,
    GRADE_MODE_SELECTED,
    SCOPE_CHAPTER,
    SCOPE_COURSE,
    SCOPE_SECTION,
)
from course_mindmap.models import CourseMindmapConfig, CourseMindmapData, CourseMindmapGeneration
from course_mindmap.registry import get_adapter


def _default_map_type() -> str:
    try:
        from counselor.mindmap_config import get_counselor_mindmap_map_type

        return get_counselor_mindmap_map_type() or "classic_vertical"
    except Exception:
        return "classic_vertical"


def _num_map_type_to_widget(map_type: str) -> str:
    """Map admin numeric choice (1-9) to widget map_type string."""
    try:
        from counselor.mindmap_config import _NUM_TO_WIDGET_MAP_TYPE

        if map_type.isdigit():
            return _NUM_TO_WIDGET_MAP_TYPE.get(map_type, "classic_vertical")
    except Exception:
        pass
    return map_type or "classic_vertical"


def build_payload(
    *,
    scope: str,
    markdown: str,
    map_type: str,
    meta: dict,
    course_type_key: str,
) -> dict:
    widget_map_type = _num_map_type_to_widget(map_type)
    return {
        "format_version": 1,
        "mindmap_type": "course",
        "map_type": widget_map_type,
        "scope": scope,
        "meta": {
            "course_type_key": course_type_key,
            **(meta or {}),
        },
        "markdown": markdown,
        "md": markdown,
    }


def validate_payload(payload: dict) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "Payload is not a dict"
    md = payload.get("markdown") or payload.get("md") or ""
    if not isinstance(md, str) or not md.strip():
        return False, "Missing markdown"
    if not md.strip().startswith("#"):
        return False, "Markdown must start with # root heading"
    return True, ""


def generate_mindmaps(
    *,
    course_type_key: str,
    course_id: int,
    dry_run: bool = True,
    map_type: str = "",
    user=None,
) -> CourseMindmapGeneration:
    adapter = get_adapter(course_type_key)
    course = adapter.get_course_by_id(course_id)
    if not course:
        gen = CourseMindmapGeneration.objects.create(
            course_type_key=course_type_key,
            content_type=adapter.content_type(),
            object_id=course_id,
            status=GENERATION_STATUS_FAILED,
            dry_run=dry_run,
            error_message="Course not found",
            generated_by=user,
        )
        return gen

    resolved_map_type = map_type or _default_map_type()
    ct = adapter.content_type()
    warnings: list[str] = []
    errors: list[str] = []
    scope_rows: list[dict] = []

    try:
        raw_scopes = adapter.build_scopes(course, map_type=resolved_map_type)
    except Exception as exc:
        return CourseMindmapGeneration.objects.create(
            course_type_key=course_type_key,
            content_type=ct,
            object_id=course_id,
            status=GENERATION_STATUS_FAILED,
            dry_run=dry_run,
            map_type=resolved_map_type,
            error_message=str(exc),
            generated_by=user,
        )

    for item in raw_scopes:
        scope_warnings = item.pop("_warnings", [])
        warnings.extend(scope_warnings)
        payload = build_payload(
            scope=item["scope"],
            markdown=item["markdown"],
            map_type=resolved_map_type,
            meta=item.get("meta") or {},
            course_type_key=course_type_key,
        )
        ok, err = validate_payload(payload)
        if not ok:
            errors.append(f"{item['scope']}:{item.get('scope_id')} — {err}")
        scope_rows.append(
            {
                "scope": item["scope"],
                "scope_id": item.get("scope_id"),
                "label": item.get("label") or "",
                "payload": payload,
                "is_valid": ok,
                "error": err if not ok else "",
            }
        )

    counts = {
        "course": sum(1 for r in scope_rows if r["scope"] == SCOPE_COURSE and r["is_valid"]),
        "chapter": sum(1 for r in scope_rows if r["scope"] == SCOPE_CHAPTER and r["is_valid"]),
        "section": sum(1 for r in scope_rows if r["scope"] == SCOPE_SECTION and r["is_valid"]),
    }

    report = {
        "course_name": adapter.get_course_display_name(course),
        "course_id": course_id,
        "dry_run": dry_run,
        "scopes": scope_rows,
        "counts": counts,
        "warnings": list(dict.fromkeys(warnings)),
        "errors": errors,
        "valid_total": sum(1 for r in scope_rows if r["is_valid"]),
        "total": len(scope_rows),
    }

    status = GENERATION_STATUS_DRY_RUN if dry_run else GENERATION_STATUS_GENERATED
    if errors and not dry_run:
        status = GENERATION_STATUS_FAILED

    with transaction.atomic():
        gen = CourseMindmapGeneration.objects.create(
            course_type_key=course_type_key,
            content_type=ct,
            object_id=course_id,
            status=status,
            dry_run=dry_run,
            map_type=resolved_map_type,
            report=report,
            scope_count=len(scope_rows),
            error_message="; ".join(errors[:5]),
            generated_by=user,
        )

        if not dry_run and not errors:
            _hard_delete_queryset(
                CourseMindmapData.objects.filter(content_type=ct, object_id=course_id)
            )
            for row in scope_rows:
                CourseMindmapData.objects.create(
                    course_type_key=course_type_key,
                    content_type=ct,
                    object_id=course_id,
                    scope=row["scope"],
                    scope_id=row["scope_id"],
                    label=row["label"],
                    payload=row["payload"],
                    is_valid=row["is_valid"],
                    generation=gen,
                )
            config, _ = CourseMindmapConfig.objects.get_or_create(
                course_type_key=course_type_key,
                content_type=ct,
                object_id=course_id,
                defaults={"map_type": resolved_map_type},
            )
            config.last_generation = gen
            config.map_type = resolved_map_type or config.map_type
            config.is_verified = False
            config.verified_at = None
            config.verified_by = None
            config.save(
                update_fields=[
                    "last_generation",
                    "map_type",
                    "is_verified",
                    "verified_at",
                    "verified_by",
                    "modified",
                ]
            )

    return gen


def verify_generation(generation: CourseMindmapGeneration, user=None) -> CourseMindmapConfig:
    ct = generation.content_type
    oid = generation.object_id
    config, _ = CourseMindmapConfig.objects.get_or_create(
        course_type_key=generation.course_type_key,
        content_type=ct,
        object_id=oid,
        defaults={"map_type": generation.map_type},
    )
    config.is_verified = True
    config.verified_at = timezone.now()
    config.verified_by = user
    config.last_generation = generation
    config.save()

    generation.status = GENERATION_STATUS_VERIFIED
    generation.save(update_fields=["status", "modified"])
    return config


def validate_course_mindmaps(course_type_key: str, course_id: int) -> dict:
    adapter = get_adapter(course_type_key)
    ct = adapter.content_type()
    rows = CourseMindmapData.objects.filter(content_type=ct, object_id=course_id)
    result = {
        "course": False,
        "chapters": {},
        "sections": {},
        "errors": [],
    }
    for row in rows:
        ok, err = validate_payload(row.payload)
        if row.scope == SCOPE_COURSE:
            result["course"] = ok and row.is_valid
        elif row.scope == SCOPE_CHAPTER:
            result["chapters"][row.scope_id] = ok and row.is_valid
        elif row.scope == SCOPE_SECTION:
            result["sections"][row.scope_id] = ok and row.is_valid
        if not ok:
            result["errors"].append(f"{row.scope}:{row.scope_id} — {err}")
    return result


def get_mindmap_data_row(
    course_type_key: str,
    course_id: int,
    scope: str,
    scope_id: int | None = None,
) -> CourseMindmapData | None:
    adapter = get_adapter(course_type_key)
    ct = adapter.content_type()
    qs = CourseMindmapData.objects.filter(
        content_type=ct,
        object_id=course_id,
        scope=scope,
        is_valid=True,
    )
    if scope_id is None or scope_id == 0:
        qs = qs.filter(scope_id=0)
    else:
        qs = qs.filter(scope_id=scope_id)
    return qs.first()


def mindmap_visible_for_user(config: CourseMindmapConfig, user) -> bool:
    if not config or not config.is_verified:
        return False
    if config.grade_mode == GRADE_MODE_NONE:
        return False
    if config.grade_mode == GRADE_MODE_ALL:
        return True
    if config.grade_mode == GRADE_MODE_SELECTED:
        if not user or not user.is_authenticated:
            return False
        try:
            from users.skilllab_dashboard import _extract_grade_number

            grade_num = _extract_grade_number(user)
        except Exception:
            grade_num = None
        if grade_num is None:
            return False
        return config.grades.filter(grade_number=grade_num).exists()
    return False


def scope_flags_for_course(course_type_key: str, course_id: int) -> tuple[bool, dict, dict]:
    """Return (course_ok, chapter_id->bool, section_id->bool)."""
    adapter = get_adapter(course_type_key)
    ct = adapter.content_type()
    rows = CourseMindmapData.objects.filter(
        content_type=ct,
        object_id=course_id,
        is_valid=True,
    )
    course_ok = False
    chapters: dict = {}
    sections: dict = {}
    for row in rows:
        if row.scope == SCOPE_COURSE:
            course_ok = True
        elif row.scope == SCOPE_CHAPTER:
            chapters[row.scope_id] = True
        elif row.scope == SCOPE_SECTION:
            sections[row.scope_id] = True
    return course_ok, chapters, sections


def course_mindmaps_globally_enabled() -> bool:
    """Core Configuration ENABLE_COURSE_MINDMAP (default on)."""
    from core.models import Configuration

    try:
        v = Configuration.get("ENABLE_COURSE_MINDMAP", "true", editable=True)
    except Exception:
        return True
    return str(v).lower() in ("true", "1", "yes", "on")


def _hard_delete_queryset(qs) -> int:
    """Permanently remove rows (BaseModel uses soft-delete by default)."""
    items = list(qs)
    for obj in items:
        obj.delete(hard_delete=True)
    return len(items)


def delete_complete_course_mindmap(
    *,
    content_type,
    object_id: int,
) -> dict[str, int]:
    """
    Remove all mindmap artifacts for one course: data rows, config (incl. grades M2M), generation logs.
    """
    from django.db import transaction

    from course_mindmap.models import CourseMindmapConfig, CourseMindmapData, CourseMindmapGeneration

    ct = content_type
    oid = int(object_id)

    with transaction.atomic():
        data_deleted = _hard_delete_queryset(
            CourseMindmapData.objects.complete().filter(content_type=ct, object_id=oid)
        )
        configs = list(CourseMindmapConfig.objects.complete().filter(content_type=ct, object_id=oid))
        for config in configs:
            config.grades.clear()
        config_deleted = _hard_delete_queryset(
            CourseMindmapConfig.objects.complete().filter(content_type=ct, object_id=oid)
        )
        gen_deleted = _hard_delete_queryset(
            CourseMindmapGeneration.objects.complete().filter(content_type=ct, object_id=oid)
        )

    return {
        "data_rows": data_deleted,
        "config_rows": config_deleted,
        "generation_rows": gen_deleted,
    }


def delete_complete_for_queryset(queryset) -> dict[str, int]:
    """Purge mindmaps for each unique course in queryset (config, data, or generation rows)."""
    seen: set[tuple[int, int]] = set()
    totals = {"data_rows": 0, "config_rows": 0, "generation_rows": 0, "courses": 0}
    for obj in queryset:
        key = (obj.content_type_id, obj.object_id)
        if key in seen:
            continue
        seen.add(key)
        part = delete_complete_course_mindmap(
            content_type=obj.content_type,
            object_id=obj.object_id,
        )
        totals["courses"] += 1
        for k in ("data_rows", "config_rows", "generation_rows"):
            totals[k] += part[k]
    return totals
