from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_student_education_audience'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrendingExam',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField(default=1, help_text='Lower numbers appear first.')),
                ('summary', models.CharField(blank=True, help_text='Short line on the widget. Leave blank to use text from the exam page.', max_length=400)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('exam', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trending_entry', to='core.entrancetestprepexam')),
            ],
            options={
                'verbose_name': 'Trending exam',
                'verbose_name_plural': 'Trending exams',
                'ordering': ('position', 'id'),
            },
        ),
    ]
