from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField


class Event(models.Model):
    """Modello unificato per tutti gli eventi (staging, pubblicati)."""

    class Status(models.TextChoices):
        STAGING = 'staging', 'Staging'
        PUBLISHED = 'published', 'Pubblicato'

    uuid = models.CharField(max_length=32, unique=True)
    content_hash = models.CharField(max_length=32, blank=True, null=True)
    source = models.CharField(max_length=50, db_index=True, db_comment='sorgente dati')
    title = models.TextField()
    category = ArrayField(models.TextField(), blank=True, null=True)

    # Stato del workflow
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.STAGING, db_index=True,
    )

    # Location
    city = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    location_name = models.CharField(max_length=255, blank=True, null=True)
    location_address = models.TextField(blank=True, null=True)
    location_coordinates = models.PointField(geography=True, srid=4326, blank=True, null=True)

    # Date
    date_start = models.DateTimeField(blank=True, null=True)
    date_end = models.DateTimeField(blank=True, null=True)

    # Orari (da ProductionEvent)
    time_start = models.TimeField(blank=True, null=True)
    time_end = models.TimeField(blank=True, null=True)
    time_info = models.TextField(blank=True, null=True)
    schedule = models.TextField(blank=True, null=True)
    weekdays = models.TextField(blank=True, null=True)

    # Info
    url = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    price = models.TextField(blank=True, null=True)
    website = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(blank=True, null=True)
    schema_org = models.JSONField(blank=True, null=True, db_comment='Schema.org/Event generato da AI')
    batch_file = models.CharField(max_length=255, blank=True, null=True, db_comment='Nome file batch di provenienza')

    # Tracciabilità
    created_by = models.CharField(
        max_length=150, blank=True, null=True,
        help_text='Username di chi ha creato l\'evento',
    )
    updated_by = models.CharField(
        max_length=150, blank=True, null=True,
        help_text='Username di chi ha modificato l\'evento',
    )
    deleted_by = models.CharField(
        max_length=150, blank=True, null=True,
        help_text='Username di chi ha disattivato l\'evento (soft delete)',
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    # Timestamps
    scraped_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'events_data"."events'
        ordering = ['-created_at']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventi'

    def __str__(self) -> str:
        return f"[{self.get_status_display()}] {self.title} - {self.city}"


# Alias per retrocompatibilità temporanea
StagingEvent = Event
ProductionEvent = Event
