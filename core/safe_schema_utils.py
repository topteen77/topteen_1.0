"""
Reusable safe schema helpers for idempotent migrations.
Use in RunPython so that tables/columns are created only if they do not exist.
Applicable for all models and all apps.
"""
import logging

logger = logging.getLogger(__name__)


def get_vendor(connection):
    """Return database vendor: 'mysql', 'postgresql', 'sqlite3', etc."""
    return (getattr(connection, "vendor", None) or "unknown").lower()


def table_exists(connection, table_name):
    """
    Return True if the table exists in the current database.
    Works with MySQL, PostgreSQL, and SQLite.
    """
    vendor = get_vendor(connection)
    with connection.cursor() as cursor:
        if vendor == "mysql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = %s
                """,
                [table_name],
            )
        elif vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
                """,
                [table_name],
            )
        elif vendor == "sqlite":
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                [table_name],
            )
        else:
            try:
                cursor.execute(f'SELECT 1 FROM "{table_name}" LIMIT 1')
                return True
            except Exception:
                return False
        return cursor.fetchone() is not None


def column_exists(connection, table_name, column_name):
    """
    Return True if the column exists on the table.
    Works with MySQL, PostgreSQL, and SQLite.
    """
    vendor = get_vendor(connection)
    with connection.cursor() as cursor:
        if vendor == "mysql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
        elif vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
        elif vendor == "sqlite":
            cursor.execute(
                "PRAGMA table_info(%s)" % connection.ops.quote_name(table_name)
            )
            rows = cursor.fetchall()
            col_names = [row[1] for row in rows]
            return column_name in col_names
        else:
            try:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                    """,
                    [table_name, column_name],
                )
                return cursor.fetchone() is not None
            except Exception:
                return False
        return cursor.fetchone() is not None


def safe_create_model_if_not_exists(schema_editor, model):
    """
    Create the table for the given model only if it does not exist.
    Model must be from apps.get_model().
    """
    connection = schema_editor.connection
    table_name = model._meta.db_table
    if table_exists(connection, table_name):
        logger.info("Table %s already exists; skipping create.", table_name)
        return
    schema_editor.create_model(model)
    logger.info("Created table %s.", table_name)


def safe_add_field_if_not_exists(schema_editor, model, field):
    """
    Add the field's column only if the column does not exist.
    """
    connection = schema_editor.connection
    table_name = model._meta.db_table
    column_name = field.column
    if column_exists(connection, table_name, column_name):
        logger.info("Column %s.%s already exists; skipping add.", table_name, column_name)
        return
    try:
        schema_editor.add_field(model, field)
        logger.info("Added column %s.%s.", table_name, column_name)
    except Exception as e:
        if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
            logger.info("Column %s.%s already present: %s", table_name, column_name, e)
        else:
            raise


def safe_ensure_app_models_schema(apps, schema_editor, app_label):
    """
    Idempotent schema sync for all models in an app:
    - If a table does not exist, create it.
    - If a table exists but a column is missing, add it.
    Use in RunPython: safe_ensure_app_models_schema(apps, schema_editor, 'core').
    Applicable for all models in the given app.
    """
    connection = schema_editor.connection
    try:
        app_config = apps.get_app_config(app_label)
    except LookupError:
        return
    for model in app_config.get_models():
        if model._meta.proxy:
            continue
        table_name = model._meta.db_table
        if not table_exists(connection, table_name):
            safe_create_model_if_not_exists(schema_editor, model)
            continue
        for field in model._meta.get_fields():
            if not getattr(field, "column", None):
                continue
            if getattr(field, "many_to_many", False) or getattr(field, "primary_key", False):
                continue
            if not getattr(field, "concrete", True):
                continue
            if not column_exists(connection, table_name, field.column):
                safe_add_field_if_not_exists(schema_editor, model, field)


def safe_ensure_all_apps_schema(apps, schema_editor, exclude_apps=None):
    """
    Run safe_ensure_app_models_schema for every installed app that has models.
    Optional: exclude_apps=('contenttypes', 'sessions') to skip system apps.
    """
    exclude_apps = set(exclude_apps or [])
    for app_label in apps.app_configs:
        if app_label in exclude_apps:
            continue
        try:
            safe_ensure_app_models_schema(apps, schema_editor, app_label)
        except Exception as e:
            logger.warning("Safe schema sync for app %s: %s", app_label, e)
