from django.apps import AppConfig


class ScrapingConfig(AppConfig):
    """Configurazione dell'app Django per la gestione dei dati di scraping."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scraping'
    verbose_name = 'Scraping'
