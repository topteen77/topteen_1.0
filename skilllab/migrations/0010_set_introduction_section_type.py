# Generated migration to set section_type for existing records

from django.db import migrations


def set_introduction_type(apps, schema_editor):
    """Set section_type='introduction' for first section (order=0) of each chapter."""
    SkillLabChapterSection = apps.get_model('skilllab', 'SkillLabChapterSection')
    for chapter_id in SkillLabChapterSection.objects.values_list('chapter_id', flat=True).distinct():
        SkillLabChapterSection.objects.filter(
            chapter_id=chapter_id, order=0
        ).update(section_type='introduction')


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('skilllab', '0009_add_section_type'),
    ]

    operations = [
        migrations.RunPython(set_introduction_type, reverse_noop),
    ]
