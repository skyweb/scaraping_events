from django.db import models


class ScrapingCategoria(models.Model):
    """Categorie uniche dagli eventi - vista aggregata"""
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
    """Location uniche dagli eventi - vista aggregata"""
    location_name = models.CharField(max_length=512, primary_key=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'events_data"."v_locations'
        ordering = ['location_name']
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'

    @property
    def nome_location(self):
        """Estrae il nome location dalla chiave composta"""
        if '|||' in self.location_name:
            return self.location_name.split('|||')[0]
        return self.location_name

    def __str__(self):
        nome = self.nome_location
        return f"{nome} ({self.city})" if self.city else nome
