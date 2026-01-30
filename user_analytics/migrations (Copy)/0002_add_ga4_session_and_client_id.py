# Generated manually for GA4 integration

from django.conf import settings
from django.db import migrations, models, connection
import django.db.models.deletion


def add_ga4_client_id_if_not_exists(apps, schema_editor):
    """Add ga4_client_id field only if it doesn't exist"""
    with schema_editor.connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'user_analytics_userjourney' 
            AND COLUMN_NAME = 'ga4_client_id'
        """)
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            # Add the column
            cursor.execute("""
                ALTER TABLE user_analytics_userjourney 
                ADD COLUMN ga4_client_id VARCHAR(255) NULL
            """)
            # Add index if it doesn't exist
            try:
                cursor.execute("""
                    CREATE INDEX user_analytics_userjourney_ga4_client_id_idx 
                    ON user_analytics_userjourney (ga4_client_id)
                """)
            except Exception:
                # Index might already exist, ignore
                pass


def reverse_add_ga4_client_id(apps, schema_editor):
    """Remove ga4_client_id field if it exists"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'user_analytics_userjourney' 
            AND COLUMN_NAME = 'ga4_client_id'
        """)
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            cursor.execute("""
                ALTER TABLE user_analytics_userjourney 
                DROP COLUMN ga4_client_id
            """)


def _create_unique_index_if_not_exists(schema_editor):
    """Create unique index with prefix on entry_page if it doesn't exist"""
    with schema_editor.connection.cursor() as cursor:
        # Check if index exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = 'user_analytics_ga4session' 
            AND index_name = 'user_analytics_ga4session_unique_idx'
        """)
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session'
            """)
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                # Create unique index with prefix on entry_page (first 200 chars)
                # Check if index already exists first
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'user_analytics_ga4session' 
                    AND index_name = 'user_analytics_ga4session_unique_idx'
                """)
                index_exists = cursor.fetchone()[0] > 0
                
                if not index_exists:
                    try:
                        cursor.execute("""
                            CREATE UNIQUE INDEX user_analytics_ga4session_unique_idx 
                            ON user_analytics_ga4session (
                                ga4_client_id, 
                                date, 
                                source, 
                                country, 
                                device, 
                                entry_page(200)
                            )
                        """)
                    except Exception as e:
                        # Index might be too long or already exists, skip
                        # This can happen if the combination of fields exceeds MySQL key length limit
                        pass


def _drop_unique_index_if_exists(schema_editor):
    """Drop unique index if it exists"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = 'user_analytics_ga4session' 
            AND index_name = 'user_analytics_ga4session_unique_idx'
        """)
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            cursor.execute("""
                DROP INDEX user_analytics_ga4session_unique_idx 
                ON user_analytics_ga4session
            """)


def _add_ga4session_indexes_if_not_exist(schema_editor):
    """Add indexes for GA4Session only if they don't exist"""
    indexes_to_create = [
        ('user_analy_ga4_cli_idx', 'ga4_client_id, date'),
        ('user_analy_django__idx', 'django_session_id, date'),
        ('user_analy_user_id_idx', 'user_id, date'),
        ('user_analy_date_so_idx', 'date, source, country, device'),
        ('user_analy_synced__idx', 'synced_at'),
    ]
    
    with connection.cursor() as cursor:
        for index_name, fields in indexes_to_create:
            # Check if index exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_analytics_ga4session' 
                AND index_name = %s
            """, [index_name])
            if cursor.fetchone()[0] > 0:
                continue  # Index already exists, skip
            
            try:
                # Create index
                cursor.execute(f"""
                    CREATE INDEX {index_name} 
                    ON user_analytics_ga4session ({fields})
                """)
            except Exception:
                pass  # Index might have been created concurrently or key too long


def _create_ga4session_table_if_not_exists(schema_editor):
    """Create GA4Session table only if it doesn't exist"""
    table_name = 'user_analytics_ga4session'
    
    with connection.cursor() as cursor:
        if connection.vendor == 'mysql':
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = %s
            """, [table_name])
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                return
        elif connection.vendor == 'postgresql':
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            """, [table_name])
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                return
    
    # If we reach here, table doesn't exist and we need to create it
    # Create temporary model class
    from django.db import models as django_models
    
    class GA4SessionModel(django_models.Model):
        id = django_models.BigAutoField(primary_key=True)
        modified = django_models.DateTimeField(auto_now=True)
        object_status = django_models.SmallIntegerField(
            choices=[(0, 'Deleted'), (1, 'Active'), (2, 'Inactive')],
            default=1
        )
        ga4_client_id = django_models.CharField(max_length=255, db_index=True)
        ga4_session_id = django_models.CharField(max_length=255, blank=True, null=True)
        django_session_id = django_models.CharField(max_length=255, blank=True, null=True, db_index=True)
        date = django_models.DateField(db_index=True)
        source = django_models.CharField(max_length=255, blank=True, null=True, db_index=True)
        medium = django_models.CharField(max_length=255, blank=True, null=True)
        campaign = django_models.CharField(max_length=255, blank=True, null=True)
        country = django_models.CharField(max_length=100, blank=True, null=True, db_index=True)
        device = django_models.CharField(max_length=50, blank=True, null=True, db_index=True)
        entry_page = django_models.CharField(max_length=500, blank=True, null=True, db_index=True)
        exit_page = django_models.CharField(max_length=500, blank=True, null=True)
        sessions_count = django_models.IntegerField(default=1)
        pageviews = django_models.IntegerField(default=0)
        users = django_models.IntegerField(default=1)
        synced_at = django_models.DateTimeField(auto_now_add=True, db_index=True)
        updated = django_models.DateTimeField(auto_now=True)
        user = django_models.ForeignKey(
            settings.AUTH_USER_MODEL,
            null=True,
            blank=True,
            on_delete=django_models.SET_NULL,
            related_name='ga4_sessions'
        )
        
        class Meta:
            db_table = 'user_analytics_ga4session'
            verbose_name = 'GA4 Session'
            verbose_name_plural = 'GA4 Sessions'
            ordering = ['-date', '-synced_at']
    
    # Create table using schema editor (without indexes - they're added separately)
    # Remove db_index from fields to avoid key length issues during table creation
    GA4SessionModel._meta.get_field('ga4_client_id').db_index = False
    GA4SessionModel._meta.get_field('django_session_id').db_index = False
    GA4SessionModel._meta.get_field('date').db_index = False
    GA4SessionModel._meta.get_field('source').db_index = False
    GA4SessionModel._meta.get_field('country').db_index = False
    GA4SessionModel._meta.get_field('device').db_index = False
    GA4SessionModel._meta.get_field('entry_page').db_index = False
    GA4SessionModel._meta.get_field('synced_at').db_index = False
    
    try:
        schema_editor.create_model(GA4SessionModel)
    except Exception:
        pass  # Table might have been created concurrently


class Migration(migrations.Migration):

    dependencies = [
        ('user_analytics', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add ga4_client_id to UserJourney (only if it doesn't exist)
        migrations.RunPython(
            add_ga4_client_id_if_not_exists,
            reverse_add_ga4_client_id,
        ),
        # Create GA4Session model (only if table doesn't exist)
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    lambda apps, schema_editor: _create_ga4session_table_if_not_exists(schema_editor),
                    lambda apps, schema_editor: None,  # No reverse needed
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='GA4Session',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modified', models.DateTimeField(auto_now=True)),
                ('object_status', models.SmallIntegerField(choices=[(0, 'Deleted'), (1, 'Active'), (2, 'Inactive')], default=1)),
                ('ga4_client_id', models.CharField(db_index=True, help_text='GA4 client ID', max_length=255)),
                ('ga4_session_id', models.CharField(blank=True, help_text='GA4 session ID', max_length=255, null=True)),
                ('django_session_id', models.CharField(blank=True, db_index=True, help_text='Django session ID', max_length=255, null=True)),
                ('date', models.DateField(db_index=True, help_text='Session date')),
                ('source', models.CharField(blank=True, db_index=True, help_text='Traffic source', max_length=255, null=True)),
                ('medium', models.CharField(blank=True, max_length=255, null=True)),
                ('campaign', models.CharField(blank=True, max_length=255, null=True)),
                ('country', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('device', models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ('entry_page', models.CharField(blank=True, db_index=True, max_length=500, null=True)),
                ('exit_page', models.CharField(blank=True, max_length=500, null=True)),
                ('sessions_count', models.IntegerField(default=1, help_text='Number of sessions (for aggregated data)')),
                ('pageviews', models.IntegerField(default=0, help_text='Total page views')),
                ('users', models.IntegerField(default=1, help_text='Number of unique users')),
                ('synced_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When this data was synced from GA4')),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, help_text='Linked Django user if identified', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ga4_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'GA4 Session',
                'verbose_name_plural': 'GA4 Sessions',
                'ordering': ['-date', '-synced_at'],
            },
        ),
            ],
        ),
        # Add indexes for GA4Session (only if they don't exist)
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    lambda apps, schema_editor: _add_ga4session_indexes_if_not_exist(schema_editor),
                    lambda apps, schema_editor: None,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='ga4session',
                    index=models.Index(fields=['ga4_client_id', 'date'], name='user_analy_ga4_cli_idx'),
                ),
                migrations.AddIndex(
                    model_name='ga4session',
                    index=models.Index(fields=['django_session_id', 'date'], name='user_analy_django__idx'),
                ),
                migrations.AddIndex(
                    model_name='ga4session',
                    index=models.Index(fields=['user', '-date'], name='user_analy_user_id_idx'),
                ),
                migrations.AddIndex(
                    model_name='ga4session',
                    index=models.Index(fields=['date', 'source', 'country', 'device'], name='user_analy_date_so_idx'),
                ),
                migrations.AddIndex(
                    model_name='ga4session',
                    index=models.Index(fields=['-synced_at'], name='user_analy_synced__idx'),
                ),
            ],
        ),
        # Add unique constraint with prefix for entry_page to avoid MySQL key length limit
        # Using RunPython to check and create unique index with prefix on entry_page (first 200 chars)
        migrations.RunPython(
            code=lambda apps, schema_editor: _create_unique_index_if_not_exists(schema_editor),
            reverse_code=lambda apps, schema_editor: _drop_unique_index_if_exists(schema_editor),
        ),
    ]
