from __future__ import annotations

from django.urls import reverse

from course_mindmap.constants import (
    COURSE_TYPE_SKILLLAB,
    SCOPE_CHAPTER,
    SCOPE_COURSE,
    SCOPE_SECTION,
)
from course_mindmap.models import CourseMindmapConfig, CourseMindmapData
from course_mindmap.registry import get_adapter
from course_mindmap.service import (
    course_mindmaps_globally_enabled,
    mindmap_visible_for_user,
    scope_flags_for_course,
)


def _get_config(course_type_key: str, course_id: int) -> CourseMindmapConfig | None:
    try:
        adapter = get_adapter(course_type_key)
        ct = adapter.content_type()
    except Exception:
        return None
    return (
        CourseMindmapConfig.objects.filter(
            content_type=ct,
            object_id=course_id,
            is_verified=True,
        )
        .first()
    )


def _data_row(course_type_key: str, course_id: int, scope: str, scope_id: int):
    try:
        adapter = get_adapter(course_type_key)
        ct = adapter.content_type()
    except Exception:
        return None
    qs = CourseMindmapData.objects.filter(
        content_type=ct,
        object_id=course_id,
        scope=scope,
        is_valid=True,
    )
    if scope == SCOPE_COURSE:
        return qs.filter(scope_id=0).first()
    return qs.filter(scope_id=scope_id).first()


def mindmap_json_url(request, course_slug: str, data_id: int) -> str:
    path = reverse(
        "skilllabcourse:mindmap_json",
        kwargs={"course_slug": course_slug, "data_id": data_id},
    )
    return request.build_absolute_uri(path) if request else path


def build_skilllab_mindmap_context(request, course) -> dict:
    """Context dict for SkillLab course_learning template."""
    empty = {
        "course_mindmap_enabled": False,
        "course_mindmap_info": None,
        "chapter_mindmap_by_id": {},
        "section_mindmap_by_id": {},
        "enable_content_area_mindmap": False,
        "course_mindmap_map_type": "",
    }
    if not course_mindmaps_globally_enabled():
        return empty

    course_type_key = COURSE_TYPE_SKILLLAB
    config = _get_config(course_type_key, course.pk)
    if not config or not mindmap_visible_for_user(config, request.user):
        return empty

    course_ok, ch_flags, sec_flags = scope_flags_for_course(course_type_key, course.pk)
    slug = course.slug
    map_type = config.map_type or ""

    ctx = {
        "course_mindmap_enabled": True,
        "course_mindmap_info": None,
        "chapter_mindmap_by_id": {},
        "section_mindmap_by_id": {},
        "enable_content_area_mindmap": bool(config.enable_content_area_mindmap),
        "course_mindmap_map_type": map_type,
    }

    if config.enable_title_mindmap and course_ok:
        row = _data_row(course_type_key, course.pk, SCOPE_COURSE, 0)
        if row:
            ctx["course_mindmap_info"] = {
                "json_url": mindmap_json_url(request, slug, row.pk),
                "fullscreen_url": reverse(
                    "skilllabcourse:mindmap_course",
                    kwargs={"course_slug": slug},
                ),
            }

    if config.enable_sidebar_mindmap:
        for ch_id, ok in ch_flags.items():
            if not ok:
                continue
            row = _data_row(course_type_key, course.pk, SCOPE_CHAPTER, ch_id)
            if row:
                ctx["chapter_mindmap_by_id"][ch_id] = {
                    "json_url": mindmap_json_url(request, slug, row.pk),
                    "fullscreen_url": reverse(
                        "skilllabcourse:mindmap_chapter",
                        kwargs={"course_slug": slug, "chapter_id": ch_id},
                    ),
                }

        for sec_id, ok in sec_flags.items():
            if not ok:
                continue
            row = _data_row(course_type_key, course.pk, SCOPE_SECTION, sec_id)
            if row:
                ctx["section_mindmap_by_id"][sec_id] = {
                    "json_url": mindmap_json_url(request, slug, row.pk),
                    "fullscreen_url": reverse(
                        "skilllabcourse:mindmap_section",
                        kwargs={"course_slug": slug, "section_id": sec_id},
                    ),
                }

    return ctx


def section_has_content_mindmap(course, section_id: int, config: CourseMindmapConfig | None = None) -> bool:
    if not course_mindmaps_globally_enabled():
        return False
    config = config or _get_config(COURSE_TYPE_SKILLLAB, course.pk)
    if not config or not config.enable_content_area_mindmap:
        return False
    _, _, sec_flags = scope_flags_for_course(COURSE_TYPE_SKILLLAB, course.pk)
    return bool(sec_flags.get(section_id))


def get_section_mindmap_for_content(request, course, section_id: int) -> dict | None:
    """Mindmap widget context for content-area tab on an intro section."""
    if not course_mindmaps_globally_enabled():
        return None
    config = _get_config(COURSE_TYPE_SKILLLAB, course.pk)
    if not config or not mindmap_visible_for_user(config, request.user):
        return None
    if not config.enable_content_area_mindmap:
        return None
    row = _data_row(COURSE_TYPE_SKILLLAB, course.pk, SCOPE_SECTION, section_id)
    if not row:
        return None
    return {
        "json_url": mindmap_json_url(request, course.slug, row.pk),
        "map_type": config.map_type or "",
        "embed_url": reverse(
            "skilllabcourse:mindmap_section_embed",
            kwargs={"course_slug": course.slug, "section_id": section_id},
        ),
    }


def user_can_access_mindmap_data(request, data_row: CourseMindmapData) -> bool:
    if not request.user.is_authenticated:
        return False
    if not course_mindmaps_globally_enabled():
        return False
    if data_row.course_type_key != COURSE_TYPE_SKILLLAB:
        return False
    from skilllab.models import SkillLabCourse

    course = SkillLabCourse.objects.filter(pk=data_row.object_id).first()
    if not course or not course.is_user_vissible(request):
        return False
    config = _get_config(data_row.course_type_key, course.pk)
    if not config or not mindmap_visible_for_user(config, request.user):
        return False
    return True
