# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class EventItem(scrapy.Item):
    """Item per gli eventi di *Today.it"""

    # Identificativi
    event_id = scrapy.Field()  # ID originale dalla fonte (estratto dall'URL)
    uuid = scrapy.Field()  # Hash di titolo + data_start + location_name
    content_hash = scrapy.Field()  # Hash di descrizione (per rilevare modifiche)

    # Metadati Fonte
    source = scrapy.Field()  # Es: "city_today"
    url = scrapy.Field()

    # Dati grezzi estratti dalle pagine
    raw_data = scrapy.Field()  # Dict con tutti i dati grezzi

    # Info base (mappate da raw_data)
    title = scrapy.Field()
    description = scrapy.Field()
    category = scrapy.Field()  # Array di stringhe
    image_url = scrapy.Field()

    # Location
    city = scrapy.Field()  # Nome città (Milano, Roma, etc.)
    city_id = scrapy.Field()  # FK a comuni_italiani.comuni.id
    location_name = scrapy.Field()
    location_address = scrapy.Field()

    # Dettagli
    price = scrapy.Field()
    website = scrapy.Field()

    # Date
    date_start = scrapy.Field()  # Data inizio (YYYY-MM-DD)
    date_end = scrapy.Field()  # Data fine (YYYY-MM-DD)
    date_display = scrapy.Field()  # Testo leggibile (es: "dal 31 gennaio al 1 febbraio")

    # Metadata
    scraped_at = scrapy.Field()
