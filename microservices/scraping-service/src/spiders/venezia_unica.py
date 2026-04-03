# -*- coding: utf-8 -*-
"""
Spider per veneziaunica.it - Portale turistico di Venezia.

Il sito usa un CMS Strapi con API REST pubblica completamente accessibile
senza autenticazione. Lo spider usa esclusivamente le API JSON.

Utilizzo:
    scrapy crawl venezia_unica
    scrapy crawl venezia_unica -a max_pages=10

Parametri:
    max_pages: Numero massimo di pagine API da scansionare (default: 5, 25 eventi/pagina)
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VeneziaUnicaSpider(BaseEventSpider):
    """
    Spider API-based per veneziaunica.it (Strapi v4).

    Strategia:
    1. GET paginato a /api/events con populate per relazioni (immagine, categorie, POI)
    2. Parsing diretto del JSON — nessun scraping HTML necessario
    """

    name = "venezia_unica"
    source_name = "venezia_unica"
    allowed_domains = ["veneziaunica.it", "ecomm-be.veneziaunica.it"]

    API_BASE = "https://ecomm-be.veneziaunica.it"
    API_EVENTS = f"{API_BASE}/api/events"
    PAGE_SIZE = 25

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        """Avvia il listing dalla pagina 1."""
        yield from self._request_page(1)

    def _request_page(self, page: int):
        """Genera richiesta GET all'API Strapi."""
        if page > self.max_pages:
            return

        url = (
            f"{self.API_EVENTS}"
            f"?locale=it"
            f"&pagination[page]={page}"
            f"&pagination[pageSize]={self.PAGE_SIZE}"
            f"&sort=start_date:asc"
            f"&populate=image,event_categories,pois"
        )

        yield scrapy.Request(
            url,
            callback=self._parse_events,
            meta={"page": page},
        )

    def _parse_events(self, response):
        """Parsa la risposta API Strapi."""
        try:
            body = response.json()
        except Exception:
            self.logger.error(f"Risposta API non valida: {response.url}")
            return

        events = body.get("data", [])
        pagination = body.get("meta", {}).get("pagination", {})
        page = response.meta["page"]
        total_pages = pagination.get("pageCount", 1)

        self.logger.info(f"Pagina {page}/{total_pages}: {len(events)} eventi")

        for event in events:
            item = self._parse_event(event)
            if item:
                yield item

        # Paginazione
        if page < min(self.max_pages, total_pages):
            yield from self._request_page(page + 1)

    def _parse_event(self, event_data: dict):
        """Costruisce un EventItem dal JSON Strapi."""
        attrs = event_data.get("attributes", {})

        title = self.clean_text(attrs.get("title"))
        if not title:
            return None

        slug = attrs.get("slug", "")
        description_brief = self.clean_text(attrs.get("description"))
        description_full = self.clean_html(attrs.get("text"))
        description = description_full or description_brief

        # Date
        date_start = self.parse_date_iso(attrs.get("start_date", ""))
        date_end = self.parse_date_iso(attrs.get("end_date", ""))
        if date_end == date_start:
            date_end = None

        # Immagine
        image_url = None
        image_data = attrs.get("image", {}).get("data")
        if image_data:
            image_attrs = image_data.get("attributes", {})
            img_path = image_attrs.get("url", "")
            if img_path:
                image_url = f"{self.API_BASE}{img_path}" if img_path.startswith("/") else img_path

        # Categorie
        categories = []
        cat_data = attrs.get("event_categories", {}).get("data", [])
        for cat in cat_data:
            name = self.clean_text(cat.get("attributes", {}).get("name"))
            if name:
                categories.append(name)

        # Location da POI
        location_name = None
        location_coords = None
        pois_data = attrs.get("pois", {}).get("data", [])
        if pois_data:
            poi_attrs = pois_data[0].get("attributes", {})
            location_name = self.clean_text(poi_attrs.get("title"))
            lat = poi_attrs.get("latitude")
            lng = poi_attrs.get("longitude")
            if lat and lng:
                location_coords = {"type": "Point", "coordinates": [float(lng), float(lat)]}

        # Coordinate dirette sull'evento (fallback)
        if not location_coords:
            lat = attrs.get("latitude")
            lng = attrs.get("longitude")
            if lat and lng:
                location_coords = {"type": "Point", "coordinates": [float(lng), float(lat)]}

        # Hash
        uuid = self.generate_uuid(title, date_start or "", location_name or "Venezia")
        content_hash = self.generate_content_hash(description or "", "", "")

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": categories,
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or ""
                },
                "city": {
                    "city_name": "Venezia",
                    "location_name": location_name,
                    "location_coords": location_coords,
                }
            },
            meta={
                "content_hash": content_hash,
                "url": f"https://www.veneziaunica.it/it/cosa-fare-a-venezia/eventi/{slug}",
                "source": self.source_name,
            },
        )

        return item
