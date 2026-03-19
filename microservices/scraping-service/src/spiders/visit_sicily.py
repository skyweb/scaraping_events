# -*- coding: utf-8 -*-
"""
Spider per visitsicily.info - Portale turistico della Sicilia.

WordPress con WP REST API attiva. Il custom post type 'evento-new'
è accessibile via /wp-json/wp/v2/evento-new.

Utilizzo:
    scrapy crawl visit_sicily
    scrapy crawl visit_sicily -a max_pages=5
"""

import json

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitSicilySpider(BaseEventSpider):
    name = "visit_sicily"
    source_name = "visit_sicily"
    allowed_domains = ["www.visitsicily.info"]

    API_URL = "https://www.visitsicily.info/wp-json/wp/v2/evento-new"
    API_LUOGO = "https://www.visitsicily.info/wp-json/wp/v2/luogo"
    PER_PAGE = 100

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._luogo_cache: dict[int, str] = {}

    def start_requests(self):
        # Carica prima le location (taxonomy "luogo")
        yield scrapy.Request(f"{self.API_LUOGO}?per_page=100", callback=self._parse_luoghi)

    def _parse_luoghi(self, response):
        try:
            luoghi = response.json()
            for l in luoghi:
                self._luogo_cache[l["id"]] = l.get("name", "")
            self.logger.info(f"Luoghi cachati: {len(self._luogo_cache)}")
        except Exception:
            self.logger.warning("Impossibile caricare luoghi")

        yield scrapy.Request(
            f"{self.API_URL}?per_page={self.PER_PAGE}&page=1",
            callback=self._parse_events, meta={"page": 1},
        )

    def _parse_events(self, response):
        try:
            events = response.json()
        except Exception:
            self.logger.error("Risposta API non valida")
            return

        if not events:
            return

        page = response.meta["page"]
        total_pages = int(response.headers.get(b"X-WP-TotalPages", b"1").decode())
        self.logger.info(f"Pagina {page}/{total_pages}: {len(events)} eventi")

        for event in events:
            item = self._build_item(event)
            if item:
                yield item

        if page < min(self.max_pages, total_pages):
            yield scrapy.Request(
                f"{self.API_URL}?per_page={self.PER_PAGE}&page={page + 1}",
                callback=self._parse_events, meta={"page": page + 1},
            )

    def _build_item(self, event: dict):
        title = self.clean_text(event.get("title", {}).get("rendered"))
        if not title:
            return None

        url = event.get("link", "")
        slug = event.get("slug", "")

        # Descrizione dai campi ACF
        acf = event.get("acf") or {}
        description = self.clean_html(acf.get("paragrafo_1")) or self.clean_html(
            event.get("content", {}).get("rendered", "")
        )

        # Immagine: featured_media
        image_url = None  # Richiederebbe call a /wp-json/wp/v2/media/{id}

        # Location dalla taxonomy "luogo"
        luogo_ids = event.get("luogo", [])
        city = None
        if luogo_ids and isinstance(luogo_ids, list):
            city = self._luogo_cache.get(luogo_ids[0])

        uuid = self.generate_uuid(title, "", city or "Sicilia")
        content_hash = self.generate_content_hash(description or "", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": "", "date_end": "", "date_display": ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
        )
