from django.test import RequestFactory, TestCase

from core import choices
from core.models import Configuration
from core.ttv2_role_context import (
    TTV2_PAGE_LOADER_CONFIG_KEY,
    ttv2_page_loader_enabled,
    ttv2_role_ctx,
)


class TestTtv2PageLoaderConfig(TestCase):
    def setUp(self):
        Configuration.objects.complete().filter(key=TTV2_PAGE_LOADER_CONFIG_KEY).delete()

    def test_missing_key_defaults_enabled(self):
        self.assertTrue(ttv2_page_loader_enabled())

    def test_false_disables_loader(self):
        Configuration.objects.create(
            key=TTV2_PAGE_LOADER_CONFIG_KEY,
            value="false",
            editable=True,
        )
        self.assertFalse(ttv2_page_loader_enabled())

    def test_true_enables_loader(self):
        Configuration.objects.create(
            key=TTV2_PAGE_LOADER_CONFIG_KEY,
            value="true",
            editable=True,
        )
        self.assertTrue(ttv2_page_loader_enabled())

    def test_soft_deleted_row_does_not_crash_and_defaults_enabled(self):
        row = Configuration.objects.create(
            key=TTV2_PAGE_LOADER_CONFIG_KEY,
            value="false",
            editable=True,
        )
        row.delete()
        self.assertTrue(ttv2_page_loader_enabled())

    def test_context_processor_exposes_flag(self):
        Configuration.objects.create(
            key=TTV2_PAGE_LOADER_CONFIG_KEY,
            value="false",
            editable=True,
        )
        req = RequestFactory().get("/institute/demo-institute/")
        ctx = ttv2_role_ctx(req)
        self.assertFalse(ctx["ttv2_role_ctx"]["page_loader_enabled"])
