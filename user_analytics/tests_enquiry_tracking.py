"""
Test enquiry source (?ref=TOKEN) tracking: simulate a browser visit and assert Activity/Journey get enquiry_source_id.
Run: python manage.py test user_analytics.tests_enquiry_tracking -v 2
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from user_analytics.models import EnquirySource, UserActivity, UserJourney, UserEvent
from user_analytics.views import _enquiry_source_stats
from core import choices
from users.models import User


class EnquirySourceTrackingTest(TestCase):
    """Simulate a GET request with ?ref=TOKEN and verify UserActivity and UserJourney get enquiry_source_id."""

    def setUp(self):
        self.client = Client()
        self.source = EnquirySource.objects.create(
            name="Test source",
            is_active=True,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.token = self.source.token
        self.assertIsNotNone(self.token, "EnquirySource must have token after save")

    def test_visit_with_ref_records_activity_and_journey_with_enquiry_source(self):
        # Use /ref-landing/ which always returns 200 (tracking only runs on 200)
        url = "/ref-landing/?ref=%s" % self.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, "ref-landing must return 200 so middleware records the visit")

        activities = UserActivity.objects.filter(enquiry_source=self.source)
        journeys = UserJourney.objects.filter(enquiry_source=self.source)

        self.assertGreater(
            activities.count(),
            0,
            "UserActivity must have enquiry_source_id set when visiting /ref-landing/?ref=TOKEN. "
            "Check middleware passes enquiry_source_id and track_page_view_sync saves it.",
        )
        self.assertGreater(
            journeys.count(),
            0,
            "UserJourney must have enquiry_source_id set when visiting /ref-landing/?ref=TOKEN. "
            "Check middleware passes enquiry_source_id and update_user_journey_sync saves it.",
        )

    def test_ref_hit_api_records_activity(self):
        url = "/entry/attribution/?ref={}&path=/skilllabcourse/test/".format(self.token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(
            UserActivity.objects.filter(enquiry_source=self.source, page_path="/skilllabcourse/test/").exists()
        )

    def test_payment_started_excludes_client_started_duplicates(self):
        user = User.objects.create_user(email="dup@example.com", name="Dup", password="x12345")
        UserActivity.objects.create(
            enquiry_source=self.source,
            session_id="sess-dup-1",
            user=user,
            page_path="/ref-landing/",
        )
        UserEvent.objects.create(
            user=user,
            event_type="payment_pending",
            event_name="Client Started",
            session_id="sess-dup-1",
            metadata={"stage": "started", "source": self.source.name},
        )
        UserEvent.objects.create(
            user=user,
            event_type="payment_pending",
            event_name="Server Started",
            session_id="sess-dup-1",
            metadata={"payment_stage": "checkout_started", "source": self.source.name},
        )
        stats = _enquiry_source_stats(self.source)
        self.assertEqual(stats["payment_started"], 1)

    def test_enquiry_source_events_api_supports_all_metric_kinds(self):
        staff = User.objects.create_user(email="staff@example.com", name="Staff", password="x12345")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        user = User.objects.create_user(email="metric@example.com", name="Metric", password="x12345")

        UserActivity.objects.create(
            enquiry_source=self.source,
            session_id="sess-metric-1",
            user=user,
            page_path="/landing/",
            page_title="Landing",
        )
        UserJourney.objects.create(
            enquiry_source=self.source,
            session_id="sess-metric-1",
            user=user,
            start_time=timezone.now(),
            entry_page="/landing/",
            converted=True,
        )
        UserEvent.objects.create(user=user, event_type="registration", event_name="Registered", session_id="sess-metric-1", metadata={})
        UserEvent.objects.create(user=user, event_type="payment_success", event_name="Paid", session_id="sess-metric-1", metadata={})
        UserEvent.objects.create(user=user, event_type="payment_failed", event_name="Fail", session_id="sess-metric-1", metadata={})
        UserEvent.objects.create(user=user, event_type="payment_pending", event_name="Started", session_id="sess-metric-1", metadata={"payment_stage": "checkout_started"})
        UserEvent.objects.create(user=user, event_type="course_enrolled", event_name="Enrolled", session_id="sess-metric-1", metadata={})

        self.client.force_login(staff)
        metric_kinds = [
            "page_views",
            "sessions",
            "registration",
            "payment_success",
            "payment_started",
            "payment_failed",
            "course_enrolled",
            "converted_sessions",
        ]
        for kind in metric_kinds:
            response = self.client.get(reverse("user_analytics:enquiry_source_events_api"), {"source_id": self.source.id, "kind": kind})
            self.assertEqual(response.status_code, 200, "kind=%s should return 200" % kind)
            payload = response.json()
            self.assertTrue(payload.get("ok"), "kind=%s should return ok" % kind)
            self.assertGreaterEqual(payload.get("total", 0), 1, "kind=%s should contain rows" % kind)
