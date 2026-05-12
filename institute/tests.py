from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from core import choices
from counselor.views import get_students_by_role
from institute.models import ClassAndSection
from institute.views import _resolve_class_and_section


class ResolveClassAndSectionTests(TestCase):
    def test_returns_first_existing_duplicate_when_stream_is_blank(self):
        first = ClassAndSection.objects.create(class_and_section="10-A")
        ClassAndSection.objects.create(class_and_section="10-A")

        resolved, created = _resolve_class_and_section("10-A")

        self.assertFalse(created)
        self.assertEqual(resolved.id, first.id)

    def test_treats_null_and_blank_stream_as_same_bucket(self):
        existing = ClassAndSection.objects.create(class_and_section="11-B", stream="")
        ClassAndSection.objects.create(class_and_section="11-B", stream=None)

        resolved, created = _resolve_class_and_section("11-B", None)

        self.assertFalse(created)
        self.assertEqual(resolved.id, existing.id)

    def test_returns_first_exact_stream_match_when_duplicates_exist(self):
        first = ClassAndSection.objects.create(class_and_section="12-A", stream="Science")
        ClassAndSection.objects.create(class_and_section="12-A", stream="Science")

        resolved, created = _resolve_class_and_section("12-A", "Science")

        self.assertFalse(created)
        self.assertEqual(resolved.id, first.id)

    def test_creates_stream_specific_row_when_no_exact_match_exists(self):
        ClassAndSection.objects.create(class_and_section="12-C", stream=None)

        resolved, created = _resolve_class_and_section("12-C", "Commerce")

        self.assertTrue(created)
        self.assertEqual(resolved.class_and_section, "12-C")
        self.assertEqual(resolved.stream, "Commerce")


class InstituteDashboardScopeTests(SimpleTestCase):
    @patch("counselor.views.StudentManagement.objects.filter")
    @patch("counselor.views.Institute.objects.filter")
    def test_institute_owner_can_view_students_for_owned_institute_even_with_multiple_institutes(
        self,
        institute_filter_mock,
        student_management_filter_mock,
    ):
        owner = MagicMock()
        owner.user_type = choices.UserType.INSTITUTE

        institute = MagicMock()
        institute.id = 60

        institute_exists_qs = MagicMock()
        institute_exists_qs.exists.return_value = True
        institute_filter_mock.return_value = institute_exists_qs

        expected_qs = MagicMock()
        expected_qs.select_related.return_value = expected_qs
        student_management_filter_mock.return_value = expected_qs

        scoped = get_students_by_role(owner, institute=institute)

        institute_filter_mock.assert_called_once_with(created_by=owner, id=60)
        student_management_filter_mock.assert_called_once_with(institute=institute)
        self.assertIs(scoped, expected_qs)
