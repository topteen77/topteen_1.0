"""
Celery tasks for demo dataset setup / reset / remove.

Large batches (e.g. 100+ students with psychometric) time out nginx when run
inside the admin HTTP request (502 Bad Gateway). Queue them on Celery instead.
"""
import logging

from topteens.celery import app

from demo_data.models import DemoDatasetConfig, DemoJobAction

logger = logging.getLogger(__name__)

_DEMO_TASK_SOFT_LIMIT = 30 * 60
_DEMO_TASK_HARD_LIMIT = 35 * 60


def _run_demo_job(action, runner, success_message):
    config = DemoDatasetConfig.get_singleton()
    label = DemoJobAction.LABELS.get(action, action)
    try:
        config.mark_job_running(f"{label}: running…")
        result = runner()
        config = DemoDatasetConfig.get_singleton()
        extra = ""
        if isinstance(result, dict) and result.get("student_user_ids") is not None:
            extra = f" ({len(result['student_user_ids'])} students)"
        config.mark_job_success(f"{success_message}{extra}")
        logger.info("Demo job %s finished successfully%s", action, extra)
        return {"ok": True, "action": action, "result": result}
    except Exception as exc:
        logger.exception("Demo job %s failed", action)
        config = DemoDatasetConfig.get_singleton()
        config.mark_job_failed(f"{label} failed: {exc}")
        raise


@app.task(
    bind=True,
    name="demo_data.tasks.setup_demo_dataset_task",
    soft_time_limit=_DEMO_TASK_SOFT_LIMIT,
    time_limit=_DEMO_TASK_HARD_LIMIT,
)
def setup_demo_dataset_task(self):
    from demo_data.demo_dataset import create_demo_dataset

    return _run_demo_job(
        DemoJobAction.SETUP_STUDENTS,
        create_demo_dataset,
        "Student / institute demo dataset created.",
    )


@app.task(
    bind=True,
    name="demo_data.tasks.reset_demo_dataset_task",
    soft_time_limit=_DEMO_TASK_SOFT_LIMIT,
    time_limit=_DEMO_TASK_HARD_LIMIT,
)
def reset_demo_dataset_task(self):
    from demo_data.demo_dataset import reset_demo_data

    return _run_demo_job(
        DemoJobAction.RESET_STUDENTS,
        reset_demo_data,
        "Student / institute demo reset complete.",
    )


@app.task(
    bind=True,
    name="demo_data.tasks.remove_demo_dataset_task",
    soft_time_limit=_DEMO_TASK_SOFT_LIMIT,
    time_limit=_DEMO_TASK_HARD_LIMIT,
)
def remove_demo_dataset_task(self):
    from demo_data.demo_dataset import remove_demo_data

    return _run_demo_job(
        DemoJobAction.REMOVE_STUDENTS,
        remove_demo_data,
        "Student / institute demo removed.",
    )


@app.task(
    bind=True,
    name="demo_data.tasks.setup_demo_counselor_task",
    soft_time_limit=10 * 60,
    time_limit=12 * 60,
)
def setup_demo_counselor_task(self):
    from demo_data.demo_dataset import setup_demo_counselor_data

    return _run_demo_job(
        DemoJobAction.SETUP_COUNSELOR,
        setup_demo_counselor_data,
        "Demo counselor created (demo_counselor@topteen.demo / demo123).",
    )


@app.task(
    bind=True,
    name="demo_data.tasks.reset_demo_counselor_task",
    soft_time_limit=10 * 60,
    time_limit=12 * 60,
)
def reset_demo_counselor_task(self):
    from demo_data.demo_dataset import reset_demo_counselor_data

    return _run_demo_job(
        DemoJobAction.RESET_COUNSELOR,
        reset_demo_counselor_data,
        "Demo counselor reset complete.",
    )


@app.task(
    bind=True,
    name="demo_data.tasks.remove_demo_counselor_task",
    soft_time_limit=5 * 60,
    time_limit=6 * 60,
)
def remove_demo_counselor_task(self):
    from demo_data.demo_dataset import remove_demo_counselor_data

    return _run_demo_job(
        DemoJobAction.REMOVE_COUNSELOR,
        remove_demo_counselor_data,
        "Demo counselor removed.",
    )
