from django.conf import settings
from django.contrib.sitemaps.views import sitemap as django_sitemap_view
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from django.http import HttpResponse
from django.urls import reverse
from core.models import URLIndexRule
from core.seo_indexing import resolve_allow_search_engine_index


def _ensure_indexable(request):
    if not resolve_allow_search_engine_index(request):
        raise Http404


def robots_txt(request):
    if not resolve_allow_search_engine_index(request):
        # Keep search engines out, but allow Meta crawlers so Facebook Login /
        # Sharing Debugger can fetch og:* tags and validate the website URL.
        lines = [
            "User-agent: facebookexternalhit",
            "Allow: /",
            "",
            "User-agent: Facebot",
            "Allow: /",
            "",
            "User-agent: *",
            "Disallow: /",
        ]
        return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")

    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    try:
        disallow_paths = [
            rule.path_pattern.strip()
            for rule in URLIndexRule.get_active_rules().filter(apply_in_robots=True)
            if rule.path_pattern and rule.match_type in (URLIndexRule.MatchType.EXACT, URLIndexRule.MatchType.PREFIX)
        ]
    except (ProgrammingError, OperationalError):
        disallow_paths = []
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /topteenadmin/",
    ]
    for path in disallow_paths:
        if not path.startswith("/"):
            path = f"/{path}"
        lines.append(f"Disallow: {path}")
    lines.append(f"Sitemap: {sitemap_url}")
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request, sitemaps):
    _ensure_indexable(request)
    return django_sitemap_view(
        request,
        sitemaps=sitemaps,
        template_name="sitemap.xml",
        content_type="application/xml",
    )

