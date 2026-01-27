# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class EventItem(scrapy.Item):
    """Item per gli eventi di *Today.it"""

    # Identificativi
    uuid = scrapy.Field()  # Hash di titolo + data_start + location_name
    content_hash = scrapy.Field()  # Hash di descrizione + prezzo + ora (per rilevare modifiche)

    # Info base dalla lista
    url = scrapy.Field()
    title = scrapy.Field()
    category = scrapy.Field()
    image_url = scrapy.Field()
    city = scrapy.Field()  # Città dell'evento (Milano, Roma, etc.)

    # Info dettaglio
    location_name = scrapy.Field()
    location_address = scrapy.Field()
    price = scrapy.Field()
    description = scrapy.Field()
    website = scrapy.Field()

    # Date e orari - campi originali
    date_start = scrapy.Field()  # Data inizio (YYYY-MM-DD)
    date_end = scrapy.Field()  # Data fine (YYYY-MM-DD)
    weekdays = scrapy.Field()  # Giorni della settimana (es. "Lunedì, Mercoledì")
    time_info = scrapy.Field()  # Orario sintetico
    schedule = scrapy.Field()  # Dettaglio completo orari/giorni

    # Date e orari - array dettagliato
    # Array di oggetti: {"date": "2026-01-31", "weekday": "Sabato", "time_start": "10:00", "time_end": "20:00"}
    dates = scrapy.Field()

    # Metadata
    scraped_at = scrapy.Field()
