"""
Modelli per le viste aggregate dello scraping (categorie e location).

Questi modelli sono collegati a viste PostgreSQL (managed=False),
quindi le rename non generano ALTER TABLE.
"""
from django.db import models


class ScrapingCategory(models.Model):
    """Categorie uniche estratte dagli eventi — vista aggregata su v_categorie."""
    categoria = models.CharField(max_length=255, primary_key=True)
    count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'events_data"."v_categorie'
        ordering = ['categoria']
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorie'

    def __str__(self):
        return self.categoria


class ScrapingLocation(models.Model):
    """Location uniche estratte dagli eventi — vista aggregata su v_locations."""
    id = models.CharField(max_length=32, primary_key=True)
    location_name = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'events_data"."v_locations'
        ordering = ['location_name']
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'

    def __str__(self):
        if self.city:
            return f"{self.location_name} ({self.city})"
        return self.location_name or ''
