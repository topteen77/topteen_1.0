"""
Middleware: merge PageSEO into template context['html_head'] using request path as url_key.
Any view that sets html_head (title, description) gets SEO overlay from the dashboard automatically.
Works for all current and future pages without per-view changes.
"""
from django.template.response import TemplateResponse


def _normalize_path(path, max_len=120):
    """Normalize URL path for use as PageSEO url_key: strip slashes, truncate."""
    if not path:
        return ""
    key = path.strip("/")
    return key[:max_len] if len(key) > max_len else key


# Map URL path segments to dashboard url_key so SEO stored for "about" applies to /about-us/
PATH_TO_STATIC_KEY = {
    "about-us": "about",
    "terms-and-condition": "terms",
    "contact-us": "contact",
    "privacy-policy": "privacy",
}


class PageSEOMiddleware:
    """
    After the view runs, if context has 'html_head' (dict), look up PageSEO by request.path.
    If found, merge its title/description/keywords/og_image into html_head.
    This gives every page that sets html_head automatic SEO support from the dashboard.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        if not isinstance(response, TemplateResponse):
            return response
        path = request.path
        if path.startswith(("/admin/", "/seo-dashboard/", "/user-analytics/", "/api/")):
            return response
        context = getattr(response, "context_data", None) or {}
        html_head = context.get("html_head")
        if not html_head or not isinstance(html_head, dict):
            return response
        url_key = _normalize_path(path)
        if not url_key:
            return response
        url_key = PATH_TO_STATIC_KEY.get(url_key, url_key)
        try:
            from core.models import PageSEO
            from core.utils import get_page_seo_html_head
            default_title = html_head.get("title") or ""
            default_description = html_head.get("description") or ""
            default_image = html_head.get("image")
            merged = get_page_seo_html_head(
                url_key, default_title, default_description,
                default_image=default_image, request=request
            )
            response.context_data["html_head"] = merged
        except Exception:
            pass
        return response
