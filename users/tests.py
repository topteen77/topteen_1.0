from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, RequestFactory
from django.urls import reverse

from core import choices
from institute.models import StudentManagement
from app.models import TestCompletion
from users.models import User, UserProfile
from users.views import _apply_institute_student_mobile_gate


def _add_session(request):
    """Attach a session to a RequestFactory request."""
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    return request


class TestInstituteStudentMobileGateAfterCompletion(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _make_student(self, email="s1@example.com", mobile=None):
        # Avoid network avatar fetch in User.save() by providing an image on the FIRST save.
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        u = User(email=email, name="Student", user_type=choices.UserType.STUDENT, mobile=mobile, image=img)
        u.set_password("pass1234")
        u.save()
        return u

    def _mark_test_completed(self, user: User, completed: bool):
        tc, _ = TestCompletion.objects.get_or_create(user=user)
        tc.test1_complete = completed
        tc.test2_complete = completed
        tc.test3_complete = completed
        tc.numerical_complete = completed
        tc.verbal_complete = completed
        tc.logical_complete = completed
        tc.emotional_complete = completed
        tc.machanical_complete = completed
        tc.language_complete = completed
        tc.spatial_complete = completed
        tc.save()
        return tc

    def test_gate_does_not_trigger_before_completion(self):
        user = self._make_student(mobile=None)
        StudentManagement.objects.create(student=user)  # institute student marker
        self._mark_test_completed(user, completed=False)

        req = _add_session(self.rf.get("/"))
        desired = "/somewhere/"
        out = _apply_institute_student_mobile_gate(req, user, desired)

        self.assertEqual(out, desired)
        self.assertFalse(req.session.get("force_mobile_popup", False))

    def test_gate_triggers_after_completion_when_mobile_missing(self):
        user = self._make_student(mobile=None)
        StudentManagement.objects.create(student=user)  # institute student marker
        self._mark_test_completed(user, completed=True)

        req = _add_session(self.rf.get("/"))
        desired = "/somewhere/"
        out = _apply_institute_student_mobile_gate(req, user, desired)

        self.assertEqual(out, reverse("users:userdashboard"))
        self.assertTrue(req.session.get("force_mobile_popup"))
        self.assertEqual(req.session.get("post_mobile_redirect"), desired)

    def test_gate_does_not_trigger_after_completion_if_mobile_present(self):
        user = self._make_student(mobile="9876543210")
        StudentManagement.objects.create(student=user)
        self._mark_test_completed(user, completed=True)

        req = _add_session(self.rf.get("/"))
        desired = "/somewhere/"
        out = _apply_institute_student_mobile_gate(req, user, desired)

        self.assertEqual(out, desired)
        self.assertFalse(req.session.get("force_mobile_popup", False))

    def test_test_buttons_redirects_to_dashboard_and_sets_session_flag(self):
        """
        Validates the bypass is closed: completed institute student with no mobile
        can't access app:test_buttons directly; they are redirected to users:userdashboard
        with force_mobile_popup session flag set.
        """
        user = self._make_student(email="s2@example.com", mobile=None)
        StudentManagement.objects.create(student=user)
        self._mark_test_completed(user, completed=True)

        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.get(reverse("app:test_buttons"), follow=False)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("users:userdashboard"))

        session = self.client.session
        self.assertTrue(session.get("force_mobile_popup"))
        self.assertEqual(session.get("post_mobile_redirect"), reverse("app:test_buttons"))


class TestInstituteStudentDashboardShowsNoBuy(TestCase):
    def test_institute_student_class10_has_test_payment_true_without_payment_record(self):
        # Create institute student (no psychometric payment record)
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        user = User(email="inst10@example.com", name="Student", user_type=choices.UserType.STUDENT, image=img)
        user.set_password("pass1234")
        user.save()
        StudentManagement.objects.create(student=user)

        # Login and load dashboard
        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.get(reverse("users:userdashboard"))
        self.assertEqual(resp.status_code, 200)

        # Jinja templates may not expose resp.context in Django test client; assert on rendered HTML instead.
        html = resp.content.decode("utf-8", errors="ignore")
        self.assertNotIn("Buy Stream Sorter Test", html)
        # Should show a test access quick-link (either reports or take test)
        self.assertTrue(
            ("Psychometric Test Reports" in html) or ("Take a Psychometric Test" in html),
            "Expected dashboard to show test access link for institute student",
        )

    def test_institute_student_class12_does_not_show_buy_card(self):
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        user = User(email="inst12@example.com", name="Student", user_type=choices.UserType.STUDENT, image=img)
        user.set_password("pass1234")
        user.save()
        UserProfile.objects.create(user=user, grade="12")
        StudentManagement.objects.create(student=user)

        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.get(reverse("users:userdashboard"))
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode("utf-8", errors="ignore")
        self.assertNotIn("Buy Career Direction Test", html)
        self.assertIn("Career Direction Dashboard", html)
