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
        db_table = 'comuni_istat"."ripartizioni'
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
        db_table = 'comuni_istat"."regioni'
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
        db_table = 'comuni_istat"."province'
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
    attivo = models.BooleanField(default=True, help_text='False se soppresso/fuso in altro comune')
    # Campi arricchiti dal JSON comuni
    codice_catastale = models.CharField(max_length=4, blank=True, null=True)
    cap = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)
    # Campi arricchiti da caratteristiche ISTAT
    altitudine = models.SmallIntegerField(blank=True, null=True, help_text='Altitudine del centro (m)')
    zona_altimetrica = models.SmallIntegerField(blank=True, null=True, help_text='1=Montagna int., 2=Montagna lit., 3=Collina int., 4=Collina lit., 5=Pianura')
    comune_litoraneo = models.BooleanField(blank=True, null=True)
    comune_isolano = models.BooleanField(blank=True, null=True)
    zona_costiera = models.SmallIntegerField(blank=True, null=True, help_text='Zona costiera ISTAT 2021')
    grado_urbanizzazione = models.SmallIntegerField(blank=True, null=True, help_text='DEGURBA 2021: 1=Densamente, 2=Mediamente, 3=Scarsamente')
    ecoregione_divisione = models.CharField(max_length=100, blank=True, null=True)
    ecoregione_provincia = models.CharField(max_length=100, blank=True, null=True)
    ecoregione_sezione = models.CharField(max_length=100, blank=True, null=True)
    ecoregione_sottosezione = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'comuni_istat"."comuni'
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


class ComuneSoppresso(models.Model):
    """Comuni soppressi/estinti ISTAT — collegati al comune attuale che li ha incorporati."""

    COD_VARIAZIONE_CHOICES = [
        ('ES', 'Estinzione'),
        ('AS', 'Acquisizione/Scorporo'),
    ]

    comune_attuale = models.ForeignKey(
        ComuneItaliano,
        on_delete=models.CASCADE,
        related_name='comuni_soppressi',
        blank=True,
        null=True,
    )
    anno = models.SmallIntegerField()
    pro_com_t = models.CharField(max_length=6, help_text='Codice ISTAT del comune soppresso')
    comune = models.CharField(max_length=100, help_text='Nome del comune soppresso')
    sigla_uts = models.CharField(max_length=2)
    cod_variazione = models.CharField(max_length=2, choices=COD_VARIAZIONE_CHOICES)
    data_inizio = models.CharField(max_length=20, blank=True, null=True)
    pro_com_t_rel = models.CharField(max_length=6, help_text='Codice ISTAT del comune associato (attuale)')
    comune_rel = models.CharField(max_length=100, help_text='Nome del comune associato (attuale)')
    sigla_uts_rel = models.CharField(max_length=2, blank=True, null=True)

    class Meta:
        db_table = 'comuni_istat"."comuni_soppressi'
        ordering = ['-anno', 'comune']
        verbose_name = 'Comune soppresso'
        verbose_name_plural = 'Comuni soppressi'
        indexes = [
            models.Index(fields=['pro_com_t']),
            models.Index(fields=['pro_com_t_rel']),
            models.Index(fields=['comune']),
        ]

    def __str__(self):
        return f"{self.comune} ({self.sigla_uts}) → {self.comune_rel} [{self.anno}]"


class DenominazionePrecedente(models.Model):
    """Denominazioni storiche dei comuni — stesso comune, nome diverso nel tempo."""

    comune_attuale = models.ForeignKey(
        ComuneItaliano,
        on_delete=models.CASCADE,
        related_name='denominazioni_precedenti',
        blank=True,
        null=True,
    )
    pro_com_t = models.CharField(max_length=6)
    comune = models.CharField(max_length=100, help_text='Denominazione precedente')
    sigla_uts = models.CharField(max_length=20)
    cod_den_storico = models.CharField(max_length=10)
    pro_com_t_corrente = models.CharField(max_length=6)
    comune_corrente = models.CharField(max_length=100, help_text='Denominazione corrente')
    sigla_uts_corrente = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'comuni_istat"."denominazioni_precedenti'
        ordering = ['comune']
        verbose_name = 'Denominazione precedente'
        verbose_name_plural = 'Denominazioni precedenti'
        indexes = [
            models.Index(fields=['pro_com_t_corrente']),
            models.Index(fields=['comune']),
        ]

    def __str__(self):
        return f"{self.comune} → {self.comune_corrente}"


class ComuneJsonStaging(models.Model):
    """Tabella staging per import dati JSON comuni"""
    codice = models.CharField(max_length=6, primary_key=True)
    nome = models.CharField(max_length=100, blank=True, null=True)
    codice_catastale = models.CharField(max_length=4, blank=True, null=True)
    cap = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'comuni_istat"."comuni_json_staging'
        verbose_name = 'Comune JSON Staging'
        verbose_name_plural = 'Comuni JSON Staging'

    def __str__(self):
        return f"{self.codice} - {self.nome}"
