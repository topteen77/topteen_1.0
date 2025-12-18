from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.models import VocationalCourse, VocationalCourseCategory


def _normalize_html(s: str) -> str:
    if not s:
        return s
    while "&amp;amp;" in s:
        s = s.replace("&amp;amp;", "&amp;")
    return s


def _extract_body_inner_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if not body:
        return ""
    inner = "".join(str(x) for x in body.contents)
    return _normalize_html(inner.strip())


class Command(BaseCommand):
    help = "Import vocational course detail HTML (.txt) files into DB using folder structure as categories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="/home/itpc6/Public/django/git-repo/7nov/topteenhtml/content- Topteen/html/vocational courses",
            help="Absolute path to the converted vocational courses html folder",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Hard-delete existing vocational categories/courses before importing",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_dir = Path(options["source"])
        replace = bool(options["replace"])

        if not source_dir.exists():
            raise SystemExit(f"Source directory not found: {source_dir}")

        if replace:
            # Soft-delete is enabled in BaseModel manager; use base_manager for real delete.
            VocationalCourse._base_manager.all().delete()
            VocationalCourseCategory._base_manager.all().delete()

        txt_files = sorted(source_dir.rglob("*.txt"))
        if not txt_files:
            self.stdout.write(self.style.WARNING("No .txt files found to import."))
            return

        def get_or_create_category(path_parts: list[str]) -> VocationalCourseCategory:
            parent = None
            for idx, part in enumerate(path_parts, start=1):
                name = part.strip()
                if not name:
                    continue
                cat = VocationalCourseCategory._base_manager.filter(
                    name__iexact=name,
                    parent=parent,
                ).first()
                if not cat:
                    cat = VocationalCourseCategory.objects.create(
                        name=name,
                        parent=parent,
                        priority=idx,
                        object_status=choices.ObjectStatus.ACTIVE,
                    )
                else:
                    # keep ordering stable
                    cat.object_status = choices.ObjectStatus.ACTIVE
                    cat.save()
                parent = cat
            return parent

        created_courses = 0
        updated_courses = 0
        created_categories = 0

        # Cache categories by (parent_id, lower_name)
        cat_cache: dict[tuple[int | None, str], VocationalCourseCategory] = {}

        def get_cat(name: str, parent: VocationalCourseCategory | None, priority: int) -> VocationalCourseCategory:
            nonlocal created_categories
            key = (parent.id if parent else None, name.strip().lower())
            if key in cat_cache:
                return cat_cache[key]
            existing = VocationalCourseCategory._base_manager.filter(name__iexact=name, parent=parent).first()
            if existing:
                existing.priority = priority
                existing.object_status = choices.ObjectStatus.ACTIVE
                existing.save()
                cat_cache[key] = existing
                return existing
            created = VocationalCourseCategory.objects.create(
                name=name,
                parent=parent,
                priority=priority,
                object_status=choices.ObjectStatus.ACTIVE,
            )
            created_categories += 1
            cat_cache[key] = created
            return created

        for txt_path in txt_files:
            rel = txt_path.relative_to(source_dir)
            # Skip list files
            if rel.name.lower().startswith("list of courses"):
                continue

            # Categories are all parent dirs of the file
            parts = list(rel.parts[:-1])
            parent = None
            for i, part in enumerate(parts, start=1):
                parent = get_cat(part, parent, i)

            if parent is None:
                # file at root without category folder — skip
                continue

            course_name = txt_path.stem.strip()
            raw = txt_path.read_text(encoding="utf-8", errors="ignore")
            content_html = _extract_body_inner_html(raw)
            if not content_html:
                continue

            course = VocationalCourse.objects.filter(category=parent, name__iexact=course_name).first()
            if not course:
                VocationalCourse.objects.create(
                    category=parent,
                    name=course_name,
                    content_html=content_html,
                    priority=1,
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_courses += 1
            else:
                course.name = course_name
                course.content_html = content_html
                course.object_status = choices.ObjectStatus.ACTIVE
                course.save()
                updated_courses += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported vocational course details. "
                f"Categories created: {created_categories}. "
                f"Courses created: {created_courses}, updated: {updated_courses}."
            )
        )


