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
