from django.db import migrations, models


def import_international_courses(apps, schema_editor):
    InternationalOnlineCourse = apps.get_model("skilllab", "InternationalOnlineCourse")
    from skilllab.international_courses_data import INTERNATIONAL_COURSES

    for priority, course in enumerate(INTERNATIONAL_COURSES):
        InternationalOnlineCourse.objects.create(
            title=course["title"],
            description=course["description"],
            url=course["url"],
            image=course.get("image", "images_new/thirdparty/course-img-1.png"),
            logo=course.get("logo", "images_new/thirdparty/logo.png"),
            subject=course["subject"],
            institute=course["institute"],
            priority=priority,
        )


def remove_international_courses(apps, schema_editor):
    InternationalOnlineCourse = apps.get_model("skilllab", "InternationalOnlineCourse")
    InternationalOnlineCourse.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("skilllab", "0017_add_db_indexes_optimize_queries"),
    ]

    operations = [
        migrations.CreateModel(
            name="InternationalOnlineCourse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                ("object_status", models.SmallIntegerField(choices=[(1, "Active"), (2, "Deleted")], default=1)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("url", models.URLField(max_length=500)),
                (
                    "image",
                    models.CharField(
                        default="images_new/thirdparty/course-img-1.png",
                        help_text="Static image path, e.g. images_new/thirdparty/course-img-1.png",
                        max_length=255,
                    ),
                ),
                (
                    "logo",
                    models.CharField(
                        default="images_new/thirdparty/logo.png",
                        help_text="Static logo path for the institute",
                        max_length=255,
                    ),
                ),
                ("subject", models.CharField(db_index=True, max_length=120)),
                ("institute", models.CharField(db_index=True, max_length=120)),
                ("priority", models.PositiveIntegerField(default=0, help_text="Lower values appear first")),
            ],
            options={
                "verbose_name": "International Online Course",
                "verbose_name_plural": "International Online Courses",
                "ordering": ["priority", "title"],
                "indexes": [models.Index(fields=["subject", "institute"], name="skilllab_in_subject_8f3a21_idx")],
            },
        ),
        migrations.RunPython(import_international_courses, remove_international_courses),
    ]
