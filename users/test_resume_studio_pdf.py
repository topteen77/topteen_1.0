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

    def test_modern_split_pdf_uses_table_rows_and_allows_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-ms-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: table !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-modern-split .tpl-ms-grid .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

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

    def test_professional_border_pdf_uses_table_layout_and_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-professional-border {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-professional-border .tpl-pb-main,", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: table-cell !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-professional-border .tpl-pb-main .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_professional_border_pdf_preserves_accent_heading_and_icon_colors(self):
        self.assertIn("body.tt-pdf-export .tpl-professional-border .tpl-h2 {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("color: var(--resume-accent) !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("border-bottom: 2px solid var(--resume-accent) !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn(
            "body.tt-pdf-export .tpl-professional-border .tpl-pb-contact-row .tpl-contact-fallback",
            STUDIO_PDF_PAGE_CSS,
        )
        block = studio_pack_root_css_block(_sample_pack("professional-border"))
        self.assertIn("--resume-accent:", block)

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

    def test_tech_focus_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-tech-focus .tpl-tf-main .tpl-job {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

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

    def test_high_contrast_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-high-contrast {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-hc-body {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-high-contrast .tpl-hc-main .tpl-job {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

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

    def test_aurora_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-aurora {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-au-body {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-au-card {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-aurora .tpl-au-card .tpl-job {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_timeline_matches_studio_sections(self):
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
        pack = _sample_pack("timeline")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-tl-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)

    def test_timeline_pdf_uses_contact_row_and_table_two_col(self):
        self.assertIn("body.tt-pdf-export .tpl-timeline .tpl-tl-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-timeline .tpl-tl-two {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-timeline .tpl-tl-dot {", STUDIO_PDF_PAGE_CSS)

    def test_timeline_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-timeline {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-timeline .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_executive_matches_studio_sections(self):
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
        pack = _sample_pack("executive")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-ex-contact", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)

    def test_executive_pdf_uses_contact_icons_and_table_layout(self):
        self.assertIn("body.tt-pdf-export .tpl-executive {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-ex-contact .tpl-contact-item {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-executive .tpl-ex-main .tpl-sec {", STUDIO_PDF_PAGE_CSS)

    def test_executive_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-executive .tpl-ex-main .tpl-job {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_studio_matches_studio_sections(self):
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
        pack = _sample_pack("studio")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-st-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-st-photo", html)

    def test_studio_pdf_uses_contact_row_and_split_table(self):
        self.assertIn("body.tt-pdf-export .tpl-studio .tpl-st-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("flex-wrap: nowrap !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-studio .tpl-st-contact-row .tpl-contact-text {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("white-space: nowrap !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-st-split {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-st-photo {", STUDIO_PDF_PAGE_CSS)

    def test_studio_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-studio {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-st-card {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-studio .tpl-st-card .tpl-job {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_nova_matches_studio_sections(self):
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
        pack = _sample_pack("nova")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-nv-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-nv-photo", html)

    def test_nova_pdf_uses_contact_row_and_split_table(self):
        self.assertIn("body.tt-pdf-export .tpl-nova .tpl-nv-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("flex-wrap: nowrap !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-nv-split {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-nv-photo {", STUDIO_PDF_PAGE_CSS)

    def test_nova_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-nova {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-nv-panel {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-nv-body {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_folio_matches_studio_sections(self):
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
        pack = _sample_pack("folio")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-fo-contact-row", html)
        self.assertIn("tpl-contact-icon", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("tpl-fo-photo", html)

    def test_folio_pdf_uses_contact_row_and_numbered_sections(self):
        self.assertIn("body.tt-pdf-export .tpl-folio .tpl-fo-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-fo-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-fo-photo {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("flex-wrap: nowrap !important", STUDIO_PDF_PAGE_CSS)

    def test_folio_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-folio {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-folio .tpl-job--fo {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_vertex_matches_studio_sections(self):
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
        pack = _sample_pack("vertex")
        pack["resume"] = sample
        html, _ = studio_proto_pack_to_mount_html(pack)
        self.assertIn("Projects", html)
        self.assertIn("Achievements &amp; Activities", html)
        self.assertIn("Career Objective", html)
        self.assertIn("Education", html)
        self.assertIn("Certifications", html)
        self.assertIn("Languages", html)
        self.assertIn(">Hobbies</h2>", html)
        self.assertIn("Reading, music, community service", html)
        self.assertNotIn(">Interests</h2>", html)
        self.assertIn("tpl-vx-contact-row", html)
        self.assertIn("tpl-vx-contact-piece", html)
        self.assertIn("+91 90000 00000", html)
        self.assertIn("tpl-vx-photo", html)
        self.assertIn("tpl-vx-banner-main", html)
        self.assertIn("tpl-contact-fallback", html)
        self.assertIn("preview@example.com", html)
        self.assertNotIn("Extracurricular interest from profile", html)

    def test_vertex_pdf_uses_contact_row_and_grid_table(self):
        self.assertIn("body.tt-pdf-export .tpl-vertex .tpl-vx-contact-row {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-vx-grid {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-vx-banner-main {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("display: table !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-vx-photo {", STUDIO_PDF_PAGE_CSS)

    def test_vertex_pdf_allows_main_content_flow(self):
        self.assertIn("body.tt-pdf-export .tpl-vertex {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-vertex .tpl-vx-body .tpl-sec {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

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

    def test_classic_sidebar_pdf_flows_main_content_without_full_page_min_height(self):
        self.assertIn("body.tt-pdf-export .tpl-classic-sidebar {", STUDIO_PDF_PAGE_CSS)
        self.assertIn("body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-side,", STUDIO_PDF_PAGE_CSS)
        self.assertIn("min-height: auto !important", STUDIO_PDF_PAGE_CSS)
        self.assertIn(
            "body.tt-pdf-export .tpl-classic-sidebar .tpl-cs-main .tpl-sec {",
            STUDIO_PDF_PAGE_CSS,
        )
        self.assertIn("page-break-inside: auto !important", STUDIO_PDF_PAGE_CSS)

    def test_pdf_shell_includes_sidebar_full_height_css(self):
        pack = _sample_pack("executive")
        mount_html, tid = studio_proto_pack_to_mount_html(pack)
        ctx = studio_pdf_template_context(mount_html, tid, pack)
        html = render_to_string("mail/user/userresumepdf_studio_prototype.html", ctx)
        self.assertIn(PDF_CONTENT_MIN_HEIGHT, html)
        self.assertIn("min-height: var(--pdf-page-min-height)", html)
        self.assertIn('data-pdf-engine=', html)
        self.assertIn("tpl-ex-side", html)

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
