# Remove guide_content - assessment pages no longer show long guide section

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_assessment_guide_content'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fourpillarsassessment',
            name='guide_content',
        ),
    ]
