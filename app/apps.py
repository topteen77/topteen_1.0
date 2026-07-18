from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        # Register Celery tasks (module is app.task, not app.tasks).
        try:
            from . import task  # noqa: F401
        except Exception:
            pass

