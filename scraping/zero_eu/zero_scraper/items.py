# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class EventItem(scrapy.Item):
    """Item per gli eventi di Zero.eu"""
    
    # Identificativi
    id = scrapy.Field()
    url = scrapy.Field()
    slug = scrapy.Field()
    
    # Info base
    title = scrapy.Field()
    description = scrapy.Field()
    category = scrapy.Field()
    image_url = scrapy.Field()
    
    # Luogo
    city = scrapy.Field()
    location_name = scrapy.Field()
    location_address = scrapy.Field() # Potrebbe non essere disponibile
    location_coords = scrapy.Field() # Lat, Lng
    
    # Prezzo
    price = scrapy.Field()
    
    # Date e orari
    date_start = scrapy.Field() # YYYY-MM-DD
    date_end = scrapy.Field()   # YYYY-MM-DD
    date_display = scrapy.Field() # Testo leggibile (es: "sabato 24 gennaio...")
    time_start = scrapy.Field()
    time_end = scrapy.Field()
    date_scope = scrapy.Field()
    
    # Metadata
    scraped_at = scrapy.Field()