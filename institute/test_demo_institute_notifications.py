"""Smoke tests for demo-institute marketing notifications."""
from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch


class DemoInstituteNotificationHelpersTests(SimpleTestCase):
    @patch("institute.demo_institute_notifications._emit_marketing")
    def test_students_added_skips_non_demo(self, emit):
        from institute.demo_institute_notifications import notify_demo_institute_students_added

        inst = MagicMock(is_demo_institute=False, is_system_demo=False)
        notify_demo_institute_students_added(inst, count=2)
        emit.assert_not_called()

    @patch("institute.demo_institute_notifications.marketing_recipient_for_institute")
    @patch("institute.demo_institute_notifications._emit_marketing")
    def test_students_added_emits_for_demo(self, emit, recipient):
        from institute.demo_institute_notifications import notify_demo_institute_students_added

        inst = MagicMock(
            id=10,
            name="Demo School",
            is_demo_institute=True,
            is_system_demo=False,
            demo_seed_count=1,
        )
        user = MagicMock(id=99, is_active=True)
        mg = MagicMock(whatsapp_notifications_enabled=True)
        recipient.return_value = (user, mg)
        notify_demo_institute_students_added(inst, count=2, source="demo_seed")
        emit.assert_called_once()
        kwargs = emit.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "marketing.demo_institute_students_added")
        self.assertIn("2 student", kwargs["body"])

    @patch("institute.demo_institute_notifications.StudentManagement.objects")
    @patch("institute.demo_institute_notifications._emit_marketing")
    def test_report_viewed_skips_when_student_not_on_demo(self, emit, sm_objects):
        from institute.demo_institute_notifications import notify_demo_institute_report_viewed

        sm_objects.select_related.return_value.filter.return_value.first.return_value = None
        notify_demo_institute_report_viewed(MagicMock(id=7, name="Asha"))
        emit.assert_not_called()
