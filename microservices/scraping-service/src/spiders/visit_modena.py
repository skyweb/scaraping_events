# -*- coding: utf-8 -*-
"""
Spider per visitmodena.it - Portale turistico di Modena.

Plone 6 con Volto (React SSR). Usa la REST API Plone per ottenere
eventi strutturati in JSON.

Utilizzo:
    scrapy crawl visit_modena
    scrapy crawl visit_modena -a max_pages=5
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitModenaSpider(BaseEventSpider):
    name = "visit_modena"
    source_name = "visit_modena"
    allowed_domains = ["www.visitmodena.it"]

    API_URL = "https://www.visitmodena.it/++api++/it/eventi/@search"
    PAGE_SIZE = 25

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        yield scrapy.Request(
            f"{self.API_URL}?portal_type=Event&sort_on=start&sort_order=ascending&b_size={self.PAGE_SIZE}&b_start=0&fullobjects=1",
            callback=self._parse_events, meta={"page": 1, "b_start": 0},
            headers={"Accept": "application/json"},
        )

    def _parse_events(self, response):
        try:
            data = response.json()
        except Exception:
            self.logger.error("Risposta API non valida")
            return

        items_list = data.get("items", [])
        total = data.get("items_total", 0)
        page = response.meta["page"]

        self.logger.info(f"Pagina {page}: {len(items_list)} eventi (totale: {total})")

        for event in items_list:
            item = self._build_item(event)
            if item:
                yield item

        # Paginazione
        batching = data.get("batching", {})
        next_url = batching.get("next")
        if next_url and page < self.max_pages:
            yield scrapy.Request(
                next_url, callback=self._parse_events,
                meta={"page": page + 1, "b_start": response.meta["b_start"] + self.PAGE_SIZE},
                headers={"Accept": "application/json"},
            )

    def _build_item(self, event: dict):
        title = self.clean_text(event.get("title"))
        if not title:
            return None

        # Descrizione dai blocks (Plone Volto DraftJS) o dal campo description
        description = self.clean_text(event.get("description"))

        date_start = self.parse_date_iso(event.get("start", ""))
        date_end = self.parse_date_iso(event.get("end", ""))

        location = self.clean_text(event.get("location"))
        address = self.clean_text(event.get("address_text"))

        # Immagine
        image_url = None
        img = event.get("image")
        if isinstance(img, dict):
            image_url = img.get("download") or img.get("scales", {}).get("large", {}).get("download")
        elif isinstance(img, str):
            image_url = img

        url = event.get("@id", "").replace("/++api++", "")

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", location or "Modena")
        content_hash = self.generate_content_hash(description or "", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "cover_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": "Modena", "location_name": location, "location_address": address},
            },
        )
