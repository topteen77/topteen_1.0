from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from user_analytics.models import EnquirySource, UserActivity, UserEvent, UserJourney


class AdminInterlinkingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create(
            name="Admin User",
            email="admin-interlink@test.com",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

        self.session_id = "dummy-session-123"
        self.enquiry_source = EnquirySource.objects.create(
            name="Dummy Enquiry Source",
            agency_name="Dummy Agency",
            user_name="Dummy Contact",
            event="Dummy Campaign",
        )
        self.activity = UserActivity.objects.create(
            user=self.admin_user,
            session_id=self.session_id,
            page_path="/sample/path/",
            page_url="http://localhost:8002/sample/path/",
            enquiry_source=self.enquiry_source,
        )
        self.event = UserEvent.objects.create(
            user=self.admin_user,
            event_type="page_view",
            event_name="Sample Page View",
            session_id=self.session_id,
            metadata={"source": "test"},
        )
        self.journey = UserJourney.objects.create(
            user=self.admin_user,
            session_id=self.session_id,
            start_time=timezone.now(),
            entry_page="/sample/path/",
            total_pages=1,
            total_time=15,
            journey_path=["/sample/path/"],
            enquiry_source=self.enquiry_source,
            conversion_event=self.event,
        )

    def test_admin_changelists_are_interlinked_and_searchable_by_session(self):
        activity_url = reverse("admin:user_analytics_useractivity_changelist")
        event_url = reverse("admin:user_analytics_userevent_changelist")
        journey_url = reverse("admin:user_analytics_userjourney_changelist")
        enquiry_source_url = reverse("admin:user_analytics_enquirysource_changelist")

        # UserActivity page has links to Journey and Events via shared session.
        activity_res = self.client.get(activity_url)
        self.assertEqual(activity_res.status_code, 200)
        self.assertContains(activity_res, f"{journey_url}?q={self.session_id}")
        self.assertContains(activity_res, f"{event_url}?q={self.session_id}")
        self.assertContains(
            activity_res,
            reverse("admin:user_analytics_enquirysource_change", args=[self.enquiry_source.id]),
        )

        # UserEvent page has links to Activities and Journey via shared session.
        event_res = self.client.get(event_url)
        self.assertEqual(event_res.status_code, 200)
        self.assertContains(event_res, self.session_id)
        self.assertContains(event_res, f"{activity_url}?q={self.session_id}")
        self.assertContains(event_res, f"{journey_url}?q={self.session_id}")

        # UserJourney page has links to Activities and Events via shared session.
        journey_res = self.client.get(journey_url)
        self.assertEqual(journey_res.status_code, 200)
        self.assertContains(journey_res, f"{activity_url}?q={self.session_id}")
        self.assertContains(journey_res, f"{event_url}?q={self.session_id}")
        self.assertContains(
            journey_res,
            reverse("admin:user_analytics_enquirysource_change", args=[self.enquiry_source.id]),
        )

        # EnquirySource page links back to activities/journeys via FK filter.
        enquiry_res = self.client.get(enquiry_source_url)
        self.assertEqual(enquiry_res.status_code, 200)
        self.assertContains(
            enquiry_res,
            f"{activity_url}?enquiry_source__id__exact={self.enquiry_source.id}&amp;first_session_only=1",
        )
        self.assertContains(
            enquiry_res,
            f"{journey_url}?enquiry_source__id__exact={self.enquiry_source.id}",
        )

        # Search-based navigation by session_id should return the linked data.
        search_activity = self.client.get(activity_url, {"q": self.session_id})
        search_event = self.client.get(event_url, {"q": self.session_id})
        search_journey = self.client.get(journey_url, {"q": self.session_id})
        self.assertContains(search_activity, self.session_id)
        self.assertContains(search_event, self.session_id)
        self.assertContains(search_journey, self.session_id)

        # FK filter links from EnquirySource should show linked records.
        filtered_activity = self.client.get(
            activity_url, {"enquiry_source__id__exact": self.enquiry_source.id}
        )
        filtered_journey = self.client.get(
            journey_url, {"enquiry_source__id__exact": self.enquiry_source.id}
        )
        self.assertContains(filtered_activity, self.session_id)
        self.assertContains(filtered_journey, self.session_id)
