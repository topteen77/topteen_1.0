"""
Export counselor course structure to JSON mindmaps (Markmap markdown + XMind-style tree).

Writes under a folder such as ../coursemindmap/14/ (sibling of topteen_1.0 by default):
  course.json, chapter_<id>.json, part_<id>.json, manifest.json

Example:
  python manage.py export_course_mindmap_json --segment 14
  python manage.py export_course_mindmap_json --segment 14 --out-dir /path/to/coursemindmap/14

Copy selected files to counselor/static/counselor/mindmaps/ if you use the built-in mindmap widget
(course.json must be that exact name there; chapter/part files use chapter_<id>.json / part_<id>.json).

Each JSON may include map_type: tree, concept, radial, cluster, career_radial (reuse careers radial-mindmap.js).
Override via ?map_type= / ?mindmap_type= on the page URL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand

from counselor.models import Chapter, CounselorCourse, Part

STRUCT_LEAF = "org.xmind.ui.logic.right"
STRUCT_ROOT_MAP = "org.xmind.ui.map.unbalanced"


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


def _course_markdown(course: CounselorCourse, chapters: list[Chapter]) -> str:
    lines = [f"# {_heading_text(course.title)}"]
    for ch in chapters:
        lines.append(f"## {_heading_text(ch.title)}")
        for p in ch.parts.all().order_by("id"):
            lines.append(f"### {_heading_text(p.title)}")
    return "\n".join(lines) + "\n"


def _course_xmind(course: CounselorCourse, chapters: list[Chapter]) -> list[dict]:
    branches = []
    for ch in chapters:
        part_nodes = [
            _xmind_leaf(_heading_text(p.title), "course", str(ch.id), "p", str(p.id))
            for p in ch.parts.all().order_by("id")
        ]
        branches.append(_xmind_branch(_heading_text(ch.title), part_nodes, "course", "ch", str(ch.id)))
    return [_sheet("course", _heading_text(course.title), _heading_text(course.title), branches)]


def _chapter_markdown(ch: Chapter) -> str:
    lines = [f"# {_heading_text(ch.title)}"]
    for p in ch.parts.all().order_by("id"):
        lines.append(f"## {_heading_text(p.title)}")
    return "\n".join(lines) + "\n"


def _chapter_xmind(ch: Chapter) -> list[dict]:
    branches = []
    for p in ch.parts.all().order_by("id"):
        bullets = _description_bullets(getattr(p, "description", None))
        if bullets:
            leaves = [_xmind_leaf(b, "ch", str(ch.id), "p", str(p.id), "b", str(i)) for i, b in enumerate(bullets)]
            branches.append(_xmind_branch(_heading_text(p.title), leaves, "ch", str(ch.id), "p", str(p.id)))
        else:
            branches.append(_xmind_leaf(_heading_text(p.title), "ch", str(ch.id), "p", str(p.id)))
    return [_sheet(f"chapter_{ch.id}", _heading_text(ch.title), _heading_text(ch.title), branches)]


def _part_markdown(part: Part) -> str:
    title = _heading_text(part.title)
    lines = [f"# {title}"]
    bullets = _description_bullets(part.description)
    if bullets:
        lines.append("## Key points")
        for b in bullets:
            lines.append(f"- {b}")
    return "\n".join(lines) + "\n"


def _part_xmind(part: Part) -> list[dict]:
    bullets = _description_bullets(part.description)
    if bullets:
        leaves = [_xmind_leaf(b, "part", str(part.id), "pt", str(i)) for i, b in enumerate(bullets)]
        branches = [_xmind_branch("Key points", leaves, "part", str(part.id), "kp")]
    else:
        branches = [_xmind_leaf("Add outline in Admin (part description)", "part", str(part.id), "placeholder")]
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

    def handle(self, *args, **options):
        segment: int = options["segment"]
        map_type: str = options["map_type"]
        out_raw = (options.get("out_dir") or "").strip()
        if out_raw:
            out_dir = Path(out_raw).resolve()
        else:
            base = Path(__file__).resolve().parents[4]
            out_dir = (base / "coursemindmap" / str(segment)).resolve()

        course = CounselorCourse.objects.prefetch_related("chapters__parts").order_by("id").first()
        if not course:
            self.stderr.write("No CounselorCourse found.")
            return

        chapters = list(course.chapters.all().order_by("id"))
        out_dir.mkdir(parents=True, exist_ok=True)

        course_md = _course_markdown(course, chapters)
        course_xm = _course_xmind(course, chapters)
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
                markdown=_chapter_markdown(ch),
                xmind_sheets=_chapter_xmind(ch),
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
                    markdown=_part_markdown(p),
                    xmind_sheets=_part_xmind(p),
                    course_id=course.id,
                    segment=segment,
                    chapter_id=ch.id,
                    part_id=p.id,
                    map_type=map_type,
                )
                (out_dir / name).write_text(json.dumps(pl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(chapter_files)} chapter + {len(part_files)} part + course + manifest -> {out_dir}"))
