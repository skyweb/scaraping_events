# -*- coding: utf-8 -*-
"""
Spider per sienacomunica.it - Eventi del Comune di Siena.

WordPress + EventON plugin. Prova WP REST API per il CPT ajde_events,
altrimenti scrapa la pagina con AJAX EventON.

Utilizzo:
    scrapy crawl siena_comunica
    scrapy crawl siena_comunica -a max_pages=5
"""

import json

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class SienaComunicaSpider(BaseEventSpider):
    name = "siena_comunica"
    source_name = "siena_comunica"
    allowed_domains = ["www.sienacomunica.it"]

    BASE_URL = "https://www.sienacomunica.it"
    API_URL = f"{BASE_URL}/wp-json/wp/v2/ajde_events"
    PER_PAGE = 100

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        yield scrapy.Request(
            f"{self.API_URL}?per_page={self.PER_PAGE}&page=1&orderby=date&order=desc",
            callback=self._parse_api, meta={"page": 1},
            errback=self._api_fallback,
        )

    def _api_fallback(self, failure):
        """Se l'API WP non espone ajde_events, prova con posts."""
        self.logger.warning(f"API ajde_events non disponibile: {failure.value}")
        yield scrapy.Request(
            f"{self.BASE_URL}/wp-json/wp/v2/posts?per_page={self.PER_PAGE}&page=1&categories=&search=evento",
            callback=self._parse_api, meta={"page": 1},
        )

    def _parse_api(self, response):
        try:
            events = response.json()
        except Exception:
            self.logger.error("Risposta API non valida")
            return

        if not isinstance(events, list) or not events:
            self.logger.info("Nessun evento trovato")
            return

        page = response.meta["page"]
        total_pages = int(response.headers.get(b"X-WP-TotalPages", b"1").decode())
        self.logger.info(f"Pagina {page}/{total_pages}: {len(events)} eventi")

        for event in events:
            item = self._build_item(event)
            if item:
                yield item

        if page < min(self.max_pages, total_pages):
            next_url = response.url.replace(f"page={page}", f"page={page + 1}")
            yield scrapy.Request(next_url, callback=self._parse_api, meta={"page": page + 1})

    def _build_item(self, event: dict):
        title = self.clean_text(event.get("title", {}).get("rendered"))
        if not title:
            return None

        url = event.get("link", "")
        slug = event.get("slug", "")
        description = self.clean_html(event.get("content", {}).get("rendered", ""))
        if not description:
            description = self.clean_html(event.get("excerpt", {}).get("rendered", ""))

        # EventON mette date nei meta fields
        meta_fields = event.get("meta") or {}
        date_start = self.parse_date_iso(meta_fields.get("evcal_srow", ""))
        date_end = self.parse_date_iso(meta_fields.get("evcal_erow", ""))

        image_url = event.get("featured_image_url") or None

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", "Siena")
        content_hash = self.generate_content_hash(description or "", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": "Siena", "location_name": None, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": url, "slug": slug, "event_id": str(event.get("id", slug)), "category": "evento", "source": self.source_name},
        )
