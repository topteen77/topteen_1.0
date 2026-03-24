"""SEO dashboard: login, page list, edit content (CMS), edit SEO. Staff can edit content; SEO group can edit SEO only."""
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from core.models import StaticPage, PageSEO, STATIC_PAGE_URL_KEYS, GeneratedPage, ScannedURL, URLIndexRule
from .seo_suggestions import get_seo_suggestions
from .ai_seo import generate_seo_with_ai, get_page_content_for_seo
from core.page_import import import_page_from_url
from core.utils import RICH_LAYOUT_STATIC_PAGES, get_frontend_path_for_url_key
from core.static_page_schema import get_static_page_schema, get_form_fields_with_values
from .decorators import seo_user_only, can_edit_content, can_edit_seo


class SEOLoginView(TemplateView):
    """Login page for SEO dashboard. POST: authenticate and redirect to dashboard."""
    template_name = "seo_dashboard/login.html"
    template_engine = "django"  # Force Django engine (templates use {% url %}, not Jinja2)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_staff or request.user.groups.filter(name="SEO").exists()):
            next_url = request.GET.get("next", "").strip()
            if next_url and next_url.startswith("/") and "seo-dashboard" in next_url and "//" not in next_url:
                return redirect(next_url)
            return redirect(reverse("seo_dashboard:dashboard"))
        return render(request, self.template_name, {"next": request.GET.get("next", "")}, using="django")

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.GET.get("next") or reverse("seo_dashboard:dashboard")
        user = authenticate(request, username=username, password=password)
        if user is not None and (user.is_staff or user.groups.filter(name="SEO").exists()):
            auth_login(request, user)
            return redirect(next_url)
        from django.contrib import messages
        messages.error(request, "Invalid credentials or you do not have access to the SEO dashboard.")
        return render(request, self.template_name, {"next": next_url}, using="django")


class SEOLogoutView(View):
    def get(self, request):
        auth_logout(request)
        return redirect(reverse("seo_dashboard:login"))


@method_decorator(seo_user_only, name="dispatch")
class ClearCacheView(LoginRequiredMixin, View):
    """POST: clear cache by scope. Staff or SEO. scope=all | home | pages. Returns JSON for AJAX for instant feedback."""
    login_url = reverse_lazy("seo_dashboard:login")

    def post(self, request, *args, **kwargs):
        from django.core.cache import cache
        from django.contrib import messages
        scope = (request.POST.get("scope") or request.GET.get("scope") or "all").strip().lower()
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accepts("application/json")
        msg_success = None
        msg_error = None
        if scope == "all":
            try:
                cache.clear()
                msg_success = "All cache cleared."
                messages.success(request, msg_success)
            except Exception as e:
                msg_error = str(e)
                messages.error(request, f"Failed to clear cache: {e}")
        elif scope == "home":
            try:
                _clear_cache_by_patterns(cache, ["home*", "home_*"])
                msg_success = "Home page cache cleared."
                messages.success(request, msg_success)
            except Exception as e:
                msg_error = str(e)
                messages.error(request, f"Failed to clear home cache: {e}")
        elif scope == "pages":
            try:
                _clear_cache_by_patterns(
                    cache,
                    ["career_library_ctx_*", "ga4_*", "template_cache_*"],
                )
                msg_success = "Other page caches cleared."
                messages.success(request, msg_success)
            except Exception as e:
                msg_error = str(e)
                messages.error(request, f"Failed to clear page cache: {e}")
        else:
            msg_error = "Invalid scope."
            messages.error(request, msg_error)
        if is_ajax:
            if msg_error:
                return JsonResponse({"success": False, "message": msg_error}, status=400)
            return JsonResponse({"success": True, "message": msg_success or "Done."})
        return redirect(reverse("seo_dashboard:dashboard"))


def _clear_cache_by_patterns(cache_backend, patterns):
    """Clear cache keys matching any of the patterns. Uses delete_pattern if available, else clear()."""
    if getattr(cache_backend, "delete_pattern", None):
        for pattern in patterns:
            try:
                cache_backend.delete_pattern(pattern)
            except Exception:
                pass
    else:
        cache_backend.clear()


@method_decorator(seo_user_only, name="dispatch")
class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard home: link to page list."""
    template_name = "seo_dashboard/dashboard.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_content"] = can_edit_content(self.request)
        ctx["can_edit_seo"] = can_edit_seo(self.request)
        return ctx


@method_decorator(seo_user_only, name="dispatch")
class PageListView(LoginRequiredMixin, TemplateView):
    """List static pages and their SEO status."""
    template_name = "seo_dashboard/page_list.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_content"] = can_edit_content(self.request)
        ctx["can_edit_seo"] = can_edit_seo(self.request)
        pages = []
        for key in STATIC_PAGE_URL_KEYS:
            sp = StaticPage.objects.filter(url_key=key).first()
            seo = PageSEO.objects.filter(url_key=key).first()
            label = key.replace("_", " ").title()
            pages.append({
                "url_key": key,
                "label": label,
                "has_cms_content": bool(sp and sp.content_html),
                "has_seo": seo is not None and (bool(seo.title) or bool(seo.description)),
                "frontend_url": self.request.build_absolute_uri(get_frontend_path_for_url_key(key)),
            })
        # Sort so pending SEO appears first (SEO user can tackle pending first)
        pages.sort(key=lambda p: (p["has_seo"], p["label"]))
        ctx["pages"] = pages
        # Counts for SEO user: how many completed vs pending (static pages)
        ctx["static_seo_completed"] = sum(1 for p in pages if p["has_seo"])
        ctx["static_seo_pending"] = sum(1 for p in pages if not p["has_seo"])
        # Blog posts: path-style url_key "blogs/<slug>" so SEO can be created/edited per post
        blog_pages = []
        try:
            from blog.models import Blog
            from core import choices
            blogs = Blog.get_published_objects().order_by("-modified")[:500]
            blog_url_keys = ["blogs/{}".format(b.slug) for b in blogs]
            seo_for_blogs = {
                row["url_key"]: row
                for row in PageSEO.objects.filter(url_key__in=blog_url_keys).values("url_key", "title", "description")
            }
            for b in blogs:
                url_key = "blogs/{}".format(b.slug)
                seo = seo_for_blogs.get(url_key)
                has_seo = seo is not None and (bool(seo.get("title")) or bool(seo.get("description")))
                blog_pages.append({
                    "url_key": url_key,
                    "label": b.title or b.slug,
                    "has_seo": has_seo,
                    "frontend_url": self.request.build_absolute_uri(get_frontend_path_for_url_key(url_key)),
                })
            # Sort so pending SEO appears first
            blog_pages.sort(key=lambda p: (p["has_seo"], p["label"]))
        except Exception:
            blog_pages = []
        ctx["blog_pages"] = blog_pages
        ctx["blog_seo_completed"] = sum(1 for p in blog_pages if p["has_seo"])
        ctx["blog_seo_pending"] = sum(1 for p in blog_pages if not p["has_seo"])
        # Other pages: PageSEO entries added via "Add SEO by URL" (not static, not blogs)
        static_keys_set = set(STATIC_PAGE_URL_KEYS)
        blog_url_keys_set = {p["url_key"] for p in blog_pages}
        other_seo = list(
            PageSEO.objects.exclude(url_key__in=static_keys_set)
            .exclude(url_key__startswith="blogs/")
            .order_by("-modified")
        )
        other_pages = [
            {
                "url_key": seo.url_key,
                "label": seo.url_key,
                "has_seo": bool(seo.title or seo.description),
                "frontend_url": self.request.build_absolute_uri(get_frontend_path_for_url_key(seo.url_key)),
            }
            for seo in other_seo
        ]
        other_pages.sort(key=lambda p: (p["has_seo"], p["label"]))
        ctx["other_pages"] = other_pages
        ctx["other_seo_completed"] = sum(1 for p in other_pages if p["has_seo"])
        ctx["other_seo_pending"] = sum(1 for p in other_pages if not p["has_seo"])
        # Detect duplicate PageSEO (same url_key multiple times) for "Remove duplicates" action
        from django.db.models import Count
        dupes = list(
            PageSEO.objects.values("url_key")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
        )
        ctx["has_duplicate_seo"] = len(dupes) > 0
        ctx["duplicate_seo_count"] = sum(d["cnt"] - 1 for d in dupes)
        return ctx


STATIC_PAGE_VIEW_URLS = {
    "terms": ("core", "terms&condition"),
    "privacy": ("core", "privacypolicy"),
    "contact": ("core", "contactus"),
    "about": ("core", "aboutus"),
    "career_planning": ("core", "career_planning"),
    "career_planning_4_year": ("core", "career_planning_4_year"),
    "career_planning_class_9": ("core", "career_planning_class_9"),
    "career_planning_class_10": ("core", "career_planning_class_10"),
    "career_planning_class_11": ("core", "career_planning_class_11"),
    "career_planning_class_12": ("core", "career_planning_class_12"),
    "emotional_intelligences": ("core", "emotional_intelligences"),
    "multiple_intelligences": ("core", "multiple_intelligences"),
    "four_pillars": ("core", "four_pillars"),
}


@method_decorator(seo_user_only, name="dispatch")
class EditStaticPageRawView(LoginRequiredMixin, TemplateView):
    """Edit static page as HTML/CSS/JS. Staff only."""
    template_name = "seo_dashboard/edit_static_page_raw.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        if not can_edit_content(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to edit pages.")
            return redirect(reverse("seo_dashboard:page_list"))
        page = get_object_or_404(StaticPage, url_key=kwargs["url_key"])
        view_url = None
        if kwargs["url_key"] in STATIC_PAGE_VIEW_URLS:
            ns, name = STATIC_PAGE_VIEW_URLS[kwargs["url_key"]]
            view_url = reverse(f"{ns}:{name}")
        return render(request, self.template_name, {"page": page, "url_key": kwargs["url_key"], "view_url": view_url}, using="django")

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        if not can_edit_content(request):
            return redirect(reverse("seo_dashboard:page_list"))
        page = get_object_or_404(StaticPage, url_key=kwargs["url_key"])
        page.title = (request.POST.get("title") or "").strip() or page.title
        page.content_html = request.POST.get("content_html", "")
        page.content_css = request.POST.get("content_css", "")
        page.content_js = request.POST.get("content_js", "")
        page.is_active = request.POST.get("is_active") == "on"
        page.save()
        messages.success(request, "Page saved.")
        return redirect(reverse("seo_dashboard:edit_static_page_raw", kwargs={"url_key": page.url_key}))


@method_decorator(seo_user_only, name="dispatch")
class EditContentView(LoginRequiredMixin, TemplateView):
    """Edit static page content (CMS). Staff only. Uses JSON form when schema exists."""
    template_name = "seo_dashboard/edit_content.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        url_key = kwargs.get("url_key")
        if not can_edit_content(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to edit page content.")
            return redirect(reverse("seo_dashboard:page_list"))
        if url_key in STATIC_PAGE_URL_KEYS:
            page, _ = StaticPage.objects.get_or_create(
                url_key=url_key,
                defaults={"title": "", "content_html": "", "is_active": True},
            )
        else:
            page = get_object_or_404(StaticPage, url_key=url_key)
        schema = get_static_page_schema(url_key)
        if schema:
            content_json = page.content_json or {}
            form_fields = get_form_fields_with_values(schema, content_json)
            return render(request, "seo_dashboard/edit_content_json.html", {
                "static_page": page,
                "url_key": url_key,
                "schema": schema,
                "content_json": content_json,
                "form_fields": form_fields,
                "upload_image_url": reverse("seo_dashboard:upload_image"),
                "frontend_url": request.build_absolute_uri(get_frontend_path_for_url_key(url_key)),
            }, using="django")
        is_rich_layout = url_key in RICH_LAYOUT_STATIC_PAGES
        return render(request, self.template_name, {
            "static_page": page,
            "url_key": url_key,
            "is_rich_layout": is_rich_layout,
            "frontend_url": request.build_absolute_uri(get_frontend_path_for_url_key(url_key)),
        }, using="django")

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        url_key = kwargs.get("url_key")
        if not can_edit_content(request):
            return redirect(reverse("seo_dashboard:page_list"))
        if url_key in STATIC_PAGE_URL_KEYS:
            page, _ = StaticPage.objects.get_or_create(
                url_key=url_key,
                defaults={"title": "", "content_html": "", "is_active": True},
            )
        else:
            page = get_object_or_404(StaticPage, url_key=url_key)
        schema = get_static_page_schema(url_key)
        if schema:
            content_json = {}
            for field in schema:
                fid = field.get("id")
                if not fid:
                    continue
                content_json[fid] = (request.POST.get("json_" + fid) or "").strip()
            page.content_json = content_json
            page.title = request.POST.get("title", "").strip() or page.title
            page.is_active = request.POST.get("is_active") == "on"
            page.save()
            messages.success(request, "Content saved.")
            return redirect(reverse("seo_dashboard:edit_content", kwargs={"url_key": url_key}))
        page.title = request.POST.get("title", "").strip() or page.title
        page.content_html = request.POST.get("content_html", "")
        page.is_active = request.POST.get("is_active") == "on"
        page.save()
        messages.success(request, "Content saved.")
        return redirect(reverse("seo_dashboard:edit_content", kwargs={"url_key": url_key}))


@seo_user_only
@require_http_methods(["POST"])
def upload_cms_image(request):
    """Upload an image for CMS static page; returns JSON with url for S3. Staff only."""
    if not can_edit_content(request):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"success": False, "error": "No file provided"}, status=400)
    name = getattr(uploaded_file, "name", "").lower()
    if not (name.endswith(".jpg") or name.endswith(".jpeg") or name.endswith(".png") or name.endswith(".gif") or name.endswith(".webp") or name.endswith(".svg")):
        return JsonResponse({"success": False, "error": "Only image files (jpg, png, gif, webp, svg) are allowed"}, status=400)
    from core.s3_utils import get_s3_upload_service
    s3_service = get_s3_upload_service()
    if not s3_service.is_enabled():
        return JsonResponse({"success": False, "error": "S3 upload is disabled"}, status=503)
    result = s3_service.upload_file(
        file_obj=uploaded_file,
        folder_path="cms/static_pages",
        uploaded_by=request.user.username if request.user.is_authenticated else "",
    )
    if result.get("success"):
        return JsonResponse({"success": True, "url": result["s3_url"]})
    return JsonResponse({"success": False, "error": result.get("error", "Upload failed")}, status=500)


def _strip_html(text, max_len=300):
    """Return plain text from HTML snippet, truncated to max_len."""
    if not text:
        return ""
    import re
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:max_len] if len(plain) > max_len else plain


def _normalize_url_key(path, max_len=120):
    """Normalize URL path for PageSEO.url_key: strip slashes, truncate to model max_length."""
    if not path or not isinstance(path, str):
        return ""
    key = path.strip("/").strip()
    return key[:max_len] if len(key) > max_len else key


def _validate_url_path(raw_path, request):
    """
    Validate URL path: must be path-only (no domain), then test that the URL works on this site.
    Returns (url_key, error_message). If error_message is not None, url_key is still set when path format was valid.
    """
    raw = (raw_path or "").strip()
    if not raw:
        return "", "Please enter a URL path (e.g. careers/software-engineer or blogs/my-post)."

    # Reject domain or protocol
    lower = raw.lower()
    if "://" in raw or lower.startswith("http") or "www." in lower:
        return "", "Do not include the domain name or http(s)://. Enter only the path (e.g. careers/software-engineer)."
    if " " in raw:
        return "", "URL path must not contain spaces. Use hyphens instead (e.g. careers/software-engineer)."

    url_key = _normalize_url_key(raw)
    if not url_key:
        return "", "URL path is invalid or too long (max 120 characters)."

    # Path for request: leading slash
    path_for_request = "/" + url_key if url_key else "/"

    # 1) Check that the path resolves to a view
    try:
        from django.urls import resolve, Resolver404
        resolve(path_for_request)
    except Resolver404:
        return url_key, "No page exists at this path. Check the path (e.g. careers/software-engineer) or create the page first."
    except Exception as e:
        return url_key, "Invalid path: {}.".format(str(e))

    # 2) Test that the URL returns a successful response
    try:
        from django.test import Client
        client = Client()
        response = client.get(path_for_request, follow=False)
        status = response.status_code
        if status in (200, 301, 302):
            return url_key, None
        if status == 404:
            return url_key, "The page was not found (404). Check the path or create the page first."
        if status == 500:
            return url_key, "The page returned a server error (500). Fix the page before adding SEO."
        if status == 403:
            return url_key, "Access denied (403). This path may require login or different permissions."
        return url_key, "The page returned an unexpected response (code {}). Ensure the URL works in the browser first.".format(status)
    except Exception as e:
        return url_key, "Could not verify URL: {}. Try again or check the path.".format(str(e))


@method_decorator(seo_user_only, name="dispatch")
class AddSEOByURLView(LoginRequiredMixin, TemplateView):
    """Add SEO for any page by entering its URL path. Path is validated (no domain, URL must work)."""
    template_name = "seo_dashboard/add_seo_by_url.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to edit SEO.")
            return redirect(reverse("seo_dashboard:page_list"))
        return render(request, self.template_name, {}, using="django")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return redirect(reverse("seo_dashboard:page_list"))
        from django.contrib import messages
        raw = (request.POST.get("url_path") or "").strip()
        url_key, error = _validate_url_path(raw, request)
        if error:
            messages.error(request, error)
            return render(request, self.template_name, {"url_path": raw}, using="django")
        seo, created = PageSEO.objects.get_or_create(
            url_key=url_key,
            defaults={"title": "", "description": "", "keywords": "", "og_image": ""},
        )
        if created:
            messages.success(request, "URL verified. You can now set title, description, and OG image.")
        else:
            messages.info(request, "This URL already has an SEO entry. You can edit it below.")
        return redirect(reverse("seo_dashboard:edit_seo", kwargs={"url_key": url_key}))


@method_decorator(seo_user_only, name="dispatch")
class EditSEOView(LoginRequiredMixin, TemplateView):
    """Edit SEO meta for a static page. Staff or SEO group."""
    template_name = "seo_dashboard/edit_seo.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        from core.utils import get_static_page
        url_key = self.kwargs.get("url_key")
        context = super().get_context_data(**kwargs)
        context["url_key"] = url_key
        page_seo, _ = PageSEO.objects.get_or_create(
            url_key=url_key,
            defaults={"title": "", "description": "", "keywords": "", "og_image": ""},
        )
        context["page_seo"] = page_seo
        # Fallbacks when SEO fields are empty: StaticPage for static keys, Blog for path blogs/<slug>
        static_page = get_static_page(url_key) or StaticPage.objects.filter(url_key=url_key).first()
        context["seo_title"] = (page_seo.title or "").strip()
        context["seo_description"] = (page_seo.description or "").strip()
        if not context["seo_title"] and static_page:
            context["seo_title"] = (getattr(static_page, "title", None) or "").strip()
        if not context["seo_description"] and static_page and getattr(static_page, "content_html", None):
            context["seo_description"] = _strip_html(static_page.content_html or "", 300)
        # Blog fallback: url_key "blogs/<slug>" -> use blog.title / blog.summary
        if (not context["seo_title"] or not context["seo_description"]) and url_key.startswith("blogs/"):
            slug = url_key[6:].strip("/")
            try:
                from blog.models import Blog
                from core import choices
                blog = Blog.get_published_objects().filter(slug=slug).first()
                if blog:
                    if not context["seo_title"]:
                        context["seo_title"] = (blog.title or "")[:70]
                    if not context["seo_description"]:
                        context["seo_description"] = (blog.summary or "")[:300]
            except Exception:
                pass
        context["seo_keywords"] = (page_seo.keywords or "").strip()
        context["seo_og_image"] = (page_seo.og_image or "").strip()
        context["frontend_url"] = self.request.build_absolute_uri(get_frontend_path_for_url_key(url_key))
        return context

    def get(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to edit SEO.")
            return redirect(reverse("seo_dashboard:page_list"))
        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context, using="django")

    def post(self, request, *args, **kwargs):
        url_key = kwargs.get("url_key")
        if not can_edit_seo(request):
            return redirect(reverse("seo_dashboard:page_list"))
        from django.contrib import messages
        # For path-style URLs, validate that the URL still works before saving
        if "/" in url_key:
            _, error = _validate_url_path(url_key, request)
            if error:
                messages.error(request, "URL validation failed: {}".format(error))
                context = self.get_context_data(**kwargs)
                context["seo_title"] = (request.POST.get("title") or "")[:70]
                context["seo_description"] = (request.POST.get("description") or "")[:300]
                context["seo_keywords"] = (request.POST.get("keywords") or "")[:500]
                context["seo_og_image"] = (request.POST.get("og_image") or "").strip()[:500]
                return render(request, self.template_name, context, using="django")
        seo, _ = PageSEO.objects.get_or_create(url_key=url_key, defaults={"title": "", "description": "", "keywords": "", "og_image": ""})
        seo.title = (request.POST.get("title") or "")[:70]
        seo.description = (request.POST.get("description") or "")[:300]
        seo.keywords = (request.POST.get("keywords") or "")[:500]
        seo.og_image = (request.POST.get("og_image") or "").strip()[:500]
        seo.save()
        messages.success(request, "SEO meta saved.")
        return redirect(reverse("seo_dashboard:edit_seo", kwargs={"url_key": url_key}))


@method_decorator(seo_user_only, name="dispatch")
class SEOSuggestionsView(LoginRequiredMixin, View):
    """GET: return JSON with suggested title, description, keywords and improvements for a url_key."""
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        url_key = kwargs.get("url_key") or request.GET.get("url_key", "")
        current_title = request.GET.get("title", "")
        current_description = request.GET.get("description", "")
        page_label = None
        if url_key.startswith("blogs/"):
            try:
                from blog.models import Blog
                from core import choices
                slug = url_key[6:].strip("/")
                blog = Blog.get_published_objects().filter(slug=slug).first()
                if blog:
                    page_label = blog.title
            except Exception:
                pass
        elif url_key.startswith("careers/"):
            try:
                from careers.models import Career
                slug = url_key.replace("careers/", "").strip("/")
                career = Career.objects.filter(slug=slug).first()
                if career:
                    page_label = career.name
            except Exception:
                pass
        try:
            out = get_seo_suggestions(
                url_key=url_key,
                current_title=current_title,
                current_description=current_description,
                page_label=page_label,
            )
            return JsonResponse(out)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(seo_user_only, name="dispatch")
class AISEOGenerateView(LoginRequiredMixin, View):
    """POST: send current SEO (and optional page content) to AI; return generated title, description, keywords."""
    login_url = reverse_lazy("seo_dashboard:login")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return JsonResponse({"error": "Forbidden"}, status=403)
        url_key = kwargs.get("url_key", "")
        if request.content_type and "application/json" in request.content_type:
            try:
                import json
                data = json.loads(request.body)
            except Exception:
                data = {}
        else:
            data = request.POST
        current_title = (data.get("title") or "").strip()
        current_description = (data.get("description") or "").strip()
        current_keywords = (data.get("keywords") or "").strip()
        include_content = data.get("include_content") in (True, "true", "1", "on")
        page_content = None
        if include_content and url_key:
            page_content = get_page_content_for_seo(url_key)
        result = generate_seo_with_ai(
            url_key=url_key,
            current_title=current_title,
            current_description=current_description,
            current_keywords=current_keywords,
            page_content=page_content,
        )
        if result.get("error"):
            return JsonResponse({"error": result["error"]}, status=400)
        return JsonResponse({
            "title": result.get("title", ""),
            "description": result.get("description", ""),
            "keywords": result.get("keywords", ""),
        })


@method_decorator(seo_user_only, name="dispatch")
class PageSEORemoveDuplicatesView(LoginRequiredMixin, View):
    """POST: remove duplicate PageSEO entries (keep one per url_key, latest modified). Redirects to page_list."""
    login_url = reverse_lazy("seo_dashboard:login")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission.")
            return redirect(reverse("seo_dashboard:page_list"))
        from django.contrib import messages
        from django.db.models import Count, Max
        # Find url_keys that have more than one PageSEO
        dupes = list(
            PageSEO.objects.values("url_key")
            .annotate(cnt=Count("id"), max_modified=Max("modified"))
            .filter(cnt__gt=1)
        )
        deleted = 0
        for d in dupes:
            # Keep the one with latest modified; delete others
            to_keep = PageSEO.objects.filter(url_key=d["url_key"]).order_by("-modified").first()
            if to_keep:
                n, _ = PageSEO.objects.filter(url_key=d["url_key"]).exclude(pk=to_keep.pk).delete()
                deleted += n
        if deleted:
            messages.success(request, "Removed {} duplicate SEO entry(ies). One entry per URL kept.".format(deleted))
        else:
            messages.info(request, "No duplicate SEO entries found.")
        return redirect(reverse("seo_dashboard:page_list"))


@method_decorator(seo_user_only, name="dispatch")
class ScannedURLListView(LoginRequiredMixin, TemplateView):
    """List scanned URLs; Scan button adds new/missed URLs; Remove selected with confirmation."""
    template_name = "seo_dashboard/scanned_url_list.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_seo"] = can_edit_seo(self.request)
        ctx["scanned_urls"] = ScannedURL.objects.all().order_by("url_path")
        return ctx

    def get(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission.")
            return redirect(reverse("seo_dashboard:page_list"))
        return render(request, self.template_name, self.get_context_data(**kwargs), using="django")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return redirect(reverse("seo_dashboard:page_list"))
        from django.contrib import messages
        action = request.POST.get("action")
        if action == "scan":
            host = (request.get_host() or "").split(":")[0].lower()
            if host in ("localhost", "127.0.0.1", "0.0.0.0", "") or host.startswith("192.168.") or host.startswith("10."):
                messages.error(
                    request,
                    "URL scan is not available on local or private networks (e.g. localhost). "
                    "Please run the scan from your production or staging website so that all pages are reachable."
                )
                return redirect(reverse("seo_dashboard:scanned_url_list"))
            from .scanner import run_site_scan
            try:
                added, total, seen, errs = run_site_scan()
                messages.success(
                    request,
                    "Scan complete. Found {} open URL(s). Added {} new; {} already stored.".format(total, added, seen)
                )
                if errs:
                    for e in errs[:5]:
                        messages.warning(request, e)
                    if len(errs) > 5:
                        messages.warning(request, "… and {} more errors.".format(len(errs) - 5))
            except Exception as e:
                messages.error(request, "Scan failed: {}.".format(str(e)))
            return redirect(reverse("seo_dashboard:scanned_url_list"))
        return redirect(reverse("seo_dashboard:scanned_url_list"))


@method_decorator(seo_user_only, name="dispatch")
class ScannedURLScanAjaxView(LoginRequiredMixin, View):
    """POST: run site scan and return JSON with added/total/seen/errors. For AJAX so UI can show status then result."""
    login_url = reverse_lazy("seo_dashboard:login")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return JsonResponse({"success": False, "message": "Permission denied."}, status=403)
        host = (request.get_host() or "").split(":")[0].lower()
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "") or host.startswith("192.168.") or host.startswith("10."):
            return JsonResponse({
                "success": False,
                "message": "URL scan is not available on local or private networks. Run the scan from production or staging.",
            }, status=400)
        from .scanner import run_site_scan
        try:
            added, total_found, seen, errs = run_site_scan()
            if total_found == 0:
                message = "Scan complete. No open URLs were found. Check that the site is reachable."
            elif added == 0 and seen > 0:
                message = "Scan complete. No new URLs added. {} URL(s) already stored (last seen updated).".format(seen)
            else:
                message = "Scan complete. Found {} open URL(s). Added {} new; {} already stored.".format(total_found, added, seen)
            return JsonResponse({
                "success": True,
                "added": added,
                "total": total_found,
                "seen": seen,
                "errors": errs[:10],
                "message": message,
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": "Scan failed: {}.".format(str(e))}, status=500)


@method_decorator(seo_user_only, name="dispatch")
class ScannedURLDeleteView(LoginRequiredMixin, View):
    """POST: delete selected ScannedURL by ids. Redirects to list."""
    login_url = reverse_lazy("seo_dashboard:login")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission.")
            return redirect(reverse("seo_dashboard:scanned_url_list"))
        from django.contrib import messages
        ids = request.POST.getlist("ids")
        if not ids:
            messages.warning(request, "No URLs selected to remove.")
            return redirect(reverse("seo_dashboard:scanned_url_list"))
        deleted, _ = ScannedURL.objects.filter(pk__in=ids).delete()
        messages.success(request, "{} URL(s) removed.".format(deleted))
        return redirect(reverse("seo_dashboard:scanned_url_list"))


@method_decorator(seo_user_only, name="dispatch")
class URLIndexRuleListView(LoginRequiredMixin, TemplateView):
    """Manage URL indexing rules used by robots.txt, sitemap.xml filtering, and X-Robots-Tag headers."""
    template_name = "seo_dashboard/url_index_rule_list.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_seo"] = can_edit_seo(self.request)
        try:
            ctx["rules"] = URLIndexRule.objects.all().order_by("path_pattern")
            ctx["rules_table_ready"] = True
        except (ProgrammingError, OperationalError):
            ctx["rules"] = []
            ctx["rules_table_ready"] = False
        return ctx

    def get(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission.")
            return redirect(reverse("seo_dashboard:page_list"))
        return render(request, self.template_name, self.get_context_data(**kwargs), using="django")

    def post(self, request, *args, **kwargs):
        if not can_edit_seo(request):
            return redirect(reverse("seo_dashboard:page_list"))
        from django.contrib import messages
        action = (request.POST.get("action") or "").strip()
        try:
            URLIndexRule.objects.exists()
        except (ProgrammingError, OperationalError):
            messages.error(request, "URL index rules table is not ready. Please run: python manage.py migrate")
            return redirect(reverse("seo_dashboard:url_index_rule_list"))

        if action == "create":
            path_pattern = (request.POST.get("path_pattern") or "").strip()
            match_type = (request.POST.get("match_type") or URLIndexRule.MatchType.PREFIX).strip()
            name = (request.POST.get("name") or "").strip()
            if not path_pattern:
                messages.error(request, "Path pattern is required.")
                return redirect(reverse("seo_dashboard:url_index_rule_list"))
            valid_types = {c[0] for c in URLIndexRule.MatchType.choices}
            if match_type not in valid_types:
                messages.error(request, "Invalid match type.")
                return redirect(reverse("seo_dashboard:url_index_rule_list"))
            URLIndexRule.objects.create(
                name=name,
                path_pattern=path_pattern,
                match_type=match_type,
                apply_in_robots=(request.POST.get("apply_in_robots") == "on"),
                apply_x_robots_tag=(request.POST.get("apply_x_robots_tag") == "on"),
                is_active=(request.POST.get("is_active") == "on"),
            )
            messages.success(request, "Indexing rule added.")
            return redirect(reverse("seo_dashboard:url_index_rule_list"))

        if action == "delete":
            ids = request.POST.getlist("ids")
            if not ids:
                messages.warning(request, "No rules selected.")
                return redirect(reverse("seo_dashboard:url_index_rule_list"))
            deleted, _ = URLIndexRule.objects.filter(pk__in=ids).delete()
            messages.success(request, "{} rule(s) removed.".format(deleted))
            return redirect(reverse("seo_dashboard:url_index_rule_list"))

        messages.error(request, "Invalid action.")
        return redirect(reverse("seo_dashboard:url_index_rule_list"))


@method_decorator(seo_user_only, name="dispatch")
class GeneratedPageListView(LoginRequiredMixin, TemplateView):
    template_name = "seo_dashboard/generated_page_list.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_content"] = can_edit_content(self.request)
        ctx["generated_pages"] = GeneratedPage.objects.all()
        return ctx


@method_decorator(seo_user_only, name="dispatch")
class CreatePageFromURLView(LoginRequiredMixin, TemplateView):
    template_name = "seo_dashboard/create_page_from_url.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        if not can_edit_content(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to create pages.")
            return redirect(reverse("seo_dashboard:page_list"))
        return render(request, self.template_name, {}, using="django")

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        if not can_edit_content(request):
            return redirect(reverse("seo_dashboard:page_list"))
        source_url = (request.POST.get("source_url") or "").strip()
        slug = (request.POST.get("slug") or "").strip().lower().replace(" ", "-")
        title = (request.POST.get("title") or "").strip()
        if not source_url:
            messages.error(request, "Please enter a source URL.")
            return render(request, self.template_name, {"source_url": source_url, "slug": slug, "title": title}, using="django")
        if not slug:
            messages.error(request, "Please enter a URL slug (e.g. my-page).")
            return render(request, self.template_name, {"source_url": source_url, "slug": slug, "title": title}, using="django")
        if GeneratedPage.objects.filter(slug=slug).exists():
            messages.error(request, f"A page with slug '{slug}' already exists.")
            return render(request, self.template_name, {"source_url": source_url, "slug": slug, "title": title}, using="django")
        result = import_page_from_url(source_url)
        if not result["success"]:
            messages.error(request, result.get("error", "Import failed."))
            return render(request, self.template_name, {"source_url": source_url, "slug": slug, "title": title}, using="django")
        page_title = title or result.get("title") or slug.replace("-", " ").title()
        GeneratedPage.objects.create(
            slug=slug,
            title=page_title,
            content_html=result.get("content_html", ""),
            content_css=result.get("content_css", ""),
            content_js=result.get("content_js", ""),
            source_url=source_url,
            is_active=True,
        )
        messages.success(request, f"Page '{slug}' created. View at /page/{slug}/")
        return redirect(reverse("seo_dashboard:generated_page_list"))


@method_decorator(seo_user_only, name="dispatch")
class EditGeneratedPageView(LoginRequiredMixin, TemplateView):
    template_name = "seo_dashboard/edit_generated_page.html"
    template_engine = "django"
    login_url = reverse_lazy("seo_dashboard:login")

    def get(self, request, *args, **kwargs):
        if not can_edit_content(request):
            from django.contrib import messages
            messages.error(request, "You do not have permission to edit pages.")
            return redirect(reverse("seo_dashboard:generated_page_list"))
        page = get_object_or_404(GeneratedPage, slug=kwargs["slug"])
        return render(request, self.template_name, {"page": page}, using="django")

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        if not can_edit_content(request):
            return redirect(reverse("seo_dashboard:generated_page_list"))
        page = get_object_or_404(GeneratedPage, slug=kwargs["slug"])
        page.title = (request.POST.get("title") or "").strip() or page.title
        page.content_html = request.POST.get("content_html", "")
        page.content_css = request.POST.get("content_css", "")
        page.content_js = request.POST.get("content_js", "")
        page.is_active = request.POST.get("is_active") == "on"
        page.save()
        messages.success(request, "Page saved.")
        return redirect(reverse("seo_dashboard:edit_generated_page", kwargs={"slug": page.slug}))
