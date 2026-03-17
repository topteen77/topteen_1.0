from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import EntranceExam


@admin.register(EntranceExam)
class EntranceExamAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category_display",
        "object_status",
        "preview_link",
        "image_safe",
    )
    list_filter = ("object_status", "category")
    search_fields = ("name",)
    ordering = ("category", "name")
    list_per_page = 50

    def category_display(self, obj):
        """Display category choice label."""
        if obj is None:
            return "-"
        return obj.get_category_display()
    category_display.short_description = "Category"
    category_display.admin_order_field = "category"

    def image_safe(self, obj):
        """Display Yes if logo present, else dash (like vocational Image column)."""
        if obj is None:
            return "-"
        return "Yes" if obj.logo else "-"
    image_safe.short_description = "Image"

    def preview_link(self, obj):
        """Preview link that opens frontend exam detail in new tab (like vocational Preview)."""
        if not obj or not getattr(obj, "id", None):
            return "-"
        try:
            url = obj.url()
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: 600; text-decoration: none;">View</a>',
                url,
            )
        except Exception:
            return "-"
    preview_link.short_description = "Preview"
    preview_link.admin_order_field = "name"
