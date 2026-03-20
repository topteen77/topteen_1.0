from django.contrib import admin

from kaunsa_mirror.models import KaunsaSnapshot, KaunsaSyncLog


@admin.register(KaunsaSnapshot)
class KaunsaSnapshotAdmin(admin.ModelAdmin):
    list_display = ('scope', 'endpoint_key', 'content_hash', 'row_count', 'updated_at')
    list_filter = ('scope', 'endpoint_key')
    readonly_fields = ('fetched_at', 'updated_at')


@admin.register(KaunsaSyncLog)
class KaunsaSyncLogAdmin(admin.ModelAdmin):
    list_display = ('scope', 'started_at', 'finished_at', 'success', 'skipped_no_change', 'http_status')
    list_filter = ('scope', 'success', 'skipped_no_change')
    readonly_fields = ('started_at',)
