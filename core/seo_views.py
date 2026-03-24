from django.conf import settings
from django.contrib.sitemaps.views import sitemap as django_sitemap_view
from django.http import Http404
from django.http import HttpResponse
from django.urls import reverse


def _ensure_production():
    if not getattr(settings, "ALLOW_SEARCH_ENGINE_INDEX", False):
        raise Http404


def robots_txt(request):
    _ensure_production()
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /topteenadmin/",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request, sitemaps):
    _ensure_production()
    return django_sitemap_view(request, sitemaps=sitemaps)

