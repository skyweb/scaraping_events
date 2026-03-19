# -*- coding: utf-8 -*-
"""
Spider per visitverona.it - Portale turistico di Verona.

CMS custom (KUMBE/Feratel). Usa endpoint AJAX che restituisce frammenti HTML.

Utilizzo:
    scrapy crawl visit_verona
    scrapy crawl visit_verona -a max_pages=10
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitVeronaSpider(BaseEventSpider):
    name = "visit_verona"
    source_name = "visit_verona"
    allowed_domains = ["www.visitverona.it"]

    BASE_URL = "https://www.visitverona.it"
    AJAX_URL = f"{BASE_URL}/it/get_include/FILTER_EVENTS_AJAX_NEW_2021/"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(f"{self.AJAX_URL}?page=0", callback=self._parse_ajax, meta={"page": 0})

    def _parse_ajax(self, response):
        cards = response.css("dt.list-item[data-id]")
        new_count = 0
        for card in cards:
            # URL dal data-url o dal link dentro la card
            href = card.css("figure.goto-elemento::attr(data-url)").get()
            if not href:
                href = card.css("div.goto-elemento::attr(data-url)").get()
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

        if new_count > 0 and (page + 1) < self.max_pages:
            yield scrapy.Request(
                f"{self.AJAX_URL}?page={page + 1}",
                callback=self._parse_ajax, meta={"page": page + 1},
            )

    def _parse_detail(self, response):
        title = self.clean_text(response.css("header.internal-page-header h1::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        description = self.clean_text(response.css("div.mce-content-body").xpath("string()").get())
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date e location dal testo con icone
        date_text = None
        location = None
        for span in response.css("header.internal-page-header span"):
            if span.css("i.fa-calendar-alt"):
                date_text = self.clean_text(span.xpath("string()").get())
            elif span.css("i.fa-map-marker-alt"):
                location = self.clean_text(span.xpath("string()").get())

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_text or "", location or "Verona")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": "", "date_end": "", "date_display": date_text or ""},
                "city": {"city_name": "Verona", "location_name": location, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
