from django.db import models


class EtlRun(models.Model):
    """Log delle esecuzioni ETL"""
    run_type = models.CharField(max_length=50)
    source = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default='running')
    staging_count = models.IntegerField(default=0)
    inserted_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    staging_completed_at = models.DateTimeField(blank=True, null=True)
    upsert_completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'etl_runs'
        ordering = ['-started_at']
        verbose_name = 'ETL Run'
        verbose_name_plural = 'ETL Runs'

    def __str__(self):
        return f"{self.run_type} - {self.source} ({self.status})"


class EtlError(models.Model):
    """Errori durante le esecuzioni ETL"""
    error_type = models.CharField(max_length=50)
    source = models.CharField(max_length=50, blank=True, null=True)
    json_file = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'etl_errors'
        ordering = ['-created_at']
        verbose_name = 'ETL Error'
        verbose_name_plural = 'ETL Errors'

    def __str__(self):
        return f"{self.error_type} - {self.source}"


class TraceLog(models.Model):
    """Log degli step di tracing distribuito — timeline consultabile da Django admin."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    trace_id = models.CharField(max_length=32, db_index=True, help_text='W3C Trace ID (32 hex chars)')
    span_id = models.CharField(max_length=16, blank=True, null=True, help_text='Span ID corrente')
    parent_span_id = models.CharField(max_length=16, blank=True, null=True)
    service = models.CharField(max_length=50, help_text='Nome del servizio (es. backoffice-django, scraping-service)')
    operation = models.CharField(max_length=100, help_text='Operazione (es. bulk.received, event.validated)')
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    message = models.TextField(blank=True, null=True, help_text='Dettaglio o messaggio errore')
    metadata = models.JSONField(blank=True, null=True, help_text='Dati strutturati (spider, uuid eventi, conteggi)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trace_logs'
        ordering = ['created_at']
        verbose_name = 'Trace Log'
        verbose_name_plural = 'Trace Logs'
        indexes = [
            models.Index(fields=['trace_id', 'created_at']),
            models.Index(fields=['level']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"[{self.level}] {self.service}:{self.operation} ({self.trace_id[:8]}...)"
