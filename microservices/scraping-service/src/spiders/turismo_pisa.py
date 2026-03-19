# -*- coding: utf-8 -*-
"""
Spider per turismo.pisa.it - Portale turistico di Pisa.

Drupal 8, paginazione standard ?page=N. Date con <time datetime> ISO.

Utilizzo:
    scrapy crawl turismo_pisa
    scrapy crawl turismo_pisa -a max_pages=10
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class TurismoPisaSpider(BaseEventSpider):
    name = "turismo_pisa"
    source_name = "turismo_pisa"
    allowed_domains = ["www.turismo.pisa.it"]

    BASE_URL = "https://www.turismo.pisa.it"
    LISTING_URL = f"{BASE_URL}/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(f"{self.LISTING_URL}?page=0", callback=self._parse_listing, meta={"page": 0})

    def _parse_listing(self, response):
        cards = response.css("div.view-box.dettaglio-eventi")
        new_count = 0
        for card in cards:
            # Link dal onclick dell'immagine
            onclick = card.css("div.image-dettaglio-evento::attr(onclick)").get() or ""
            match = re.search(r"self\.location\.href='([^']+)'", onclick)
            if match:
                href = match.group(1)
            else:
                href = card.css("a::attr(href)").get()
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

        has_next = response.css("li.pager__item--next a::attr(href)").get()
        if has_next and (page + 1) < self.max_pages:
            yield scrapy.Request(response.urljoin(has_next), callback=self._parse_listing, meta={"page": page + 1})

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h2.node-title-large span::text").get())
        if not title:
            title = self.clean_text(response.css("h1::text").get())
        if not title:
            return

        description = self.clean_text(response.css("div.evento-body").xpath("string()").get())
        image_url = response.css("figure.figure img::attr(src)").get()

        # Date ISO da <time datetime>
        date_start = None
        date_end = None
        start_el = response.css("div.node-field-startdate time[datetime]")
        end_el = response.css("div.node-field-enddate time[datetime]")
        if start_el:
            date_start = self.parse_date_iso(start_el.attrib.get("datetime", ""))
        if end_el:
            date_end = self.parse_date_iso(end_el.attrib.get("datetime", ""))

        location = self.clean_text(
            response.css("div.node-field-luogo .field-content::text").get()
        )
        category = self.clean_text(
            response.css("div.node-field-tags .field-content a::text").get()
        )

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", location or "Pisa")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [category] if category else [],
                "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": "Pisa", "location_name": location, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": category or "evento", "source": self.source_name},
        )
