from django.apps import AppConfig


class UserAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_analytics'
    verbose_name = 'User Analytics'

    def ready(self):
        """Import signals when app is ready"""
        import user_analytics.signals  # noqa
