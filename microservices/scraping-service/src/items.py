# -*- coding: utf-8 -*-
"""
Definizione degli Item per gli eventi.

Struttura:
    uuid        — Hash univoco per deduplicazione (titolo + data + location)
    title       — Titolo dell'evento
    data        — Dict con contenuto, date, location, dettagli
    meta        — Dict metadati (url, slug, event_id, ...)
"""

import scrapy


class EventItem(scrapy.Item):
    """Item unificato per gli eventi da tutte le fonti."""

    # Identificativi
    uuid = scrapy.Field()
    title = scrapy.Field()

    # Blocchi annidati
    data = scrapy.Field()           # contenuto, date, location, dettagli
    meta = scrapy.Field()           # url, slug, event_id ...
