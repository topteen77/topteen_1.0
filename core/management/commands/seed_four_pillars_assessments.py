"""
Seed all four Four Pillars assessments from JSON files into the database.
Run: python manage.py seed_four_pillars_assessments
Use --force to overwrite existing assessments (delete questions/profiles and re-import).
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

# Slug (URL) -> json filename and display title/subtitle
ASSESSMENT_CONFIG = {
    "learning-preferences": {
        "json": "learning_preferences.json",
        "title": "Learning Preferences Assessment",
        "subtitle": "Answer 20 short questions to discover how you learn best. Then view your personalised learning style profile.",
    },
    "natural-abilities": {
        "json": "natural_abilities.json",
        "title": "Natural Abilities Assessment",
        "subtitle": "Answer 20 short questions to discover your inherent talents and strengths. Then view your personalised natural abilities profile.",
    },
    "engagement-patterns": {
        "json": "engagement_patterns.json",
        "title": "Engagement Patterns Assessment",
        "subtitle": "Discovering Your Motivation and Energy Styles",
    },
    "interest-drivers": {
        "json": "interest_drivers.json",
        "title": "Interest Drivers Assessment",
        "subtitle": "Answer 20 short questions to discover what captivates your curiosity. Then view your personalised interest profile.",
    },
}


def seed_one(cmd, core_dir, slug, config, force):
    json_path = core_dir / "four_pillars_assessments" / config["json"]
    if not json_path.exists():
        cmd.stderr.write(cmd.style.ERROR(f"JSON not found: {json_path}"))
        return False
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    title = config["title"]
    subtitle = config.get("subtitle", "")
    assessment, created = FourPillarsAssessment.objects.get_or_create(
        slug=slug,
        defaults={
            "title": title,
            "subtitle": subtitle,
            "scoring_intro": data.get("scoring_intro", ""),
            "mixed_results": data.get("mixed_results", ""),
            "is_active": True,
        },
    )
    if not created and not force:
        cmd.stdout.write(cmd.style.WARNING(f"  {slug} already exists (use --force to overwrite)."))
        return True
    if not created and force:
        assessment.questions.all().delete()
        assessment.profiles.all().delete()
    assessment.title = title
    assessment.subtitle = subtitle
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
    cmd.stdout.write(cmd.style.SUCCESS(f"  {slug}: {assessment.questions.count()} questions, {assessment.profiles.count()} profiles."))
    return True


class Command(BaseCommand):
    help = "Seed all four Four Pillars assessments from JSON files into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing assessments (delete questions/profiles and re-import from JSON).",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Seed only this assessment slug (e.g. learning-preferences). Default: all four.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        only_slug = options.get("slug")
        core_dir = Path(__file__).resolve().parent.parent.parent  # core/
        slugs = [only_slug] if only_slug else list(ASSESSMENT_CONFIG.keys())
        if only_slug and only_slug not in ASSESSMENT_CONFIG:
            self.stderr.write(self.style.ERROR(f"Unknown slug: {only_slug}. Use one of: {list(ASSESSMENT_CONFIG.keys())}"))
            return
        for slug in slugs:
            config = ASSESSMENT_CONFIG[slug]
            seed_one(self, core_dir, slug, config, force)
        self.stdout.write(self.style.SUCCESS("Done."))
