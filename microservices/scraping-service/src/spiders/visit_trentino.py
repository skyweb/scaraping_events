# -*- coding: utf-8 -*-
"""
Spider per visittrentino.info - Portale turistico del Trentino.

Usa un endpoint AJAX JSON per la paginazione e JSON-LD Event nelle pagine dettaglio.

Utilizzo:
    scrapy crawl visit_trentino
    scrapy crawl visit_trentino -a max_pages=10
"""

import json
import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitTrentinoSpider(BaseEventSpider):
    name = "visit_trentino"
    source_name = "visit_trentino"
    allowed_domains = ["www.visittrentino.info"]

    BASE_URL = "https://www.visittrentino.info"
    LISTING_URL = f"{BASE_URL}/it/guida/cosa-fare/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(
            f"{self.LISTING_URL}?mode=grid&page=1&ajax=1&json=1",
            callback=self._parse_ajax, meta={"page": 1},
        )

    def _parse_ajax(self, response):
        try:
            data = response.json()
        except Exception:
            self.logger.error("Risposta AJAX non valida")
            return

        html = data.get("content", "")
        if not html:
            return

        sel = scrapy.Selector(text=html)
        links = sel.css('a[href*="/it/guida/cosa-fare/eventi/"]::attr(href)').getall()
        new_count = 0
        for href in links:
            full_url = self.BASE_URL + href if href.startswith("/") else href
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi")

        # Paginazione: se ci sono risultati, prova la pagina successiva
        if new_count > 0 and page < self.max_pages:
            yield scrapy.Request(
                f"{self.LISTING_URL}?mode=grid&page={page + 1}&ajax=1&json=1",
                callback=self._parse_ajax, meta={"page": page + 1},
            )

    def _parse_detail(self, response):
        # Prova JSON-LD Event
        ld_event = self.extract_jsonld_node(response, "Event") or {}

        title = self.clean_text(ld_event.get("name")) or self.clean_text(response.css("h1::text").get())
        if not title:
            return

        description = self.clean_text(ld_event.get("description"))
        if not description:
            description = self.clean_text(response.css("div.wysiwyg").xpath("string()").get())

        date_start = self.parse_date_iso(ld_event.get("startDate", ""))
        date_end = self.parse_date_iso(ld_event.get("endDate", ""))

        # Location da JSON-LD
        location = ld_event.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        location_name = self.clean_text(location.get("name"))
        address_obj = location.get("address") or {}
        city = self.clean_text(address_obj.get("addressLocality"))

        image_url = None
        ld_images = ld_event.get("image")
        if isinstance(ld_images, list) and ld_images:
            img = ld_images[0]
            image_url = img.get("url") if isinstance(img, dict) else str(img)
        elif isinstance(ld_images, dict):
            image_url = ld_images.get("url")
        if not image_url:
            image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", location_name or city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": city, "location_name": location_name, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
