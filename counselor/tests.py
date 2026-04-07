"""
Tests for counselor course flows (course learning URL, access control).
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core import choices
from counselor.models import Chapter, Counselor, CounselorCourse, Part
from users.models import User


def _make_counselor_user(email: str) -> User:
    """Create a counselor user; provide an image so User.save() does not fetch avatars over HTTP."""
    img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
    u = User(
        email=email,
        name="Test Counselor",
        user_type=choices.UserType.COUNSELOR,
        image=img,
    )
    u.set_password("test-pass-123")
    u.save()
    return u


class CounselorCourseLearningTests(TestCase):
    """Integration tests for the course learning view backed by CounselorCourse / Chapter / Part."""

    @classmethod
    def setUpTestData(cls):
        cls.course = CounselorCourse.objects.create(title="Test counselor course")
        cls.chapter = Chapter.objects.create(course=cls.course, title="Chapter 1")
        cls.part = Part.objects.create(chapter=cls.chapter, title="Part 1", video_url="")

    def setUp(self):
        self.user = _make_counselor_user("counselor_a@example.com")
        self.counselor = Counselor.objects.create(
            counselor_name="Counselor A",
            coun_user=self.user,
            counselor_email="counselor_a@example.com",
        )
        self.client = Client()

    def test_course_learning_requires_login(self):
        url = reverse("counselor:course_learning", kwargs={"counselor_id": self.counselor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/user/login", response.url)

    def test_course_learning_ok_for_own_counselor(self):
        self.client.force_login(self.user)
        url = reverse("counselor:course_learning", kwargs={"counselor_id": self.counselor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test counselor course")

    def test_course_learning_forbidden_for_other_counselor(self):
        other_user = _make_counselor_user("counselor_b@example.com")
        other_counselor = Counselor.objects.create(
            counselor_name="Counselor B",
            coun_user=other_user,
            counselor_email="counselor_b@example.com",
        )
        self.client.force_login(self.user)
        url = reverse("counselor:course_learning", kwargs={"counselor_id": other_counselor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
