from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Category, Course, Stream
from app.riasec_report_utils import normalize_career_pathways_mode


class Command(BaseCommand):
    help = "Sync Category, Course, and Stream records from RIASEC.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="json_path",
            default=str(Path(settings.BASE_DIR) / "RIASEC.json"),
            help="Path to RIASEC.json (default: project root RIASEC.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database",
        )

    def handle(self, *args, **options):
        json_path = Path(options["json_path"])
        dry_run = bool(options["dry_run"])

        if not json_path.exists():
            raise SystemExit(f"RIASEC JSON file not found: {json_path}")

        with json_path.open(encoding="utf-8") as handle:
            entries = json.load(handle)

        if not isinstance(entries, list):
            raise SystemExit("RIASEC JSON must be a list of category objects.")

        created = updated = 0
        course_count = stream_count = 0

        sync_fn = self._sync_entry if not dry_run else self._validate_entry

        with transaction.atomic():
            for entry in entries:
                result = sync_fn(entry)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                course_count += len(self._course_names(entry))
                stream_count += len(entry.get("streams") or {})

            if dry_run:
                transaction.set_rollback(True)

        mode = "Dry run" if dry_run else "Sync complete"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {len(entries)} categories "
                f"({created} created, {updated} updated), "
                f"{course_count} courses, {stream_count} streams "
                f"from {json_path}"
            )
        )

    def _validate_entry(self, entry):
        self._require_fields(entry)
        for stream_name, stream_data in (entry.get("streams") or {}).items():
            label = self._stream_label(stream_name, stream_data)
            if not label:
                raise SystemExit(
                    f"Category {entry.get('category')} stream {stream_name} is missing a label"
                )
        return "updated"

    def _sync_entry(self, entry):
        self._require_fields(entry)

        code = entry["category"].upper()
        category_obj, was_created = Category.objects.update_or_create(
            category=code,
            defaults={
                "fullname": entry["fullname"],
                "summary": entry["summary"],
                "fields": entry["fields"],
                "best_colleges": entry.get("best_colleges") or "",
                "career_pathways_mode": normalize_career_pathways_mode(
                    entry.get("career_pathways_mode")
                ),
            },
        )

        category_obj.courses.all().delete()
        category_obj.streams.all().delete()

        for course_name in self._course_names(entry):
            Course.objects.create(category=category_obj, course_name=course_name)

        for stream_name, stream_data in (entry.get("streams") or {}).items():
            stream_key = str(stream_name).strip()
            career_options = self._stream_career_options(entry, stream_key)
            Stream.objects.create(
                category=category_obj,
                stream_name=stream_key,
                subjects=self._stream_label(stream_name, stream_data),
                career_options=career_options,
            )

        return "created" if was_created else "updated"

    def _stream_career_options(self, entry, stream_key):
        stream_careers = entry.get("stream_careers") or {}
        if stream_key in stream_careers:
            return [
                str(item).strip()
                for item in stream_careers[stream_key]
                if str(item).strip()
            ]
        _label, careers = self._parse_legacy_stream((entry.get("streams") or {}).get(stream_key))
        if careers and not _label:
            return careers
        return []

    def _course_names(self, entry) -> list[str]:
        mode = normalize_career_pathways_mode(entry.get("career_pathways_mode"))
        if entry.get("courses"):
            return self._dedupe_names(
                str(item).strip() for item in entry["courses"] if str(item).strip()
            )

        stream_careers = entry.get("stream_careers") or {}
        if stream_careers:
            if mode == Category.CAREER_PATHWAYS_COMBINED:
                first_careers = next(iter(stream_careers.values()), [])
                return self._dedupe_names(
                    str(item).strip() for item in first_careers if str(item).strip()
                )
            names: list[str] = []
            for careers in stream_careers.values():
                names.extend(str(item).strip() for item in careers if str(item).strip())
            return self._dedupe_names(names)

        names = []
        for _stream_name, stream_data in (entry.get("streams") or {}).items():
            _label, careers = self._parse_legacy_stream(stream_data)
            names.extend(careers)
        return self._dedupe_names(names)

    def _dedupe_names(self, names) -> list[str]:
        seen: list[str] = []
        for name in names:
            if name and name not in seen:
                seen.append(name)
        return seen

    def _stream_label(self, stream_name, stream_data) -> str:
        label, _careers = self._parse_legacy_stream(stream_data)
        return label or str(stream_name).strip()

    def _parse_legacy_stream(self, stream_data):
        if isinstance(stream_data, dict):
            label = str(stream_data.get("label") or stream_data.get("name") or "").strip()
            careers = stream_data.get("careers") or stream_data.get("options") or []
            if isinstance(careers, str):
                careers = [item.strip() for item in careers.split(",") if item.strip()]
            return label, [str(item).strip() for item in careers if str(item).strip()]

        if isinstance(stream_data, list):
            if len(stream_data) == 1 and self._looks_like_subject_label(stream_data[0]):
                return str(stream_data[0]).strip(), []
            careers = [str(item).strip() for item in stream_data if str(item).strip()]
            return "", careers

        return str(stream_data).strip(), []

    def _looks_like_subject_label(self, value) -> bool:
        text = str(value).strip()
        if not text:
            return False
        subject_markers = (
            "Physics",
            "Commerce",
            "Humanities",
            "Fine Arts",
            "Biology",
            "Mathematics",
            "Science",
        )
        return any(marker in text for marker in subject_markers) and len(text) < 80

    def _require_fields(self, entry):
        missing = [field for field in ("category", "fullname", "summary", "fields") if not entry.get(field)]
        if missing:
            code = entry.get("category", "?")
            raise SystemExit(f"Category {code} is missing required fields: {', '.join(missing)}")
