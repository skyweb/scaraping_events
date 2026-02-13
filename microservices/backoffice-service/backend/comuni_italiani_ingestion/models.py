from django.db import models


class ComuniItalianiRawData(models.Model):
    """Dati grezzi ricevuti dallo scraping comuni italiani (regioni, province, comuni)"""

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
        db_table = 'comuni_italiani_ingestion"."raw_data'
        verbose_name = 'Raw Data'
        verbose_name_plural = 'Raw Data'
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['codice_istat']),
            models.Index(fields=['tipo', 'codice_istat']),
        ]

    def __str__(self):
        nome = self.comune or self.provincia or self.regione
        return f"{self.tipo}: {nome} ({self.codice_istat})"
