"""Tests for report PDF button UX: status/prefetch JSON + template wiring."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings


_LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "report-pdf-async-ux-tests",
    }
}

_REPO = Path(__file__).resolve().parents[1]


@override_settings(ENABLE_CELERY=True, CACHES=_LOCMEM_CACHE)
class ReportPdfAsyncApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = MagicMock()
        self.user.id = 42
        self.user.name = "Demo Student"
        self.user.email = "demo@example.com"
        self.user.is_authenticated = True

    def _request(self, path="/web/combined_report/download-pdf/", **params):
        req = self.factory.get(path, params)
        req.user = self.user
        return req

    @patch("app.views.user_pdf_browser_url", return_value="https://cdn.example/media/users_pdfs/42/r.pdf")
    @patch("app.views.user_pdf_exists", return_value=True)
    def test_status_ready_returns_json_url(self, _exists, _browser_url):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        resp = _try_serve_or_enqueue_web_report_pdf(self._request(status="1"), self.user, "combined")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"].split(";")[0], "application/json")
        data = json.loads(resp.content.decode())
        self.assertTrue(data["ready"])
        self.assertFalse(data["preparing"])
        self.assertEqual(data["url"], "https://cdn.example/media/users_pdfs/42/r.pdf")

    @patch("app.task.enqueue_class10_web_report_pdf", return_value=True)
    @patch("app.views.user_pdf_exists", return_value=False)
    def test_status_not_ready_enqueues_and_returns_preparing(self, _exists, mock_enqueue):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        resp = _try_serve_or_enqueue_web_report_pdf(self._request(status="1"), self.user, "combined")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode())
        self.assertFalse(data["ready"])
        self.assertTrue(data["preparing"])
        self.assertIsNone(data.get("url"))
        mock_enqueue.assert_called_once()

    @patch("app.task.enqueue_class10_web_report_pdf", return_value=True)
    @patch("app.views.user_pdf_exists", return_value=False)
    def test_prefetch_returns_204_without_wait_html(self, _exists, mock_enqueue):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        resp = _try_serve_or_enqueue_web_report_pdf(self._request(prefetch="1"), self.user, "test1")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(resp.content)
        mock_enqueue.assert_called_once()

    @patch("app.views.user_pdf_exists", return_value=True)
    def test_prefetch_when_ready_still_204(self, _exists):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        resp = _try_serve_or_enqueue_web_report_pdf(self._request(prefetch="1"), self.user, "combined")
        self.assertEqual(resp.status_code, 204)

    @patch("app.task.enqueue_class10_web_report_pdf", return_value=True)
    @patch("app.views.user_pdf_exists", return_value=False)
    def test_direct_nav_still_returns_preparing_html_fallback(self, _exists, _enqueue):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        resp = _try_serve_or_enqueue_web_report_pdf(self._request(), self.user, "combined")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Preparing your report", body)
        self.assertNotIn('"ready"', body)

    @patch("app.views.user_pdf_browser_url", return_value="https://cdn.example/media/users_pdfs/42/r.pdf")
    @patch("app.views.user_pdf_exists")
    def test_status_probes_storage_so_buttons_auto_enable(self, mock_exists, _browser_url):
        from app.views import _try_serve_or_enqueue_web_report_pdf

        mock_exists.return_value = True
        resp = _try_serve_or_enqueue_web_report_pdf(self._request(status="1"), self.user, "combined")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode())
        self.assertTrue(data["ready"])
        # status path must ask for storage probe
        mock_exists.assert_called()
        kwargs = mock_exists.call_args.kwargs
        self.assertTrue(kwargs.get("probe_storage"))

    @patch("app.views.serve_user_pdf_response")
    @patch("app.views.user_pdf_exists", return_value=True)
    def test_direct_nav_when_ready_serves_pdf_response(self, _exists, mock_serve):
        from app.views import _try_serve_or_enqueue_web_report_pdf
        from django.http import HttpResponseRedirect

        mock_serve.return_value = HttpResponseRedirect("https://cdn.example/r.pdf")
        resp = _try_serve_or_enqueue_web_report_pdf(self._request(), self.user, "combined")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://cdn.example/r.pdf")


class UserPdfReadyCacheTests(SimpleTestCase):
    @override_settings(
        ENABLE_REDIS=True,
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
            },
            "translations": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "pdf-ready-tr-tests",
            },
        },
    )
    def test_ready_flag_survives_dummy_default_cache(self):
        from django.core.cache import caches
        from core.utils import mark_user_pdf_ready, user_pdf_exists

        caches["translations"].clear()
        mark_user_pdf_ready(9, "report.pdf", True)
        # Default DummyCache would lose this; Redis/translations alias must keep it.
        self.assertTrue(user_pdf_exists(9, "report.pdf"))
        mark_user_pdf_ready(9, "report.pdf", False)
        self.assertFalse(user_pdf_exists(9, "report.pdf"))


class ReportPdfTemplateWiringTests(SimpleTestCase):
    def test_dashboard_pdf_buttons_use_async_class_and_preparing_state(self):
        html = (
            _REPO
            / "templates/template20/psychometric/includes/dashboard_main_content.html"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(html.count("js-report-pdf-btn"), 4)
        self.assertIn('data-label-default="PDF"', html)
        self.assertIn('data-label-default="Download PDF"', html)
        self.assertIn("Preparing…", html)
        self.assertIn("Preparing PDF…", html)
        # Must not open wait page via target=_blank on async buttons
        self.assertNotIn('js-report-pdf-btn" target="_blank"', html.replace("\n", " "))

    def test_dashboard_includes_async_script(self):
        dash = (_REPO / "templates/template20/psychometric/dashboard.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("report_pdf_async_download.html", dash)

    def test_async_script_disables_until_ready(self):
        script = (
            _REPO / "templates/template20/app/partials/report_pdf_async_download.html"
        ).read_text(encoding="utf-8")
        self.assertIn("setGroupPreparing", script)
        self.assertIn("setGroupReady", script)
        self.assertIn("aria-disabled", script)
        self.assertIn("prefetch", script)
        self.assertIn("status", script)
        # Click must no-op while disabled
        self.assertIn("getAttribute('aria-disabled') === 'true'", script)
