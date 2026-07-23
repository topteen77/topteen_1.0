from django.db import migrations


def _alter_mysql_text_columns(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    alters = [
        (
            'communication_communicationlog',
            {
                'to': 'VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
                'body': 'LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
                'response': 'LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
            },
        ),
        (
            'communication_emailmessagetemplate',
            {
                'slug': 'VARCHAR(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
                'name': 'VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
                'subject_template': 'VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
                'body_html_template': 'LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL',
            },
        ),
    ]

    with schema_editor.connection.cursor() as cursor:
        for table, columns in alters:
            for column, definition in columns.items():
                cursor.execute(
                    'ALTER TABLE `{table}` MODIFY `{column}` {definition}'.format(
                        table=table,
                        column=column,
                        definition=definition,
                    )
                )


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0003_emailmessagetemplate'),
    ]

    operations = [
        migrations.RunPython(_alter_mysql_text_columns, migrations.RunPython.noop),
    ]
