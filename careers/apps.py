from django.apps import AppConfig


class CareersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "careers"

    def ready(self):
        # Register cache invalidation signals
        from careers import signals  # noqa: F401
