"""
Load Engagement Patterns assessment from core/four_pillars_assessments/engagement_patterns.json
into the database (FourPillarsAssessment) so it can be edited from admin.
Run: python manage.py seed_engagement_patterns_from_json
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import (
    FourPillarsAssessment,
    FourPillarsAssessmentQuestion,
    FourPillarsAssessmentQuestionOption,
    FourPillarsAssessmentProfile,
)


class Command(BaseCommand):
    help = "Seed Engagement Patterns assessment from engagement_patterns.json into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            default="engagement-patterns",
            help="Assessment slug to create/update (default: engagement-patterns)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing assessment (delete and recreate).",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        force = options["force"]
        core_dir = Path(__file__).resolve().parent.parent.parent  # core/
        json_path = core_dir / "four_pillars_assessments" / "engagement_patterns.json"
        if not json_path.exists():
            self.stderr.write(self.style.ERROR(f"JSON not found: {json_path}"))
            return
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assessment, created = FourPillarsAssessment.objects.get_or_create(
            slug=slug,
            defaults={
                "title": "Engagement Patterns",
                "subtitle": "Discovering Your Motivation and Energy Styles",
                "scoring_intro": data.get("scoring_intro", ""),
                "mixed_results": data.get("mixed_results", ""),
                "is_active": True,
            },
        )
        if not created and not force:
            self.stdout.write(self.style.WARNING(f"Assessment slug={slug} already exists. Use --force to overwrite."))
            return
        if not created and force:
            assessment.questions.all().delete()
            assessment.profiles.all().delete()
            self.stdout.write(self.style.WARNING(f"Recreated assessment slug={slug}"))
        else:
            self.stdout.write(f"Created assessment slug={slug}")
        assessment.title = "Engagement Patterns"
        assessment.subtitle = "Discovering Your Motivation and Energy Styles"
        assessment.scoring_intro = data.get("scoring_intro", "")
        assessment.mixed_results = data.get("mixed_results", "")
        assessment.is_active = True
        assessment.save()
        for i, q_data in enumerate(data.get("questions", [])):
            q = FourPillarsAssessmentQuestion.objects.create(
                assessment=assessment,
                order=i,
                title=q_data.get("title", f"Question {i + 1}"),
                text=q_data.get("text", ""),
            )
            for key, text in (q_data.get("options") or {}).items():
                if key in ("A", "B", "C", "D"):
                    FourPillarsAssessmentQuestionOption.objects.create(
                        question=q,
                        option_key=key,
                        text=text,
                    )
        for key in ("A", "B", "C", "D"):
            profile_data = (data.get("profiles") or {}).get(key, {})
            FourPillarsAssessmentProfile.objects.create(
                assessment=assessment,
                option_key=key,
                name=profile_data.get("name", ""),
                summary=profile_data.get("summary", ""),
                scoring_heading=profile_data.get("scoring_heading", ""),
                scoring_bullets=profile_data.get("scoring_bullets") or [],
            )
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {assessment.questions.count()} questions and {assessment.profiles.count()} profiles."
        ))
