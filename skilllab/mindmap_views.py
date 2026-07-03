"""SkillLab course player mindmap views (Phase 2 frontend)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from course_mindmap.constants import COURSE_TYPE_SKILLLAB, SCOPE_CHAPTER, SCOPE_COURSE, SCOPE_SECTION
from course_mindmap.frontend import (
    _data_row,
    _get_config,
    mindmap_json_url,
    user_can_access_mindmap_data,
)
from course_mindmap.models import CourseMindmapData
from course_mindmap.service import course_mindmaps_globally_enabled, mindmap_visible_for_user
from skilllab.models import SkillLabCourse, SkillLabCourseChapter, SkillLabChapterSection


def _course_or_404(request, slug: str) -> SkillLabCourse:
    course = get_object_or_404(SkillLabCourse, slug=slug)
    if not course.is_user_vissible(request):
        raise Http404
    return course


def _fullscreen_context(request, course, *, scope: str, scope_id: int, page_title: str, back_url: str):
    if not course_mindmaps_globally_enabled():
        raise Http404
    config = _get_config(COURSE_TYPE_SKILLLAB, course.pk)
    if not config or not mindmap_visible_for_user(config, request.user):
        raise Http404
    if scope == SCOPE_COURSE and not config.enable_title_mindmap:
        raise Http404
    if scope in (SCOPE_CHAPTER, SCOPE_SECTION) and not config.enable_sidebar_mindmap:
        raise Http404
    row = _data_row(COURSE_TYPE_SKILLLAB, course.pk, scope, scope_id)
    if not row:
        raise Http404
    try:
        from counselor.mindmap_config import get_counselor_mindmap_map_type

        default_map_type = get_counselor_mindmap_map_type()
    except Exception:
        default_map_type = "classic_vertical"
    return {
        "mindmap_json_url": mindmap_json_url(request, course.slug, row.pk),
        "page_title": page_title,
        "back_url": back_url,
        "counselor_mindmap_map_type": config.map_type or default_map_type,
    }


@method_decorator(login_required(login_url="/users/login/"), name="dispatch")
class SkillLabMindmapJsonView(View):
    """JSON for authenticated students with course access."""

    def get(self, request, course_slug, data_id):
        course = _course_or_404(request, course_slug)
        row = get_object_or_404(CourseMindmapData, pk=data_id, object_id=course.pk)
        if not user_can_access_mindmap_data(request, row):
            raise Http404
        return JsonResponse(row.payload)


@method_decorator(login_required(login_url="/users/login/"), name="dispatch")
class SkillLabCourseMindmapFullscreenView(View):
    template_name = "template20/skilllab/mindmap_fullscreen.html"

    def get(self, request, course_slug):
        course = _course_or_404(request, course_slug)
        ctx = _fullscreen_context(
            request,
            course,
            scope=SCOPE_COURSE,
            scope_id=0,
            page_title=course.name,
            back_url=reverse("skilllabcourse:course_learning", kwargs={"course_slug": course.slug}),
        )
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url="/users/login/"), name="dispatch")
class SkillLabChapterMindmapFullscreenView(View):
    template_name = "template20/skilllab/mindmap_fullscreen.html"

    def get(self, request, course_slug, chapter_id):
        course = _course_or_404(request, course_slug)
        chapter = get_object_or_404(SkillLabCourseChapter, pk=chapter_id, skilllab=course)
        ctx = _fullscreen_context(
            request,
            course,
            scope=SCOPE_CHAPTER,
            scope_id=chapter.id,
            page_title=chapter.chapter_name,
            back_url=reverse("skilllabcourse:course_learning", kwargs={"course_slug": course.slug}),
        )
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url="/users/login/"), name="dispatch")
class SkillLabSectionMindmapFullscreenView(View):
    template_name = "template20/skilllab/mindmap_fullscreen.html"

    def get(self, request, course_slug, section_id):
        course = _course_or_404(request, course_slug)
        section = get_object_or_404(
            SkillLabChapterSection,
            pk=section_id,
            chapter__skilllab=course,
        )
        ctx = _fullscreen_context(
            request,
            course,
            scope=SCOPE_SECTION,
            scope_id=section.id,
            page_title=section.title or "Section",
            back_url=reverse("skilllabcourse:course_learning", kwargs={"course_slug": course.slug}),
        )
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url="/users/login/"), name="dispatch")
class SkillLabSectionMindmapEmbedView(View):
    """Chrome-less section mindmap for embedding in the content-area tab (iframe)."""

    template_name = "template20/skilllab/mindmap_embed.html"

    def get(self, request, course_slug, section_id):
        course = _course_or_404(request, course_slug)
        section = get_object_or_404(
            SkillLabChapterSection,
            pk=section_id,
            chapter__skilllab=course,
        )
        if not course_mindmaps_globally_enabled():
            raise Http404
        config = _get_config(COURSE_TYPE_SKILLLAB, course.pk)
        if not config or not mindmap_visible_for_user(config, request.user):
            raise Http404
        if not config.enable_content_area_mindmap:
            raise Http404
        row = _data_row(COURSE_TYPE_SKILLLAB, course.pk, SCOPE_SECTION, section.id)
        if not row:
            raise Http404
        return render(
            request,
            self.template_name,
            {
                "mindmap_json_url": mindmap_json_url(request, course.slug, row.pk),
                "mindmap_map_type": config.map_type or "",
            },
        )
