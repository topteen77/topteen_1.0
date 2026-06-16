from django.db import migrations, models

import skilllab.models


class Migration(migrations.Migration):

    dependencies = [
        ("skilllab", "0018_internationalonlinecourse"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="internationalonlinecourse",
            name="image",
        ),
        migrations.RemoveField(
            model_name="internationalonlinecourse",
            name="logo",
        ),
        migrations.AddField(
            model_name="internationalonlinecourse",
            name="image",
            field=models.ImageField(
                blank=True,
                help_text="Course card image. Leave empty to use the default placeholder.",
                max_length=250,
                null=True,
                upload_to=skilllab.models.international_course_image_directory,
            ),
        ),
        migrations.AddField(
            model_name="internationalonlinecourse",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Institute logo shown on the course card. Leave empty to use the default placeholder.",
                max_length=250,
                null=True,
                upload_to=skilllab.models.international_course_logo_directory,
            ),
        ),
    ]
