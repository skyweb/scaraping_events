# -*- coding: utf-8 -*-
"""
Spider per visitlazio.com - Portale turistico del Lazio.

WordPress + Modern Events Calendar (MEC). Scrapa il calendario eventi
dalla pagina listing e segue le pagine dettaglio.

Utilizzo:
    scrapy crawl visit_lazio
    scrapy crawl visit_lazio -a max_pages=5
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitLazioSpider(BaseEventSpider):
    name = "visit_lazio"
    source_name = "visit_lazio"
    allowed_domains = ["www.visitlazio.com"]

    BASE_URL = "https://www.visitlazio.com"
    LISTING_URL = f"{BASE_URL}/eventi/"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing)

    def _parse_listing(self, response):
        # MEC slider + calendar sidebar
        links = response.css("h4.mec-event-title a::attr(href)").getall()
        new_count = 0
        for href in links:
            if href in self._seen_urls:
                continue
            self._seen_urls.add(href)
            new_count += 1
            yield scrapy.Request(href, callback=self._parse_detail)

        self.logger.info(f"Trovati {new_count} eventi dalla pagina listing")

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1.mec-single-title::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        # Descrizione
        description = self.clean_text(
            response.css(".mec-single-event-description").xpath("string()").get()
        )

        # Date MEC
        date_start = None
        date_end = None
        start_abbr = response.css(".mec-start-date-abbr::attr(content)").get()
        end_abbr = response.css(".mec-end-date-abbr::attr(content)").get()
        if start_abbr:
            date_start = self.parse_date_iso(start_abbr)
        if end_abbr:
            date_end = self.parse_date_iso(end_abbr)
        date_display = self.clean_text(
            response.css(".mec-single-event-date").xpath("string()").get()
        )

        # Location MEC
        location_name = self.clean_text(
            response.css(".mec-single-event-location .mec-location-title::text").get()
        )
        city = self.clean_text(
            response.css(".mec-single-event-location .mec-address::text").get()
        )

        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Categoria
        categories = []
        for cat in response.css(".mec-event-category a::text").getall():
            c = self.clean_text(cat)
            if c:
                categories.append(c)

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", city or location_name or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": categories, "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_display or ""},
                "city": {"city_name": city, "location_name": location_name, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": categories[0] if categories else "evento", "source": self.source_name},
        )
