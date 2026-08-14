from django.apps import AppConfig


class LoanDeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "loan_desk"
    verbose_name = "Loan Desk"

    def ready(self):
        try:
            from loan_desk.beat import sync_loan_daily_report_beat_schedule

            sync_loan_daily_report_beat_schedule()
        except Exception:
            pass
