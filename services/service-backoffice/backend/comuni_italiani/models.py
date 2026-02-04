from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField


class RipartizioneGeografica(models.Model):
    """Ripartizioni geografiche ISTAT (Nord-Ovest, Nord-Est, Centro, Sud, Isole)"""
    cod_rip = models.IntegerField(unique=True)
    den_rip = models.CharField(max_length=50)
    geom = models.MultiPolygonField(srid=4326, blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_italiani"."ripartizioni'
        ordering = ['cod_rip']
        verbose_name = 'Ripartizione Geografica'
        verbose_name_plural = 'Ripartizioni Geografiche'

    def __str__(self):
        return self.den_rip


class RegioneItaliana(models.Model):
    """Regioni italiane - tabella di lookup"""
    cod_rip = models.ForeignKey(
        RipartizioneGeografica,
        on_delete=models.CASCADE,
        to_field='cod_rip',
        db_column='cod_rip'
    )
    cod_reg = models.IntegerField(unique=True)
    den_reg = models.CharField(max_length=50)
    geom = models.MultiPolygonField(srid=4326, blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_italiani"."regioni'
        ordering = ['den_reg']
        verbose_name = 'Regione'
        verbose_name_plural = 'Regioni'

    def __str__(self):
        return self.den_reg


class ProvinciaItaliana(models.Model):
    """Province italiane - tabella di lookup"""
    cod_rip = models.IntegerField()
    cod_reg = models.ForeignKey(
        RegioneItaliana,
        on_delete=models.CASCADE,
        to_field='cod_reg',
        db_column='cod_reg'
    )
    cod_prov = models.IntegerField()
    cod_cm = models.IntegerField(blank=True, null=True)
    cod_uts = models.IntegerField(unique=True)
    den_prov = models.CharField(max_length=50, blank=True, null=True)
    den_cm = models.CharField(max_length=50, blank=True, null=True)
    den_uts = models.CharField(max_length=50)
    sigla = models.CharField(max_length=2)
    tipo_uts = models.CharField(max_length=50, blank=True, null=True)
    geom = models.MultiPolygonField(srid=4326, blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_italiani"."province'
        ordering = ['den_uts']
        verbose_name = 'Provincia'
        verbose_name_plural = 'Province'
        indexes = [
            models.Index(fields=['sigla']),
            models.Index(fields=['cod_prov']),
        ]

    def __str__(self):
        return self.den_uts


class ComuneItaliano(models.Model):
    """Comuni italiani - tabella di lookup"""
    cod_rip = models.IntegerField()
    cod_reg = models.IntegerField()
    cod_prov = models.IntegerField()
    cod_cm = models.IntegerField(blank=True, null=True)
    cod_uts = models.ForeignKey(
        ProvinciaItaliana,
        on_delete=models.CASCADE,
        to_field='cod_uts',
        db_column='cod_uts'
    )
    pro_com = models.IntegerField(unique=True)
    pro_com_t = models.CharField(max_length=6)
    comune = models.CharField(max_length=100)
    comune_a = models.CharField(max_length=100, blank=True, null=True)
    cc_uts = models.IntegerField(blank=True, null=True)
    geom = models.MultiPolygonField(srid=4326, blank=True, null=True)
    centroid = models.PointField(srid=4326, blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    # Campi arricchiti dal JSON
    codice_catastale = models.CharField(max_length=4, blank=True, null=True)
    cap = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_italiani"."comuni'
        ordering = ['comune']
        verbose_name = 'Comune'
        verbose_name_plural = 'Comuni'
        indexes = [
            models.Index(fields=['pro_com_t']),
            models.Index(fields=['comune']),
            models.Index(fields=['cod_prov']),
            models.Index(fields=['cod_reg']),
            models.Index(fields=['codice_catastale']),
            models.Index(fields=['popolazione']),
        ]

    def __str__(self):
        return self.comune


class ComuneJsonStaging(models.Model):
    """Tabella staging per import dati JSON comuni"""
    codice = models.CharField(max_length=6, primary_key=True)
    nome = models.CharField(max_length=100, blank=True, null=True)
    codice_catastale = models.CharField(max_length=4, blank=True, null=True)
    cap = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_italiani"."comuni_json_staging'
        verbose_name = 'Comune JSON Staging'
        verbose_name_plural = 'Comuni JSON Staging'

    def __str__(self):
        return f"{self.codice} - {self.nome}"
