from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')

app = Celery('Topteens',broker=settings.CELERY_BROKER_URL)

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
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'psychometric-result-every-2-minutes': {
        'task': 'psychometric_tests.task.central_test_automate',
        'schedule':  900,
    },
    'aggregate-daily-analytics': {
        'task': 'user_analytics.tasks.aggregate_daily_analytics',
        'schedule': 86400.0,  # Run daily at midnight
    },
}