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

    def test_colored_header_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, music"
        sample["projects"] = [
            {
                "title": "Capstone app",
                "company": "React, Node",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a dashboard for school analytics."],
            }
        ]
        pack = _sample_pack("colored-header")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-ch-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("Projects", html)
        self.assertIn(">Certifications</h2>", html)
        self.assertIn(">Languages</h2>", html)
        self.assertIn("tpl-ch-lang-chip", html)
        self.assertNotIn("Certifications &amp; languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertNotIn(">Interests</h2>", html)

    def test_colored_header_pdf_css_preserves_two_column_rows(self):
        pack = _sample_pack("colored-header")
        mount_html, tid = studio_proto_pack_to_mount_html(pack)
        ctx = studio_pdf_template_context(mount_html, tid, pack)
        html = render_to_string("mail/user/userresumepdf_studio_prototype.html", ctx)
        self.assertIn("tpl-ch-row", mount_html)
        self.assertIn(".tpl-colored-header .tpl-ch-row > .tpl-sec", STUDIO_PDF_PAGE_CSS)
        self.assertIn("width: 49%", STUDIO_PDF_PAGE_CSS)
        self.assertIn(".tpl-colored-header .tpl-ch-body > .tpl-sec", STUDIO_PDF_PAGE_CSS)
        self.assertIn("tpl-ch-lang-chip", html)

    def test_modern_split_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Debate, reading, cricket"
        sample["achievements"] = [
            {
                "title": "Plant Growth Experiment",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Collected and analyzed data on plant growth."],
            }
        ]
        sample["projects"] = [
            {
                "title": "School Debate Club",
                "company": "Public Speaking, Teamwork",
                "location": "",
                "dates": "",
                "bullets": ["Led team to regional finals."],
            }
        ]
        sample["experience"] = list(sample.get("experience") or []) + [
            {
                "title": "Science Fair Project",
                "company": "Research, Presentation",
                "location": "",
                "dates": "",
                "bullets": ["Presented findings at school science exhibition."],
            }
        ]
        pack = _sample_pack("modern-split")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-ms-row", html)
        self.assertIn("tpl-ms-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Work Experience", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Debate, reading, cricket", html)
        self.assertNotIn(">Interests</h2>", html)
        ctx = studio_pdf_template_context(html, "modern-split", pack)
        shell = render_to_string("mail/user/userresumepdf_studio_prototype.html", ctx)
        self.assertIn("tpl-ms-grid", shell)
        self.assertIn("tpl-ms-contact-row", shell)

    def test_professional_border_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Debate, reading, cricket"
        sample["projects"] = [
            {
                "title": "Capstone app",
                "company": "React, Node",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a dashboard for school analytics."],
            }
        ]
        pack = _sample_pack("professional-border")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-pb-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("Projects", html)
        self.assertIn("Work Experience", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Debate, reading, cricket", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-pb-side", html)

    def test_professional_border_pdf_css_no_forced_page_min_height(self):
        self.assertIn(".tpl-professional-border {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertNotIn(
            "body.tt-pdf-export .tpl-professional-border,\nbody.tt-pdf-export .tpl-tech-focus",
            STUDIO_PDF_PAGE_CSS,
        )

    def test_professional_border_interests_fallback_as_hobbies(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = ""
        sample["interests"] = "Reading, cricket, music"
        pack = _sample_pack("professional-border")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Reading, cricket, music", html)

    def test_pdf_contact_icons_use_text_fallback(self):
        self.assertIn("body.tt-pdf-export .tpl-contact-fallback", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: inline-flex !important", STUDIO_PDF_PAGE_CSS)
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        pack = _sample_pack("professional-border")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        pack = _sample_pack("bold-header")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-bh-contact-row", html)
        self.assertIn("tpl-contact-icon", html)

    def test_bold_header_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, cricket, music"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Capstone app",
                "company": "React, Node",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a dashboard for school analytics."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Plant Growth Experiment",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Collected and analyzed data on plant growth."],
            }
        ]
        pack = _sample_pack("bold-header")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Work Experience", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Reading, cricket, music", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-bh-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)

    def test_tech_focus_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, playing musical instruments, community service"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Personal Portfolio Website",
                "company": "HTML, CSS",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a personal portfolio site."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Smart Water Level Alarm",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Designed and built a water level alarm."],
            }
        ]
        pack = _sample_pack("tech-focus")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Certifications", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Reading, playing musical instruments, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-tf-contact", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-skill-bar", html)

    def test_education_grade_renders_ordinal_superscript(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["education"] = [
            {
                "degree": "10",
                "school": "Don Bosco School",
                "dates": "2022",
                "detail": "",
            }
        ]
        pack = _sample_pack("tech-focus")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("10<sup>th</sup>", html)
        self.assertNotIn("<strong>10</strong>", html)

    def test_tech_focus_pdf_uses_full_width_layout(self):
        self.assertIn("body.tt-pdf-export .tpl-tech-focus {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("table-layout: fixed", STUDIO_PDF_PAGE_CSS)
        self.assertIn("width: 72%", STUDIO_PDF_PAGE_CSS)
        self.assertIn("max-width: none !important", STUDIO_PDF_PAGE_CSS)

    def test_geometric_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, music, community service"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Personal Portfolio Website",
                "company": "HTML, CSS",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a personal portfolio site."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Smart Water Level Alarm",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Designed and built a water level alarm."],
            }
        ]
        pack = _sample_pack("geometric")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-geo-layout", html)
        self.assertIn("tpl-geo-aside", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-geo-contact-row", html)
        self.assertIn("tpl-geo-photo", html)

    def test_geometric_pdf_uses_table_layout_and_left_skill_pills(self):
        self.assertIn("body.tt-pdf-export .tpl-geo-layout {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("table-layout: fixed", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-geo-pills {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("justify-content: flex-start !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-geo-pills .tpl-pill {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("inline-flex !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("justify-content: center !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-geometric .tpl-geo-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-geometric .tpl-geo-head + .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("width: 66%", STUDIO_PDF_PAGE_CSS)
        self.assertIn("width: 34%", STUDIO_PDF_PAGE_CSS)

    def test_high_contrast_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, cricket, music"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Personal Portfolio Website",
                "company": "HTML, CSS",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a personal portfolio site."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Smart Water Level Alarm",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Designed and built a water level alarm."],
            }
        ]
        pack = _sample_pack("high-contrast")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Hobbies</h3>", html)
        self.assertIn("Reading, cricket, music", html)
        self.assertNotIn(">Interests</h3>", html)
        self.assertIn("tpl-hc-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)

    def test_high_contrast_pdf_uses_table_layout(self):
        self.assertIn("body.tt-pdf-export .tpl-hc-body {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-high-contrast .tpl-hc-contact-row {", STUDIO_PDF_PAGE_CSS)

    def test_aurora_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, music, community service"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Personal Portfolio Website",
                "company": "HTML, CSS",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a personal portfolio site."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Smart Water Level Alarm",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Designed and built a water level alarm."],
            }
        ]
        pack = _sample_pack("aurora")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications</h2>", html)
        self.assertIn("Languages</h2>", html)
        self.assertNotIn("Certifications &amp; languages", html)
        self.assertIn("Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-au-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-au-photo", html)

    def test_aurora_pdf_uses_contact_row_and_education_skills_table(self):
        self.assertIn("body.tt-pdf-export .tpl-aurora .tpl-au-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-au-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-au-row .tpl-au-card--half {", STUDIO_PDF_PAGE_CSS)

    def test_magazine_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, music, cricket"
        sample["interests"] = "Should not appear as Interests"
        sample["projects"] = [
            {
                "title": "Personal Portfolio Website",
                "company": "HTML, CSS",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a personal portfolio site."],
            }
        ]
        sample["achievements"] = [
            {
                "title": "Smart Water Level Alarm",
                "company": "Activity",
                "location": "",
                "dates": "",
                "bullets": ["Designed and built a water level alarm."],
            }
        ]
        pack = _sample_pack("magazine")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Skills</h3>", html)
        self.assertIn("Education</h3>", html)
        self.assertIn("Languages</h3>", html)
        self.assertIn("Certifications</h3>", html)
        self.assertIn("Hobbies</h3>", html)
        self.assertIn("Reading, music, cricket", html)
        self.assertNotIn(">Interests</h3>", html)
        self.assertIn("tpl-mz-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-mz-grid", html)

    def test_magazine_pdf_uses_table_layout(self):
        self.assertIn("body.tt-pdf-export .tpl-mz-grid {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-magazine .tpl-mz-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: table !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-magazine {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn(
            'body.tt-pdf-export[data-pdf-engine="weasyprint"] .tpl-mz-grid {',
            STUDIO_PDF_PAGE_CSS,
        )

    def test_pdf_css_shows_contact_icon_fallbacks(self):
        self.assertIn("body.tt-pdf-export .tpl-contact-icon svg", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-contact-icon .tpl-contact-fallback", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: inline-flex !important", STUDIO_PDF_PAGE_CSS)

    def test_professional_border_renders_profile_photo_markup(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["photo"] = "data:image/png;base64,iVBORw0KGgo="
        pack = _sample_pack("professional-border")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("tpl-pb-avatar", html)
        self.assertIn('src="data:image/png;base64,iVBORw0KGgo="', html)
        self.assertIn('width="100"', html)

    def test_classic_sidebar_matches_studio_sections(self):
        sample = dict(ADMIN_STUDIO_HTML_PREVIEW_SAMPLE)
        sample["hobbies"] = "Reading, music"
        sample["projects"] = [
            {
                "title": "Capstone app",
                "company": "React, Node",
                "location": "",
                "dates": "2025",
                "bullets": ["Built a dashboard for school analytics."],
            }
        ]
        pack = _sample_pack("classic-sidebar")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Work Experience", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertNotIn(">Interests</h2>", html)

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
