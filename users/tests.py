from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import Resolver404, resolve, reverse

from core import choices
from institute.models import InstituteMarketingGroup, StudentManagement
from app.models import TestCompletion
from users.models import User, UserProfile
from users.session_utils import (
    DEFAULT_LOGIN_SESSION_AGE,
    REMEMBER_ME_SESSION_AGE,
    apply_login_session_expiry,
    login_user_with_session,
)
from users.views import _apply_institute_student_mobile_gate, get_dashboard_url_for_user


def _add_session(request):
    """Attach a session to a RequestFactory request."""
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    return request


class TestRoleDashboardRouting(TestCase):
    def test_marketing_admin_userdashboard_redirects_to_marketing_dashboard(self):
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        user = User(
            email="mktg@example.com",
            name="Marketing Admin",
            user_type=choices.UserType.MARKETINGGROUPADMIN,
            image=img,
        )
        user.set_password("pass1234")
        user.save()
        InstituteMarketingGroup.objects.create(
            m_group_name="Test marketing group",
            marketing_group_admin=user,
        )
        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.get(reverse("users:userdashboard"), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("institute:marketinggroupdashboard"))

    def test_get_dashboard_url_for_marketing_admin(self):
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        user = User(
            email="mktg2@example.com",
            name="Marketing Admin 2",
            user_type=choices.UserType.MARKETINGGROUPADMIN,
            image=img,
        )
        user.set_password("pass1234")
        user.save()
        req = _add_session(RequestFactory().get("/"))
        url = get_dashboard_url_for_user(req, user, apply_mobile_gate=False)
        self.assertEqual(url, reverse("institute:marketinggroupdashboard"))


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


class TestChangeOwnPasswordView(TestCase):
    def _make_role_user(self, user_type, email):
        img = SimpleUploadedFile("u.jpg", b"fake-image-bytes", content_type="image/jpeg")
        user = User(email=email, name="Role User", user_type=user_type, image=img)
        user.set_password("OldPass123")
        user.save()
        return user

    def test_marketing_admin_can_change_own_password(self):
        user = self._make_role_user(
            choices.UserType.MARKETINGGROUPADMIN, "mktg-pwd@example.com"
        )
        InstituteMarketingGroup.objects.create(
            m_group_name="Pwd group",
            marketing_group_admin=user,
        )
        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.post(
            reverse("users:changeownpassword"),
            {
                "old_password": "OldPass123",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass456"))
        self.assertFalse(user.check_password("OldPass123"))

    def test_wrong_old_password_rejected(self):
        user = self._make_role_user(
            choices.UserType.INSTITUTEGROUPADMIN, "ig-pwd@example.com"
        )
        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.post(
            reverse("users:changeownpassword"),
            {
                "old_password": "WrongOld",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json().get("success"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("OldPass123"))

    def test_student_cannot_change_own_password_via_endpoint(self):
        user = self._make_role_user(choices.UserType.STUDENT, "stu-pwd@example.com")
        self.client.force_login(user, backend="users.backends.CustomUserBackend")
        resp = self.client.post(
            reverse("users:changeownpassword"),
            {
                "old_password": "OldPass123",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith("/") or resp.url == "/")
        user.refresh_from_db()
        self.assertTrue(user.check_password("OldPass123"))


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


class TestResumeAiDesignRouteRemoved(SimpleTestCase):
    """Removed PDF AI designer (/templates/ai-design/); URLConf must not register these paths."""

    def test_ai_design_paths_do_not_resolve(self):
        for path in (
            "/user/resume-builder/studio/28/templates/ai-design/",
            "/user/resume-builder/studio/28/templates/ai-design/api/",
        ):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)


class TestLoginSessionExpiry(SimpleTestCase):
    class _SessionStub:
        def __init__(self):
            self.expiry = None

        def set_expiry(self, value):
            self.expiry = value

        def get_expiry_age(self):
            return self.expiry

    def _request_with_session(self):
        request = RequestFactory().get("/")
        request.session = self._SessionStub()
        return request

    def test_default_login_uses_persistent_age_not_browser_session(self):
        request = self._request_with_session()
        apply_login_session_expiry(request, remember_me=False)
        self.assertEqual(request.session.get_expiry_age(), DEFAULT_LOGIN_SESSION_AGE)

    def test_remember_me_uses_longer_session(self):
        request = self._request_with_session()
        apply_login_session_expiry(request, remember_me=True)
        self.assertEqual(request.session.get_expiry_age(), REMEMBER_ME_SESSION_AGE)

    def test_demo_login_uses_browser_session(self):
        request = self._request_with_session()
        apply_login_session_expiry(request, demo=True)
        self.assertEqual(request.session.get_expiry_age(), 0)

    def test_session_settings_keep_users_signed_in_during_browsing(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertGreaterEqual(settings.SESSION_COOKIE_AGE, DEFAULT_LOGIN_SESSION_AGE)
        self.assertEqual(
            settings.SESSION_SERIALIZER,
            "django.contrib.sessions.serializers.JSONSerializer",
        )
        self.assertIn(
            settings.SESSION_ENGINE,
            (
                "django.contrib.sessions.backends.db",
                "django.contrib.sessions.backends.cached_db",
                "django.contrib.sessions.backends.signed_cookies",
            ),
        )

    def test_login_user_with_session_applies_expiry_after_login(self):
        calls = []

        class _UserStub:
            pk = 1

        class _SessionStub:
            def __init__(self):
                self.expiry = None
                self.modified = False
                self._data = {}

            def __setitem__(self, key, value):
                self._data[key] = value

            def __getitem__(self, key):
                return self._data[key]

            def get(self, key, default=None):
                return self._data.get(key, default)

            def pop(self, key, default=None):
                return self._data.pop(key, default)

            def set_expiry(self, value):
                self.expiry = value
                calls.append(("set_expiry", value))

            def get_expiry_age(self):
                return self.expiry

            def save(self):
                calls.append(("save",))

        request = self._request_with_session()
        request.session = _SessionStub()

        from unittest.mock import patch

        def _fake_login(req, user, backend=None):
            calls.append(("login", backend))

        with patch("django.contrib.auth.login", side_effect=_fake_login):
            login_user_with_session(request, _UserStub(), remember_me=True)

        self.assertEqual(calls[0][0], "login")
        self.assertEqual(calls[1], ("set_expiry", REMEMBER_ME_SESSION_AGE))
        self.assertIn(("save",), calls)

