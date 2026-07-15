import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import logging

        for noisy_logger in ('matplotlib', 'PIL', 'urllib3', 'botocore', 'boto3'):
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

        try:
            from topteens.services_status import run_startup_checks
            run_startup_checks()
        except Exception as e:
            logger.exception("Service startup checks failed: %s", e)

        # Apply DAILY_USER_REPORT_TIME from DB to Celery beat (HH:MM = IST when CELERY_TIMEZONE=Asia/Kolkata).
        try:
            from celery.schedules import crontab

            from core.models import Configuration
            from topteens.celery import app

            raw = str(Configuration.get('DAILY_USER_REPORT_TIME', default='15:00', editable=True)).strip()
            hour_str, minute_str = raw.split(':', 1)
            hour, minute = int(hour_str), int(minute_str)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError('invalid hour/minute')
            app.conf.beat_schedule['send-daily-new-user-report'] = {
                'task': 'user_analytics.tasks.send_daily_new_user_report',
                'schedule': crontab(minute=minute, hour=hour),
            }
        except Exception as e:
            logger.debug('Daily report beat schedule not patched from Configuration: %s', e)

        try:
            from core.admin_hub import register_admin_hub_urls
            register_admin_hub_urls()
        except Exception as e:
            logger.exception('Failed to register admin hub URLs: %s', e)

        # Invalidate cached dashboard config when the admin edits the rule tables.
        try:
            from django.db.models.signals import post_delete, post_save

            from core.dashboard_cache import invalidate_dashboard_config_cache
            from core.models import (
                DashboardLevelBand,
                DashboardPointRule,
                DashboardTrophyDefinition,
            )

            for model in (DashboardPointRule, DashboardTrophyDefinition, DashboardLevelBand):
                post_save.connect(
                    invalidate_dashboard_config_cache,
                    sender=model,
                    dispatch_uid=f'dashcfg_invalidate_save_{model.__name__}',
                )
                post_delete.connect(
                    invalidate_dashboard_config_cache,
                    sender=model,
                    dispatch_uid=f'dashcfg_invalidate_delete_{model.__name__}',
                )
        except Exception as e:
            logger.debug('Dashboard config cache invalidation not wired: %s', e)
