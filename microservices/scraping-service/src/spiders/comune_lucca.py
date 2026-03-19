# -*- coding: utf-8 -*-
"""
Spider per comune.lucca.it - Eventi del Comune di Lucca.

WordPress con tema design-comuni. Paginazione AJAX via admin-ajax.php
con action=load_more e post_types="evento".

Utilizzo:
    scrapy crawl comune_lucca
    scrapy crawl comune_lucca -a max_pages=10
"""

import json
import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class ComuneLuccaSpider(BaseEventSpider):
    name = "comune_lucca"
    source_name = "comune_lucca"
    allowed_domains = ["www.comune.lucca.it"]

    BASE_URL = "https://www.comune.lucca.it"
    LISTING_URL = f"{BASE_URL}/vivere-il-comune/eventi/"
    AJAX_URL = f"{BASE_URL}/wp/wp-admin/admin-ajax.php"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 0})

    def _parse_listing(self, response):
        # Parsa le card dalla pagina SSR
        yield from self._extract_events(response)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: estratti eventi dalla pagina")

        # AJAX load more
        if page + 1 < self.max_pages:
            yield scrapy.FormRequest(
                self.AJAX_URL,
                formdata={
                    "action": "load_more",
                    "page": str(page + 1),
                    "post_count": "12",
                    "load_posts": "12",
                    "post_types": "evento",
                    "load_card_type": "evento",
                },
                callback=self._parse_ajax,
                meta={"page": page + 1},
            )

    def _parse_ajax(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except Exception:
            self.logger.error(f"Risposta AJAX non valida pagina {page}")
            return

        html = data.get("response", "")
        all_results = data.get("all_results", False)

        if not html:
            return

        sel = scrapy.Selector(text=html)
        fake = response.replace(body=html.encode("utf-8"))
        events = list(self._extract_events(fake))
        yield from events

        self.logger.info(f"Pagina {page}: {len(events)} link eventi (all_results={all_results})")

        if not all_results and (page + 1) < self.max_pages and events:
            yield scrapy.FormRequest(
                self.AJAX_URL,
                formdata={
                    "action": "load_more",
                    "page": str(page + 1),
                    "post_count": "12",
                    "load_posts": "12",
                    "post_types": "evento",
                    "load_card_type": "evento",
                },
                callback=self._parse_ajax,
                meta={"page": page + 1},
            )

    def _extract_events(self, response):
        cards = response.css("div.card.card-img, div.cmp-list-card-img")
        for card in cards:
            href = card.css('h3 a[data-element="live-category-link"]::attr(href)').get()
            if not href:
                href = card.css("h3 a::attr(href)").get()
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self._parse_detail)

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1[data-audio]::text").get())
        if not title:
            title = self.clean_text(response.css("h1::text").get())
        if not title:
            return

        # Descrizione
        description = self.clean_text(
            response.css("article#cos-e .richtext-wrapper").xpath("string()").get()
        )

        # Immagine
        image_url = response.css(".figure.img-full img::attr(src)").get()
        if not image_url:
            image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date dal testo (es. "dal 06 Settembre 2024 al 08 Settembre 2024")
        date_text = self.clean_text(response.css("h3.h4.py-2[data-audio]::text").get())
        date_start = None
        date_end = None
        if date_text:
            parts = re.split(r'\b(?:al|fino al)\b', date_text, flags=re.IGNORECASE)
            start_text = re.sub(r'^(dal|da)\s+', '', parts[0].strip(), flags=re.IGNORECASE)
            date_start, _ = parse_italian_date_time(start_text)
            if len(parts) >= 2:
                date_end, _ = parse_italian_date_time(parts[-1].strip())

        # Costi
        price = self.clean_text(
            response.css("article#costi .card-body p").xpath("string()").get()
        )

        # Categoria/argomenti
        categories = []
        for chip in response.css('a.chip-simple[data-element="service-topic"] .chip-label::text').getall():
            c = self.clean_text(chip)
            if c:
                categories.append(c)

        # Tipo evento
        event_type = self.clean_text(response.css("article#tipo p::text").get())
        if event_type and event_type not in categories:
            categories.insert(0, event_type)

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", "Lucca")
        content_hash = self.generate_content_hash(description or "", price or "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": categories, "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_text or ""},
                "city": {"city_name": "Lucca", "location_name": None, "location_address": None},
                "section": {"price": price} if price else {},
            },
        )
