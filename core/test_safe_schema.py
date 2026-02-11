"""
Unit tests for safe_schema_utils (idempotent migration helpers).
No actual migrations or real DB: all tests use mocks (SimpleTestCase = no DB created).
Run: python manage.py test core.test_safe_schema
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.safe_schema_utils import (
    column_exists,
    get_vendor,
    safe_add_field_if_not_exists,
    safe_create_model_if_not_exists,
    safe_ensure_app_models_schema,
    table_exists,
)


class TestGetVendor(SimpleTestCase):
    """Test get_vendor without using a real connection."""

    def test_returns_mysql(self):
        conn = MagicMock()
        conn.vendor = "mysql"
        self.assertEqual(get_vendor(conn), "mysql")

    def test_returns_postgresql(self):
        conn = MagicMock()
        conn.vendor = "postgresql"
        self.assertEqual(get_vendor(conn), "postgresql")

    def test_returns_lowercase(self):
        conn = MagicMock()
        conn.vendor = "MySQL"
        self.assertEqual(get_vendor(conn), "mysql")

    def test_unknown_fallback(self):
        conn = MagicMock(spec=[])  # no vendor
        self.assertEqual(get_vendor(conn), "unknown")


class TestTableExists(SimpleTestCase):
    """Test table_exists with mocked cursor (no real DB)."""

    def test_mysql_table_exists(self):
        conn = MagicMock()
        conn.vendor = "mysql"
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        self.assertTrue(table_exists(conn, "core_fourpillarsassessment"))
        cursor.execute.assert_called_once()
        self.assertIn("information_schema.tables", cursor.execute.call_args[0][0])

    def test_mysql_table_not_exists(self):
        conn = MagicMock()
        conn.vendor = "mysql"
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        self.assertFalse(table_exists(conn, "missing_table"))
        cursor.execute.assert_called_once()

    def test_sqlite_table_exists(self):
        conn = MagicMock()
        conn.vendor = "sqlite"
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        self.assertTrue(table_exists(conn, "core_ebook"))
        cursor.execute.assert_called_once()
        self.assertIn("sqlite_master", cursor.execute.call_args[0][0])


class TestColumnExists(SimpleTestCase):
    """Test column_exists with mocked cursor (no real DB)."""

    def test_mysql_column_exists(self):
        conn = MagicMock()
        conn.vendor = "mysql"
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        self.assertTrue(column_exists(conn, "core_fourpillarsassessment", "slug"))
        cursor.execute.assert_called_once()
        self.assertIn("information_schema.columns", cursor.execute.call_args[0][0])

    def test_mysql_column_not_exists(self):
        conn = MagicMock()
        conn.vendor = "mysql"
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        self.assertFalse(column_exists(conn, "core_ebook", "nonexistent_col"))
        cursor.execute.assert_called_once()


class TestSafeCreateModelIfNotExists(SimpleTestCase):
    """Test safe_create_model_if_not_exists: no real migration, mocked schema_editor."""

    @patch("core.safe_schema_utils.table_exists")
    def test_skips_when_table_exists(self, mock_table_exists):
        mock_table_exists.return_value = True
        schema_editor = MagicMock()
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        safe_create_model_if_not_exists(schema_editor, model)
        schema_editor.create_model.assert_not_called()

    @patch("core.safe_schema_utils.table_exists")
    def test_creates_when_table_missing(self, mock_table_exists):
        mock_table_exists.return_value = False
        schema_editor = MagicMock()
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        safe_create_model_if_not_exists(schema_editor, model)
        schema_editor.create_model.assert_called_once_with(model)


class TestSafeAddFieldIfNotExists(SimpleTestCase):
    """Test safe_add_field_if_not_exists: no real migration, mocked schema_editor."""

    @patch("core.safe_schema_utils.column_exists")
    def test_skips_when_column_exists(self, mock_column_exists):
        mock_column_exists.return_value = True
        schema_editor = MagicMock()
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        field = MagicMock()
        field.column = "slug"
        safe_add_field_if_not_exists(schema_editor, model, field)
        schema_editor.add_field.assert_not_called()

    @patch("core.safe_schema_utils.column_exists")
    def test_adds_when_column_missing(self, mock_column_exists):
        mock_column_exists.return_value = False
        schema_editor = MagicMock()
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        field = MagicMock()
        field.column = "slug"
        safe_add_field_if_not_exists(schema_editor, model, field)
        schema_editor.add_field.assert_called_once_with(model, field)

    @patch("core.safe_schema_utils.column_exists")
    def test_swallows_duplicate_column_error(self, mock_column_exists):
        mock_column_exists.return_value = False
        schema_editor = MagicMock()
        schema_editor.add_field.side_effect = Exception("Duplicate column name 'slug'")
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        field = MagicMock()
        field.column = "slug"
        # Should not raise
        safe_add_field_if_not_exists(schema_editor, model, field)

    @patch("core.safe_schema_utils.column_exists")
    def test_reraises_other_errors(self, mock_column_exists):
        mock_column_exists.return_value = False
        schema_editor = MagicMock()
        schema_editor.add_field.side_effect = Exception("Disk full")
        model = MagicMock()
        model._meta.db_table = "core_fourpillarsassessment"
        field = MagicMock()
        field.column = "slug"
        with self.assertRaises(Exception) as ctx:
            safe_add_field_if_not_exists(schema_editor, model, field)
        self.assertIn("Disk full", str(ctx.exception))


class TestSafeEnsureAppModelsSchema(SimpleTestCase):
    """Test safe_ensure_app_models_schema with mocked apps/schema_editor (no real migration)."""

    @patch("core.safe_schema_utils.safe_add_field_if_not_exists")
    @patch("core.safe_schema_utils.safe_create_model_if_not_exists")
    @patch("core.safe_schema_utils.column_exists")
    @patch("core.safe_schema_utils.table_exists")
    def test_creates_table_when_missing(
        self, mock_table_exists, mock_column_exists, mock_create, mock_add_field
    ):
        mock_table_exists.return_value = False
        mock_column_exists.return_value = True
        apps = MagicMock()
        app_config = MagicMock()
        model = MagicMock()
        model._meta.proxy = False
        model._meta.db_table = "core_fourpillarsassessment"
        model._meta.get_fields.return_value = []
        app_config.get_models.return_value = [model]
        apps.get_app_config.return_value = app_config
        schema_editor = MagicMock()
        safe_ensure_app_models_schema(apps, schema_editor, "core")
        mock_create.assert_called_once()
        mock_create.assert_called_with(schema_editor, model)

    @patch("core.safe_schema_utils.safe_add_field_if_not_exists")
    @patch("core.safe_schema_utils.safe_create_model_if_not_exists")
    @patch("core.safe_schema_utils.column_exists")
    @patch("core.safe_schema_utils.table_exists")
    def test_skips_proxy_models(
        self, mock_table_exists, mock_column_exists, mock_create, mock_add_field
    ):
        mock_table_exists.return_value = False
        apps = MagicMock()
        app_config = MagicMock()
        model = MagicMock()
        model._meta.proxy = True
        model._meta.db_table = "core_someproxy"
        app_config.get_models.return_value = [model]
        apps.get_app_config.return_value = app_config
        schema_editor = MagicMock()
        safe_ensure_app_models_schema(apps, schema_editor, "core")
        mock_create.assert_not_called()

    def test_handles_lookup_error(self):
        apps = MagicMock()
        apps.get_app_config.side_effect = LookupError("No app 'nonexistent'")
        schema_editor = MagicMock()
        # Should not raise
        safe_ensure_app_models_schema(apps, schema_editor, "nonexistent")
