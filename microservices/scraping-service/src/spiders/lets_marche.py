# -*- coding: utf-8 -*-
"""
Spider per letsmarche.it - Portale turistico delle Marche.

Il sito usa Liferay DXP con paginazione SSR tramite parametri portlet.

Utilizzo:
    scrapy crawl lets_marche
    scrapy crawl lets_marche -a max_pages=10
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class LetsMarcheSpider(BaseEventSpider):
    name = "lets_marche"
    source_name = "lets_marche"
    allowed_domains = ["letsmarche.it"]

    BASE_URL = "https://letsmarche.it"
    LISTING_URL = f"{BASE_URL}/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 1})

    def _parse_listing(self, response):
        cards = response.css("a.event-container")
        new_count = 0
        for card in cards:
            href = card.attrib.get("href", "")
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi")

        # Paginazione Liferay
        next_link = response.css("li.page-item a.page-link")
        for link in next_link:
            text = self.clean_text(link.css("::text").get())
            if text and (">" in text or "next" in text.lower() or "succ" in text.lower()):
                next_href = link.attrib.get("href")
                if next_href and page < self.max_pages:
                    yield scrapy.Request(
                        response.urljoin(next_href),
                        callback=self._parse_listing, meta={"page": page + 1},
                    )
                break

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1.title::text").get())
        if not title:
            return

        description = self.clean_text(
            response.css("div.read-more-description.desc-container").xpath("string()").get()
        )
        image_url = response.css("img.detail-img-object-fit::attr(src)").get()

        # Date (formato italiano: "21 mar 2026")
        date_start = None
        date_end = None
        date_display = ""
        for info in response.css(".info-container"):
            label = self.clean_text(info.css("span.tit-link::text").get())
            if label and "quando" in label.lower():
                date_display = self.clean_text(info.xpath("string()").get())
                # Cerca date DD/MM/YYYY o "DD mon YYYY"
                dates = self.extract_dates_from_text(date_display)
                if dates:
                    date_start = dates[0]
                if len(dates) >= 2:
                    date_end = dates[-1]
                break

        # Location
        city = None
        for info in response.css(".map-wrapper"):
            label = self.clean_text(info.css("span.tit-link::text").get())
            if label and "dove" in label.lower():
                city = self.clean_text(info.css("p span::text").get())
                break

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_display},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
        )
