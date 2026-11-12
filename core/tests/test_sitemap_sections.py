import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import ExtracurricularActivity, ExtracurricularActivityCategory
from core.sitemaps import SITEMAPS

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

SECTION_PATHS = {
    "extracurricular": "/extracurricular-activities/",
    "vocational-courses": "/vocational-courses/",
    "career-planning": "/career-planning/",
    "blogs": "/blogs/",
    "ebooks": "/ebooks/",
    "career-library": "/careers/",
    "colleges": "/colleges/",
    "video-library": "/careers/career-videos/",
    "assessments": "/four-pillars-of-learning/",
    "college-career-readiness": "/skilllabcourse/",
    "counselor-course": "/counselor/Counselor_Course_payment/",
    "entrance-exams": "/entrance-test-prep/",
    "pages": "/",
}


def _locs(content, tag):
    root = ET.fromstring(content)
    return [node.text for node in root.findall(f"sm:{tag}/sm:loc", NS)]


@override_settings(
    ALLOW_SEARCH_ENGINE_INDEX=True,
    ALLOWED_HOSTS=["testserver"],
    SECURE_SSL_REDIRECT=False,
)
class SitemapSectionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_lists_every_section(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"])
        locs = _locs(response.content, "sitemap")
        self.assertEqual(len(locs), len(SITEMAPS))
        for section in SITEMAPS:
            expected = reverse("sitemap-section", kwargs={"section": section})
            self.assertTrue(
                any(loc.endswith(expected) for loc in locs),
                msg=f"missing {section} in {locs}",
            )

    def test_each_section_contains_its_hub(self):
        for section, path in SECTION_PATHS.items():
            response = self.client.get(f"/sitemap-{section}.xml")
            self.assertEqual(response.status_code, 200, msg=section)
            root = ET.fromstring(response.content)
            self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
            locs = _locs(response.content, "url")
            self.assertTrue(
                any(urlparse(loc).path == path for loc in locs),
                msg=f"{section} missing {path} in {locs}",
            )

    def test_extracurricular_includes_activity_detail(self):
        category = ExtracurricularActivityCategory.objects.create(name="Sports")
        activity = ExtracurricularActivity.objects.create(category=category, name="Debate")
        response = self.client.get("/sitemap-extracurricular.xml")
        locs = _locs(response.content, "url")
        detail = reverse("core:extracurricular_activity_detail", args=[activity.pk])
        self.assertTrue(any(loc.endswith(detail) for loc in locs))

    def test_assessments_include_pillar_pages(self):
        response = self.client.get("/sitemap-assessments.xml")
        locs = _locs(response.content, "url")
        for number in (1, 2, 3, 4):
            path = reverse("core:four_pillars_pillar", args=[number])
            self.assertTrue(any(loc.endswith(path) for loc in locs), msg=path)

    def test_unknown_section_is_404(self):
        response = self.client.get("/sitemap-not-a-section.xml")
        self.assertEqual(response.status_code, 404)

    def test_hidden_when_indexing_disabled(self):
        with override_settings(ALLOW_SEARCH_ENGINE_INDEX=False, ALLOW_DEMO_SEARCH_INDEX=False):
            index = self.client.get("/sitemap.xml")
            section = self.client.get("/sitemap-blogs.xml")
        self.assertEqual(index.status_code, 404)
        self.assertEqual(section.status_code, 404)

    def test_courses_section_is_urlset(self):
        response = self.client.get("/sitemap-courses.xml")
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertTrue(root.tag.endswith("urlset"))
