"""Minimal tests for Class 10 async PDF enqueue / serve-if-exists path."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.utils import (
    class10_assessment_pdf_filename,
    class10_pdf_lock_key,
    user_pdf_key,
)


User = get_user_model()

_LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'class10-pdf-tests',
    }
}


class Class10PdfHelperTests(SimpleTestCase):
    def test_filename_for_test_papers(self):
        user = MagicMock()
        user.name = "Demo Student"
        user.email = "demo@example.com"
        self.assertEqual(
            class10_assessment_pdf_filename(user, "test2"),
            "Demo Student-Interest_Assessment_report.pdf",
        )
        self.assertEqual(
            class10_assessment_pdf_filename(user, "test1"),
            "Demo Student-Personality_Assessment_report.pdf",
        )

    def test_user_pdf_key(self):
        self.assertEqual(
            user_pdf_key(42, "a.pdf"),
            "users_pdfs/42/a.pdf",
        )


@override_settings(ENABLE_CELERY=True, CACHES=_LOCMEM_CACHE)
class Class10PdfEnqueueTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("app.task.generate_class10_assessment_pdf.delay")
    @patch("app.task.user_pdf_exists", return_value=False)
    @patch("app.task.User.objects")
    def test_enqueue_queues_once(self, mock_users, _exists, mock_delay):
        from app.task import enqueue_class10_assessment_pdf

        user = MagicMock()
        user.id = 99
        user.name = "Stu"
        user.email = "s@test.com"
        mock_users.only.return_value.get.return_value = user

        lock_state = {'held': False}

        def _add(key, value, timeout=None):
            if lock_state['held']:
                return False
            lock_state['held'] = True
            return True

        with patch("app.task.cache.add", side_effect=_add):
            self.assertTrue(
                enqueue_class10_assessment_pdf(99, "test2", "https://www.topteen.in/")
            )
            mock_delay.assert_called_once_with(99, "test2", "https://www.topteen.in/")

            mock_delay.reset_mock()
            # Second call should hit lock and not queue again
            self.assertTrue(
                enqueue_class10_assessment_pdf(99, "test2", "https://www.topteen.in/")
            )
            mock_delay.assert_not_called()

    @patch("app.task.user_pdf_exists", return_value=True)
    @patch("app.task.User.objects")
    @patch("app.task.generate_class10_assessment_pdf.delay")
    def test_enqueue_skips_when_pdf_exists(self, mock_delay, mock_users, _exists):
        from app.task import enqueue_class10_assessment_pdf

        user = MagicMock()
        user.name = "Stu"
        user.email = "s@test.com"
        mock_users.only.return_value.get.return_value = user

        self.assertTrue(
            enqueue_class10_assessment_pdf(7, "test2", "https://www.topteen.in/")
        )
        mock_delay.assert_not_called()


@override_settings(ENABLE_CELERY=True, CACHES=_LOCMEM_CACHE)
class DownloadPdfFastPathTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    @patch("app.views.redirect")
    @patch("app.views.user_pdf_exists", return_value=True)
    def test_download_pdf_redirects_when_file_exists(self, _exists, mock_redirect):
        from app.views import download_pdf

        mock_redirect.return_value = MagicMock(status_code=302)
        user = MagicMock()
        user.id = 5
        user.name = "A"
        user.email = "a@b.com"
        user.is_authenticated = True
        request = self.factory.get("/psychometric/download_pdf/test2/")
        request.user = user

        download_pdf(request, "test2")
        mock_redirect.assert_called_with("app:app_submit")

    @patch("app.views.redirect")
    @patch("app.views.user_pdf_exists", return_value=False)
    def test_download_pdf_enqueues_instead_of_weasyprint(self, _exists, mock_redirect):
        from app.views import download_pdf

        mock_redirect.return_value = MagicMock(status_code=302)
        user = MagicMock()
        user.id = 5
        user.name = "A"
        user.email = "a@b.com"
        user.is_authenticated = True
        request = self.factory.get("/psychometric/download_pdf/test2/")
        request.user = user

        with patch("app.task.enqueue_class10_assessment_pdf", return_value=True) as enqueue:
            with patch("app.views.weasyprint") as weasy:
                download_pdf(request, "test2")
                enqueue.assert_called_once()
                weasy.HTML.assert_not_called()
        mock_redirect.assert_called_with("app:app_submit")
