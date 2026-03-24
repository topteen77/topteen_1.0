from django.contrib.sitemaps import Sitemap
from django.db.utils import OperationalError, ProgrammingError
from django.urls import NoReverseMatch, reverse
from urllib.parse import urlparse

from blog.models import Blog
from careers.models import Career
from colleges.models import College
from core import choices
from core.models import EntranceTestPrepExam, GeneratedPage, URLIndexRule, VocationalCourse
from courses.models import Course
from entrance_exams.models import EntranceExam


class IndexRuleFilteredSitemap(Sitemap):
    """
    Exclude URLs from sitemap when they match active URLIndexRule records that
    are configured to block indexing/robots.
    """

    def _get_active_blocking_rules(self):
        try:
            return URLIndexRule.get_active_rules().filter(
                apply_in_robots=True
            ).only("path_pattern", "match_type")
        except (ProgrammingError, OperationalError):
            return []

    def _is_blocked_path(self, location):
        path = urlparse(location).path or "/"
        for rule in self._get_active_blocking_rules():
            if rule.matches(path):
                return True
        return False

    def get_urls(self, page=1, site=None, protocol=None):
        urls = super().get_urls(page=page, site=site, protocol=protocol)
        return [entry for entry in urls if not self._is_blocked_path(entry.get("location", ""))]


class StaticViewSitemap(IndexRuleFilteredSitemap):
    priority = 0.8
    changefreq = "weekly"

    # Keep this list restricted to public pages without required args.
    url_names = [
        "core:home",
        "core:aboutus",
        "core:contactus",
        "core:terms&condition",
        "core:privacypolicy",
        "core:allfaq",
        "core:extracurricular_activities",
        "core:vocational_courses",
        "core:entrance_test_prep",
        "core:career_planning",
        "core:career_planning_4_year",
        "core:career_planning_class_9",
        "core:career_planning_class_10",
        "core:career_planning_class_11",
        "core:career_planning_class_12",
        "core:emotional_intelligences",
        "core:multiple_intelligences",
        "core:four_pillars",
        "core:ebook_list",
        "careers:career",
        "colleges:college",
        "entrance_exams:testpreptenth",
        "blog:blogs",
    ]

    def items(self):
        valid_names = []
        for name in self.url_names:
            try:
                reverse(name)
                valid_names.append(name)
            except NoReverseMatch:
                continue
        return valid_names

    def location(self, item):
        return reverse(item)


class BlogSitemap(IndexRuleFilteredSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Blog.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("blog:blogdetail", args=[obj.slug])


class CareerSitemap(IndexRuleFilteredSitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("careers:careerdetail", args=[obj.slug, obj.id])


class CollegeSitemap(IndexRuleFilteredSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return College.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("colleges:collegedetail", args=[obj.slug])


class CourseSitemap(IndexRuleFilteredSitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Course.objects.all().order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("courses:coursedetail", args=[obj.slug, obj.id])


class EntranceExamSitemap(IndexRuleFilteredSitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return EntranceExam.objects.all().order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("entrance_exams:testprepdetail", args=[obj.slug])


class EntranceTestPrepExamSitemap(IndexRuleFilteredSitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return EntranceTestPrepExam.objects.all().order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("core:entrance_test_prep_exam_detail", args=[obj.slug])


class VocationalCourseSitemap(IndexRuleFilteredSitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return VocationalCourse.objects.all().order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        category = obj.category
        if category and category.parent:
            return reverse(
                "core:vocational_courses_level",
                args=[category.parent.slug],
            ) + f"?category={category.slug}"
        if category:
            return reverse("core:vocational_courses_level", args=[category.slug])
        return reverse("core:vocational_courses")


class GeneratedPageSitemap(IndexRuleFilteredSitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return GeneratedPage.objects.filter(is_active=True).order_by("-modified", "-id")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("core:generated_page", args=[obj.slug])

