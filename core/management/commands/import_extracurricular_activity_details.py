from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.models import ExtracurricularActivity, ExtracurricularActivityCategory


def _normalize_html(s: str) -> str:
    if not s:
        return s
    # Fix common double-escaped sequences produced by converter + Word content
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
    help = "Import extracurricular activity detail HTML from converted .txt files into DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="/home/itpc6/Public/django/git-repo/7nov/topteenhtml/content- Topteen/extracurricular activities/html",
            help="Absolute path to the converted extracurricular activities html folder",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing extracurricular categories/activities before importing",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_dir = Path(options["source"])
        replace = bool(options["replace"])

        if not source_dir.exists():
            raise SystemExit(f"Source directory not found: {source_dir}")

        # Map category name → (css_class, icon_class)
        cat_meta = {
            "Academic & Competitive Activities": ("academic", "bx bx-brain"),
            "Sports & Physical Activities": ("sports", "bx bx-football"),
            "Arts & Cultural Pursuits": ("arts", "bx bx-palette"),
            "Community Service, Leadership & Social Initiatives": ("leadership", "bx bx-group"),
            "Technology, Innovation & Entrepreneurship": ("technology", "bx bx-code-alt"),
            "Cultural & Language Clubs": ("arts", "bx bx-world"),
            "Other Enriching Activities": ("international", "bx bx-globe"),
            "International Extracurricular Activities": ("technology", "bx bx-bulb"),
        }

        if replace:
            # These models use soft-delete by default; for a true replace we must hard-delete.
            ExtracurricularActivity._base_manager.all().delete()
            ExtracurricularActivityCategory._base_manager.all().delete()

        created_categories = 0
        created_activities = 0
        updated_activities = 0

        # categories are subfolders; root also has "list of activities.txt"
        category_dirs = sorted([p for p in source_dir.iterdir() if p.is_dir() and p.name != "__pycache__"])

        for c_idx, cat_dir in enumerate(category_dirs, start=1):
            cat_name = cat_dir.name.strip()
            css_class, icon_class = cat_meta.get(cat_name, ("", "bx bx-star"))

            cat = ExtracurricularActivityCategory.objects.filter(name__iexact=cat_name).first()
            if not cat:
                cat = ExtracurricularActivityCategory.objects.create(
                    name=cat_name,
                    css_class=css_class,
                    icon_class=icon_class,
                    priority=c_idx,
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_categories += 1
            else:
                cat.name = cat_name
                cat.css_class = css_class
                cat.icon_class = icon_class
                cat.priority = c_idx
                cat.object_status = choices.ObjectStatus.ACTIVE
                cat.save()

            txt_files = sorted([p for p in cat_dir.glob("*.txt") if p.is_file()])
            for a_idx, txt_path in enumerate(txt_files, start=1):
                # Skip lock/temp artifacts if any
                if txt_path.name.startswith("~$"):
                    continue

                activity_name = txt_path.stem.strip()
                raw = txt_path.read_text(encoding="utf-8", errors="ignore")
                content_html = _extract_body_inner_html(raw)
                if not content_html:
                    continue

                act = ExtracurricularActivity.objects.filter(category=cat, name__iexact=activity_name).first()
                if not act:
                    ExtracurricularActivity.objects.create(
                        category=cat,
                        name=activity_name,
                        content_html=content_html,
                        priority=a_idx,
                        object_status=choices.ObjectStatus.ACTIVE,
                    )
                    created_activities += 1
                else:
                    act.name = activity_name
                    act.content_html = content_html
                    act.priority = a_idx
                    act.object_status = choices.ObjectStatus.ACTIVE
                    # keep act.url as-is if already set
                    act.save()
                    updated_activities += 1

        # Also hide any categories not present in the source dir (optional safety)
        # (We won't delete them unless --replace.)
        # Optional: mark any categories not present in source as inactive (no hard deletes unless --replace).
        ExtracurricularActivityCategory._base_manager.exclude(
            name__in=[p.name for p in category_dirs]
        ).update(object_status=choices.ObjectStatus.INACTIVE)

        self.stdout.write(
            self.style.SUCCESS(
                "Imported extracurricular activity details. "
                f"Categories created: {created_categories}. "
                f"Activities created: {created_activities}, updated: {updated_activities}."
            )
        )


