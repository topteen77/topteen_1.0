from datetime import datetime, timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from communication.models import CommunicationLog
from core.daily_failure_alert import send_daily_failure_alert
from core.models import LLMUsageLog
from user_analytics.models import UserEvent


@override_settings(
    ENVIRONMENT="production",
    WEBADMINEMAIL="ops@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class DailyFailureAlertTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate() - timedelta(days=1)
        self.when = timezone.make_aware(datetime.combine(self.day, datetime.min.time())) + timedelta(hours=11)

    def _stamp(self, model, pk, field):
        model.objects.filter(pk=pk).update(**{field: self.when})

    def test_quiet_day_sends_nothing(self):
        result = send_daily_failure_alert(report_date=self.day)
        self.assertEqual(result, "skipped_no_failures")
        self.assertEqual(len(mail.outbox), 0)

    def test_one_email_lists_ai_and_payment_failures(self):
        ai = LLMUsageLog.objects.create(
            feature="forum",
            provider="gemini",
            model="gemini-3-flash-preview",
            success=False,
            error_message="RESOURCE_EXHAUSTED prepayment credits are depleted",
        )
        self._stamp(LLMUsageLog, ai.pk, "created_at")
        payment = UserEvent.objects.create(
            event_type="payment_failed",
            event_name="Checkout failed",
            metadata={"error": "Gateway timeout"},
        )
        self._stamp(UserEvent, payment.pk, "created")

        result = send_daily_failure_alert(report_date=self.day)

        self.assertEqual(result["failures"], 2)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ops@example.com"])
        self.assertIn(self.day.isoformat(), message.subject)
        self.assertIn("gemini-3-flash-preview", message.body)
        self.assertIn("Checkout failed", message.body)
        self.assertTrue(
            CommunicationLog.objects.filter(body=message.subject, response="success").exists()
        )

    def test_second_run_same_day_does_not_send_again(self):
        ai = LLMUsageLog.objects.create(
            feature="translation",
            provider="openai",
            model="gpt-4o-mini",
            success=False,
            error_message="rate limit",
        )
        self._stamp(LLMUsageLog, ai.pk, "created_at")

        send_daily_failure_alert(report_date=self.day)
        again = send_daily_failure_alert(report_date=self.day)

        self.assertEqual(again, "skipped_already_sent")
        self.assertEqual(len(mail.outbox), 1)
