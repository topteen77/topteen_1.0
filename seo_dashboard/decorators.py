"""SEO dashboard access: staff or users in Django Group 'SEO'."""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def seo_user_only(view_func):
    """Allow access only to staff or users in group 'SEO'. Redirect others to login."""
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access the SEO dashboard.")
            return redirect(reverse("seo_dashboard:login") + "?next=" + request.get_full_path())
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if request.user.groups.filter(name="SEO").exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, "You do not have permission to access the SEO dashboard.")
        return redirect(reverse("seo_dashboard:login"))
    return wrap


def can_edit_content(request):
    """True if user can edit static page content (CMS). Only staff."""
    return request.user.is_authenticated and request.user.is_staff


def can_edit_seo(request):
    """True if user can edit SEO meta. Staff or SEO group."""
    if not request.user.is_authenticated:
        return False
    return request.user.is_staff or request.user.groups.filter(name="SEO").exists()
