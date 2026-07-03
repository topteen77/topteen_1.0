from __future__ import annotations

from core import choices
from skilllab.models import SkillLabChapterSection, SkillLabCourse, SkillLabCourseChapter

from course_mindmap.constants import (
    COURSE_TYPE_SKILLLAB,
    SCOPE_CHAPTER,
    SCOPE_COURSE,
    SCOPE_SECTION,
)
from course_mindmap.registry import BaseCourseMindmapAdapter
from course_mindmap.utils import html_to_markdown_bullets, markdown_outline


def _section_display_title(sec: SkillLabChapterSection, section_num: int) -> str:
    if sec.section_type == "introduction":
        return sec.title or "Introduction"
    if sec.section_type == "chapter_wrap_up":
        return sec.title or "Chapter Wrap-Up"
    return sec.title or f"Section {section_num}"


def _intro_sections_for_chapter(ch: SkillLabCourseChapter) -> list[dict]:
    """Intro-type sections only (no worksheet/mcq)."""
    sections = list(ch.sections.order_by("order"))
    if sections:
        section_num = 0
        out = []
        for sec in sections:
            if sec.section_type == "introduction":
                title = _section_display_title(sec, 0)
            elif sec.section_type == "chapter_wrap_up":
                title = _section_display_title(sec, 0)
            else:
                section_num += 1
                title = _section_display_title(sec, section_num)
            out.append({"id": sec.id, "title": title, "content": sec.content or ""})
        return out
    # Legacy chapter.content — treat whole chapter as one pseudo-section
    if (ch.content or "").strip():
        return [{"id": ch.id, "title": ch.chapter_name, "content": ch.content, "legacy_step": True}]
    return []


def _chapter_sidebar_extras(ch: SkillLabCourseChapter) -> list[str]:
    """Worksheet/quiz labels for course/chapter trees only (not section mindmaps)."""
    extras = []
    for act in ch.skilllabcourseactivity.filter(type=choices.SkillLabAcivityChoice.worksheet):
        extras.append(f"Worksheet: {act.name}")
    for mcq in ch.mcqs.all():
        extras.append(f"Quiz: {mcq.title or 'Quiz'}")
    return extras


class SkillLabMindmapAdapter(BaseCourseMindmapAdapter):
    course_type_key = COURSE_TYPE_SKILLLAB
    label = "SkillLab Course"

    def get_course_queryset(self):
        return SkillLabCourse.objects.complete().order_by("name")

    def get_course_display_name(self, course) -> str:
        return course.name or str(course)

    def build_scopes(self, course, *, map_type: str = "classic_vertical") -> list[dict]:
        course_id = course.pk
        chapters = list(
            course.skilllabcoursechapter.order_by("created").prefetch_related(
                "sections",
                "skilllabcourseactivity",
                "mcqs",
            )
        )
        scopes: list[dict] = []
        warnings: list[str] = []

        # --- Course scope ---
        course_children: list[str | tuple[str, list[str]]] = []
        for ch in chapters:
            intro_secs = _intro_sections_for_chapter(ch)
            sec_labels = [s["title"] for s in intro_secs]
            sec_labels.extend(_chapter_sidebar_extras(ch))
            if sec_labels:
                course_children.append((ch.chapter_name, sec_labels))
            else:
                course_children.append(ch.chapter_name)
                warnings.append(f"Chapter '{ch.chapter_name}' has no intro sections.")

        course_md = markdown_outline(course.name or "Course", course_children)
        scopes.append(
            {
                "scope": SCOPE_COURSE,
                "scope_id": 0,
                "label": course.name or "Course",
                "markdown": course_md,
                "meta": {"course_id": course_id, "chapter_id": None, "section_id": None},
            }
        )

        # --- Chapter + section scopes ---
        for ch in chapters:
            intro_secs = _intro_sections_for_chapter(ch)
            ch_children: list[str | tuple[str, list[str]]] = []
            for s in intro_secs:
                bullets = html_to_markdown_bullets(s.get("content") or "")
                if bullets:
                    ch_children.append((s["title"], bullets))
                else:
                    ch_children.append(s["title"])
            ch_children.extend(_chapter_sidebar_extras(ch))

            ch_md = markdown_outline(ch.chapter_name, ch_children)
            scopes.append(
                {
                    "scope": SCOPE_CHAPTER,
                    "scope_id": ch.id,
                    "label": ch.chapter_name,
                    "markdown": ch_md,
                    "meta": {"course_id": course_id, "chapter_id": ch.id, "section_id": None},
                }
            )

            for s in intro_secs:
                sid = s["id"]
                bullets = html_to_markdown_bullets(s.get("content") or "")
                if not bullets:
                    warnings.append(f"Section '{s['title']}' has no extractable headings — using title only.")
                sec_md = markdown_outline(s["title"], bullets or ["Content"])
                scopes.append(
                    {
                        "scope": SCOPE_SECTION,
                        "scope_id": sid,
                        "label": s["title"],
                        "markdown": sec_md,
                        "meta": {
                            "course_id": course_id,
                            "chapter_id": ch.id,
                            "section_id": sid,
                        },
                    }
                )

        if warnings:
            for scope in scopes:
                scope.setdefault("_warnings", []).extend(warnings)

        return scopes
