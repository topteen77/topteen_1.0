from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.ttv2_role_context import _nav_for_role


class UploadHistoryNavigationTests(SimpleTestCase):
    @staticmethod
    def _labels(sections):
        return [
            item.get("label")
            for section in sections
            for item in section.get("items", [])
        ]

    @patch("core.ttv2_role_context._institute_nav_gates")
    def test_history_link_is_hidden_without_entries(self, gates):
        gates.return_value = {
            "has_students": True,
            "has_counselors": False,
            "has_sessions": False,
            "has_upload_history": False,
        }

        sections = _nav_for_role(
            role="institute",
            institute=SimpleNamespace(slug="demo", pk=1),
            counselor=None,
        )

        self.assertNotIn("Uploaded History Log", self._labels(sections))

    @patch("core.ttv2_role_context._institute_nav_gates")
    def test_history_link_is_shown_when_entry_exists(self, gates):
        gates.return_value = {
            "has_students": True,
            "has_counselors": False,
            "has_sessions": False,
            "has_upload_history": True,
        }

        sections = _nav_for_role(
            role="institute",
            institute=SimpleNamespace(slug="demo", pk=1),
            counselor=None,
        )

        self.assertIn("Uploaded History Log", self._labels(sections))
