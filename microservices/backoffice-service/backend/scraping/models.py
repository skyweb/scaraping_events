"""
Modelli per le viste aggregate dello scraping (categorie e location)
e per la gestione dei siti web scrapati.

I modelli ScrapingCategory e ScrapingLocation sono collegati a viste
PostgreSQL (managed=False). ScrapingWebsite è una tabella gestita.
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
    location_name = models.CharField(max_length=255, primary_key=True)
    city_name = models.CharField(max_length=100, blank=True, null=True, db_column='city_name')
    count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'events_data"."v_locations'
        ordering = ['location_name']
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'

    def __str__(self):
        if self.city_name:
            return f"{self.location_name} ({self.city_name})"
        return self.location_name or ''


class ScrapingWebsite(models.Model):
    """Portali web da cui vengono scrapati gli eventi."""

    class CmsType(models.TextChoices):
        DRUPAL = 'drupal', 'Drupal'
        WORDPRESS = 'wordpress', 'WordPress'
        CUSTOM = 'custom', 'Custom'
        API_REST = 'api_rest', 'API REST'
        API_GRAPHQL = 'api_graphql', 'API GraphQL'
        LIFERAY = 'liferay', 'Liferay'
        STRAPI = 'strapi', 'Strapi'
        DIRECTUS = 'directus', 'Directus'
        ANGULAR_SPA = 'angular_spa', 'Angular SPA'
        AEM = 'aem', 'Adobe AEM'
        ORCHARD = 'orchard', 'Orchard CMS'
        PIMCORE = 'pimcore', 'Pimcore'

    name = models.CharField(max_length=255, verbose_name='Nome portale')
    source_url = models.URLField(max_length=500, verbose_name='URL base')
    spider_name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nome spider',
        help_text='Nome del file spider Scrapy (es: in_lombardia)',
    )
    cms = models.CharField(
        max_length=20,
        choices=CmsType.choices,
        default=CmsType.CUSTOM,
        verbose_name='CMS',
    )
    is_active = models.BooleanField(default=True, verbose_name='Attivo')
    notes = models.TextField(blank=True, verbose_name='Note')

    class Meta:
        db_table = 'scraping_website'
        ordering = ['name']
        verbose_name = 'Website'
        verbose_name_plural = 'Websites'

    def __str__(self):
        return f"{self.name} ({self.spider_name})"
