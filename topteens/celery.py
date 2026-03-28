from __future__ import absolute_import, unicode_literals
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')

from django.conf import settings
from celery import Celery
from celery.schedules import crontab

app = Celery('Topteens', broker=settings.CELERY_BROKER_URL)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Optimal worker config: reduce lag and avoid one task blocking others
app.conf.worker_prefetch_multiplier = 2
app.conf.worker_concurrency = 4
app.conf.task_acks_late = False
app.conf.task_reject_on_worker_lost = True
app.conf.broker_connection_retry_on_startup = True
app.conf.result_expires = 3600
# Beat crontab schedules use CELERY_TIMEZONE (Asia/Kolkata = IST for DAILY_USER_REPORT_TIME).
if not getattr(app.conf, 'timezone', None):
    app.conf.timezone = 'Asia/Kolkata'

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Default until core.apps.CoreConfig.ready() patches from core.Configuration (DAILY_USER_REPORT_TIME, HH:MM IST).
app.conf.beat_schedule = {
    'psychometric-result-every-2-minutes': {
        'task': 'psychometric_tests.task.central_test_automate',
        'schedule': 900,
    },
    'aggregate-daily-analytics': {
        'task': 'user_analytics.tasks.aggregate_daily_analytics',
        'schedule': 86400.0,  # Run daily at midnight
    },
    'send-daily-new-user-report': {
        'task': 'user_analytics.tasks.send_daily_new_user_report',
        'schedule': crontab(minute=0, hour=15),  # 15:00 IST — overridden from DB when Django starts
    },
}
