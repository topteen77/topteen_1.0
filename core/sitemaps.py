from django.contrib.sitemaps import Sitemap
from django.urls import NoReverseMatch, reverse

from blog.models import Blog
from careers.models import Career
from colleges.models import College
from core import choices
from core.models import EntranceTestPrepExam, GeneratedPage, VocationalCourse
from courses.models import Course
from entrance_exams.models import EntranceExam


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    # Keep this list restricted to public pages without required args.
    url_names = [
        "home",
        "aboutus",
        "contactus",
        "terms&condition",
        "privacypolicy",
        "allfaq",
        "extracurricular_activities",
        "vocational_courses",
        "entrance_test_prep",
        "career_planning",
        "career_planning_4_year",
        "career_planning_class_9",
        "career_planning_class_10",
        "career_planning_class_11",
        "career_planning_class_12",
        "emotional_intelligences",
        "multiple_intelligences",
        "four_pillars",
        "ebook_list",
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


class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("blog:blogdetail", args=[obj.slug])


class CareerSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("careers:careerdetail", args=[obj.slug, obj.id])


class CollegeSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return College.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("colleges:collegedetail", args=[obj.slug])


class CourseSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Course.objects.all()

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("courses:coursedetail", args=[obj.slug, obj.id])


class EntranceExamSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return EntranceExam.objects.all()

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("entrance_exams:testprepdetail", args=[obj.slug])


class EntranceTestPrepExamSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return EntranceTestPrepExam.objects.all()

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("entrance_test_prep_exam_detail", args=[obj.slug])


class VocationalCourseSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return VocationalCourse.objects.all()

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        category = obj.category
        if category and category.parent:
            return reverse(
                "vocational_courses_level",
                args=[category.parent.slug],
            ) + f"?category={category.slug}"
        if category:
            return reverse("vocational_courses_level", args=[category.slug])
        return reverse("vocational_courses")


class GeneratedPageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return GeneratedPage.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("generated_page", args=[obj.slug])

