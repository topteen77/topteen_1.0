from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_urlindexrule'),
    ]

    operations = [
        migrations.CreateModel(
            name='VocationalCourseReasoningMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('object_status', models.SmallIntegerField(choices=[(0, 'Deleted'), (1, 'Active'), (2, 'Inactive')], default=1)),
                ('reasoning_area', models.CharField(choices=[('NUMERICAL', 'Numerical'), ('VERBAL', 'Verbal'), ('LOGICAL', 'Logical'), ('MECHANICAL', 'Mechanical'), ('SPATIAL', 'Spatial'), ('LANGUAGE', 'Language'), ('CRITICAL', 'Critical')], db_index=True, max_length=20)),
                ('priority', models.PositiveSmallIntegerField(default=1, help_text='Lower value = preferred when multiple courses map to the same reasoning area.')),
                ('vocational_course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reasoning_mappings', to='core.vocationalcourse')),
            ],
            options={
                'verbose_name': 'Vocational Course Reasoning Mapping',
                'verbose_name_plural': 'Vocational Course Reasoning Mappings',
                'ordering': ('reasoning_area', 'priority', 'vocational_course__name'),
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='vocationalcoursereasoningmapping',
            constraint=models.UniqueConstraint(fields=('vocational_course', 'reasoning_area'), name='unique_vocational_course_reasoning_area'),
        ),
    ]
