from django.db import models
from django.contrib.postgres.fields import ArrayField


class ComuneItaliano(models.Model):
    """Comuni italiani - tabella di lookup"""
    comune = models.CharField(max_length=255, primary_key=True)
    codice_catastale = models.CharField(max_length=10, blank=True, null=True)
    cap = models.CharField(max_length=10, blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)
    pro_com_t = models.CharField(max_length=20, blank=True, null=True)
    cod_uts = models.IntegerField(blank=True, null=True)
    geom = models.TextField(blank=True, null=True)
    centroid = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'comuni_italiani"."comuni'
        ordering = ['comune']
        verbose_name = 'Comune'
        verbose_name_plural = 'Comuni'

    def __str__(self):
        return self.comune


class ProvinciaItaliana(models.Model):
    """Province italiane - tabella di lookup"""
    den_uts = models.CharField(max_length=255, primary_key=True)
    sigla = models.CharField(max_length=10, blank=True, null=True)
    tipo_uts = models.CharField(max_length=100, blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    geom = models.TextField(blank=True, null=True)  # PostGIS geometry stored as text for display

    class Meta:
        managed = False
        db_table = 'comuni_italiani"."province'
        ordering = ['den_uts']
        verbose_name = 'Provincia'
        verbose_name_plural = 'Province'

    def __str__(self):
        return self.den_uts


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


class EtlRun(models.Model):
    """Log delle esecuzioni ETL"""
    run_type = models.CharField(max_length=50)
    source = models.CharField(max_length=50, blank=True, null=True)
    cities = ArrayField(models.TextField(), blank=True, null=True)
    periodo = models.CharField(max_length=50, blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    staging_completed_at = models.DateTimeField(blank=True, null=True)
    upsert_completed_at = models.DateTimeField(blank=True, null=True)
    staging_count = models.IntegerField(default=0)
    inserted_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    unchanged_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='running')
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'events_data"."etl_runs'
        ordering = ['-started_at']
        verbose_name = 'ETL Run'
        verbose_name_plural = 'ETL Runs'

    def __str__(self):
        return f"{self.run_type} - {self.started_at}"


class EtlError(models.Model):
    """Log dei record problematici"""
    error_type = models.CharField(max_length=50)
    source = models.CharField(max_length=50, blank=True, null=True)
    json_file = models.CharField(max_length=255, blank=True, null=True)
    record_data = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    dag_run_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'events_data"."etl_errors'
        ordering = ['-created_at']
        verbose_name = 'ETL Error'
        verbose_name_plural = 'ETL Errors'

    def __str__(self):
        return f"{self.error_type} - {self.source}"


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
    location_name = models.CharField(max_length=512, primary_key=True)  # Contiene location|||city
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
