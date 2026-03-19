# -*- coding: utf-8 -*-
"""
Spider per incampania.com - Portale turistico della Campania.

WordPress con tema custom. Paginazione standard /eventi/page/N/.

Utilizzo:
    scrapy crawl in_campania
    scrapy crawl in_campania -a max_pages=10
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class InCampaniaSpider(BaseEventSpider):
    name = "in_campania"
    source_name = "in_campania"
    allowed_domains = ["incampania.com"]

    BASE_URL = "https://incampania.com"
    LISTING_URL = f"{BASE_URL}/eventi/"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 1})

    def _parse_listing(self, response):
        cards = response.css("div.tour-box")
        new_count = 0
        for card in cards:
            href = card.css("figure a::attr(href)").get() or card.css("h3 a::attr(href)").get()
            if not href:
                continue
            if href in self._seen_urls:
                continue
            self._seen_urls.add(href)
            new_count += 1
            yield scrapy.Request(href, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi")

        next_page = page + 1
        has_next = response.css("a.pagination-next::attr(href)").get()
        if has_next and next_page <= self.max_pages:
            yield scrapy.Request(has_next, callback=self._parse_listing, meta={"page": next_page})

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1").xpath("string()").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        description = self.clean_text(
            response.css(".entry-content").xpath("string()").get()
            or response.xpath('//meta[@property="og:description"]/@content').get()
        )
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date e location dal testo della pagina
        date_start = None
        date_end = None
        city = self.clean_text(response.css(".tour-info .info span::text").get())

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
        )
