from django.urls import path
from . import views

app_name = "seo_dashboard"

urlpatterns = [
    path("login/", views.SEOLoginView.as_view(), name="login"),
    path("logout/", views.SEOLogoutView.as_view(), name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("clear-cache/", views.ClearCacheView.as_view(), name="clear_cache"),
    path("pages/", views.PageListView.as_view(), name="page_list"),
    path("pages/remove-duplicates/", views.PageSEORemoveDuplicatesView.as_view(), name="page_seo_remove_duplicates"),
    path("pages/add-seo-by-url/", views.AddSEOByURLView.as_view(), name="add_seo_by_url"),
    path("scanned-urls/", views.ScannedURLListView.as_view(), name="scanned_url_list"),
    path("scanned-urls/scan-ajax/", views.ScannedURLScanAjaxView.as_view(), name="scanned_url_scan_ajax"),
    path("scanned-urls/delete/", views.ScannedURLDeleteView.as_view(), name="scanned_url_delete"),
    path("pages/<path:url_key>/content/", views.EditContentView.as_view(), name="edit_content"),
    path("pages/<path:url_key>/edit-raw/", views.EditStaticPageRawView.as_view(), name="edit_static_page_raw"),
    path("pages/<path:url_key>/seo/", views.EditSEOView.as_view(), name="edit_seo"),
    path("api/suggestions/<path:url_key>/", views.SEOSuggestionsView.as_view(), name="seo_suggestions"),
    path("api/ai-seo/<path:url_key>/", views.AISEOGenerateView.as_view(), name="ai_seo_generate"),
    path("upload-image/", views.upload_cms_image, name="upload_image"),
    path("pages/create-from-url/", views.CreatePageFromURLView.as_view(), name="create_page_from_url"),
    path("generated-pages/", views.GeneratedPageListView.as_view(), name="generated_page_list"),
    path("generated-pages/<slug:slug>/edit/", views.EditGeneratedPageView.as_view(), name="edit_generated_page"),
]
