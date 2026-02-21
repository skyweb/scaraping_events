# -*- coding: utf-8 -*-
"""
Definizione degli Item per gli eventi.

Questo modulo definisce la struttura dati unificata per tutti gli spider.
Ogni spider popola questi campi in modo consistente per facilitare
l'elaborazione downstream.
"""

import scrapy


class EventItem(scrapy.Item):
    """
    Item unificato per gli eventi da tutte le fonti.

    Campi obbligatori:
        - source: Identificativo della fonte (zero_eu, city_today, artribune)
        - url: URL della pagina evento
        - title: Titolo dell'evento
        - scraped_at: Timestamp dello scraping

    Campi identificativi:
        - uuid: Hash univoco per deduplicazione (titolo + data + location)
        - content_hash: Hash del contenuto per rilevare modifiche
        - event_id: ID originale dalla fonte (se disponibile)
        - slug: Slug URL dell'evento

    Campi contenuto:
        - description: Descrizione testuale dell'evento
        - category: Lista di categorie/tag
        - image_url: URL immagine principale
        - image_urls: Lista di tutte le immagini

    Campi location:
        - city: Nome della città
        - city_id: FK alla tabella comuni (opzionale)
        - location_name: Nome del luogo/venue
        - location_address: Indirizzo completo
        - location_coords: Coordinate geografiche (lat, lng)

    Campi temporali:
        - date_start: Data inizio (YYYY-MM-DD)
        - date_end: Data fine (YYYY-MM-DD)
        - date_display: Data in formato leggibile
        - time_start: Orario inizio (HH:MM)
        - time_end: Orario fine (HH:MM)
        - date_scope: Ambito temporale (es: "weekend", "settimana")
        - schedule: Orari dettagliati

    Campi aggiuntivi:
        - price: Informazioni sul prezzo
        - website: Sito web dell'evento/organizzatore
        - raw_data: Dati grezzi originali (per debug)
    """

    # === Metadati fonte ===
    source = scrapy.Field()         # Identificativo fonte: zero_eu, city_today, artribune
    url = scrapy.Field()            # URL pagina evento
    scraped_at = scrapy.Field()     # Timestamp ISO dello scraping

    # === Identificativi ===
    uuid = scrapy.Field()           # Hash univoco per deduplicazione
    content_hash = scrapy.Field()   # Hash contenuto per rilevare modifiche
    event_id = scrapy.Field()       # ID originale dalla fonte
    slug = scrapy.Field()           # Slug URL

    # === Contenuto ===
    title = scrapy.Field()          # Titolo evento
    description = scrapy.Field()    # Descrizione completa
    category = scrapy.Field()       # Lista categorie (TEXT[])
    image_url = scrapy.Field()      # URL immagine principale
    image_urls = scrapy.Field()     # Lista tutte le immagini

    # === Location ===
    city = scrapy.Field()           # Nome città
    city_id = scrapy.Field()        # FK a comuni_istat.comuni.id
    location_name = scrapy.Field()  # Nome venue/luogo
    location_address = scrapy.Field()  # Indirizzo completo
    location_coords = scrapy.Field()   # Dict con lat/lng

    # === Date e orari ===
    date_start = scrapy.Field()     # YYYY-MM-DD
    date_end = scrapy.Field()       # YYYY-MM-DD
    date_display = scrapy.Field()   # Testo leggibile
    time_start = scrapy.Field()     # HH:MM
    time_end = scrapy.Field()       # HH:MM
    date_scope = scrapy.Field()     # Ambito temporale
    schedule = scrapy.Field()       # Orari dettagliati

    # === Dettagli ===
    price = scrapy.Field()          # Info prezzo
    website = scrapy.Field()        # Sito web evento
    stars = scrapy.Field()          # Rating stelle (intero, opzionale)

    # === Contenuto strutturato ===
    section = scrapy.Field()        # Dict annidato sezione (es: {"teatro": {"cast": "...", "rassegna": "..."}})
    info_extra = scrapy.Field()     # Dict info aggiuntive spider-specific (es: info_e_costi, info_e_contatti)
    time_info = scrapy.Field()      # Testo/HTML raw dell'informazione date (per il campo dates.time_info)

    # === Debug ===
    raw_data = scrapy.Field()       # Dati grezzi originali
