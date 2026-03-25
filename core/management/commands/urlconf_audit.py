"""
Walk ROOT_URLCONF (all urlpatterns, not sitemap.xml), generate concrete URLs via reverse()
and ORM-backed expanders, HTTP GET each path, report only HTTP 404 responses.

Notes:
  - Admin and topteenadmin trees are skipped unless --include-admin.
  - robots.txt / sitemap.xml return 404 when ALLOW_SEARCH_ENGINE_INDEX is False.
  - Patterns without DB expanders use placeholder path segments (may 404).

Usage:
  python manage.py urlconf_audit
  python manage.py urlconf_audit -o /tmp/url_404.txt
  python manage.py urlconf_audit --include-admin
  python manage.py urlconf_audit --max-urls 2000
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import URLPattern, URLResolver, NoReverseMatch, reverse


# Do not crawl these namespace prefixes unless --include-admin
_DEFAULT_SKIP_NS = frozenset(
    {
        "admin",
        "topteenadmin",
        "topteenadminmanaged",
    }
)

# URL names to skip (cannot reverse meaningfully or not useful)
_SKIP_NAMES = frozenset({"404"})


def _resolver_skip_namespace(resolver_namespace, include_admin):
    """Skip whole subtrees (admin / topteenadmin) unless --include-admin."""
    if include_admin:
        return False
    if not resolver_namespace:
        return False
    return resolver_namespace in _DEFAULT_SKIP_NS


def _iter_patterns(urlpatterns, prefix="", namespace=None, include_admin=False):
    """Yield (full_name, URLPattern, pattern_prefix) for every named route."""
    for p in urlpatterns:
        if isinstance(p, URLResolver):
            ns = p.namespace
            if _resolver_skip_namespace(ns, include_admin):
                continue
            if namespace and ns:
                new_ns = f"{namespace}:{ns}"
            elif ns:
                new_ns = ns
            else:
                new_ns = namespace
            yield from _iter_patterns(
                p.url_patterns,
                prefix + str(p.pattern),
                new_ns,
                include_admin=include_admin,
            )
        elif isinstance(p, URLPattern) and p.name:
            if p.name in _SKIP_NAMES:
                continue
            full = f"{namespace}:{p.name}" if namespace else p.name
            if not include_admin:
                skip = False
                for pfx in _DEFAULT_SKIP_NS:
                    if full == pfx or full.startswith(pfx + ":"):
                        skip = True
                        break
                if skip:
                    continue
            yield full, p, prefix + str(p.pattern)


def _converters_map(urlpattern):
    pat = urlpattern.pattern
    return getattr(pat, "converters", None) or {}


def _default_kwargs(converters):
    kw = {}
    for key, conv in converters.items():
        cn = conv.__class__.__name__
        if cn == "IntConverter":
            kw[key] = 1
        elif cn == "SlugConverter":
            kw[key] = "x"
        elif cn == "StrConverter":
            kw[key] = "x"
        elif cn == "PathConverter":
            kw[key] = "app/index.html"
        elif cn == "UUIDConverter":
            kw[key] = uuid.UUID(int=0)
        else:
            kw[key] = "1"
    return kw


def _reverse_or_none(full_name, kwargs=None, args=None):
    try:
        if kwargs is not None:
            return reverse(full_name, kwargs=kwargs)
        if args is not None:
            return reverse(full_name, args=args)
        return reverse(full_name)
    except NoReverseMatch:
        return None


@lru_cache(maxsize=1)
def _expanders_by_key():
    """(full_name, frozenset(param_keys)) -> callable returning iterable of dict (kwargs)."""
    ex = {}

    def add(fname, keys, fn):
        ex[(fname, frozenset(keys))] = fn

    # --- blog ---
    def blog_details():
        from blog.models import Blog
        from core import choices

        qs = Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).values_list(
            "slug", flat=True
        )
        for slug in qs:
            yield {"blog_slug": slug}

    add("blog:blogdetail", ("blog_slug",), blog_details)

    # --- careers ---
    def career_published():
        from careers.models import Career
        from core import choices

        for slug, pk in Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).values_list("slug", "id"):
            yield {"slug": slug, "career_id": pk}

    add("careers:careerdetail", ("slug", "career_id"), career_published)
    add("careers:career_mindmap", ("slug", "career_id"), career_published)

    def career_clusters():
        from careers.models import CareerCluster
        from core import choices

        # CareerCluster uses BaseModel.object_status, not PublishableModel.publish_status
        for slug, pk in CareerCluster.objects.filter(
            object_status=choices.ObjectStatus.ACTIVE
        ).values_list("slug", "id"):
            yield {"cluster_slug": slug, "cluster_id": pk}

    add("careers:career_cluster", ("cluster_slug", "cluster_id"), career_clusters)
    add("careers:careerlibrary", ("cluster_slug", "cluster_id"), career_clusters)

    def career_tags():
        from careers.models import CareerTags

        for slug in CareerTags.objects.values_list("slug", flat=True).distinct():
            if slug:
                yield {"tagslug": slug}

    add("careers:careertag", ("tagslug",), career_tags)

    def professions():
        from careers.models import Career
        from core import choices

        for slug in Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).values_list("slug", flat=True):
            yield {"career_slug": slug}

    add("careers:profession", ("career_slug",), professions)

    def video_cats():
        from careers.models import VideoCategory

        for slug in VideoCategory.objects.values_list("slug", flat=True):
            if slug:
                yield {"category_slug": slug}

    add("careers:category", ("category_slug",), video_cats)

    def video_details():
        from careers.models import Videos

        for slug in Videos.objects.values_list("slug", flat=True):
            if slug:
                yield {"video_slug": slug}

    add("careers:videodetail", ("video_slug",), video_details)

    # --- colleges ---
    def college_slugs():
        from colleges.models import College
        from core import choices

        for slug in College.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).values_list("slug", flat=True):
            yield {"slug": slug}

    add("colleges:collegedetail", ("slug",), college_slugs)

    # --- courses (two patterns share name; kwargs disambiguate) ---
    def course_by_id():
        from courses.models import Course

        for pk in Course.objects.values_list("id", flat=True):
            yield {"course_id": pk}

    add("courses:coursedetail", ("course_id",), course_by_id)

    def course_slug_id():
        from courses.models import Course

        for slug, pk in Course.objects.values_list("slug", "id"):
            yield {"slug": slug, "course_id": pk}

    add("courses:coursedetail", ("slug", "course_id"), course_slug_id)

    # --- entrance exams ---
    def exam_slugs():
        from entrance_exams.models import EntranceExam

        for slug in EntranceExam.objects.values_list("slug", flat=True):
            if slug:
                yield {"exam_slug": slug}

    add("entrance_exams:testprepdetail", ("exam_slug",), exam_slugs)

    # --- core: generated / ebooks / pillars / extracurricular / vocational / etp ---
    def gen_pages():
        from core.models import GeneratedPage

        for slug in GeneratedPage.objects.filter(is_active=True).values_list("slug", flat=True):
            yield {"slug": slug}

    add("core:generated_page", ("slug",), gen_pages)

    # Career Battle SPA catch-all: no single canonical path without knowing built assets.
    add("core:language_game_app_path", ("path",), lambda: iter(()))

    def ebooks():
        from core.models import Ebook

        for slug in Ebook.objects.values_list("slug", flat=True):
            if slug:
                yield {"slug": slug}

    add("core:ebook_detail", ("slug",), ebooks)

    def pillars():
        for n in (1, 2, 3, 4):
            yield {"pillar_number": n}

    add("core:four_pillars_pillar", ("pillar_number",), pillars)

    def pillar_assessments():
        from core.views import FOUR_PILLARS_ASSESSMENT_SLUGS

        for slug in FOUR_PILLARS_ASSESSMENT_SLUGS:
            yield {"pillar_slug": slug}

    add("core:four_pillars_assessment", ("pillar_slug",), pillar_assessments)

    def extracurricular():
        from core.models import ExtracurricularActivity

        for pk in ExtracurricularActivity.objects.values_list("id", flat=True):
            yield {"pk": pk}

    add("core:extracurricular_activity_detail", ("pk",), extracurricular)

    def vocational_levels():
        from core.models import VocationalCourseCategory

        for slug in VocationalCourseCategory.objects.values_list("slug", flat=True):
            if slug:
                yield {"level_slug": slug}

    add("core:vocational_courses_level", ("level_slug",), vocational_levels)

    def vocational_courses_pk():
        from core.models import VocationalCourse

        for pk in VocationalCourse.objects.values_list("id", flat=True):
            yield {"pk": pk}

    add("core:vocational_course_detail", ("pk",), vocational_courses_pk)

    def etp_exams():
        from core.models import EntranceTestPrepExam

        for slug in EntranceTestPrepExam.objects.values_list("slug", flat=True):
            if slug:
                yield {"slug": slug}

    add("core:entrance_test_prep_exam_detail", ("slug",), etp_exams)

    def etp_category():
        from core.models import EntranceTestPrepCategory

        for lvl_slug, cat_slug in EntranceTestPrepCategory.objects.filter(
            parent__isnull=False
        ).values_list("parent__slug", "slug"):
            if lvl_slug and cat_slug:
                yield {"level_slug": lvl_slug, "category_slug": cat_slug}

    add(
        "core:entrance_test_prep_category",
        ("level_slug", "category_slug"),
        etp_category,
    )

    # --- skilllab (slugs from DB) ---
    def _skilllab_course_slugs():
        from skilllab.models import SkillLabCourse

        for slug in SkillLabCourse.objects.values_list("slug", flat=True):
            if slug:
                yield slug

    def skilllab_detail():
        for slug in _skilllab_course_slugs():
            yield {"skilllab_slug": slug}

    def skilllab_course_slug_routes():
        for slug in _skilllab_course_slugs():
            yield {"course_slug": slug}

    def skilllab_payment_slug():
        for slug in _skilllab_course_slugs():
            yield {"slug": slug}

    add("skilllabcourse:skilllabcoursedetail", ("skilllab_slug",), skilllab_detail)
    add("skilllabcourse:course_learning", ("course_slug",), skilllab_course_slug_routes)
    add("skilllabcourse:skilllab_certificate", ("course_slug",), skilllab_course_slug_routes)
    add("skilllabcourse:createskilllabcoursepayment", ("slug",), skilllab_payment_slug)

    def skilllab_chapters():
        from skilllab.models import SkillLabCourseChapter

        for slug in SkillLabCourseChapter.objects.values_list("slug", flat=True):
            if slug:
                yield {"chapter_slug": slug}

    add("skilllabcourse:skilllabcoursechapterdetail", ("chapter_slug",), skilllab_chapters)

    def skilllab_activities():
        from skilllab.models import SkillLabCourseActivity

        for slug in SkillLabCourseActivity.objects.values_list("slug", flat=True):
            if slug:
                yield {"workactive_slug": slug}

    add(
        "skilllabcourse:skilllabcourseactivityworksheetdetail",
        ("workactive_slug",),
        skilllab_activities,
    )

    def skilllab_activity_ids():
        from skilllab.models import SkillLabCourseActivity

        for pk in SkillLabCourseActivity.objects.values_list("id", flat=True):
            yield {"activity_id": pk}

    add("skilllabcourse:download_worksheet", ("activity_id",), skilllab_activity_ids)

    return ex


def _paths_for_route(full_name, urlpattern):
    converters = _converters_map(urlpattern)
    keys = frozenset(converters.keys())
    expanders = _expanders_by_key()
    fn = expanders.get((full_name, keys))

    if fn is not None:
        try:
            for kwargs in fn():
                u = _reverse_or_none(full_name, kwargs=kwargs)
                if u:
                    yield u
        except Exception as exc:
            # Wrong field names / DB schema: fall back to placeholder reverse below
            logger.warning(
                "urlconf_audit expander failed for %s (%s); using defaults if possible",
                full_name,
                exc,
            )
        else:
            return

    if not converters:
        u = _reverse_or_none(full_name)
        if u:
            yield u
        return

    kw = _default_kwargs(converters)
    u = _reverse_or_none(full_name, kwargs=kw)
    if u:
        yield u


def _path_only(url):
    """Normalize to path + query for Client.get."""
    if not url:
        return "/"
    p = urlsplit(url)
    out = p.path or "/"
    if p.query:
        out = f"{out}?{p.query}"
    return out


class Command(BaseCommand):
    help = (
        "Discover URLs from Django urlconf (not sitemap), GET each, print paths that return HTTP 404."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            default=None,
            help="Write one 404 path per line (UTF-8).",
        )
        parser.add_argument(
            "--include-admin",
            action="store_true",
            help="Include admin / topteenadmin / topteenadminmanaged named routes (very large).",
        )
        parser.add_argument(
            "--max-urls",
            type=int,
            default=None,
            help="Stop after this many distinct URLs checked.",
        )

    def handle(self, *args, **options):
        include_admin = options["include_admin"]
        out_path = options["output"]
        max_urls = options["max_urls"]

        urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [""])
        routes = list(
            _iter_patterns(urlconf.urlpatterns, include_admin=include_admin)
        )

        paths_ordered = []
        seen = set()

        for full_name, urlpattern, _prefix in routes:
            for url in _paths_for_route(full_name, urlpattern):
                p = _path_only(url)
                if p in seen:
                    continue
                seen.add(p)
                paths_ordered.append((full_name, p))
                if max_urls is not None and len(seen) >= max_urls:
                    break
            if max_urls is not None and len(seen) >= max_urls:
                break

        self.stdout.write(self.style.NOTICE(f"Checking {len(paths_ordered)} distinct URL(s)…"))

        client = Client()
        not_found = []

        for full_name, path in paths_ordered:
            try:
                resp = client.get(path, follow=False)
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"{path} ({full_name}): request error: {exc}"))
                continue
            if resp.status_code == 404:
                not_found.append((full_name, path))

        if not_found:
            self.stdout.write(self.style.ERROR(f"404 ({len(not_found)}):"))
            for fname, path in not_found:
                self.stdout.write(f"{path}\t# {fname}")
            if out_path:
                with open(out_path, "w", encoding="utf-8") as fh:
                    for _fname, path in not_found:
                        fh.write(path + "\n")
                self.stdout.write(self.style.SUCCESS(f"Wrote {len(not_found)} path(s) to {out_path}"))
        else:
            self.stdout.write(self.style.SUCCESS("No HTTP 404 responses among checked URLs."))
            if out_path:
                open(out_path, "w", encoding="utf-8").close()
