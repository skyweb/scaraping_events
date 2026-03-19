# -*- coding: utf-8 -*-
"""
Spider per lovevda.it - Portale turistico della Valle d'Aosta.

Il sito usa Orchard CMS (ASP.NET) con paginazione server-side.

Utilizzo:
    scrapy crawl love_vda
    scrapy crawl love_vda -a max_pages=10

Parametri:
    max_pages: Numero massimo di pagine (default: 5, 10 eventi/pagina)
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class LoveVdaSpider(BaseEventSpider):
    name = "love_vda"
    source_name = "love_vda"
    allowed_domains = ["www.lovevda.it"]

    BASE_URL = "https://www.lovevda.it"
    LISTING_URL = "https://www.lovevda.it/it/eventi/ricerca-generale"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 1})

    def _parse_listing(self, response):
        links = response.css('a[href*="/it/banca-dati/"]::attr(href)').getall()
        new_count = 0
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi")

        has_next = response.css("li.page-item a.page-link[rel='next']::attr(href)").get()
        if has_next and page < self.max_pages:
            yield scrapy.Request(response.urljoin(has_next), callback=self._parse_listing, meta={"page": page + 1})

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1.page-title::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        # Descrizione
        description = self.clean_text(
            response.css(".text-truncate-3").xpath("string()").get()
            or response.css(".collapse-body").xpath("string()").get()
        )

        # Immagine
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date (formato italiano: "06 marzo 2026 - 06 aprile 2026")
        date_text = self.clean_text(response.css("p.left.grey div::text").get())
        date_start = None
        date_end = None
        if date_text:
            parts = re.split(r'\s*-\s*', date_text)
            if parts:
                date_start, _ = parse_italian_date_time(parts[0])
            if len(parts) >= 2:
                date_end, _ = parse_italian_date_time(parts[-1])

        if date_end == date_start:
            date_end = None

        # Location
        city = self.clean_text(response.css("a.link-localita::text").get())

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description,
                "category": [],
                "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_text or ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
