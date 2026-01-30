# Generated manually for enhanced journey tracking

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user_analytics', '0004_userjourney_ga4_client_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userjourney',
            name='is_registered',
            field=models.BooleanField(db_index=True, default=False, help_text='User registered during this journey'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='has_payment',
            field=models.BooleanField(db_index=True, default=False, help_text='User made a payment during this journey'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='has_psychometric_test',
            field=models.BooleanField(db_index=True, default=False, help_text='User started psychometric test during this journey'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='test_completed',
            field=models.BooleanField(db_index=True, default=False, help_text='User completed psychometric test during this journey'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='result_generated',
            field=models.BooleanField(db_index=True, default=False, help_text='Psychometric test result was generated during this journey'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='registration_event',
            field=models.ForeignKey(blank=True, help_text='User registration event', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registration_journeys', to='user_analytics.userevent'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='payment_event',
            field=models.ForeignKey(blank=True, help_text='Payment event', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_journeys', to='user_analytics.userevent'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='psychometric_test_event',
            field=models.ForeignKey(blank=True, help_text='Psychometric test started event', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='psychometric_test_journeys', to='user_analytics.userevent'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='test_completion_event',
            field=models.ForeignKey(blank=True, help_text='Test completion event', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='test_completion_journeys', to='user_analytics.userevent'),
        ),
        migrations.AddField(
            model_name='userjourney',
            name='result_generation_event',
            field=models.ForeignKey(blank=True, help_text='Result generation event', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='result_generation_journeys', to='user_analytics.userevent'),
        ),
    ]
