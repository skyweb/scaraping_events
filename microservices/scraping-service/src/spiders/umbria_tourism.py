# -*- coding: utf-8 -*-
"""
Spider per umbriatourism.it - Portale turistico dell'Umbria.

Il sito usa Liferay DXP con SPA. Gli eventi sono parzialmente visibili
nel mega-menu server-rendered. Lo spider usa l'endpoint AJAX del portlet di ricerca.

Utilizzo:
    scrapy crawl umbria_tourism
    scrapy crawl umbria_tourism -a max_pages=5
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class UmbriaTourismSpider(BaseEventSpider):
    name = "umbria_tourism"
    source_name = "umbria_tourism"
    allowed_domains = ["www.umbriatourism.it"]

    BASE_URL = "https://www.umbriatourism.it"
    LISTING_URL = f"{BASE_URL}/it/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing)

    def _parse_listing(self, response):
        # Estrai eventi dal mega-menu e dalla pagina (SSR)
        cards = response.css("div.card.card-event-1, div.card.card-offerta")
        new_count = 0
        for card in cards:
            href = card.css("a::attr(href)").get()
            if not href or not href.startswith("/-/"):
                continue
            full_url = f"{self.BASE_URL}{href}"
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        self.logger.info(f"Trovati {new_count} eventi dalla pagina SSR")

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        description = self.clean_text(
            response.xpath('//meta[@property="og:description"]/@content').get()
        )
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date dal testo (formato dd.MM.yyyy)
        date_text = self.clean_text(response.css(".card-subtitle::text").get())
        date_start = None
        date_end = None
        if date_text:
            dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", date_text)
            if dates:
                date_start = dates[0].replace(".", "/")
                date_start = self.parse_date_dmy(date_start)
            if len(dates) >= 2:
                date_end = dates[1].replace(".", "/")
                date_end = self.parse_date_dmy(date_end)

        city = self.clean_text(response.css(".badge.badge-light-green::text").get())

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_text or ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
        )
