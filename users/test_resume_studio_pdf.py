"""Tests for studio resume template HTML + PDF export."""

from __future__ import annotations

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from users.resume_studio_html import ADMIN_STUDIO_HTML_PREVIEW_SAMPLE
from users.resume_studio_pdf_html import (
    PDF_CONTENT_MIN_HEIGHT,
    SIDEBAR_PDF_TEMPLATE_ROOTS,
    STUDIO_PDF_PAGE_CSS,
    TPL_RENDERERS,
    all_studio_template_ids,
    resolve_studio_template_id,
    studio_pack_root_css_block,
    studio_pdf_template_context,
    studio_proto_pack_to_mount_html,
)


def _sample_pack(template_id: str) -> dict:
    return {
        "resume": dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE),
        "template": template_id,
        "color": "teal",
        "font": "Inter",
        "textAlign": "start",
        "fontSize": "standard",
    }


class StudioTemplateRenderTests(SimpleTestCase):
    def test_all_catalog_templates_render_mount_html(self):
        for tid in all_studio_template_ids():
            with self.subTest(template=tid):
                pack = _sample_pack(tid)
                mount_html, resolved = studio_proto_pack_to_mount_html(pack)
                self.assertTrue(mount_html.strip(), f"empty mount html for {tid}")
                self.assertIn('class="tpl ', mount_html)
                canonical = resolve_studio_template_id(tid)
                self.assertIn(canonical, TPL_RENDERERS)

    def test_aliases_resolve_to_base_renderer(self):
        self.assertEqual(resolve_studio_template_id("global-elegance"), "magazine")
        self.assertEqual(resolve_studio_template_id("euro-corporate"), "executive")
        self.assertEqual(resolve_studio_template_id("tokyo-minimal"), "minimalist")
        self.assertEqual(resolve_studio_template_id("nordic-clean"), "horizon")

    def test_international_templates_have_distinct_markup(self):
        pack = _sample_pack("atlantic-pro")
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-atlantic-pro", html)
        pack["template"] = "global-grid"
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-global-grid", html)

    def test_pdf_shell_includes_sidebar_full_height_css(self):
        pack = _sample_pack("classic-sidebar")
        mount_html, tid = studio_proto_pack_to_mount_html(pack)
        ctx = studio_pdf_template_context(mount_html, tid, pack)
        html = render_to_string("mail/user/userresumepdf_studio_prototype.html", ctx)
        self.assertIn(PDF_CONTENT_MIN_HEIGHT, html)
        self.assertIn("min-height: var(--pdf-page-min-height)", html)
        self.assertIn('data-pdf-engine=', html)
        self.assertIn("tpl-cs-side", html)

    def test_sidebar_templates_use_known_root_classes(self):
        sidebar_ids = (
            "classic-sidebar",
            "professional-border",
            "tech-focus",
            "high-contrast",
            "executive",
            "magazine",
            "euro-corporate",
        )
        for tid in sidebar_ids:
            with self.subTest(template=tid):
                mount_html, _ = studio_proto_pack_to_mount_html(_sample_pack(tid))
                self.assertTrue(
                    any(root in mount_html for root in SIDEBAR_PDF_TEMPLATE_ROOTS),
                    f"expected sidebar root in {tid}",
                )

    def test_pdf_css_declares_page_min_height(self):
        self.assertIn("--pdf-page-min-height", STUDIO_PDF_PAGE_CSS)
        self.assertIn(PDF_CONTENT_MIN_HEIGHT, STUDIO_PDF_PAGE_CSS)

    def test_preview_embed_css_locks_sidebar_layout(self):
        from django.contrib.staticfiles import finders
        from pathlib import Path

        css_path = finders.find("resume-builder-prototype/styles.css")
        self.assertTrue(css_path)
        css = Path(css_path).read_text(encoding="utf-8")
        self.assertIn("body.tt-mode-preview-only .tpl-hc-body", css)
        self.assertIn("grid-template-columns: 200px 1fr", css)
        self.assertIn("body.tt-mode-preview-only .tpl-hc-side", css)
        self.assertIn("order: 0", css)


class StudioPdfGenerationTests(SimpleTestCase):
    def test_weasyprint_generates_pdf_for_each_template(self):
        try:
            from users.pdf_utils import _weasyprint_pdf_bytes
        except ImportError:
            self.skipTest("WeasyPrint not installed")

        for tid in sorted(TPL_RENDERERS.keys()):
            with self.subTest(template=tid):
                pack = _sample_pack(tid)
                mount_html, resolved = studio_proto_pack_to_mount_html(pack)
                ctx = studio_pdf_template_context(mount_html, resolved, pack)
                html = render_to_string("mail/user/userresumepdf_studio_prototype.html", ctx)
                pdf = _weasyprint_pdf_bytes(html, base_url="http://testserver/")
                self.assertTrue(pdf.startswith(b"%PDF"), f"{tid} did not produce a PDF")
                self.assertGreater(len(pdf), 800, f"{tid} PDF too small")

    def test_pack_root_css_includes_font_vars(self):
        block = studio_pack_root_css_block(_sample_pack("classic-sidebar"))
        self.assertIn("--body-size:", block)
        self.assertIn("--pdf-body-size:", block)
