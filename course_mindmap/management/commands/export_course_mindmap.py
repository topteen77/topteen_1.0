from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from course_mindmap.registry import course_type_choices, get_adapter
from course_mindmap.service import (
    delete_complete_course_mindmap,
    generate_mindmaps,
    validate_course_mindmaps,
)


class Command(BaseCommand):
    help = "Generate or validate course mindmaps (DB storage). GUI: Django admin → Course mindmap generations → Generate."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-type",
            type=str,
            default="skilllab",
            help="Registry key or alias: skilllab → skilllab.skilllabcourse",
        )
        parser.add_argument("--slug", type=str, default="", help="Course slug (SkillLab)")
        parser.add_argument("--id", type=int, default=0, help="Course primary key")
        parser.add_argument("--dry-run", action="store_true", help="Build without saving to DB")
        parser.add_argument("--validate-only", action="store_true", help="Validate existing DB rows only")
        parser.add_argument("--map-type", type=str, default="", help="Map type override (1-9 or name)")
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete complete mindmap (data + config + generation logs) for the course",
        )

    def _resolve_course_type_key(self, raw: str) -> str:
        aliases = {"skilllab": "skilllab.skilllabcourse"}
        if raw in aliases:
            return aliases[raw]
        valid = {k for k, _ in course_type_choices()}
        if raw in valid:
            return raw
        raise CommandError(f"Unknown course type {raw!r}. Choices: {sorted(valid)}")

    def handle(self, *args, **options):
        course_type_key = self._resolve_course_type_key(options["course_type"])
        adapter = get_adapter(course_type_key)

        course = None
        if options["id"]:
            course = adapter.get_course_by_id(options["id"])
        elif options["slug"]:
            course = adapter.get_course_queryset().filter(slug=options["slug"]).first()

        if not course:
            raise CommandError("Course not found. Pass --slug or --id.")

        if options["delete"]:
            ct = adapter.content_type()
            totals = delete_complete_course_mindmap(content_type=ct, object_id=course.pk)
            self.stdout.write(self.style.SUCCESS(f"Deleted complete mindmap: {totals}"))
            return

        if options["validate_only"]:
            result = validate_course_mindmaps(course_type_key, course.pk)
            self.stdout.write(self.style.SUCCESS(str(result)))
            if result.get("errors"):
                raise CommandError("Validation failed")
            return

        dry_run = options["dry_run"]
        gen = generate_mindmaps(
            course_type_key=course_type_key,
            course_id=course.pk,
            dry_run=dry_run,
            map_type=options.get("map_type") or "",
        )
        report = gen.report or {}
        self.stdout.write(f"Status: {gen.status} (dry_run={dry_run})")
        self.stdout.write(f"Scopes: {report.get('valid_total')}/{report.get('total')} valid")
        counts = report.get("counts") or {}
        self.stdout.write(
            f"  course={counts.get('course', 0)} chapter={counts.get('chapter', 0)} section={counts.get('section', 0)}"
        )
        for w in report.get("warnings") or []:
            self.stdout.write(self.style.WARNING(f"  warn: {w}"))
        for e in report.get("errors") or []:
            self.stdout.write(self.style.ERROR(f"  err: {e}"))
        if gen.status == "failed":
            raise CommandError(gen.error_message or "Generation failed")
