# -*- coding: utf-8 -*-
"""
Spider per turismofvg.it - Portale turistico del Friuli Venezia Giulia.

Il sito usa un CMS custom (Ikon Author) con paginazione server-side ?page=N.

Utilizzo:
    scrapy crawl turismo_fvg
    scrapy crawl turismo_fvg -a max_pages=10
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class TurismoFvgSpider(BaseEventSpider):
    name = "turismo_fvg"
    source_name = "turismo_fvg"
    allowed_domains = ["www.turismofvg.it"]

    BASE_URL = "https://www.turismofvg.it"
    LISTING_URL = f"{BASE_URL}/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "10", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(f"{self.LISTING_URL}?page=0", callback=self._parse_listing, meta={"page": 0})

    def _parse_listing(self, response):
        cards = response.css("a.c-eventsResults__item")
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

        has_next = response.css('link[rel="next"]::attr(href)').get()
        if has_next and (page + 1) < self.max_pages:
            yield scrapy.Request(response.urljoin(has_next), callback=self._parse_listing, meta={"page": page + 1})

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1.c-detail__title::text").get())
        if not title:
            return

        description = self.clean_text(response.css("section.c-detail__body .body_col1").xpath("string()").get())
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Info dalla sidebar (distinguere per icona/label)
        city = None
        date_text = None
        location_name = None
        for row in response.css(".body_col2 .info_rows > div"):
            label = self.clean_text(row.css("strong::text").get() or row.css("p::text").get())
            if not label:
                continue
            label_lower = label.lower()
            value = self.clean_text(row.xpath("string()").get())
            if "dove" in label_lower or "location" in label_lower:
                city = value.replace(label, "").strip() if value else None
            elif "quando" in label_lower or "date" in label_lower:
                date_text = value.replace(label, "").strip() if value else None
            elif "sede" in label_lower or "venue" in label_lower:
                location_name = value.replace(label, "").strip() if value else None

        date_start = None
        date_end = None
        if date_text:
            date_start, _ = parse_italian_date_time(date_text.split(" - ")[0] if " - " in date_text else date_text)
            if " - " in date_text:
                date_end, _ = parse_italian_date_time(date_text.split(" - ")[-1])

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": date_text or ""},
                "city": {"city_name": city, "location_name": location_name, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
