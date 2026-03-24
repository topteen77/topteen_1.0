from django.conf import settings
from django.contrib.sitemaps.views import sitemap as django_sitemap_view
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from django.http import HttpResponse
from django.urls import reverse
from core.models import URLIndexRule


def _ensure_production():
    if not getattr(settings, "ALLOW_SEARCH_ENGINE_INDEX", False):
        raise Http404


def robots_txt(request):
    _ensure_production()
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
    _ensure_production()
    return django_sitemap_view(
        request,
        sitemaps=sitemaps,
        template_name="sitemap.xml",
        content_type="application/xml",
    )

