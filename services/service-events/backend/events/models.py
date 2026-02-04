from django.db import models
from django.contrib.postgres.fields import ArrayField


class ProductionEvent(models.Model):
    """Eventi finali validati - tabella esistente"""
    uuid = models.CharField(max_length=16, unique=True)
    content_hash = models.CharField(max_length=16, blank=True, null=True)
    source = models.CharField(max_length=50)
    url = models.TextField(blank=True, null=True)
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    category = ArrayField(models.TextField(), blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    location_name = models.CharField(max_length=255, blank=True, null=True)
    location_address = models.TextField(blank=True, null=True)
    price = models.TextField(blank=True, null=True)
    website = models.TextField(blank=True, null=True)
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)
    time_start = models.TimeField(blank=True, null=True)
    time_end = models.TimeField(blank=True, null=True)
    time_info = models.TextField(blank=True, null=True)
    schedule = models.TextField(blank=True, null=True)
    weekdays = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(blank=True, null=True)
    scraped_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'events_data"."production_events'
        ordering = ['-date_start', '-created_at']
        verbose_name = 'Production Event'
        verbose_name_plural = 'Production Events'

    def __str__(self):
        return f"{self.title} ({self.city})"


class StagingEvent(models.Model):
    """Eventi temporanei dallo scraping"""
    uuid = models.CharField(max_length=16)
    content_hash = models.CharField(max_length=16, blank=True, null=True)
    source = models.CharField(max_length=50)
    url = models.TextField(blank=True, null=True)
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    category = ArrayField(models.TextField(), blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    location_name = models.CharField(max_length=255, blank=True, null=True)
    location_address = models.TextField(blank=True, null=True)
    price = models.TextField(blank=True, null=True)
    website = models.TextField(blank=True, null=True)
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)
    time_start = models.TimeField(blank=True, null=True)
    time_end = models.TimeField(blank=True, null=True)
    time_info = models.TextField(blank=True, null=True)
    schedule = models.TextField(blank=True, null=True)
    weekdays = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(blank=True, null=True)
    scraped_at = models.DateTimeField(blank=True, null=True)
    loaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'events_data"."staging_events'
        ordering = ['-loaded_at']
        verbose_name = 'Staging Event'
        verbose_name_plural = 'Staging Events'

    def __str__(self):
        return f"[STAGING] {self.title}"
