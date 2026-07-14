"""
Reconcile DemoDatasetConfig job markers with live Celery state.

The admin status panel stores last_job_* in MySQL. Celery inspect is authoritative
for whether work is actually running. When a task is lost (worker restart,
unregistered task, Redis flush), the marker can stay Queued/Running forever.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from demo_data.models import DemoDatasetConfig, DemoJobStatus
from notifications.services import get_celery_open_tasks

# If still "in progress" with no matching Celery task after this long, mark failed.
_ORPHAN_GRACE = timedelta(seconds=90)


def celery_workers_ready(required_task_name=None):
    """
    Return (ok: bool, detail: str).

    ok=False when Celery is disabled, inspect fails, no workers, or required task
    name is not registered on any worker (stale Docker image).
    """
    if not getattr(settings, "ENABLE_CELERY", True) or not getattr(
        settings, "ENABLE_REDIS", True
    ):
        return False, "Celery/Redis is disabled (ENABLE_CELERY / ENABLE_REDIS)."

    diag = get_celery_open_tasks()
    if not diag.get("inspect_ok"):
        err = diag.get("inspect_error") or "unknown inspect error"
        return False, f"Cannot reach Celery workers ({err})."

    workers = int(diag.get("workers_up") or 0)
    if workers < 1:
        return False, "No Celery workers are up. Start/restart the celery container."

    if required_task_name:
        try:
            from topteens.celery import app as celery_app

            insp = celery_app.control.inspect(timeout=1.5)
            registered = insp.registered() or {}
            known = set()
            for names in registered.values():
                known.update(names or [])
            if known and required_task_name not in known:
                return (
                    False,
                    f"Workers are up but do not know task '{required_task_name}'. "
                    "The celery container is still on an old image (often after "
                    "'./deploy.sh web' without recreating workers). "
                    "On the server: rebuild then "
                    "'docker compose ... up -d --force-recreate --no-deps celery celery_beat' "
                    "or './deploy.sh web' / full './deploy.sh deploy' with the updated script. "
                    "Verify with: celery -A topteens inspect registered | grep demo_data",
                )
        except Exception as exc:
            return False, f"Could not check registered tasks: {exc}"

    return True, f"{workers} worker(s) ready."


def reconcile_stale_demo_job(grace=None):
    """
    If config says queued/running but Celery has no matching open task after grace,
    mark the job failed so admin can enqueue again.

    Returns True if status was updated.
    """
    grace = grace if grace is not None else _ORPHAN_GRACE
    config = DemoDatasetConfig.get_singleton()
    if not config.job_in_progress():
        return False

    started = config.last_job_started_at
    if not started:
        return False
    if timezone.now() - started < grace:
        return False

    task_id = (config.last_job_task_id or "").strip()
    diag = get_celery_open_tasks()
    open_ids = {
        (row.get("id") or "").strip()
        for row in (diag.get("task_rows") or [])
        if row.get("id")
    }

    if task_id and task_id in open_ids:
        return False

    # No matching live task — orphaned marker.
    workers = int(diag.get("workers_up") or 0)
    if workers < 1:
        reason = (
            "Celery job never completed: no workers available. "
            "Data was NOT reset/removed. Restart celery, then run Reset/Remove again."
        )
    else:
        reason = (
            f"Celery job lost (task id {task_id or '—'} not active). "
            "Data was NOT reset/removed. "
            "Often caused by a worker restart or an outdated celery image missing demo_data tasks. "
            "Fix workers, then run Reset/Remove again."
        )
    config.mark_job_failed(reason)
    return True
