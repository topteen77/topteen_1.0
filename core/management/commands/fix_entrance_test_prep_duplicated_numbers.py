"""
Fix duplicated numbers in Entrance Test Prep content (DOCX import artifact)
and normalize INR to prefix form only when the text already contains "INR"
(e.g. 500 INR -> INR 500). Rupee symbols (₹) are preserved, not converted to INR.

Examples: 500500 -> 500, ₹2₹2 -> ₹2, around 500 INR -> around INR 500

Updates:
  - EntranceTestPrepExam.content_html
  - EntranceTestPrepExam.content_json (string fields, recursively)
  - EntranceTestPrepExamSection.content_html
"""
from __future__ import annotations

import re
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import EntranceTestPrepExam, EntranceTestPrepExamSection

# e.g. 500500, 100100
DUPLICATE_DIGITS_RE = re.compile(r"(\d{2,})\1")

# e.g. 60−10060−100 or 250-500250-500
DUPLICATE_RANGE_RE = re.compile(r"(\d+[−–\-]\d+)\1")

# e.g. ₹2₹2 -> ₹2, &#8377;1250&#8377;1250 -> &#8377;1250 (group 1 keeps symbol+digits)
DUPLICATE_RUPEE_RE = re.compile(r"((?:&#8377;|₹)(\d+))(?:&#8377;|₹)\2")

_NBSP = r"(?:&#160;|&nbsp;|\s)"

TRAILING_INR_RE = re.compile(
    rf"(?<![A-Za-z])(\d+(?:[−–\-]\d+)?){_NBSP}+INR\b",
    re.IGNORECASE,
)

INR_IN_TEXT_RE = re.compile(r"\bINR\b", re.IGNORECASE)

INR_PREFIX_RE = re.compile(
    r"\bINR\s*(\d+(?:[−–\-]\d+)?)\b",
    re.IGNORECASE,
)

HTML_KEYS = frozenset({"html", "content", "body", "overview", "programtitle"})


def fix_duplicated_numbers_in_text(text: str) -> tuple[str, list[str]]:
    if not text or not isinstance(text, str):
        return text, []

    changes: list[str] = []
    out = text

    def _apply(pattern: re.Pattern[str], label: str, repl: str = r"\1") -> None:
        nonlocal out
        for m in pattern.finditer(out):
            replacement = m.expand(repl)
            changes.append(f"{label}: {m.group(0)!r} -> {replacement!r}")
        new_out = pattern.sub(repl, out)
        if new_out != out:
            out = new_out

    prev = None
    while prev != out:
        prev = out
        _apply(DUPLICATE_DIGITS_RE, "digits")
        _apply(DUPLICATE_RANGE_RE, "range")
        _apply(DUPLICATE_RUPEE_RE, "rupee_dup", r"\1")

    while True:
        new_out = DUPLICATE_DIGITS_RE.sub(r"\1", out)
        if new_out == out:
            break
        out = new_out

    return out, changes


def normalize_inr_prefix(text: str) -> tuple[str, list[str]]:
    """Only when 'INR' appears in text: trailing amount -> INR prefix, normalize spacing."""
    if not text or not isinstance(text, str):
        return text, []
    if not INR_IN_TEXT_RE.search(text):
        return text, []

    changes: list[str] = []
    out = text

    def _sub(pattern: re.Pattern[str], repl: str, label: str) -> None:
        nonlocal out

        def _repl(m: re.Match[str]) -> str:
            new = m.expand(repl)
            if m.group(0) != new:
                changes.append(f"{label}: {m.group(0)!r} -> {new!r}")
            return new

        out = pattern.sub(_repl, out)

    _sub(TRAILING_INR_RE, r"INR \1", "trailing_inr")
    _sub(INR_PREFIX_RE, r"INR \1", "inr_prefix")
    out = re.sub(r"\bINR\s+INR\s+", "INR ", out, flags=re.IGNORECASE)

    return out, changes


def fix_content_text(text: str) -> tuple[str, list[str]]:
    text, ch1 = fix_duplicated_numbers_in_text(text)
    text, ch2 = normalize_inr_prefix(text)
    return text, ch1 + ch2


def fix_json_value(value: Any) -> tuple[Any, list[str]]:
    all_changes: list[str] = []

    if isinstance(value, str):
        return fix_content_text(value)

    if isinstance(value, dict):
        new_dict = {}
        for k, v in value.items():
            if isinstance(v, str) and (
                k in HTML_KEYS or "html" in k.lower() or "content" in k.lower()
            ):
                fixed, ch = fix_content_text(v)
                new_dict[k] = fixed
                for c in ch:
                    all_changes.append(f"json[{k!r}] {c}")
            else:
                fixed_v, ch = fix_json_value(v)
                new_dict[k] = fixed_v
                all_changes.extend(ch)
        return new_dict, all_changes

    if isinstance(value, list):
        new_list = []
        for i, item in enumerate(value):
            fixed_item, ch = fix_json_value(item)
            new_list.append(fixed_item)
            for c in ch:
                all_changes.append(f"json[{i}] {c}")
        return new_list, all_changes

    return value, all_changes


class Command(BaseCommand):
    help = (
        "Fix duplicated numbers/rupee symbols; normalize INR prefix only where INR appears. "
        "Use --dry-run first, then --slug for one exam, then run without filters for all."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes only; do not write to the database.",
        )
        parser.add_argument(
            "--slug",
            default=None,
            help="Process a single exam by slug (for testing).",
        )
        parser.add_argument(
            "--exam-id",
            type=int,
            default=None,
            help="Process a single exam by primary key.",
        )
        parser.add_argument(
            "--name",
            default=None,
            help="Process exam(s) whose name contains this string (case-insensitive).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of exams to process (after filters).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print every replacement detail.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        slug = options.get("slug")
        exam_id = options.get("exam_id")
        name = options.get("name")
        limit = options.get("limit")

        qs = EntranceTestPrepExam.objects.all().order_by("id")
        if exam_id:
            qs = qs.filter(pk=exam_id)
        elif slug:
            qs = qs.filter(slug=slug)
        elif name:
            qs = qs.filter(name__icontains=name)

        if limit:
            qs = qs[:limit]

        if not qs.exists():
            self.stderr.write(self.style.ERROR("No exams matched the filter."))
            return

        total_scanned = 0
        total_updated = 0
        total_sections = 0

        for exam in qs:
            total_scanned += 1
            exam_changes: list[str] = []
            updates: dict[str, Any] = {}

            if exam.content_html:
                new_html, ch = fix_content_text(exam.content_html)
                if new_html != exam.content_html:
                    updates["content_html"] = new_html
                    exam_changes.extend([f"content_html: {c}" for c in ch])

            if exam.content_json:
                new_json, ch = fix_json_value(exam.content_json)
                if new_json != exam.content_json:
                    updates["content_json"] = new_json
                    exam_changes.extend(ch)

            section_updates = []
            for sec in exam.sections.all():
                if not sec.content_html:
                    continue
                new_sec_html, ch = fix_content_text(sec.content_html)
                if new_sec_html != sec.content_html:
                    section_updates.append((sec, new_sec_html, ch))

            if not exam_changes and not section_updates:
                continue

            total_updated += 1
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"Exam [{exam.id}] {exam.name} (slug={exam.slug})")
            )
            if dry_run:
                self.stdout.write(self.style.WARNING("  [DRY RUN] would update:"))

            if verbose or dry_run:
                for line in exam_changes:
                    self.stdout.write(f"    {line}")

            for sec, _new_html, ch in section_updates:
                total_sections += 1
                self.stdout.write(f"    section {sec.section_id!r} (id={sec.id})")
                if verbose or dry_run:
                    for c in ch:
                        self.stdout.write(f"      {c}")

            if dry_run:
                continue

            with transaction.atomic():
                if updates:
                    for field, value in updates.items():
                        setattr(exam, field, value)
                    exam.save(update_fields=list(updates.keys()))
                for sec, new_html, _ in section_updates:
                    sec.content_html = new_html
                    sec.save(update_fields=["content_html"])

            self.stdout.write(self.style.SUCCESS("  Saved."))

        self.stdout.write("")
        self.stdout.write(
            f"Scanned {total_scanned} exam(s); "
            f"{'would update' if dry_run else 'updated'} {total_updated} exam(s), "
            f"{total_sections} inline section(s)."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no DB changes."))
