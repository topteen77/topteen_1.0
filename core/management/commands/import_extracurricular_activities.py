from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.models import ExtracurricularActivity, ExtracurricularActivityCategory


class Command(BaseCommand):
    help = "Import extracurricular categories/activities from the static HTML file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--html",
            dest="html_path",
            default="/home/itpc6/Public/django/git-repo/7nov/topteenhtml/html/extracurricular-activities.html",
            help="Absolute path to extracurricular-activities.html",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing extracurricular categories/activities before importing",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        html_path = Path(options["html_path"])
        replace = bool(options["replace"])

        if not html_path.exists():
            raise SystemExit(f"HTML file not found: {html_path}")

        html = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select(".activity-cards .activity-item")
        if not cards:
            self.stdout.write(self.style.WARNING("No activity cards found in HTML (selector: .activity-cards .activity-item)"))
            return

        if replace:
            ExtracurricularActivity.objects.all().delete()
            ExtracurricularActivityCategory.objects.all().delete()

        created_categories = 0
        created_activities = 0

        for idx, card in enumerate(cards, start=1):
            # Category title + icon
            h3 = card.select_one(".card-header h3")
            if not h3:
                continue

            icon = h3.find("i")
            icon_class = (icon.get("class") if icon else None) or []
            # icon_class may be list like ['bx','bx-brain']
            icon_class_str = " ".join(icon_class).strip() if isinstance(icon_class, (list, tuple)) else str(icon_class).strip()
            icon_class_str = icon_class_str or "bx bx-star"

            # category name = text of h3 without the icon
            if icon:
                icon.extract()
            category_name = h3.get_text(strip=True)
            if not category_name:
                continue

            # css class hint (e.g. academic/sports/arts/technology/etc)
            css_class = ""
            for cls in (card.get("class") or []):
                if cls in {"academic", "sports", "arts", "leadership", "technology", "international"}:
                    css_class = cls
                    break

            cat = ExtracurricularActivityCategory.objects.filter(name__iexact=category_name).first()
            if not cat:
                cat = ExtracurricularActivityCategory.objects.create(
                    name=category_name,
                    icon_class=icon_class_str,
                    css_class=css_class,
                    priority=idx,
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_categories += 1
            else:
                cat.name = category_name
                cat.icon_class = icon_class_str
                cat.css_class = css_class
                cat.priority = idx
                cat.object_status = choices.ObjectStatus.ACTIVE
                cat.save()

            # Replace activities under the category (idempotent)
            ExtracurricularActivity.objects.filter(category=cat).delete()

            items = card.select(".activity-list li a")
            for a_idx, a in enumerate(items, start=1):
                name = a.get_text(" ", strip=True)
                if not name:
                    continue

                href = (a.get("href") or "").strip()
                url = None
                if href and href not in {"#", "javascript:void(0)", "javascript:void(0);"}:
                    url = href

                ExtracurricularActivity.objects.create(
                    category=cat,
                    name=name,
                    url=url,
                    priority=a_idx,
                    object_status=choices.ObjectStatus.ACTIVE,
                )
                created_activities += 1

        self.stdout.write(self.style.SUCCESS(
            f"Imported extracurricular activities from {html_path}. "
            f"Categories created: {created_categories}, Activities created: {created_activities}."
        ))


