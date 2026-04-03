# -*- coding: utf-8 -*-
"""
Spider per basilicataturistica.it - Portale turistico della Basilicata.

WordPress + Events Manager plugin. Scrapa la griglia eventi HTML.

Utilizzo:
    scrapy crawl basilicata_turistica
    scrapy crawl basilicata_turistica -a max_pages=5
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class BasilicataTuristicaSpider(BaseEventSpider):
    name = "basilicata_turistica"
    source_name = "basilicata_turistica"
    allowed_domains = ["www.basilicataturistica.it"]

    BASE_URL = "https://www.basilicataturistica.it"
    LISTING_URL = f"{BASE_URL}/eventi/"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing)

    def _parse_listing(self, response):
        cards = response.css("div.em-event.em-item")
        new_count = 0
        for card in cards:
            href = card.attrib.get("data-href") or card.css(".em-item-title a::attr(href)").get()
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        self.logger.info(f"Trovati {new_count} eventi")

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        description = self.clean_text(
            response.css(".em-event-single .entry-content").xpath("string()").get()
            or response.xpath('//meta[@property="og:description"]/@content').get()
        )
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date dal EM plugin
        date_start = None
        date_end = None
        date_text = self.clean_text(response.css(".em-event-date::text").get())
        time_text = self.clean_text(response.css(".em-event-time::text").get())

        # Location
        location_name = self.clean_text(response.css(".em-event-location::text").get())

        uuid = self.generate_uuid(title, date_start or "", location_name or "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "cover_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_text or "",
                    "orari": time_text
                },
                "city": {
                    "city_name": None,
                    "location_name": location_name,
                    "location_address": None
                },
            },
        )
