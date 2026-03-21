from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone


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

    # Info
    url = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    price = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(blank=True, null=True)
    schema_org = models.JSONField(blank=True, null=True, db_comment='Schema.org/Event generato da AI')
    batch_file = models.CharField(max_length=255, blank=True, null=True, db_comment='Nome file batch di provenienza')

    # Ranking
    rank_score = models.FloatField(default=0.0, db_index=True, help_text='Score calcolato automaticamente')
    boost = models.SmallIntegerField(default=0, help_text='Override manuale redazione (-10..+10)')

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

    def compute_rank_score(self) -> float:
        """
        Calcola il rank_score basato su:
        - Completezza dati (0-30 punti)
        - Stato temporale (0-30 punti)
        - Freschezza scraping (0-20 punti)
        - Qualità fonte (0-10 punti)
        - Schema.org presente (0-10 punti)
        """
        score = 0.0
        now = timezone.now()

        # ── Completezza (max 30) ──
        completeness_fields = [
            self.description, self.image_url, self.location_coordinates,
            self.price, self.category, self.location_address, self.url,
        ]
        filled = sum(1 for f in completeness_fields if f)
        score += (filled / len(completeness_fields)) * 30

        # ── Stato temporale (max 30) ──
        if self.date_start:
            if self.date_end and self.date_start <= now <= self.date_end:
                score += 30  # In corso
            elif self.date_start > now:
                # Futuro: più è vicino, più alto
                days_ahead = (self.date_start - now).days
                if days_ahead <= 7:
                    score += 25
                elif days_ahead <= 30:
                    score += 20
                elif days_ahead <= 90:
                    score += 15
                else:
                    score += 5
            else:
                score += 0  # Passato

        # ── Freschezza scraping (max 20) ──
        ref_date = self.scraped_at or self.created_at
        if ref_date:
            days_old = (now - ref_date).days
            if days_old <= 1:
                score += 20
            elif days_old <= 7:
                score += 15
            elif days_old <= 30:
                score += 10
            elif days_old <= 90:
                score += 5

        # ── Schema.org (max 10) ──
        if self.schema_org:
            score += 10

        # ── Qualità fonte (max 10) ──
        premium_sources = {'borghi_italia', 'artribune', 'turismo_torino', 'visit_tuscany'}
        if self.source in premium_sources:
            score += 10
        elif self.source:
            score += 5

        return round(score, 2)


# Alias per retrocompatibilità temporanea
StagingEvent = Event
ProductionEvent = Event
