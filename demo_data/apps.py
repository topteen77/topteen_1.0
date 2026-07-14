from django.apps import AppConfig


class DemoDataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "demo_data"
    verbose_name = "Demo data"

    def ready(self):
        # Ensure Celery registers tasks even if autodiscover path differs.
        from . import tasks  # noqa: F401
