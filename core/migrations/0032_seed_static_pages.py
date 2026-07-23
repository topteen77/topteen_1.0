# Data migration: seed StaticPage rows for the 11 static routes

from django.db import migrations


def seed_static_pages(apps, schema_editor):
    StaticPage = apps.get_model("core", "StaticPage")
    for key in [
        "terms",
        "privacy",
        "contact",
        "about",
        "career_planning",
        "career_planning_4_year",
        "career_planning_class_9",
        "career_planning_class_10",
        "career_planning_class_11",
        "career_planning_class_12",
        "emotional_intelligences",
        "multiple_intelligences",
        "four_pillars",
    ]:
        StaticPage.objects.get_or_create(
            url_key=key,
            defaults={"title": key.replace("_", " ").title(), "is_active": True},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_static_page_cms_page_seo"),
    ]

    operations = [
        migrations.RunPython(seed_static_pages, noop),
    ]
