from django.db import models
from django.utils.text import slugify


class PaginaCitta(models.Model):
    """Configurazione principale di una pagina città."""
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    is_attiva = models.BooleanField(default=True, verbose_name='Attiva')
    ordine = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordine', 'nome']
        verbose_name = 'Pagina Città'
        verbose_name_plural = 'Pagine Città'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)


class TabNavigazione(models.Model):
    """Tab di navigazione nell'header della pagina città."""
    pagina = models.ForeignKey(
        PaginaCitta, on_delete=models.CASCADE, related_name='navigazione'
    )
    label = models.CharField(max_length=50)
    url = models.CharField(max_length=200)
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Tab Navigazione'
        verbose_name_plural = 'Tab Navigazione'

    def __str__(self):
        return f"{self.label} ({self.pagina.nome})"


class SezionePagina(models.Model):
    """Sezione tematica dentro una pagina città (es. Notizie, Sport)."""
    COLORE_CHOICES = [
        ('blue', 'Blu'),
        ('green', 'Verde'),
        ('red', 'Rosso'),
        ('orange', 'Arancione'),
        ('yellow', 'Giallo'),
        ('purple', 'Viola'),
    ]

    pagina = models.ForeignKey(
        PaginaCitta, on_delete=models.CASCADE, related_name='sezioni'
    )
    titolo = models.CharField(max_length=100)
    colore = models.CharField(max_length=20, choices=COLORE_CHOICES, default='blue')
    link_vedi_tutti = models.CharField(max_length=200, blank=True, verbose_name='Link "Vedi tutti"')
    ordine = models.IntegerField(default=0)
    is_attiva = models.BooleanField(default=True, verbose_name='Attiva')

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Sezione Pagina'
        verbose_name_plural = 'Sezioni Pagina'

    def __str__(self):
        return f"{self.titolo} ({self.pagina.nome})"


class ArticoloSezione(models.Model):
    """Card/articolo dentro una sezione della pagina città."""
    COLORE_CATEGORIA_CHOICES = [
        ('red', 'Rosso'),
        ('blue', 'Blu'),
        ('green', 'Verde'),
        ('orange', 'Arancione'),
    ]

    sezione = models.ForeignKey(
        SezionePagina, on_delete=models.CASCADE, related_name='articoli'
    )
    titolo = models.CharField(max_length=200)
    immagine = models.ImageField(upload_to='cms/articoli/', blank=True, null=True)
    immagine_url = models.URLField(blank=True, verbose_name='Immagine URL (alternativa)')
    categoria = models.CharField(max_length=50, blank=True, verbose_name='Occhiello')
    colore_categoria = models.CharField(
        max_length=10, choices=COLORE_CATEGORIA_CHOICES, default='red',
        verbose_name='Colore occhiello'
    )
    url = models.CharField(max_length=200)
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Articolo'
        verbose_name_plural = 'Articoli'

    def __str__(self):
        return self.titolo

    @property
    def immagine_finale(self):
        """Restituisce l'URL dell'immagine: file caricato o URL esterno."""
        if self.immagine:
            return self.immagine.url
        return self.immagine_url or ''


class EventoInSezione(models.Model):
    """Bridge: collega una SezionePagina a un Event esistente."""
    sezione = models.ForeignKey(
        SezionePagina, on_delete=models.CASCADE, related_name='eventi'
    )
    evento = models.ForeignKey(
        'events.Event', on_delete=models.CASCADE,
        verbose_name='Evento'
    )
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Evento (da Staging)'
        verbose_name_plural = 'Eventi (da Staging)'

    def __str__(self):
        return f"{self.evento.title[:60]}"


class SezioneEventi(models.Model):
    """Sezione che mostra staging events selezionati (senza riscrivere articoli)."""
    pagina = models.ForeignKey(
        PaginaCitta, on_delete=models.CASCADE, related_name='sezioni_eventi'
    )
    titolo = models.CharField(max_length=100)
    colore = models.CharField(
        max_length=20, choices=SezionePagina.COLORE_CHOICES, default='blue'
    )
    link_vedi_tutti = models.CharField(
        max_length=200, blank=True, verbose_name='Link "Vedi tutti"'
    )
    ordine = models.IntegerField(default=0)
    is_attiva = models.BooleanField(default=True, verbose_name='Attiva')

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Sezione Eventi'
        verbose_name_plural = 'Sezioni Eventi'

    def __str__(self):
        return f"{self.titolo} ({self.pagina.nome})"


class EventoSelezionato(models.Model):
    """Bridge: collega una SezioneEventi a un Event esistente."""
    sezione = models.ForeignKey(
        SezioneEventi, on_delete=models.CASCADE, related_name='eventi'
    )
    evento = models.ForeignKey(
        'events.Event', on_delete=models.CASCADE,
        verbose_name='Evento'
    )
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ['ordine']
        verbose_name = 'Evento Selezionato'
        verbose_name_plural = 'Eventi Selezionati'

    def __str__(self):
        return f"{self.evento.title[:60]}"
