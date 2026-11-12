from django.contrib.sitemaps import Sitemap
from django.core.paginator import Paginator
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from urllib.parse import urlparse

from blog.models import Blog, BlogCategory
from careers.models import Career, CareerCluster, VideoCategory, Videos
from colleges.models import College
from core import choices
from core.models import (
    Ebook,
    EntranceTestPrepCategory,
    EntranceTestPrepExam,
    ExtracurricularActivity,
    GeneratedPage,
    URLIndexRule,
    VocationalCourse,
    VocationalCourseCategory,
)
from courses.models import Course
from entrance_exams.models import EntranceExam
from skilllab.models import SkillLabCourse


class IndexRuleFilteredSitemap(Sitemap):
    """
    Exclude URLs from sitemap when they match active URLIndexRule records that
    are configured to block indexing/robots.
    """

    def _get_active_blocking_rules(self):
        try:
            return URLIndexRule.get_active_rules().filter(
                Q(apply_in_robots=True) | Q(apply_x_robots_tag=True)
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

    def get_latest_lastmod(self):
        # Keep sitemap.xml (the index) from loading every section just to stamp lastmod.
        return None


class _SectionPaginator:
    """Index reads num_pages only. URL rows are loaded when that section file is rendered."""

    def __init__(self, sitemap):
        self.sitemap = sitemap
        self.per_page = sitemap.limit

    @property
    def num_pages(self):
        count = self.sitemap.estimated_count()
        if count <= 0:
            return 1
        return (count + self.per_page - 1) // self.per_page

    def page(self, number):
        return Paginator(self.sitemap.items(), self.per_page).page(number)


class SectionSitemap(IndexRuleFilteredSitemap):
    """Hub URL names plus model rows, cached so a section file is built once."""

    changefreq = "weekly"
    priority = 0.7
    named_urls = []

    @property
    def paginator(self):
        return _SectionPaginator(self)

    def estimated_count(self):
        return len(self._named_items()) + self._model_count()

    def _model_count(self):
        return 0

    def items(self):
        cached = getattr(self, "_items_cache", None)
        if cached is None:
            cached = self._named_items() + self._model_items()
            self._items_cache = cached
        return cached

    def _named_items(self):
        rows = []
        for name in self.named_urls:
            try:
                reverse(name)
            except NoReverseMatch:
                continue
            rows.append(("named", name))
        return rows

    def _model_items(self):
        return []

    def location(self, item):
        kind, value = item
        if kind == "named":
            return reverse(value)
        return self.model_location(kind, value)

    def model_location(self, kind, value):
        raise NotImplementedError

    def lastmod(self, item):
        kind, value = item
        if kind == "named":
            return None
        return getattr(value, "modified", None)


def _with_slug(queryset):
    return queryset.exclude(slug__isnull=True).exclude(slug="")


class PagesSitemap(SectionSitemap):
    priority = 0.8
    named_urls = [
        "core:home",
        "core:aboutus",
        "core:contactus",
        "core:terms&condition",
        "core:privacypolicy",
        "core:allfaq",
    ]

    def _page_queryset(self):
        return _with_slug(GeneratedPage.objects.filter(is_active=True))

    def _model_count(self):
        return self._page_queryset().count()

    def _model_items(self):
        return [("page", page) for page in self._page_queryset().order_by("-modified", "-id")]

    def model_location(self, kind, value):
        return reverse("core:generated_page", args=[value.slug])


class ExtracurricularSitemap(SectionSitemap):
    priority = 0.7
    named_urls = ["core:extracurricular_activities"]

    def _model_count(self):
        return ExtracurricularActivity.objects.count()

    def _model_items(self):
        activities = ExtracurricularActivity.objects.order_by("priority", "id")
        return [("activity", activity) for activity in activities]

    def model_location(self, kind, value):
        return reverse("core:extracurricular_activity_detail", args=[value.pk])


class VocationalCoursesSitemap(SectionSitemap):
    priority = 0.7
    changefreq = "monthly"
    named_urls = ["core:vocational_courses"]

    def _model_count(self):
        levels = _with_slug(VocationalCourseCategory.objects.filter(parent__isnull=True))
        return levels.count() + VocationalCourse.objects.count()

    def _model_items(self):
        rows = []
        levels = VocationalCourseCategory.objects.filter(parent__isnull=True).order_by("priority", "name")
        for level in _with_slug(levels):
            rows.append(("level", level))
        courses = VocationalCourse.objects.order_by("-modified", "-id")
        for course in courses:
            rows.append(("course", course))
        return rows

    def model_location(self, kind, value):
        if kind == "level":
            return reverse("core:vocational_courses_level", args=[value.slug])
        return reverse("core:vocational_course_detail", args=[value.pk])


class CareerPlanningSitemap(SectionSitemap):
    priority = 0.8
    named_urls = [
        "core:career_planning",
        "core:career_planning_4_year",
        "core:career_planning_class_9",
        "core:career_planning_class_10",
        "core:career_planning_class_11",
        "core:career_planning_class_12",
    ]

    def model_location(self, kind, value):
        raise NotImplementedError


class BlogSitemap(SectionSitemap):
    priority = 0.8
    named_urls = ["blog:blogs"]

    def _model_count(self):
        posts = Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)
        return _with_slug(BlogCategory.objects).count() + _with_slug(posts).count()

    def _model_items(self):
        rows = [("category", category) for category in _with_slug(BlogCategory.objects.order_by("name"))]
        posts = Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).order_by("-modified", "-id")
        rows.extend(("post", post) for post in _with_slug(posts))
        return rows

    def model_location(self, kind, value):
        if kind == "category":
            return reverse("blog:category", args=[value.slug])
        return reverse("blog:blogdetail", args=[value.slug])


class EbookSitemap(SectionSitemap):
    priority = 0.6
    changefreq = "monthly"
    named_urls = ["core:ebook_list"]

    def _published_ebooks(self):
        return _with_slug(Ebook.objects.filter(publish_status=choices.PublishStatus.PUBLISHED))

    def _model_count(self):
        return self._published_ebooks().count()

    def _model_items(self):
        return [("ebook", book) for book in self._published_ebooks().order_by("priority", "title")]

    def model_location(self, kind, value):
        return reverse("core:ebook_detail", args=[value.slug])


class CareerLibrarySitemap(SectionSitemap):
    priority = 0.9
    named_urls = ["careers:career"]

    def _model_count(self):
        careers = Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)
        return _with_slug(CareerCluster.objects).count() + _with_slug(careers).count()

    def _model_items(self):
        rows = []
        clusters = CareerCluster.objects.order_by("name")
        for cluster in _with_slug(clusters):
            rows.append(("cluster", cluster))
        careers = Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).order_by("-modified", "-id")
        for career in _with_slug(careers):
            rows.append(("career", career))
        return rows

    def model_location(self, kind, value):
        if kind == "cluster":
            return reverse("careers:career_cluster", args=[value.slug, value.id])
        return reverse("careers:careerdetail", args=[value.slug, value.id])


class CollegeSitemap(SectionSitemap):
    priority = 0.8
    named_urls = ["colleges:college"]

    def _published_colleges(self):
        return _with_slug(College.objects.filter(publish_status=choices.PublishStatus.PUBLISHED))

    def _model_count(self):
        return self._published_colleges().count()

    def _model_items(self):
        colleges = self._published_colleges().order_by("-modified", "-id")
        return [("college", college) for college in colleges]

    def model_location(self, kind, value):
        return reverse("colleges:collegedetail", args=[value.slug])


class VideoLibrarySitemap(SectionSitemap):
    priority = 0.6
    named_urls = ["careers:careervideos"]

    def _model_count(self):
        return _with_slug(VideoCategory.objects).count() + _with_slug(Videos.objects).count()

    def _model_items(self):
        rows = [("category", category) for category in _with_slug(VideoCategory.objects.order_by("name"))]
        rows.extend(("video", video) for video in _with_slug(Videos.objects.order_by("-modified", "-id")))
        return rows

    def model_location(self, kind, value):
        if kind == "category":
            return reverse("careers:category", args=[value.slug])
        return reverse("careers:videodetail", args=[value.slug])


class AssessmentsSitemap(SectionSitemap):
    priority = 0.7
    named_urls = [
        "psychometrictests:psychometrictest",
        "psychometrictests:PsychometricTest12",
        "core:four_pillars",
        "core:multiple_intelligences",
        "core:emotional_intelligences",
    ]

    def _model_count(self):
        from core.views import FOUR_PILLARS_PILLAR_CONFIG

        return len(FOUR_PILLARS_PILLAR_CONFIG)

    def _model_items(self):
        from core.views import FOUR_PILLARS_PILLAR_CONFIG

        return [("pillar", number) for number in sorted(FOUR_PILLARS_PILLAR_CONFIG)]

    def model_location(self, kind, value):
        return reverse("core:four_pillars_pillar", args=[value])

    def lastmod(self, item):
        return None


class CollegeCareerReadinessSitemap(SectionSitemap):
    priority = 0.7
    named_urls = ["skilllabcourse:skilllabcourselist"]

    def _model_count(self):
        return _with_slug(SkillLabCourse.objects).count()

    def _model_items(self):
        courses = SkillLabCourse.objects.order_by("name")
        return [("course", course) for course in _with_slug(courses)]

    def model_location(self, kind, value):
        return reverse("skilllabcourse:skilllabcoursedetail", args=[value.slug])


class CounselorCourseSitemap(SectionSitemap):
    priority = 0.7
    named_urls = [
        "counselor:CounselorCoursepayment",
        "counselor:counselor_course_detail",
        "counselor:counselor_course_curriculum",
    ]

    def model_location(self, kind, value):
        raise NotImplementedError


class EntranceExamsSitemap(SectionSitemap):
    priority = 0.7
    changefreq = "monthly"
    named_urls = [
        "core:entrance_test_prep",
        "entrance_exams:testpreptenth",
    ]

    def _model_count(self):
        categories = EntranceTestPrepCategory.objects.filter(parent__isnull=False, parent__slug__gt="")
        return (
            _with_slug(categories).count()
            + _with_slug(EntranceTestPrepExam.objects).count()
            + _with_slug(EntranceExam.objects).count()
        )

    def _model_items(self):
        rows = []
        categories = EntranceTestPrepCategory.objects.filter(parent__isnull=False).select_related("parent")
        for category in _with_slug(categories):
            parent = category.parent
            if parent and parent.slug:
                rows.append(("category", category))
        exams = EntranceTestPrepExam.objects.order_by("priority", "name")
        rows.extend(("exam", exam) for exam in _with_slug(exams))
        legacy = EntranceExam.objects.order_by("-modified", "-id")
        rows.extend(("legacy", exam) for exam in _with_slug(legacy))
        return rows

    def model_location(self, kind, value):
        if kind == "category":
            return reverse(
                "core:entrance_test_prep_category",
                args=[value.parent.slug, value.slug],
            )
        if kind == "exam":
            return reverse("core:entrance_test_prep_exam_detail", args=[value.slug])
        return reverse("entrance_exams:testprepdetail", args=[value.slug])


class CourseSitemap(SectionSitemap):
    priority = 0.7

    def _model_count(self):
        return _with_slug(Course.objects).count()

    def _model_items(self):
        courses = Course.objects.order_by("-modified", "-id")
        return [("course", course) for course in _with_slug(courses)]

    def model_location(self, kind, value):
        return reverse("courses:coursedetail", args=[value.slug, value.id])


# Keys become /sitemap-<key>.xml and are listed from /sitemap.xml.
SITEMAPS = {
    "extracurricular": ExtracurricularSitemap,
    "vocational-courses": VocationalCoursesSitemap,
    "career-planning": CareerPlanningSitemap,
    "blogs": BlogSitemap,
    "ebooks": EbookSitemap,
    "career-library": CareerLibrarySitemap,
    "colleges": CollegeSitemap,
    "video-library": VideoLibrarySitemap,
    "assessments": AssessmentsSitemap,
    "college-career-readiness": CollegeCareerReadinessSitemap,
    "counselor-course": CounselorCourseSitemap,
    "entrance-exams": EntranceExamsSitemap,
    "courses": CourseSitemap,
    "pages": PagesSitemap,
}
