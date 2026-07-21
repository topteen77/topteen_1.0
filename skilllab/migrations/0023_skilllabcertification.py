from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('skilllab', '0022_add_fk_and_query_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='SkillLabCertification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('object_status', models.SmallIntegerField(choices=[(1, 'Active'), (2, 'Deleted')], default=1)),
                ('certificate_code', models.CharField(blank=True, max_length=12, null=True)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('skilllab_course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certifications', to='skilllab.skilllabcourse')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skilllab_certifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Skill Lab Certification',
                'verbose_name_plural': 'Skill Lab Certifications',
                'indexes': [models.Index(fields=['user', 'skilllab_course'], name='skilllab_sk_user_id_8a4f2e_idx')],
                'unique_together': {('user', 'skilllab_course')},
            },
        ),
    ]
