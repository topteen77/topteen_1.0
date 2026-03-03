from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        try:
            from topteens.services_status import run_startup_checks
            run_startup_checks()
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Service startup checks failed: %s", e)
