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
