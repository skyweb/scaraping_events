from django.contrib.postgres.fields import ArrayField
from django.db import models


# Schema DB: comuni_italiani
SCHEMA = 'comuni_italiani"."'


# =============================================================================
# Tabella raw data (dati grezzi JSON dallo scraping)
# =============================================================================

class ComuniIstatRawData(models.Model):
    """Dati grezzi ricevuti dallo scraping (regioni, province, comuni)."""

    TIPO_CHOICES = [
        ('regione', 'Regione'),
        ('provincia', 'Provincia'),
        ('comune', 'Comune'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    codice_istat = models.CharField(max_length=10)
    regione = models.CharField(max_length=100)
    provincia = models.CharField(max_length=100, blank=True, null=True)
    comune = models.CharField(max_length=100, blank=True, null=True)
    raw_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = f'{SCHEMA}raw_data'
        verbose_name = 'Raw Data'
        verbose_name_plural = 'Raw Data'
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['codice_istat']),
            models.Index(fields=['tipo', 'codice_istat']),
        ]

    def __str__(self):
        """Restituisce tipo, nome e codice ISTAT del record grezzo."""
        nome = self.comune or self.provincia or self.regione
        return f"{self.tipo}: {nome} ({self.codice_istat})"


# =============================================================================
# Tabelle relazionali (dati strutturati dallo schema.sql)
# =============================================================================

class Regione(models.Model):
    """Regioni italiane con dati demografici dallo scraping."""
    nome = models.CharField(max_length=100, unique=True)
    codice_istat = models.CharField(max_length=5, unique=True)
    popolazione = models.IntegerField(blank=True, null=True)
    popolazione_maschi = models.IntegerField(blank=True, null=True)
    popolazione_femmine = models.IntegerField(blank=True, null=True)
    superficie_kmq = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    densita = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    num_province = models.SmallIntegerField(blank=True, null=True)
    num_comuni = models.SmallIntegerField(blank=True, null=True)
    capoluogo = models.CharField(max_length=100, blank=True, null=True)
    iso_3166_2 = models.CharField(max_length=10, blank=True, null=True)
    nuts = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = f'{SCHEMA}regioni'
        ordering = ['nome']
        verbose_name = 'Regione'
        verbose_name_plural = 'Regioni'

    def __str__(self):
        """Restituisce il nome della regione."""
        return self.nome


class Provincia(models.Model):
    """Province italiane con dati demografici dallo scraping."""
    regione = models.ForeignKey(Regione, on_delete=models.CASCADE, related_name='province')
    nome = models.CharField(max_length=100)
    sigla = models.CharField(max_length=5, blank=True, null=True)
    codice_istat = models.CharField(max_length=5, unique=True)
    zona = models.CharField(max_length=100, blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)
    popolazione_maschi = models.IntegerField(blank=True, null=True)
    popolazione_femmine = models.IntegerField(blank=True, null=True)
    superficie_kmq = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    densita = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    num_comuni = models.SmallIntegerField(blank=True, null=True)
    capoluogo = models.CharField(max_length=100, blank=True, null=True)
    iso_3166_2 = models.CharField(max_length=10, blank=True, null=True)
    nuts = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = f'{SCHEMA}province'
        ordering = ['nome']
        verbose_name = 'Provincia'
        verbose_name_plural = 'Province'
        unique_together = [('regione', 'nome')]
        indexes = [
            models.Index(fields=['sigla'], name='ing_province_sigla_idx'),
            models.Index(fields=['codice_istat'], name='ing_province_codice_idx'),
        ]

    def __str__(self):
        """Restituisce il nome della provincia con sigla, se disponibile."""
        return f"{self.nome} ({self.sigla})" if self.sigla else self.nome


class Comune(models.Model):
    """Comuni italiani con dati completi dallo scraping."""
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE, related_name='comuni')
    nome = models.CharField(max_length=200)
    codice_istat = models.CharField(max_length=10, unique=True)
    codice_catastale = models.CharField(max_length=10, unique=True, blank=True, null=True)
    zona = models.CharField(max_length=100, blank=True, null=True)
    popolazione = models.IntegerField(blank=True, null=True)
    superficie_kmq = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    densita = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cap = models.CharField(max_length=10, blank=True, null=True)
    prefisso_telefonico = models.CharField(max_length=10, blank=True, null=True)
    patrono = models.CharField(max_length=200, blank=True, null=True)
    festa_patronale = models.CharField(max_length=100, blank=True, null=True)
    demonimo = models.CharField(max_length=200, blank=True, null=True)
    etimologia = models.TextField(blank=True, null=True)
    il_comune_e = ArrayField(models.TextField(), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = f'{SCHEMA}comuni'
        ordering = ['nome']
        verbose_name = 'Comune'
        verbose_name_plural = 'Comuni'
        indexes = [
            models.Index(fields=['nome'], name='ing_comuni_nome_idx'),
            models.Index(fields=['codice_istat'], name='ing_comuni_codice_idx'),
            models.Index(fields=['cap'], name='ing_comuni_cap_idx'),
        ]

    def __str__(self):
        """Restituisce il nome del comune."""
        return self.nome


# =============================================================================
# Tabelle figlie (array → relazionali)
# =============================================================================

class ComuneFrazione(models.Model):
    """Frazioni e località di un comune."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='frazioni')
    nome = models.CharField(max_length=300)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_frazioni'
        ordering = ['ordine']
        verbose_name = 'Frazione'
        verbose_name_plural = 'Frazioni'

    def __str__(self):
        """Restituisce il nome della frazione."""
        return self.nome


class ComuneConfinante(models.Model):
    """Comuni confinanti."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='confinanti')
    descrizione = models.CharField(max_length=500)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_confinanti'
        ordering = ['ordine']
        verbose_name = 'Comune confinante'
        verbose_name_plural = 'Comuni confinanti'

    def __str__(self):
        """Restituisce la descrizione del comune confinante."""
        return self.descrizione


class Appartenenza(models.Model):
    """Entità di appartenenza normalizzata (comunità montane, parchi, associazioni)."""
    nome = models.CharField(max_length=500, unique=True)

    class Meta:
        db_table = f'{SCHEMA}appartenenze'
        ordering = ['nome']
        verbose_name = 'Appartenenza'
        verbose_name_plural = 'Appartenenze'

    def __str__(self):
        """Restituisce il nome dell'appartenenza."""
        return self.nome


class ComuneAppartenenza(models.Model):
    """Appartenenze: comunità montane, parchi, associazioni."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='appartenenze')
    appartenenza = models.ForeignKey(
        Appartenenza, on_delete=models.CASCADE,
        related_name='comuni_appartenenza',
        blank=True, null=True,
    )
    nome = models.CharField(max_length=500)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_appartenenze'
        ordering = ['ordine']
        verbose_name = 'Appartenenza'
        verbose_name_plural = 'Appartenenze'

    def __str__(self):
        """Restituisce il nome dell'appartenenza del comune."""
        return self.nome


class ComunePuntoInteresse(models.Model):
    """Punti di interesse: musei, chiese, ville, castelli, ecc."""
    TIPO_CHOICES = [
        ('museo', 'Museo'),
        ('chiesa', 'Chiesa'),
        ('villa_palazzo', 'Villa / Palazzo'),
        ('castello_fortificazione', 'Castello / Fortificazione'),
        ('fontana', 'Fontana'),
        ('giardino_orto_botanico', 'Giardino / Orto Botanico'),
        ('luogo_interesse', 'Luogo di interesse'),
        ('teatro', 'Teatro'),
        ('stadio', 'Stadio'),
    ]

    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='punti_interesse')
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    nome = models.CharField(max_length=500)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_punti_interesse'
        ordering = ['ordine']
        verbose_name = 'Punto di interesse'
        verbose_name_plural = 'Punti di interesse'
        indexes = [
            models.Index(fields=['tipo'], name='ing_poi_tipo_idx'),
        ]

    def __str__(self):
        """Restituisce il tipo e il nome del punto di interesse."""
        return f"{self.get_tipo_display()}: {self.nome}"


class ComuneEvento(models.Model):
    """Eventi, feste, sagre del comune."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='eventi')
    nome = models.CharField(max_length=500)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_eventi'
        ordering = ['ordine']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventi'

    def __str__(self):
        """Restituisce il nome dell'evento."""
        return self.nome


class ComuneGemellaggio(models.Model):
    """Gemellaggi con altre città."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='gemellaggi')
    citta = models.CharField(max_length=300)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_gemellaggi'
        ordering = ['ordine']
        verbose_name = 'Gemellaggio'
        verbose_name_plural = 'Gemellaggi'

    def __str__(self):
        """Restituisce il nome della città gemellata."""
        return self.citta


class ComuneCittadinoIllustre(models.Model):
    """Cittadini illustri del comune."""
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name='cittadini_illustri')
    nome = models.CharField(max_length=500)
    ordine = models.SmallIntegerField(default=0)

    class Meta:
        db_table = f'{SCHEMA}comune_cittadini_illustri'
        ordering = ['ordine']
        verbose_name = 'Cittadino illustre'
        verbose_name_plural = 'Cittadini illustri'

    def __str__(self):
        """Restituisce il nome del cittadino illustre."""
        return self.nome
