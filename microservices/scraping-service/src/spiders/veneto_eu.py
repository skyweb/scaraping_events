# -*- coding: utf-8 -*-
"""
Spider per veneto.eu - Portale turistico del Veneto.

Il sito espone un'API REST pubblica a api.veneto.eu/events con tutti i dati
strutturati. Nessun scraping HTML necessario.

Utilizzo:
    scrapy crawl veneto_eu
    scrapy crawl veneto_eu -a max_pages=10
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VenetoEuSpider(BaseEventSpider):
    name = "veneto_eu"
    source_name = "veneto_eu"
    allowed_domains = ["veneto.eu", "api.veneto.eu"]

    API_URL = "https://api.veneto.eu/events"
    PAGE_SIZE = 50

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        # L'API restituisce tutti gli eventi in una singola risposta (no paginazione)
        yield scrapy.Request(self.API_URL, callback=self._parse_events)

    def _parse_events(self, response):
        try:
            events = response.json()
        except Exception:
            self.logger.error(f"Risposta API non valida: {response.text[:200]}")
            return

        if not isinstance(events, list):
            self.logger.error(f"Formato inatteso: {type(events)}")
            return

        self.logger.info(f"Trovati {len(events)} eventi totali")

        for event in events:
            item = self._build_item(event)
            if item:
                yield item

    def _build_item(self, event: dict):
        title = self.clean_text(event.get("title"))
        if not title:
            return None

        description = self.clean_html(event.get("description"))
        date_start = self.parse_date_iso(event.get("startDate", ""))
        date_end = self.parse_date_iso(event.get("endDate", ""))
        city = self.clean_text(event.get("municipality"))
        address = self.clean_text(event.get("address"))

        image_url = None
        img = event.get("image") or {}
        if isinstance(img, dict):
            image_url = img.get("url")

        coords = event.get("coordinates") or {}
        location_coords = None
        lat = coords.get("latitude") or event.get("latitude")
        lng = coords.get("longitude") or event.get("longitude")
        if lat and lng:
            location_coords = {"type": "Point", "coordinates": [float(lng), float(lat)]}

        categories = [c.get("label", "") for c in (event.get("categories") or []) if c.get("label")]
        website = event.get("website")
        phone = event.get("telephone")
        email = event.get("email")

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        contacts = [v for v in [website, phone, email] if v]

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": categories, "cover_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": city, "location_name": event.get("site"), "location_address": address, "location_coords": location_coords},
                "contacts": contacts or None,
            },
        )
