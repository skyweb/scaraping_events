# -*- coding: utf-8 -*-
"""
Spider per abruzzoturismo.it - Portale turistico dell'Abruzzo.

Drupal 9 con paginazione standard ?page=N.

Utilizzo:
    scrapy crawl abruzzo_turismo
    scrapy crawl abruzzo_turismo -a max_pages=10
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class AbruzzoTurismoSpider(BaseEventSpider):
    name = "abruzzo_turismo"
    source_name = "abruzzo_turismo"
    allowed_domains = ["www.abruzzoturismo.it"]

    BASE_URL = "https://www.abruzzoturismo.it"
    LISTING_URL = f"{BASE_URL}/it/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(f"{self.LISTING_URL}?page=0", callback=self._parse_listing, meta={"page": 0})

    def _parse_listing(self, response):
        cards = response.css("div.card.card-img")
        new_count = 0
        for card in cards:
            href = card.css("a[href*='/it/eventi/']::attr(href)").get()
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
        title = self.clean_text(response.css("h1::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        description = self.clean_text(
            response.css(".field--name-body .field__item").xpath("string()").get()
        )
        if not description:
            description = self.clean_text(response.xpath('//meta[@property="og:description"]/@content').get())

        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Date
        date_start = None
        date_end = None
        time_els = response.css("time[datetime]")
        if time_els:
            date_start = self.parse_date_iso(time_els[0].attrib.get("datetime", ""))
        if len(time_els) >= 2:
            date_end = self.parse_date_iso(time_els[1].attrib.get("datetime", ""))

        # Location dal link Google Maps
        maps_link = response.css("a.icon-position-map::attr(href)").get()
        city = None
        if maps_link and "q=" in maps_link:
            import re
            q = re.search(r'q=([^&]+)', maps_link)
            if q:
                from urllib.parse import unquote
                city = unquote(q.group(1)).replace("+", " ")

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
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
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
