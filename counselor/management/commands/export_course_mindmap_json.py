"""
Export counselor course structure to JSON mindmaps (Markmap markdown + XMind-style tree).

Writes under a folder such as ../coursemindmap/14/ (sibling of topteen_1.0 by default):
  course.json, chapter_<id>.json, part_<id>.json, manifest.json

Example:
  python manage.py export_course_mindmap_json --segment 14
  python manage.py export_course_mindmap_json --segment 14 --out-dir /path/to/coursemindmap/14
  python manage.py export_course_mindmap_json --segment 14 --no-pdf \\
    --content-root "/path/to/career counsellor course"

Copy selected files to counselor/static/counselor/mindmaps/ if you use the built-in mindmap widget
(course.json must be that exact name there; chapter/part files use chapter_<id>.json / part_<id>.json).

With --content-root, also writes html/ under the output dir: attachments and Quiz .docx → .html via mammoth.

Per part tree: **Chapter → Part →** lesson branch (`video` for Practical Training, `PDF` for Case Studies with `N pdf`, else `Video/PDF`), then **Quiz**.
`course.json` is course title plus chapters/parts only (no course-level index or intro blocks). Use --no-pdf to skip remote PDF fetch.

Each JSON may include map_type: tree, concept, radial, cluster, career_radial (reuse careers radial-mindmap.js).
Override via ?map_type= / ?mindmap_type= on the page URL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from counselor.docx_html_export import export_docx_tree_to_html
from counselor.local_course_attachments import (
    lesson_headings_for_part,
    scan_quiz_video_sets,
)
from counselor.models import Chapter, CounselorCourse, Part

STRUCT_LEAF = "org.xmind.ui.logic.right"
STRUCT_ROOT_MAP = "org.xmind.ui.map.unbalanced"

# Default branch for lesson read/watch material (extracted headings); not a separate "Video" leaf.
VIDEO_PDF_LABEL = "Video/PDF"


def _part_title_lower(part: Part) -> str:
    return (getattr(part, "title", None) or "").strip().lower()


def _is_practical_training_part(part: Part) -> bool:
    """Matches 'Practical Training' and common typo 'Practicle Training'."""
    t = _part_title_lower(part)
    return ("practical" in t or "practicle" in t) and "training" in t


def _is_case_studies_part(part: Part) -> bool:
    t = _part_title_lower(part)
    return "case stud" in t


def _part_lesson_branch_label(part: Part) -> str:
    """Under Advanced Practical Training (and elsewhere): video / PDF / Video/PDF."""
    if _is_case_studies_part(part):
        return "PDF"
    if _is_practical_training_part(part):
        return "video"
    return VIDEO_PDF_LABEL


def _part_lesson_branch_leaves(
    part: Part,
    pdf_bullets: list[str],
    has_video: bool,
) -> list[str]:
    """Leaf lines under the lesson branch (markdown + xmind)."""
    if _is_case_studies_part(part):
        n = part.case_studies.count()
        return [f"{n} pdf"]
    if _is_practical_training_part(part):
        if pdf_bullets:
            return pdf_bullets
        if has_video:
            return ["(Lesson video)"]
        return ["(No outline — Admin description or --content-root lesson .docx)"]
    if pdf_bullets:
        return pdf_bullets
    if has_video:
        return ["(Lesson video)"]
    return ["(No outline — Admin description or --content-root lesson .docx)"]


def _heading_text(s: str) -> str:
    if not s:
        return "Untitled"
    t = str(s).replace("\r", " ").replace("\n", " ").strip()
    return t or "Untitled"


def _topic_id(*parts: str) -> str:
    safe = "_".join(re.sub(r"[^a-zA-Z0-9]+", "_", str(p)).strip("_") for p in parts if p is not None)
    return f"cc_{safe}"[:120]


def _xmind_leaf(title: str, *id_parts: str) -> dict:
    return {
        "id": _topic_id(*id_parts),
        "structureClass": STRUCT_LEAF,
        "title": title,
        "children": {"attached": []},
    }


def _xmind_branch(title: str, attached: list, *id_parts: str) -> dict:
    return {
        "id": _topic_id(*id_parts),
        "structureClass": STRUCT_LEAF,
        "title": title,
        "children": {"attached": attached},
    }


def _description_bullets(description: str | None, max_items: int = 8) -> list[str]:
    if not description:
        return []
    text = re.sub(r"\s+", " ", description.strip())
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for c in chunks:
        c = c.strip()
        if len(c) < 8:
            continue
        if len(c) > 160:
            c = c[:157] + "…"
        out.append(c)
        if len(out) >= max_items:
            break
    return out


def _part_ordinals(chapter: Chapter | None, chapters: list[Chapter], part: Part) -> tuple[int, int]:
    if not chapter:
        return 1, 1
    ch_ord = next((i for i, c in enumerate(chapters, start=1) if c.id == chapter.id), 1)
    plist = list(chapter.parts.all().order_by("id"))
    p_ord = next((i for i, p in enumerate(plist, start=1) if p.id == part.id), 1)
    return ch_ord, p_ord


def _part_pdf_bullets(
    part: Part,
    chapter: Chapter | None,
    chapters: list[Chapter],
    *,
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    part_max_items: int = 10,
) -> list[str]:
    """Lesson outline only (docx headings, else PDF text, else Admin description)."""
    ch_ord, p_ord = _part_ordinals(chapter, chapters, part)
    headings = lesson_headings_for_part(
        part,
        use_remote_pdf=use_remote_pdf,
        base_dir=base_dir,
        content_root=content_root,
        chapter_ord=ch_ord,
        part_ord=p_ord,
        max_items=part_max_items,
    )
    if headings:
        return headings
    return _description_bullets(part.description, max_items=part_max_items)


def _part_quiz_video_flags(
    part: Part,
    chapter: Chapter | None,
    chapters: list[Chapter],
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> tuple[bool, bool]:
    ch_ord, p_ord = _part_ordinals(chapter, chapters, part)
    key = (ch_ord, p_ord)
    return (key in quiz_set, key in video_set)


def _append_part_tree_markdown(
    lines: list[str],
    part: Part,
    pdf_bullets: list[str],
    has_quiz: bool,
    has_video: bool,
) -> None:
    """Nested list: lesson branch (video / PDF / Video/PDF) → bullets; then Quiz."""
    label = _part_lesson_branch_label(part)
    leaves = _part_lesson_branch_leaves(part, pdf_bullets, has_video)
    lines.append(f"- {label}")
    for b in leaves:
        lines.append(f"  - {b}")
    if has_quiz:
        lines.append("- Quiz")


def _xmind_part_subtree(
    part: Part,
    part_title: str,
    pdf_bullets: list[str],
    has_quiz: bool,
    has_video: bool,
    *id_parts: str,
) -> dict:
    """Under a chapter: Part node with children video/PDF/Video/PDF → bullets, Quiz."""
    attached = _xmind_part_root_children(part, pdf_bullets, has_quiz, has_video, *id_parts)
    return _xmind_branch(part_title, attached, *id_parts, "part")


def _xmind_part_root_children(
    part: Part,
    pdf_bullets: list[str],
    has_quiz: bool,
    has_video: bool,
    *id_parts: str,
) -> list[dict]:
    """Children under a part: lesson branch (label varies by part title), Quiz."""
    attached: list[dict] = []
    label = _part_lesson_branch_label(part)
    leaves = _part_lesson_branch_leaves(part, pdf_bullets, has_video)
    pdf_leaves = [_xmind_leaf(b, *id_parts, "vpdf", str(i)) for i, b in enumerate(leaves)]
    attached.append(_xmind_branch(label, pdf_leaves, *id_parts, "vpdfroot"))
    if has_quiz:
        attached.append(_xmind_leaf("Quiz", *id_parts, "qz"))
    return attached


def _sheet(sheet_key: str, sheet_title: str, root_title: str, branches: list[dict]) -> dict:
    return {
        "id": _topic_id("sheet", sheet_key),
        "class": "sheet",
        "title": sheet_title,
        "extensions": [],
        "topicPositioning": "fixed",
        "topicOverlapping": "overlap",
        "coreVersion": "2.100.0",
        "rootTopic": {
            "id": _topic_id("root", sheet_key),
            "structureClass": STRUCT_ROOT_MAP,
            "title": root_title,
            "children": {"attached": branches},
            "class": "topic",
        },
    }


def _course_markdown(
    course: CounselorCourse,
    chapters: list[Chapter],
    *,
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> str:
    lines = [f"# {_heading_text(course.title)}"]
    for ch in chapters:
        lines.append(f"## {_heading_text(ch.title)}")
        for p in ch.parts.all().order_by("id"):
            lines.append(f"### {_heading_text(p.title)}")
            pdf_b = _part_pdf_bullets(
                p,
                ch,
                chapters,
                use_remote_pdf=use_remote_pdf,
                base_dir=base_dir,
                content_root=content_root,
                part_max_items=8,
            )
            hq, hv = _part_quiz_video_flags(p, ch, chapters, quiz_set, video_set)
            _append_part_tree_markdown(lines, p, pdf_b, hq, hv)
    return "\n".join(lines) + "\n"


def _course_xmind(
    course: CounselorCourse,
    chapters: list[Chapter],
    *,
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> list[dict]:
    branches: list[dict] = []
    for ch in chapters:
        part_nodes = []
        for p in ch.parts.all().order_by("id"):
            pdf_b = _part_pdf_bullets(
                p,
                ch,
                chapters,
                use_remote_pdf=use_remote_pdf,
                base_dir=base_dir,
                content_root=content_root,
                part_max_items=8,
            )
            hq, hv = _part_quiz_video_flags(p, ch, chapters, quiz_set, video_set)
            part_nodes.append(
                _xmind_part_subtree(
                    p,
                    _heading_text(p.title),
                    pdf_b,
                    hq,
                    hv,
                    "course",
                    str(ch.id),
                    str(p.id),
                )
            )
        branches.append(_xmind_branch(_heading_text(ch.title), part_nodes, "course", "ch", str(ch.id)))
    return [_sheet("course", _heading_text(course.title), _heading_text(course.title), branches)]


def _chapter_markdown(
    ch: Chapter,
    *,
    chapters: list[Chapter],
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> str:
    lines = [f"# {_heading_text(ch.title)}"]
    for p in ch.parts.all().order_by("id"):
        lines.append(f"## {_heading_text(p.title)}")
        pdf_b = _part_pdf_bullets(
            p,
            ch,
            chapters,
            use_remote_pdf=use_remote_pdf,
            base_dir=base_dir,
            content_root=content_root,
            part_max_items=8,
        )
        hq, hv = _part_quiz_video_flags(p, ch, chapters, quiz_set, video_set)
        _append_part_tree_markdown(lines, p, pdf_b, hq, hv)
    return "\n".join(lines) + "\n"


def _chapter_xmind(
    ch: Chapter,
    *,
    chapters: list[Chapter],
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> list[dict]:
    branches = []
    for p in ch.parts.all().order_by("id"):
        pdf_b = _part_pdf_bullets(
            p,
            ch,
            chapters,
            use_remote_pdf=use_remote_pdf,
            base_dir=base_dir,
            content_root=content_root,
            part_max_items=8,
        )
        hq, hv = _part_quiz_video_flags(p, ch, chapters, quiz_set, video_set)
        branches.append(
            _xmind_part_subtree(
                p,
                _heading_text(p.title),
                pdf_b,
                hq,
                hv,
                "ch",
                str(ch.id),
                str(p.id),
            )
        )
    return [_sheet(f"chapter_{ch.id}", _heading_text(ch.title), _heading_text(ch.title), branches)]


def _part_markdown(
    part: Part,
    *,
    chapters: list[Chapter],
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> str:
    title = _heading_text(part.title)
    lines = [f"# {title}"]
    ch = getattr(part, "chapter", None)
    pdf_b = _part_pdf_bullets(
        part,
        ch,
        chapters,
        use_remote_pdf=use_remote_pdf,
        base_dir=base_dir,
        content_root=content_root,
        part_max_items=10,
    )
    hq, hv = _part_quiz_video_flags(part, ch, chapters, quiz_set, video_set)
    _append_part_tree_markdown(lines, part, pdf_b, hq, hv)
    return "\n".join(lines) + "\n"


def _part_xmind(
    part: Part,
    *,
    chapters: list[Chapter],
    use_remote_pdf: bool,
    base_dir: Path,
    content_root: Path | None,
    quiz_set: set[tuple[int, int]],
    video_set: set[tuple[int, int]],
) -> list[dict]:
    ch = getattr(part, "chapter", None)
    pdf_b = _part_pdf_bullets(
        part,
        ch,
        chapters,
        use_remote_pdf=use_remote_pdf,
        base_dir=base_dir,
        content_root=content_root,
        part_max_items=10,
    )
    hq, hv = _part_quiz_video_flags(part, ch, chapters, quiz_set, video_set)
    branches = _xmind_part_root_children(part, pdf_b, hq, hv, "part", str(part.id))
    return [_sheet(f"part_{part.id}", _heading_text(part.title), _heading_text(part.title), branches)]


def _payload(
    *,
    scope: str,
    markdown: str,
    xmind_sheets: list[dict],
    course_id: int,
    segment: int,
    chapter_id: int | None,
    part_id: int | None,
    map_type: str = "tree",
) -> dict:
    return {
        "format_version": 1,
        "mindmap_type": "counselor_course",
        "map_type": map_type,
        "scope": scope,
        "meta": {
            "course_learning_url_segment": segment,
            "note": "counselor_id in /counselor/course_learning/<segment>/",
            "course_id": course_id,
            "chapter_id": chapter_id,
            "part_id": part_id,
        },
        "markdown": markdown,
        "md": markdown,
        "xmind": xmind_sheets,
    }


class Command(BaseCommand):
    help = "Export course/chapter/part mindmap JSON (markdown + xmind tree) to coursemindmap/<segment>/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--segment",
            type=int,
            default=14,
            help="Folder name and meta.course_learning_url_segment (default 14)",
        )
        parser.add_argument(
            "--out-dir",
            type=str,
            default="",
            help="Output directory. Default: repo sibling coursemindmap/<segment>/",
        )
        parser.add_argument(
            "--map-type",
            type=str,
            choices=("tree", "concept", "radial", "cluster", "career_radial"),
            default="tree",
            help=(
                "Visualization stored as map_type: tree=Markmap; concept=custom bubbles; "
                "radial=D3 radial tree; cluster=D3 dendrogram; career_radial=static/js/radial-mindmap.js (same as career detail XMind UI)."
            ),
        )
        parser.add_argument(
            "--no-pdf",
            action="store_true",
            help="Do not fetch lesson PDFs from Part.pdf_url (local attachments .docx still used if --content-root is set).",
        )
        parser.add_argument(
            "--content-root",
            type=str,
            default="",
            help=(
                "Folder such as …/career counsellor course with attachments/, Quiz/, videos/ "
                "(chapter N part M docx/mp4; enriches mindmaps without relying on URLs)."
            ),
        )
        parser.add_argument(
            "--no-html",
            action="store_true",
            help="Skip generating html/ from attachments/.docx and Quiz/.docx (when --content-root is set).",
        )

    def handle(self, *args, **options):
        segment: int = options["segment"]
        map_type: str = options["map_type"]
        use_remote_pdf: bool = not bool(options.get("no_pdf"))
        base_dir = Path(settings.BASE_DIR)
        cr = (options.get("content_root") or "").strip()
        content_root: Path | None = Path(cr).expanduser().resolve() if cr else None
        if content_root is not None and not content_root.is_dir():
            self.stderr.write(self.style.WARNING(f"Not a directory, ignoring --content-root: {content_root}"))
            content_root = None
        quiz_set, video_set, _ = scan_quiz_video_sets(content_root)
        out_raw = (options.get("out_dir") or "").strip()
        if out_raw:
            out_dir = Path(out_raw).resolve()
        else:
            base = Path(__file__).resolve().parents[4]
            out_dir = (base / "coursemindmap" / str(segment)).resolve()

        course = CounselorCourse.objects.prefetch_related(
            "chapters__parts__case_studies",
        ).order_by("id").first()
        if not course:
            self.stderr.write("No CounselorCourse found.")
            return

        chapters = list(course.chapters.all().order_by("id"))
        out_dir.mkdir(parents=True, exist_ok=True)

        course_md = _course_markdown(
            course,
            chapters,
            use_remote_pdf=use_remote_pdf,
            base_dir=base_dir,
            content_root=content_root,
            quiz_set=quiz_set,
            video_set=video_set,
        )
        course_xm = _course_xmind(
            course,
            chapters,
            use_remote_pdf=use_remote_pdf,
            base_dir=base_dir,
            content_root=content_root,
            quiz_set=quiz_set,
            video_set=video_set,
        )
        course_payload = _payload(
            scope="course",
            markdown=course_md,
            xmind_sheets=course_xm,
            course_id=course.id,
            segment=segment,
            chapter_id=None,
            part_id=None,
            map_type=map_type,
        )
        (out_dir / "course.json").write_text(
            json.dumps(course_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        chapter_files: list[str] = []
        for ch in chapters:
            name = f"chapter_{ch.id}.json"
            chapter_files.append(name)
            pl = _payload(
                scope="chapter",
                markdown=_chapter_markdown(
                    ch,
                    chapters=chapters,
                    use_remote_pdf=use_remote_pdf,
                    base_dir=base_dir,
                    content_root=content_root,
                    quiz_set=quiz_set,
                    video_set=video_set,
                ),
                xmind_sheets=_chapter_xmind(
                    ch,
                    chapters=chapters,
                    use_remote_pdf=use_remote_pdf,
                    base_dir=base_dir,
                    content_root=content_root,
                    quiz_set=quiz_set,
                    video_set=video_set,
                ),
                course_id=course.id,
                segment=segment,
                chapter_id=ch.id,
                part_id=None,
                map_type=map_type,
            )
            (out_dir / name).write_text(json.dumps(pl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        part_files: list[str] = []
        for ch in chapters:
            for p in ch.parts.all().order_by("id"):
                name = f"part_{p.id}.json"
                part_files.append(name)
                pl = _payload(
                    scope="part",
                    markdown=_part_markdown(
                        p,
                        chapters=chapters,
                        use_remote_pdf=use_remote_pdf,
                        base_dir=base_dir,
                        content_root=content_root,
                        quiz_set=quiz_set,
                        video_set=video_set,
                    ),
                    xmind_sheets=_part_xmind(
                        p,
                        chapters=chapters,
                        use_remote_pdf=use_remote_pdf,
                        base_dir=base_dir,
                        content_root=content_root,
                        quiz_set=quiz_set,
                        video_set=video_set,
                    ),
                    course_id=course.id,
                    segment=segment,
                    chapter_id=ch.id,
                    part_id=p.id,
                    map_type=map_type,
                )
                (out_dir / name).write_text(json.dumps(pl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        html_note = ""
        html_export_meta: dict | None = None
        if content_root and not options.get("no_html"):
            html_dir = out_dir / "html"
            try:
                n_html, html_errs = export_docx_tree_to_html(content_root, html_dir)
                html_note = f" + {n_html} HTML -> {html_dir}"
                html_export_meta = {
                    "folder": "html",
                    "source_folders": ["attachments", "Quiz"],
                    "files_written": n_html,
                    "error_count": len(html_errs),
                }
                for err in html_errs[:12]:
                    self.stderr.write(self.style.WARNING(f"HTML export: {err}"))
                if len(html_errs) > 12:
                    self.stderr.write(self.style.WARNING(f"HTML export: … and {len(html_errs) - 12} more errors"))
            except ImportError as e:
                self.stderr.write(self.style.WARNING(str(e)))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"HTML export failed: {e}"))

        manifest = {
            "course_learning_url": f"http://localhost:8002/counselor/course_learning/{segment}/",
            "course_learning_url_segment": segment,
            "course_id": course.id,
            "course_title": _heading_text(course.title),
            "reference_mindmap_example": "Ag-FinTech Product Manager (XMind content.json style mirrored under xmind key)",
            "files": {
                "course": "course.json",
                "chapters": sorted(
                    chapter_files,
                    key=lambda x: int(x.replace("chapter_", "").replace(".json", "")),
                ),
                "parts": sorted(
                    part_files,
                    key=lambda x: int(x.replace("part_", "").replace(".json", "")),
                ),
            },
            "usage": {
                "markdown": "Field markdown (or md) is required; parsed by counselor_mindmap_widget.html.",
                "map_type": "tree=Markmap; concept=rings; radial=D3 radial; cluster=D3 dendrogram; career_radial=radial-mindmap.js (career detail style). URL ?map_type= overrides JSON.",
                "xmind": "Array xmind matches XMind sheet/rootTopic/children.attached shape for import or custom radial UI.",
            },
        }
        if html_export_meta is not None:
            manifest["html_export"] = html_export_meta
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(chapter_files)} chapter + {len(part_files)} part + course + manifest -> {out_dir}{html_note}"
            )
        )
