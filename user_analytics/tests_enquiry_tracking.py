"""
Test enquiry source (?ref=TOKEN) tracking: simulate a browser visit and assert Activity/Journey get enquiry_source_id.
Run: python manage.py test user_analytics.tests_enquiry_tracking -v 2
"""
from django.test import TestCase, Client
from django.urls import reverse
from user_analytics.models import EnquirySource, UserActivity, UserJourney
from core import choices


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
        url = "/user-analytics/api/enquiry-ref-hit/?ref={}&path=/skilllabcourse/test/".format(self.token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(
            UserActivity.objects.filter(enquiry_source=self.source, page_path="/skilllabcourse/test/").exists()
        )
