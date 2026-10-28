from celery import shared_task


@shared_task
def send_daily_failure_alert(force_send=False, override_recipients=None, report_date=None):
    """Send one email covering the previous day's AI and website failures."""
    from core.daily_failure_alert import send_daily_failure_alert as _send

    if isinstance(report_date, str) and report_date:
        from datetime import date

        report_date = date.fromisoformat(report_date)
    return _send(
        force_send=force_send,
        override_recipients=override_recipients,
        report_date=report_date,
    )
