
from django.db import migrations, models
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),  # Ensure this points to your initial migration
    ]

    operations = [
        migrations.AddField(
            model_name='testcompletion',
            name='user',
            field=models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
