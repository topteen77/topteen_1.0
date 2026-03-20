from django.db import models


class KaunsaSnapshot(models.Model):
    """
    Raw JSON payload + content hash per sync scope (India / international) and endpoint.
    Aligns with doc-md/sql/kaunsa_mirror_schema.sql
    """

    class Scope(models.TextChoices):
        INDIA = 'india', 'India'
        INTERNATIONAL = 'international', 'International'

    scope = models.CharField(max_length=32, choices=Scope.choices, db_index=True)
    endpoint_key = models.CharField(max_length=64, db_index=True)
    content_hash = models.CharField(max_length=64)
    row_count = models.IntegerField(null=True, blank=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kaunsa_snapshot'
        constraints = [
            models.UniqueConstraint(fields=['scope', 'endpoint_key'], name='uniq_kaunsa_snapshot_scope_endpoint'),
        ]
        indexes = [
            models.Index(fields=['scope', 'endpoint_key']),
        ]

    def __str__(self):
        return f'{self.scope}:{self.endpoint_key}'


class KaunsaSyncLog(models.Model):
    """Audit trail for each sync attempt (success, API errors, unchanged hash)."""

    class Scope(models.TextChoices):
        INDIA = 'india', 'India'
        INTERNATIONAL = 'international', 'International'

    scope = models.CharField(max_length=32, choices=Scope.choices, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    http_status = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    hash_before = models.CharField(max_length=64, blank=True)
    hash_after = models.CharField(max_length=64, blank=True)
    skipped_no_change = models.BooleanField(default=False)

    class Meta:
        db_table = 'kaunsa_sync_log'
        indexes = [
            models.Index(fields=['scope', '-started_at']),
        ]

    def __str__(self):
        return f'{self.scope} @ {self.started_at} ok={self.success}'
